//! Dual-perspective (768→512)×2 SCReLU with 8 material output buckets.
//! Copy to third_party/bullet/examples/nsce.rs via tools/setup_bullet.sh.

use bullet_lib::{
    game::{inputs::Chess768, outputs::MaterialCount},
    nn::optimiser::AdamW,
    trainer::{
        save::SavedFormat,
        schedule::{TrainingSchedule, TrainingSteps, lr, wdl},
        settings::LocalSettings,
    },
    value::{ValueTrainerBuilder, loader::DirectSequentialDataLoader},
};

fn env_usize(name: &str, default: usize) -> usize {
    std::env::var(name)
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

fn main() {
    let hl_size = 512;
    // cargo runs with cwd = third_party/bullet
    let dataset_path = std::env::var("NSCE_DATASET")
        .unwrap_or_else(|_| "../../train/data/gen0.bin".to_string());
    let smoke = std::env::var("NSCE_SMOKE").is_ok();
    let initial_lr = 0.001;
    let final_lr = 0.001 * 0.3f32.powi(5);
    // GTX 1650 4 GB: 16384 OOMs; 8192 × 12208 ≈ 100 M / superbatch.
    let batch_size = env_usize("NSCE_BATCH", 8_192);
    let batches_per_superbatch = env_usize("NSCE_BATCHES", if smoke { 2 } else { 12_208 });
    let superbatches = env_usize("NSCE_SUPERBATCHES", if smoke { 1 } else { 320 });
    // CPU feature extraction. 2 threads starved the 1650; 8 keeps the queue full
    // once datagen has released the cores. Override with NSCE_THREADS / NSCE_QUEUE.
    let loader_threads = env_usize("NSCE_THREADS", if smoke { 2 } else { 8 });
    let batch_queue_size = env_usize("NSCE_QUEUE", if smoke { 2 } else { 64 });
    let wdl_proportion = 0.75;
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
        ])
        .loss_fn(|output, target| output.sigmoid().squared_error(target))
        .build(|builder, stm_inputs, ntm_inputs, output_buckets| {
            let l0 = builder.new_affine("l0", 768, hl_size);
            let l1 = builder.new_affine("l1", 2 * hl_size, NUM_OUTPUT_BUCKETS);
            let stm_hidden = l0.forward(stm_inputs).screlu();
            let ntm_hidden = l0.forward(ntm_inputs).screlu();
            let hidden_layer = stm_hidden.concat(ntm_hidden);
            l1.forward(hidden_layer).select(output_buckets)
        });

    let schedule = TrainingSchedule {
        net_id: "nsce".to_string(),
        eval_scale: 400.0,
        steps: TrainingSteps {
            batch_size,
            batches_per_superbatch,
            start_superbatch: 1,
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

    let output_directory = std::env::var("NSCE_CHECKPOINT_DIR").unwrap_or_else(|_| {
        if smoke {
            "../../tmp/bullet_smoke".to_string()
        } else {
            "../../train/bullet_checkpoints".to_string()
        }
    });
    let settings = LocalSettings {
        threads: loader_threads,
        test_set: None,
        output_directory: output_directory.as_str(),
        batch_queue_size,
    };
    let dataloader = DirectSequentialDataLoader::new(&[dataset_path.as_str()]);
    trainer.run(&schedule, &settings, &dataloader);
}
