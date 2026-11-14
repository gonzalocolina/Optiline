//! (768→FT)×2 SCReLU → 1, eight output buckets by piece count, fed from
//! Stockfish-format binpacks (NSCE_BINPACKS, comma separated).
//! FT is NSCE_FT (default 768, any multiple of 16 up to 1024).
//!
//! The HL graph spends 32 dense rows of 2·FT on every evaluation. This one
//! spends a single row, so the engine searches about twice as many nodes.
//! Bullet's own initialisation and learning rate: nothing here needs the
//! bias lift that the HL graph did.
//! Copy to third_party/bullet/examples/nsce_simple_binpack.rs.

use bullet_lib::{
    game::{inputs::Chess768, outputs::MaterialCount},
    nn::optimiser::AdamW,
    trainer::{
        save::SavedFormat,
        schedule::{TrainingSchedule, TrainingSteps, lr, wdl},
        settings::LocalSettings,
    },
    value::{
        ValueTrainerBuilder,
        loader::sfbinpack::{MoveType, PieceType, SfBinpackLoader, TrainingDataEntry},
    },
};
use std::path::{Path, PathBuf};

const OUTPUT_BUCKETS: usize = 8;

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

fn file_sha256(path: &Path) -> String {
    let output = std::process::Command::new("sha256sum").arg(path).output().unwrap_or_else(|err| {
        eprintln!("sha256sum failed for {}: {err}", path.display());
        std::process::exit(1);
    });
    if !output.status.success() {
        eprintln!(
            "sha256sum {}: {}",
            path.display(),
            String::from_utf8_lossy(&output.stderr)
        );
        std::process::exit(1);
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let Some(hash) = text.split_whitespace().next() else {
        eprintln!("sha256sum produced no hash for {}", path.display());
        std::process::exit(1);
    };
    if hash.len() != 64 || !hash.chars().all(|c| c.is_ascii_hexdigit()) {
        eprintln!("sha256sum produced {hash:?} for {}", path.display());
        std::process::exit(1);
    }
    hash.to_string()
}

fn training_source_sha256() -> String {
    let configured = std::env::var("NSCE_GRAPH_SOURCE").unwrap_or_else(|_| "examples/nsce_simple_binpack.rs".to_string());
    let path = PathBuf::from(configured);
    if !path.is_file() {
        eprintln!(
            "training source {} is missing; set NSCE_GRAPH_SOURCE to the graph file that was compiled",
            path.display()
        );
        std::process::exit(1);
    }
    file_sha256(&path)
}

fn ensure_graph_dir(dir: &Path, graph_id: &str) {
    let path = dir.join("graph_id");
    let accept_unmarked = std::env::var("NSCE_ACCEPT_UNMARKED").ok().as_deref() == Some("1");
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
            if latest_checkpoint(dir).is_some() && !accept_unmarked {
                eprintln!(
                    "refusing to resume {}: checkpoints exist but graph_id is missing. Provenance was not recorded. Use a new NSCE_CHECKPOINT_DIR, or set NSCE_ACCEPT_UNMARKED=1 only after checking that these checkpoints were trained with this exact source.",
                    dir.display()
                );
                std::process::exit(1);
            }
            if latest_checkpoint(dir).is_some() {
                eprintln!(
                    "NSCE_ACCEPT_UNMARKED=1: writing graph_id {graph_id:?} into {}. This asserts provenance; it does not prove it.",
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
    let binpacks = std::env::var("NSCE_BINPACKS").expect("NSCE_BINPACKS: comma-separated .binpack paths");
    let binpack_paths: Vec<&str> = binpacks.split(',').collect();
    let smoke = std::env::var("NSCE_SMOKE").is_ok();
    let ft = env_usize("NSCE_FT", 768);
    if ft == 0 || ft % 16 != 0 || ft > 1024 {
        eprintln!("NSCE_FT={ft}: the engine steps the accumulator by 16 and stops at 1024");
        std::process::exit(1);
    }
    let initial_lr = env_f32("NSCE_LR", 0.001);
    let final_lr = initial_lr * 0.3f32.powi(5);
    let batch_size = env_usize("NSCE_BATCH", 16_384);
    let batches_per_superbatch = env_usize("NSCE_BATCHES", if smoke { 2 } else { 6_104 });
    let superbatches = env_usize("NSCE_SUPERBATCHES", if smoke { 1 } else { 100 });
    let loader_threads = env_usize("NSCE_THREADS", if smoke { 2 } else { 4 });
    let batch_queue_size = env_usize("NSCE_QUEUE", if smoke { 2 } else { 32 });
    let wdl_proportion = env_f32("NSCE_WDL", 0.0);
    println!("wdl_proportion={wdl_proportion}");
    println!("binpacks={binpacks}");
    println!("graph=simple hidden={ft} buckets={OUTPUT_BUCKETS} lr={initial_lr} batch={batch_size}");

    let mut trainer = ValueTrainerBuilder::default()
        .dual_perspective()
        .optimiser(AdamW)
        .inputs(Chess768)
        .output_buckets(MaterialCount::<OUTPUT_BUCKETS>)
        .save_format(&[
            SavedFormat::id("l0w").round().quantise::<i16>(255),
            SavedFormat::id("l0b").round().quantise::<i16>(255),
            // [bucket][2 * FT], the row the engine reads for one evaluation.
            SavedFormat::id("l1w").round().quantise::<i16>(64).transpose(),
            // i32: a bucket bias above 2.0 would not fit i16 at 255 * 64.
            SavedFormat::id("l1b").round().quantise::<i32>(255 * 64),
        ])
        .loss_fn(|output, target| output.sigmoid().squared_error(target))
        .build(|builder, stm_inputs, ntm_inputs, output_buckets| {
            let l0 = builder.new_affine("l0", 768, ft);
            let l1 = builder.new_affine("l1", 2 * ft, OUTPUT_BUCKETS);
            let stm = l0.forward(stm_inputs).screlu();
            let ntm = l0.forward(ntm_inputs).screlu();
            l1.forward(stm.concat(ntm)).select(output_buckets)
        });

    let output_directory = std::env::var("NSCE_CHECKPOINT_DIR").unwrap_or_else(|_| {
        if smoke {
            "../../tmp/bullet_smoke_simple_binpack".to_string()
        } else {
            "../../train/bullet_checkpoints_simple_binpack".to_string()
        }
    });
    std::fs::create_dir_all(&output_directory).ok();
    let graph_sha = training_source_sha256();
    let graph_id = format!(
        "simple ft={ft} buckets={OUTPUT_BUCKETS} screlu=1 lr={initial_lr} batch={batch_size} wdl={wdl_proportion:.4} sha256={graph_sha}"
    );
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
        save_rate: env_usize("NSCE_SAVE_RATE", if smoke { 1 } else { 10 }),
    };

    let settings = LocalSettings {
        threads: loader_threads,
        test_set: None,
        output_directory: output_directory.as_str(),
        batch_queue_size,
    };
    // bullet's own filter for these files: skip the opening, checks, captures,
    // promotions and decided scores.
    fn filter(entry: &TrainingDataEntry) -> bool {
        entry.ply >= 16
            && !entry.pos.is_checked(entry.pos.side_to_move())
            && entry.score.unsigned_abs() <= 10000
            && entry.mv.mtype() == MoveType::Normal
            && entry.pos.piece_at(entry.mv.to()).piece_type() == PieceType::None
    }
    let buffer_mb = env_usize("NSCE_BUFFER_MB", 4096);
    let dataloader = SfBinpackLoader::new_concat_multiple(&binpack_paths, buffer_mb, loader_threads, filter);
    trainer.run(&schedule, &settings, &dataloader);
}
