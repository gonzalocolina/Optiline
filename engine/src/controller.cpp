#include "nsce/controller.hpp"

#include <algorithm>
#include <cstring>

namespace nsce {

SearchController& SearchController::instance() {
  static SearchController c;
  return c;
}

bool SearchController::load_default() {
  // Conservative prior: prefer classical LMR; only mild extra reductions on very late moves.
  w_depth = 40;
  w_index = 50;
  w_eval_gap = 1;
  w_quiet = 20;
  w_policy = -1;
  w_hist = 0;
  w_improving = 0;
  w_cut = 0;
  w_see = 0;
  bias = -120;
  loaded_ = true;
  enabled_ = true;
  return true;
}

bool SearchController::load(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) return false;
  char magic[8]{};
  in.read(magic, 8);
  const bool v2 = std::strncmp(magic, "NSCECTL2", 8) == 0;
  if (!v2 && std::strncmp(magic, "NSCECTRL", 8) != 0) return false;
  in.read(reinterpret_cast<char*>(&w_depth), 4);
  in.read(reinterpret_cast<char*>(&w_index), 4);
  in.read(reinterpret_cast<char*>(&w_eval_gap), 4);
  in.read(reinterpret_cast<char*>(&w_quiet), 4);
  in.read(reinterpret_cast<char*>(&w_policy), 4);
  in.read(reinterpret_cast<char*>(&bias), 4);
  w_hist = w_improving = w_cut = w_see = 0;
  if (v2) {
    in.read(reinterpret_cast<char*>(&w_hist), 4);
    in.read(reinterpret_cast<char*>(&w_improving), 4);
    in.read(reinterpret_cast<char*>(&w_cut), 4);
    in.read(reinterpret_cast<char*>(&w_see), 4);
  }
  if (!in) return false;
  loaded_ = true;
  enabled_ = true;
  return true;
}

void SearchController::set_telemetry(const std::string& path) {
  std::lock_guard<std::mutex> lock(telemetry_mu_);
  if (telemetry_.is_open()) telemetry_.close();
  telemetry_enabled_ = false;
  if (!path.empty() && path != "<empty>") {
    telemetry_.open(path, std::ios::app);
    telemetry_enabled_ = telemetry_.is_open();
  }
}

bool SearchController::telemetry_open() const { return telemetry_enabled_.load(std::memory_order_relaxed); }

void SearchController::log_decision(uint64_t key, int depth, int move_index, int reduce, int score, bool cutoff,
                                    int hist, bool improving, bool cut_node, bool quiet, bool researched) {
  std::lock_guard<std::mutex> lock(telemetry_mu_);
  if (!telemetry_.is_open()) return;
  telemetry_ << std::hex << key << std::dec << ',' << depth << ',' << move_index << ',' << reduce << ',' << score
             << ',' << (cutoff ? 1 : 0) << ',' << hist << ',' << (improving ? 1 : 0) << ',' << (cut_node ? 1 : 0)
             << ',' << (quiet ? 1 : 0) << ',' << (researched ? 1 : 0) << '\n';
}

int SearchController::reduction_delta(int depth, int move_index, int static_eval, int alpha, int beta, bool is_quiet,
                                      int policy_score, int hist, bool improving, bool cut_node, int see_sign) const {
  if (!is_enabled()) return 0;
  int gap = std::abs(static_eval - (alpha + beta) / 2);
  int raw = bias + w_depth * depth / 8 + w_index * move_index / 4 + w_eval_gap * gap / 100 +
            (is_quiet ? w_quiet : 0) + w_policy * policy_score / 50 +
            w_hist * std::clamp(hist, -2000, 2000) / 200 + (improving ? w_improving : 0) +
            (cut_node ? w_cut : 0) + w_see * see_sign;
  // Map to delta in [-1, +2] — never more aggressive than +2 vs classical LMR
  int delta = raw / 250;
  return std::clamp(delta, -1, 2);
}

int SearchController::prune_score(int depth, int move_index, int static_eval, int alpha) const {
  if (!is_enabled()) return 0;
  int raw = w_index * move_index + w_depth * depth + (static_eval < alpha - 100 ? 100 : 0);
  return std::clamp(raw, 0, 1000);
}

}  // namespace nsce
