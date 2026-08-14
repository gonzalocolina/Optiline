#include "nsce/search.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/nnue.hpp"
#include "nsce/zobrist.hpp"

#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

static bool load_eval_net(const char* path, std::string& identity) {
  using namespace nsce;
  identity = (path && path[0]) ? path : "internal";
  if (identity == "internal" || identity == "hce") {
    return Nnue::instance().load_default_from_hce();
  }
  return Nnue::instance().load(identity);
}

static uint64_t file_fingerprint(const std::string& path) {
  if (path == "internal" || path == "hce") return 0;
  std::ifstream in(path, std::ios::binary);
  if (!in) return 0;
  uint64_t hash = 1469598103934665603ULL;
  char byte = 0;
  while (in.get(byte)) {
    hash ^= static_cast<unsigned char>(byte);
    hash *= 1099511628211ULL;
  }
  return hash;
}

int main(int argc, char** argv) {
  using namespace nsce;
  init_bitboards();
  Zobrist::init();
  std::string eval_identity;
  if (!load_eval_net(argc > 4 ? argv[4] : nullptr, eval_identity)) {
    std::cerr << "nsce_bench: unable to load EvalFile " << eval_identity << '\n';
    return 2;
  }

  int depth = 5;
  if (argc > 1) depth = std::atoi(argv[1]);
  int threads = 1;
  if (argc > 2) threads = std::atoi(argv[2]);
  int repetitions = 1;
  if (argc > 3) repetitions = std::atoi(argv[3]);
  int movetime = 0;
  if (argc > 5) movetime = std::atoi(argv[5]);

  Search search;
  search.set_hash_mb(64);
  search.set_threads(threads);
  search.set_silent(true);

  const std::vector<std::string> fens = {
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
      "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
      "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
      "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
      "r4rk1/1pp1qppp/p1np1n2/8/2B1P3/2N2Q1p/PPP2PPP/R1B2RK1 w - - 0 10",
  };

  SearchLimits limits;
  if (movetime > 0)
    limits.movetime_ms = movetime;
  else
    limits.depth = depth;

  Position warmup;
  warmup.set_startpos();
  search.set_position(warmup);
  search.go(limits);

  auto t0 = std::chrono::steady_clock::now();
  uint64_t total_nodes = 0;
  SearchStats total_stats{};
  Move last_best{};
  int last_score = 0;
  for (int repetition = 0; repetition < repetitions; ++repetition) {
    for (const std::string& fen : fens) {
      Position pos;
      pos.set_fen(fen);
      search.set_position(pos);
      SearchInfo info = search.go(limits);
      total_nodes += info.nodes;
      total_stats += search.last_stats();
      last_best = info.best_move;
      last_score = info.score;
    }
  }
  auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();

  uint64_t nps = ms > 0 ? total_nodes * 1000ULL / static_cast<uint64_t>(ms) : total_nodes;
  std::cout << "nsce_bench positions=" << fens.size() * repetitions
            << (movetime > 0 ? " movetime=" : " depth=") << (movetime > 0 ? movetime : depth)
            << " threads=" << threads << " nodes=" << total_nodes << " time_ms=" << ms << " nps=" << nps
            << " best=" << last_best.raw << " score=" << last_score << " eval_file=" << eval_identity
            << " eval_fingerprint=" << std::hex << file_fingerprint(eval_identity) << std::dec;
#if defined(NSCE_STATS)
  double first_cut = total_stats.beta_cutoffs
                         ? 100.0 * static_cast<double>(total_stats.first_move_cutoffs) / total_stats.beta_cutoffs
                         : 0.0;
  std::cout << " qnodes=" << total_stats.qnodes << " tt_hits=" << total_stats.tt_hits
            << " tt_probes=" << total_stats.tt_probes << " tt_cutoffs=" << total_stats.tt_cutoffs
            << " first_cut_pct=" << first_cut << " lmr=" << total_stats.lmr_attempts
            << " researches=" << total_stats.lmr_researches
            << " see_order=" << total_stats.see_order_calls << " see_prune=" << total_stats.see_prune_calls
            << " see_pruned=" << total_stats.see_prunes << " null=" << total_stats.null_cutoffs << '/'
            << total_stats.null_attempts << " razor=" << total_stats.razor_cutoffs << '/'
            << total_stats.razor_attempts << " rfp=" << total_stats.rfp_cutoffs << '/' << total_stats.rfp_attempts
            << " futility=" << total_stats.futility_prunes << " lmp=" << total_stats.lmp_prunes;
#endif
  std::cout << '\n';
  return 0;
}
