#pragma once

#include "nsce/board.hpp"
#include "nsce/movegen.hpp"
#include "nsce/tt.hpp"
#include "nsce/types.hpp"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
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

struct SearchStats {
  uint64_t qnodes = 0;
  uint64_t evaluations = 0;
  uint64_t tt_probes = 0;
  uint64_t tt_hits = 0;
  uint64_t tt_cutoffs = 0;
  uint64_t generated_moves = 0;
  uint64_t beta_cutoffs = 0;
  uint64_t first_move_cutoffs = 0;
  uint64_t cutoff_index_sum = 0;
  uint64_t see_order_calls = 0;
  uint64_t see_prune_calls = 0;
  uint64_t see_prunes = 0;
  uint64_t lmr_attempts = 0;
  uint64_t lmr_researches = 0;
  uint64_t null_attempts = 0;
  uint64_t null_cutoffs = 0;
  uint64_t razor_attempts = 0;
  uint64_t razor_cutoffs = 0;
  uint64_t rfp_attempts = 0;
  uint64_t rfp_cutoffs = 0;
  uint64_t futility_prunes = 0;
  uint64_t lmp_prunes = 0;
  uint64_t see_search_prunes = 0;
  uint64_t singular_attempts = 0;
  uint64_t singular_extensions = 0;
  uint64_t iir_reductions = 0;
  uint64_t qs_tt_cutoffs = 0;
  uint64_t root_moves = 0;
  uint64_t probcut_attempts = 0;
  uint64_t probcut_cutoffs = 0;

  SearchStats& operator+=(const SearchStats& other);
};

struct SearchStack {
  Move current_move{};
  Move excluded{};
  int static_eval = 0;
  int double_extensions = 0;
  bool skip_null = false;
  Piece moved_piece = NO_PIECE;
};

struct SearchWorker {
  static constexpr int kMaxPly = 128;
  static constexpr int kStackPad = 6;
  static constexpr int kCorrSize = 16384;
  Move killers[kMaxPly][2]{};
  int history[12][SQUARE_NB]{};
  int capture_history[12][SQUARE_NB][PIECE_TYPE_NB]{};
  int16_t continuation[12][SQUARE_NB][12][SQUARE_NB]{};
  int pawn_corr[COLOR_NB][kCorrSize]{};
  int nonpawn_corr[COLOR_NB][kCorrSize]{};
  int cont_corr[12][SQUARE_NB]{};
  Move countermove[SQUARE_NB][SQUARE_NB]{};
  Move pv[kMaxPly][kMaxPly]{};
  int pv_len[kMaxPly]{};
  uint64_t nodes = 0;
  uint64_t published_nodes = 0;
  SearchStats stats{};
};

class Search {
 public:
  Search();
  ~Search();

  void set_position(const Position& pos);
  SearchInfo go(const SearchLimits& limits);
  void prepare() { stop_.store(false, std::memory_order_relaxed); }
  SearchInfo go_prepared(const SearchLimits& limits);
  void stop() { stop_.store(true, std::memory_order_relaxed); }
  void set_hash_mb(std::size_t mb) { tt_.resize(mb); }
  void set_threads(int n);
  void set_use_tt(bool on) { use_tt_ = on; }
  void set_use_see(bool on) { use_see_ = on; }
  void set_use_lmr(bool on) { use_lmr_ = on; }
  void set_use_null_move(bool on) { use_null_move_ = on; }
  void set_use_futility(bool on) { use_futility_ = on; }
  void set_use_lmp(bool on) { use_lmp_ = on; }
  void set_use_razoring(bool on) { use_razoring_ = on; }
  void set_use_rfp(bool on) { use_rfp_ = on; }
  void set_use_probcut(bool on) { use_probcut_ = on; }
  void set_silent(bool on) { silent_ = on; }
  const SearchStats& last_stats() const { return last_stats_; }

  uint64_t bench(int depth);

 private:
  int search(Position& pos, SearchWorker& w, SearchStack* ss, int depth, int alpha, int beta, int ply,
             bool cut_node);
  int quiescence(Position& pos, SearchWorker& w, SearchStack* ss, int alpha, int beta, int ply);
  bool time_up() const;
  bool count_node(SearchWorker& w);
  void flush_nodes(SearchWorker& w);
  void score_moves(SearchWorker& w, const Position& pos, const SearchStack* ss, MoveList& list, Move tt_move,
                   Move counter, int ply, int* scores) const;
  void sort_moves(MoveList& list, int* scores) const;
  void update_quiet_stats(SearchWorker& w, const Position& pos, SearchStack* ss, Move best, const Move* quiets,
                          int quiet_count, int depth, int ply, Move prev);
  void update_capture_stats(SearchWorker& w, const Position& pos, Move best, const Move* captures, int capture_count,
                            int depth);
  int correction(const SearchWorker& w, const Position& pos) const;
  int correction(const SearchWorker& w, const Position& pos, const SearchStack* ss, int ply) const;
  void update_correction(SearchWorker& w, const Position& pos, int static_eval, int best_score, Bound bound, int depth);

  int lmr_quiet_[64][64]{};
  int lmr_capture_[64][64]{};
  int pick_next_move(MoveList& list, int* scores, int start) const;
  int search_root_parallel(int depth, int alpha, int beta);
  void start_helper_pool();
  void stop_helper_pool();
  void helper_worker_loop(std::size_t index);
  void launch_helper_job(std::function<void(SearchWorker&)> job);
  void wait_helper_job();

  Position root_;
  TranspositionTable tt_;
  std::atomic<bool> stop_{false};
  std::atomic<uint64_t> nodes_{0};
  std::chrono::steady_clock::time_point start_{};
  int optimum_ms_ = 0;
  int maximum_ms_ = 0;
  bool use_soft_time_ = false;
  int64_t nodes_limit_ = 0;
  int threads_ = 1;
  bool use_tt_ = true;
  bool use_see_ = true;
  bool use_lmr_ = true;
  bool use_null_move_ = true;
  bool use_futility_ = true;
  bool use_lmp_ = true;
  bool use_razoring_ = true;
  bool use_rfp_ = true;
  bool use_probcut_ = true;
  bool silent_ = false;
  int root_depth_ = 0;
  SearchWorker main_worker_{};
  SearchStats last_stats_{};
  std::vector<std::unique_ptr<SearchWorker>> helper_workers_;
  std::vector<std::thread> helper_threads_;
  std::mutex helper_mutex_;
  std::condition_variable helper_start_cv_;
  std::condition_variable helper_done_cv_;
  std::function<void(SearchWorker&)> helper_job_;
  uint64_t helper_generation_ = 0;
  std::size_t helper_completed_ = 0;
  bool helper_exit_ = false;
};

}  // namespace nsce
