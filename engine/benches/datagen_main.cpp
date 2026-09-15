// nsce_datagen: fixed-node self-play → bulletformat ChessBoard records.
//
//   ./build/nsce_datagen --out train/data/gen0.bin --games 20000 --nodes 5000 \
//       --threads 14 --eval-file nets/nnue_search_leaves40k_rw0.bin --seed 1
//
// Positions written = quiet, non-check, non-mate positions of finished games,
// labelled with the stm-relative search score and the game result.

#include "nsce/datagen.hpp"

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
  using namespace nsce;
  DatagenOptions opt;
  opt.output = "train/data/datagen.bin";
  opt.eval_file = "nets/nnue_search_leaves40k_rw0.bin";
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    auto next = [&](const char* name) -> std::string {
      if (i + 1 >= argc) {
        std::cerr << name << " needs a value\n";
        std::exit(2);
      }
      return argv[++i];
    };
    if (arg == "--out") opt.output = next("--out");
    else if (arg == "--eval-file") opt.eval_file = next("--eval-file");
    else if (arg == "--games") opt.games = std::atoi(next("--games").c_str());
    else if (arg == "--nodes") opt.nodes = std::atoi(next("--nodes").c_str());
    else if (arg == "--threads") opt.threads = std::atoi(next("--threads").c_str());
    else if (arg == "--random-plies") opt.random_plies = std::atoi(next("--random-plies").c_str());
    else if (arg == "--hash") opt.hash_mb = std::atoi(next("--hash").c_str());
    else if (arg == "--seed") opt.seed = std::strtoull(next("--seed").c_str(), nullptr, 10);
    else if (arg == "--resign-cp") opt.resign_cp = std::atoi(next("--resign-cp").c_str());
    else if (arg == "--resign-plies") opt.resign_plies = std::atoi(next("--resign-plies").c_str());
    else if (arg == "--draw-min-ply") opt.draw_min_ply = std::atoi(next("--draw-min-ply").c_str());
    else if (arg == "--draw-cp") opt.draw_cp = std::atoi(next("--draw-cp").c_str());
    else if (arg == "--draw-plies") opt.draw_plies = std::atoi(next("--draw-plies").c_str());
    else if (arg == "--max-plies") opt.max_plies = std::atoi(next("--max-plies").c_str());
    else if (arg == "--max-start-imbalance") opt.max_start_imbalance_cp = std::atoi(next("--max-start-imbalance").c_str());
    else if (arg == "--no-extras") opt.use_extras = false;
    else if (arg == "--text") opt.text = true;
    else if (arg == "--help" || arg == "-h") {
      std::cout
          << "nsce_datagen --out FILE [--eval-file NET|internal] [--games N] [--nodes N] [--threads T]\n"
             "             [--random-plies N] [--hash MB] [--seed S] [--resign-cp CP] [--resign-plies N]\n"
             "             [--draw-min-ply N] [--draw-cp CP] [--draw-plies N] [--max-plies N]\n"
             "             [--max-start-imbalance CP] [--no-extras] [--text]\n";
      return 0;
    } else {
      std::cerr << "unknown argument " << arg << '\n';
      return 2;
    }
  }
  if (opt.text && opt.output.size() > 4 && opt.output.compare(opt.output.size() - 4, 4, ".bin") == 0)
    std::cerr << "warning: --text output into a .bin path\n";
  const uint64_t written = run_datagen(opt);
  return written > 0 ? 0 : 1;
}
