//! Count what a Stockfish binpack holds and what the training filter keeps.
//! One thread per file. Copy to third_party/bullet/examples/nsce_binpack_stats.rs.
//!
//!   cargo r -r --example nsce_binpack_stats -- a.binpack b.binpack
//!
//! Prints one JSON object per file: entries, entries the trainers' filter
//! keeps, those split by the eight piece-count buckets, and by game result.

use bullet_lib::value::loader::sfbinpack::{MoveType, PieceType, TrainingDataEntry};
use sfbinpack::{ChunkReader, read_chunk_into};
use std::{fs::File, io::BufReader, thread};

// Keep in step with bullet_nsce_simple_binpack.rs and bullet_nsce_hl_binpack.rs.
fn filter(entry: &TrainingDataEntry) -> bool {
    entry.ply >= 16
        && !entry.pos.is_checked(entry.pos.side_to_move())
        && entry.score.unsigned_abs() <= 10000
        && entry.mv.mtype() == MoveType::Normal
        && entry.pos.piece_at(entry.mv.to()).piece_type() == PieceType::None
}

#[derive(Default)]
struct Stats {
    entries: u64,
    kept: u64,
    buckets: [u64; 8],
    results: [u64; 3],
    abs_score_sum: u64,
}

fn scan(path: &str) -> Stats {
    let mut reader = BufReader::with_capacity(1 << 22, File::open(path).unwrap_or_else(|err| {
        eprintln!("cannot open {path}: {err}");
        std::process::exit(1);
    }));
    let mut stats = Stats::default();
    let mut chunk = Vec::new();
    while read_chunk_into(&mut reader, &mut chunk).unwrap() {
        let mut entries = ChunkReader::default();
        while entries.has_next(&chunk) {
            let entry = entries.next(&chunk);
            stats.entries += 1;
            if !filter(&entry) {
                continue;
            }
            stats.kept += 1;
            let pieces = entry.pos.occupied().count() as usize;
            stats.buckets[(pieces.clamp(2, 32) - 2) / 4] += 1;
            stats.results[(entry.result + 1) as usize] += 1;
            stats.abs_score_sum += u64::from(entry.score.unsigned_abs());
        }
    }
    stats
}

fn main() {
    let paths: Vec<String> = std::env::args().skip(1).collect();
    if paths.is_empty() {
        eprintln!("usage: nsce_binpack_stats <file.binpack>...");
        std::process::exit(1);
    }
    let handles: Vec<_> = paths.iter().cloned().map(|path| thread::spawn(move || (scan(&path), path))).collect();
    for handle in handles {
        let (s, path) = handle.join().unwrap();
        println!(
            "{{\"file\": \"{}\", \"entries\": {}, \"kept\": {}, \"kept_by_bucket\": {:?}, \"kept_loss_draw_win\": {:?}, \"kept_mean_abs_score\": {:.1}}}",
            path.rsplit('/').next().unwrap_or(&path),
            s.entries,
            s.kept,
            s.buckets,
            s.results,
            s.abs_score_sum as f64 / s.kept.max(1) as f64
        );
    }
}
