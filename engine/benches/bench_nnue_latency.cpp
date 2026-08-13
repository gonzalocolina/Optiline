#include "nsce/nnue.hpp"
#include "nsce/board.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/zobrist.hpp"
#include "nsce/eval.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>

static bool load_eval_net(const char* path, std::string& identity) {
  using namespace nsce;
  identity = (path && path[0]) ? path : "internal";
  if (identity == "internal" || identity == "hce") return Nnue::instance().load_default_from_hce();
  return Nnue::instance().load(identity);
}

int main(int argc, char** argv) {
  using namespace nsce;
  init_bitboards();
  Zobrist::init();
  std::string eval_identity;
  if (!load_eval_net(argc > 2 ? argv[2] : nullptr, eval_identity)) {
    std::fprintf(stderr, "nsce_bench_nnue: unable to load EvalFile %s\n", eval_identity.c_str());
    return 2;
  }

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
  std::printf("nnue_eval_latency_ns=%.1f iters=%d sink=%d eval_file=%s\n", ns, iters, sink,
              eval_identity.c_str());
  return 0;
}
