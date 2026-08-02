#pragma once

#include "nsce/board.hpp"
#include "nsce/movegen.hpp"
#include "nsce/tt.hpp"
#include "nsce/types.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <thread>
#include <vector>

namespace nsce {

struct SearchLimits {
  int depth = 0;
  int64_t nodes = 0;
  int movetime_ms = 0;
  int wtime = 0;
  int btime = 0;
  int winc = 0;
  int binc = 0;
  int movestogo = 0;
  bool infinite = false;
};

struct SearchInfo {
  Move best_move{};
  Move ponder_move{};
  int score = 0;
  int depth = 0;
  uint64_t nodes = 0;
  int time_ms = 0;
};

struct SearchStack {
  Move killers[2]{};
  Move current_move{};
  int static_eval = 0;
  bool skip_null = false;
};

struct SearchWorker {
  static constexpr int kMaxPly = 128;
  Move killers[kMaxPly][2]{};
  int history[12][SQUARE_NB]{};
  Move countermove[SQUARE_NB][SQUARE_NB]{};
  Move pv[kMaxPly][kMaxPly]{};
  int pv_len[kMaxPly]{};
};

class Search {
 public:
  Search();

  void set_position(const Position& pos);
  SearchInfo go(const SearchLimits& limits);
  void stop() { stop_.store(true, std::memory_order_relaxed); }
  void set_hash_mb(std::size_t mb) { tt_.resize(mb); }
  void set_threads(int n);

  uint64_t bench(int depth);

 private:
  int search(Position& pos, SearchWorker& w, SearchStack* ss, int depth, int alpha, int beta, int ply,
             bool cut_node);
  int quiescence(Position& pos, SearchWorker& w, SearchStack* ss, int alpha, int beta, int ply);
  bool time_up() const;
  void score_moves(SearchWorker& w, const Position& pos, MoveList& list, Move tt_move, Move counter, int ply,
                   int* scores) const;
  void sort_moves(MoveList& list, int* scores) const;
  void update_quiet_stats(SearchWorker& w, const Position& pos, Move best, const Move* quiets, int quiet_count,
                          int depth, int ply, Move prev);
  void helper_loop(Position root, int max_depth);

  Position root_;
  TranspositionTable tt_;
  std::atomic<bool> stop_{false};
  std::atomic<uint64_t> nodes_{0};
  std::chrono::steady_clock::time_point start_{};
  int allocated_ms_ = 0;
  int64_t nodes_limit_ = 0;
  int threads_ = 1;
  SearchWorker main_worker_{};
};

}  // namespace nsce
