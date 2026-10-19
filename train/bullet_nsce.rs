//! Dual-perspective net shaped like Stockfish 19's MLP, not a clone of SFNNv16.
//!
//! SFNNv16 is L1=1024 / L2=32 / L3=32, HalfKA-hm, PP_3Wide, GPL weights. This
//! graph keeps Chess768 (so gen0.bin stays valid) and L1=512 (GTX 1650; do not
//! clone the 1024-wide FT). L2=32 L3=32 with pair activations (CReLU ∥ SCReLU)
//! and skip = CReLU of the last two L2 neurons — the SF19 MLP ideas.
//! Copy to third_party/bullet/examples/nsce.rs via train/run_bullet.sh.

use bullet_lib::{
    game::{inputs::Chess768, outputs::MaterialCount},
    nn::optimiser::AdamW,
    trainer::{
        save::SavedFormat,
        schedule::{TrainingSchedule, TrainingSteps, lr, wdl},
        settings::{LocalSettings, TestDataset},
    },
    value::{ValueTrainerBuilder, loader::DirectSequentialDataLoader},
};
use std::path::{Path, PathBuf};

fn env_usize(name: &str, default: usize) -> usize {
    std::env::var(name)
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

fn env_f32(name: &str, default: f32) -> f32 {
    std::env::var(name)
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

fn latest_checkpoint(dir: &Path) -> Option<(usize, PathBuf)> {
    let mut best: Option<(usize, PathBuf)> = None;
    let rd = std::fs::read_dir(dir).ok()?;
    for entry in rd.flatten() {
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|s| s.to_str()) else { continue };
        let Some(num) = name.strip_prefix("nsce-") else { continue };
        let Ok(n) = num.parse::<usize>() else { continue };
        if !path.join("optimiser_state").exists() {
            continue;
        }
        if best.as_ref().map(|(m, _)| *m).unwrap_or(0) < n {
            best = Some((n, path));
        }
    }
    best
}

fn main() {
    // SF19-shaped MLP: 512/32/32, not SF18-small 128/16/32 (collapsed) and not
    // SFNNv16 L1=1024. Pairwise CReLU at the FT; pair acts at L2 and L3; skip.
    let l1 = 512;
    let l2 = 32;
    let l3 = 32;
    let dataset_path = std::env::var("NSCE_DATASET")
        .unwrap_or_else(|_| "../../train/data/gen0.bin".to_string());
    let smoke = std::env::var("NSCE_SMOKE").is_ok();
    let initial_lr = 0.001;
    let final_lr = 0.001 * 0.3f32.powi(5);
    let batch_size = env_usize("NSCE_BATCH", 8_192);
    let batches_per_superbatch = env_usize("NSCE_BATCHES", if smoke { 2 } else { 12_208 });
    let superbatches = env_usize("NSCE_SUPERBATCHES", if smoke { 1 } else { 320 });
    let loader_threads = env_usize("NSCE_THREADS", if smoke { 2 } else { 8 });
    let batch_queue_size = env_usize("NSCE_QUEUE", if smoke { 2 } else { 64 });
    let wdl_proportion = env_f32("NSCE_WDL", 0.0);
    println!("wdl_proportion={wdl_proportion}");
    println!("graph=mlp hidden={l1} l2={l2} l3={l3} pair_act=1 skip=crelu clip=0");
    const NUM_OUTPUT_BUCKETS: usize = 8;

    let mut trainer = ValueTrainerBuilder::default()
        .dual_perspective()
        .optimiser(AdamW)
        .inputs(Chess768)
        .output_buckets(MaterialCount::<NUM_OUTPUT_BUCKETS>)
        .save_format(&[
            SavedFormat::id("l0w").round().quantise::<i16>(255),
            SavedFormat::id("l0b").round().quantise::<i16>(255),
            SavedFormat::id("l1w").round().quantise::<i16>(64).transpose(),
            SavedFormat::id("l1b").round().quantise::<i16>(255 * 64),
            SavedFormat::id("l2w").round().quantise::<i16>(64).transpose(),
            SavedFormat::id("l2b").round().quantise::<i16>(255 * 64),
            SavedFormat::id("l3w").round().quantise::<i16>(64).transpose(),
            SavedFormat::id("l3b").round().quantise::<i16>(255 * 64),
        ])
        .loss_fn(|output, target| output.sigmoid().squared_error(target))
        .build(|builder, stm_inputs, ntm_inputs, output_buckets| {
            let l0 = builder.new_affine("l0", 768, l1);
            // Pair act concat(CReLU, SCReLU) doubles L2/L3 into the next affine.
            let aff1 = builder.new_affine("l1", l1, NUM_OUTPUT_BUCKETS * l2);
            let aff2 = builder.new_affine("l2", 2 * l2, NUM_OUTPUT_BUCKETS * l3);
            let aff3 = builder.new_affine("l3", 2 * l3, NUM_OUTPUT_BUCKETS);
            let ft = |input, start, end| l0.slice(start, end).forward(input).crelu();
            let stm_hidden = ft(stm_inputs, 0, l1 / 2) * ft(stm_inputs, l1 / 2, l1);
            let ntm_hidden = ft(ntm_inputs, 0, l1 / 2) * ft(ntm_inputs, l1 / 2, l1);
            let hl1 = stm_hidden.concat(ntm_hidden);
            // Skip from CReLU outputs (already [0,1]), not the raw affine.
            // Raw skip drowned the MLP (nsce-10..50). Layer-wide clip(0,1) just
            // slammed 28/32 L2 units into the walls (clip nsce-10).
            let h2 = aff1.forward(hl1).select(output_buckets);
            let c2 = h2.crelu();
            let skip = c2.slice_rows(l2 - 2, l2 - 1) - c2.slice_rows(l2 - 1, l2);
            let hl2 = c2.concat(c2 * c2);
            let h3 = aff2.forward(hl2).select(output_buckets);
            let c3 = h3.crelu();
            let hl3 = c3.concat(c3 * c3);
            aff3.forward(hl3).select(output_buckets) + skip
        });

    let output_directory = std::env::var("NSCE_CHECKPOINT_DIR").unwrap_or_else(|_| {
        if smoke {
            "../../tmp/bullet_smoke".to_string()
        } else {
            "../../train/bullet_checkpoints_512mlp_skipact".to_string()
        }
    });
    std::fs::create_dir_all(&output_directory).ok();

    let resume = std::env::var("NSCE_RESUME").ok().as_deref() != Some("0");
    let mut start_superbatch = env_usize("NSCE_START", 1);
    if resume && start_superbatch == 1 {
        if let Some((n, path)) = latest_checkpoint(Path::new(&output_directory)) {
            println!("resume checkpoint {} (superbatch {})", path.display(), n);
            trainer.load_from_checkpoint(path.to_str().expect("checkpoint path"));
            start_superbatch = n + 1;
        }
    } else if start_superbatch > 1 {
        let path = format!("{output_directory}/nsce-{}", start_superbatch - 1);
        println!("resume checkpoint {path}");
        trainer.load_from_checkpoint(&path);
    }
    if start_superbatch > superbatches {
        println!("already trained through superbatch {superbatches}; skip");
        return;
    }

    let schedule = TrainingSchedule {
        net_id: "nsce".to_string(),
        eval_scale: 400.0,
        steps: TrainingSteps {
            batch_size,
            batches_per_superbatch,
            start_superbatch,
            end_superbatch: superbatches,
        },
        wdl_scheduler: wdl::ConstantWDL { value: wdl_proportion },
        lr_scheduler: lr::CosineDecayLR {
            initial_lr,
            final_lr,
            final_superbatch: superbatches,
        },
        save_rate: if smoke { 1 } else { 10 },
    };

    let test_set_path = std::env::var("NSCE_TEST_SET").ok().filter(|p| !p.is_empty());
    let test_freq = env_usize("NSCE_TEST_FREQ", 32);
    if let Some(path) = test_set_path.as_deref() {
        println!("test_set={path} freq={test_freq}");
    }
    let test_set = test_set_path
        .as_deref()
        .map(|path| TestDataset { path, freq: test_freq });
    let settings = LocalSettings {
        threads: loader_threads,
        test_set,
        output_directory: output_directory.as_str(),
        batch_queue_size,
    };
    let dataloader = DirectSequentialDataLoader::new(&[dataset_path.as_str()]);
    trainer.run(&schedule, &settings, &dataloader);
}
