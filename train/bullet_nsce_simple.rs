//! Original P1 graph: (768 → 512)×2 SCReLU → 1. Chess768 so gen0.bin stays valid.
//! Copy to third_party/bullet/examples/nsce.rs with NSCE_GRAPH=simple.
//! Resumed after 512/32/32 pair-act collapsed to per-bucket constants (nsce-20).

use bullet_lib::{
    game::inputs::Chess768,
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

fn ensure_graph_dir(dir: &Path, graph_id: &str) {
    let path = dir.join("graph_id");
    match std::fs::read_to_string(&path) {
        Ok(existing) => {
            let existing = existing.trim();
            if existing != graph_id {
                eprintln!(
                    "refusing to train in {}: graph_id is {existing:?}, this run is {graph_id:?}. Use a new NSCE_CHECKPOINT_DIR.",
                    dir.display()
                );
                std::process::exit(1);
            }
        }
        Err(_) => {
            if latest_checkpoint(dir).is_some() {
                eprintln!(
                    "warning: {} has checkpoints and no graph_id; stamping {graph_id:?}.",
                    dir.display()
                );
            }
            if let Err(err) = std::fs::write(&path, format!("{graph_id}\n")) {
                eprintln!("cannot write {}: {err}", path.display());
                std::process::exit(1);
            }
        }
    }
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
    const HIDDEN: usize = 512;
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
    println!("graph=simple hidden={HIDDEN}");

    let mut trainer = ValueTrainerBuilder::default()
        .dual_perspective()
        .optimiser(AdamW)
        .inputs(Chess768)
        .save_format(&[
            SavedFormat::id("l0w").round().quantise::<i16>(255),
            SavedFormat::id("l0b").round().quantise::<i16>(255),
            SavedFormat::id("l1w").round().quantise::<i16>(64),
            SavedFormat::id("l1b").round().quantise::<i16>(255 * 64),
        ])
        .loss_fn(|output, target| output.sigmoid().squared_error(target))
        .build(|builder, stm_inputs, ntm_inputs| {
            let l0 = builder.new_affine("l0", 768, HIDDEN);
            let l1 = builder.new_affine("l1", 2 * HIDDEN, 1);
            let stm_hidden = l0.forward(stm_inputs).screlu();
            let ntm_hidden = l0.forward(ntm_inputs).screlu();
            l1.forward(stm_hidden.concat(ntm_hidden))
        });

    let output_directory = std::env::var("NSCE_CHECKPOINT_DIR").unwrap_or_else(|_| {
        if smoke {
            "../../tmp/bullet_smoke_simple".to_string()
        } else {
            "../../train/bullet_checkpoints_simple".to_string()
        }
    });
    std::fs::create_dir_all(&output_directory).ok();
    let graph_id = format!("simple hidden=512 buckets=0 screlu=1 wdl={wdl_proportion:.4}");
    ensure_graph_dir(Path::new(&output_directory), &graph_id);

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
