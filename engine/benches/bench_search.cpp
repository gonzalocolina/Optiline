#include "nsce/search.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/nnue.hpp"
#include "nsce/zobrist.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>

int main(int argc, char** argv) {
  using namespace nsce;
  init_bitboards();
  Zobrist::init();
  Nnue::instance().load_default_from_hce();

  int depth = 5;
  if (argc > 1) depth = std::atoi(argv[1]);

  Search search;
  search.set_hash_mb(16);
  Position pos;
  pos.set_startpos();
  search.set_position(pos);

  SearchLimits limits;
  limits.depth = depth;

  auto t0 = std::chrono::steady_clock::now();
  SearchInfo info = search.go(limits);
  auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();

  std::cout << "nsce_bench depth=" << depth << " nodes=" << info.nodes << " time_ms=" << ms
            << " best=" << info.best_move.raw << " score=" << info.score << '\n';
  return 0;
}
