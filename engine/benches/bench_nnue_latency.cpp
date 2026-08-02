#include "nsce/nnue.hpp"
#include "nsce/board.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/zobrist.hpp"
#include "nsce/eval.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>

int main(int argc, char** argv) {
  using namespace nsce;
  init_bitboards();
  Zobrist::init();
  Nnue::instance().load_default_from_hce();

  int iters = 100000;
  if (argc > 1) iters = std::atoi(argv[1]);

  Position pos;
  pos.set_startpos();

  // Warmup
  for (int i = 0; i < 1000; ++i) (void)evaluate(pos);

  auto t0 = std::chrono::steady_clock::now();
  volatile int sink = 0;
  for (int i = 0; i < iters; ++i) sink += evaluate(pos);
  auto t1 = std::chrono::steady_clock::now();
  double ns = std::chrono::duration<double, std::nano>(t1 - t0).count() / iters;
  std::printf("nnue_eval_latency_ns=%.1f iters=%d sink=%d\n", ns, iters, sink);
  return 0;
}
