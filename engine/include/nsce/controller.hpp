#pragma once

#include "nsce/types.hpp"

#include <atomic>
#include <cstdint>
#include <fstream>
#include <mutex>
#include <string>

namespace nsce {

class Position;

// Learned search budget controller: suggests LMR reduction delta and prune probability.
class SearchController {
 public:
  SearchController() = default;
  static SearchController& instance();

  bool load_default();
  bool load(const std::string& path);
  void set_enabled(bool on) { enabled_ = on && loaded_; }
  bool is_enabled() const { return enabled_ && loaded_; }

  void set_telemetry(const std::string& path);
  bool telemetry_open() const;
  void log_decision(uint64_t key, int depth, int move_index, int reduce, int score, bool cutoff, int hist,
                    bool improving, bool cut_node, bool quiet, bool researched);

  // Extra plies to reduce (can be negative = extend). Conservative clamp applied by caller.
  int reduction_delta(int depth, int move_index, int static_eval, int alpha, int beta, bool is_quiet,
                      int policy_score, int hist, bool improving, bool cut_node, int see_sign) const;

  // 0..1000 probability-like score that a late quiet can be pruned harder.
  int prune_score(int depth, int move_index, int static_eval, int alpha) const;

 private:
  // Linear model weights (x1000 scale).
  int w_depth = 100;
  int w_index = 80;
  int w_eval_gap = 2;
  int w_quiet = 50;
  int w_policy = -1;
  int w_hist = 0;
  int w_improving = 0;
  int w_cut = 0;
  int w_see = 0;
  int bias = 0;
  bool loaded_ = false;
  bool enabled_ = true;
  std::ofstream telemetry_;
  std::mutex telemetry_mu_;
  std::atomic<bool> telemetry_enabled_{false};
};

}  // namespace nsce
