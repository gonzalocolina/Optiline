#include "nsce/bitboard.hpp"
#include "nsce/board.hpp"
#include "nsce/eval.hpp"
#include "nsce/movegen.hpp"
#include "nsce/nnue.hpp"
#include "nsce/see.hpp"
#include "nsce/zobrist.hpp"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>

namespace {

using Clock = std::chrono::steady_clock;

bool load_eval(const char* path, std::string& identity) {
  using namespace nsce;
  identity = path && path[0] ? path : "internal";
  if (identity == "internal" || identity == "hce") return Nnue::instance().load_default_from_hce();
  return Nnue::instance().load(identity);
}

template <typename Fn>
double elapsed_ns(int iterations, Fn&& fn) {
  for (int i = 0; i < 1000; ++i) fn();
  const auto start = Clock::now();
  for (int i = 0; i < iterations; ++i) fn();
  const auto end = Clock::now();
  return std::chrono::duration<double, std::nano>(end - start).count() / iterations;
}

}  // namespace

int main(int argc, char** argv) {
  using namespace nsce;
  init_bitboards();
  Zobrist::init();

  const int iterations = argc > 1 ? std::max(1, std::atoi(argv[1])) : 100000;
  std::string eval_identity;
  if (!load_eval(argc > 2 ? argv[2] : nullptr, eval_identity)) {
    std::fprintf(stderr, "nsce_bench_components: unable to load EvalFile %s\n", eval_identity.c_str());
    return 2;
  }

  Position pos;
  pos.set_startpos();
  MoveList legal;
  generate_legal(pos, legal);
  if (legal.size == 0) return 3;
  MoveList captures;
  generate_captures(pos, captures);
  Move see_move = captures.size ? captures.moves[0] : legal.moves[0];
  volatile uint64_t sink = 0;

  const double movegen = elapsed_ns(iterations, [&] {
    MoveList list;
    generate_legal(pos, list);
    sink += static_cast<uint64_t>(list.size);
  });
  const double make_unmake = elapsed_ns(iterations, [&] {
    StateInfo state;
    pos.do_move(legal.moves[0], state);
    sink += pos.key();
    pos.undo_move(legal.moves[0], state);
  });
  const double eval = elapsed_ns(iterations, [&] { sink += static_cast<uint64_t>(evaluate(pos)); });
  const double see = elapsed_ns(iterations, [&] { sink += static_cast<uint64_t>(static_exchange_eval(pos, see_move)); });

  std::printf("nsce_bench_components iterations=%d eval_file=%s movegen_ns=%.1f make_unmake_ns=%.1f "
              "eval_ns=%.1f see_ns=%.1f sink=%llu\n",
              iterations, eval_identity.c_str(), movegen, make_unmake, eval, see,
              static_cast<unsigned long long>(sink));
  return 0;
}
