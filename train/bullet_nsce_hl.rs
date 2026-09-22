//! (768→512)×2 SCReLU → 32 SCReLU → 1. No material buckets.
//! The bucketed 512/32/32 MLP collapsed to a constant inside each bucket.
//! The 1-layer net learned chess and lost ~100 Elo (corr 0.44 vs 0.64).
//! Copy to third_party/bullet/examples/nsce.rs with NSCE_GRAPH=hl.

use bullet_lib::{
    game::inputs::Chess768,
    nn::{optimiser::AdamW, Affine, InitSettings},
    trainer::{
        save::SavedFormat,
        schedule::{TrainingSchedule, TrainingSteps, lr, wdl},
        settings::LocalSettings,
    },
    value::{ValueTrainerBuilder, loader::DirectSequentialDataLoader},
};
use std::path::{Path, PathBuf};

const FT: usize = 512;
const HL: usize = 32;

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
    let dataset_path = std::env::var("NSCE_DATASET")
        .unwrap_or_else(|_| "../../train/data/gen0.bin".to_string());
    let smoke = std::env::var("NSCE_SMOKE").is_ok();
    let initial_lr = env_f32("NSCE_LR", 0.0002);
    let final_lr = initial_lr * 0.3f32.powi(5);
    let batch_size = env_usize("NSCE_BATCH", 8_192);
    let batches_per_superbatch = env_usize("NSCE_BATCHES", if smoke { 2 } else { 12_208 });
    let superbatches = env_usize("NSCE_SUPERBATCHES", if smoke { 1 } else { 320 });
    let loader_threads = env_usize("NSCE_THREADS", if smoke { 2 } else { 8 });
    let batch_queue_size = env_usize("NSCE_QUEUE", if smoke { 2 } else { 64 });
    let wdl_proportion = env_f32("NSCE_WDL", 0.0);
    println!("wdl_proportion={wdl_proportion}");
    println!(
        "graph=hl hidden={FT} hl={HL} buckets=0 lr={initial_lr} ft_bias=0.15 l1_bias=0.4 l1_std_div=4"
    );

    let mut trainer = ValueTrainerBuilder::default()
        .dual_perspective()
        .optimiser(AdamW)
        .inputs(Chess768)
        .save_format(&[
            SavedFormat::id("l0w").round().quantise::<i16>(255),
            SavedFormat::id("l0b").round().quantise::<i16>(255),
            SavedFormat::id("l1w").round().quantise::<i16>(64).transpose(),
            SavedFormat::id("l1b").round().quantise::<i16>(255 * 64),
            SavedFormat::id("l2w").round().quantise::<i16>(64),
            SavedFormat::id("l2b").round().quantise::<i16>(255 * 64),
        ])
        .loss_fn(|output, target| output.sigmoid().squared_error(target))
        .build(|builder, stm_inputs, ntm_inputs| {
            // Bias 0.5 on both SCReLU layers saturated 31/32 hidden units by nsce-10:
            // the FT outputs got large and the 1024-wide dot left (0, 1).
            // Keep a small FT lift, and shrink the hidden weights so that dot stays inside.
            let l0w = builder.new_weights(
                "l0w",
                (FT, 768),
                InitSettings::Normal { mean: 0.0, stdev: (2.0 / 768.0_f32).sqrt() },
            );
            let l0b = builder.new_weights(
                "l0b",
                (FT, 1),
                InitSettings::Normal { mean: 0.15, stdev: 0.02 },
            );
            let l0 = Affine { weights: l0w, bias: l0b };
            let l1_stdev = (2.0 / (2 * FT) as f32).sqrt() / 4.0;
            let l1w = builder.new_weights(
                "l1w",
                (HL, 2 * FT),
                InitSettings::Normal { mean: 0.0, stdev: l1_stdev },
            );
            let l1b = builder.new_weights(
                "l1b",
                (HL, 1),
                InitSettings::Normal { mean: 0.4, stdev: 0.05 },
            );
            let l1 = Affine { weights: l1w, bias: l1b };
            let l2 = builder.new_affine("l2", HL, 1);
            let stm = l0.forward(stm_inputs).screlu();
            let ntm = l0.forward(ntm_inputs).screlu();
            l2.forward(l1.forward(stm.concat(ntm)).screlu())
        });

    let output_directory = std::env::var("NSCE_CHECKPOINT_DIR").unwrap_or_else(|_| {
        if smoke {
            "../../tmp/bullet_smoke_hl".to_string()
        } else {
            "../../train/bullet_checkpoints_hl_l1small".to_string()
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

    let settings = LocalSettings {
        threads: loader_threads,
        test_set: None,
        output_directory: output_directory.as_str(),
        batch_queue_size,
    };
    let dataloader = DirectSequentialDataLoader::new(&[dataset_path.as_str()]);
    trainer.run(&schedule, &settings, &dataloader);
}
