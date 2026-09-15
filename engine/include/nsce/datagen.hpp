#pragma once

#include <cstdint>
#include <string>

namespace nsce {

// Fixed-node self-play data generation straight from the engine (no UCI hop).
//
// Each thread owns a Search (private TT) and plays games from `random_plies`
// uniformly random legal moves out of the start position, then `go nodes N`
// for both sides. Every searched position is written in bulletformat
// `ChessBoard` (32 bytes: occ u64, pcs[16] nibbles, score i16 stm-relative,
// result u8 stm-relative 0/1/2, ksq, opp_ksq, extra[3]) after the game result
// is known, so bullet can train on the file directly. Positions in check, with
// a capturing/promoting best move, or with a mate score are skipped; that is
// the usual filter and keeps the label a quiet static-eval target.
struct DatagenOptions {
  std::string output;             // .bin (bulletformat) or .txt (`fen | score | wdl`)
  std::string eval_file;          // EvalFile for the playing engine; "internal" for HCE init
  int games = 1000;
  int nodes = 5000;               // per move
  int threads = 1;
  int random_plies = 8;           // random moves before search starts
  int hash_mb = 16;
  uint64_t seed = 1;
  int resign_cp = 1500;           // |score| >= this for resign_plies consecutive plies ends the game
  int resign_plies = 4;
  int draw_min_ply = 80;          // |score| <= draw_cp for draw_plies consecutive plies after this ply
  int draw_cp = 10;
  int draw_plies = 10;
  int max_plies = 400;
  int max_start_imbalance_cp = 1000;  // discard openings whose first search says one side is already lost
  bool use_extras = true;
  bool text = false;
};

// Returns the number of positions written.
uint64_t run_datagen(const DatagenOptions& options);

}  // namespace nsce
