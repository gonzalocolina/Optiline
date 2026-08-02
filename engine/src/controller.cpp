#include "nsce/controller.hpp"

#include <algorithm>
#include <cstring>

namespace nsce {

SearchController& SearchController::instance() {
  static SearchController c;
  return c;
}

bool SearchController::load_default() {
  // Conservative prior: reduce more on late quiet moves at higher depth.
  w_depth = 80;
  w_index = 70;
  w_eval_gap = 2;
  w_quiet = 40;
  w_policy = -1;
  bias = -50;
  loaded_ = true;
  enabled_ = true;
  return true;
}

bool SearchController::load(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) return false;
  char magic[8]{};
  in.read(magic, 8);
  if (std::strncmp(magic, "NSCECTRL", 8) != 0) return false;
  in.read(reinterpret_cast<char*>(&w_depth), 4);
  in.read(reinterpret_cast<char*>(&w_index), 4);
  in.read(reinterpret_cast<char*>(&w_eval_gap), 4);
  in.read(reinterpret_cast<char*>(&w_quiet), 4);
  in.read(reinterpret_cast<char*>(&w_policy), 4);
  in.read(reinterpret_cast<char*>(&bias), 4);
  if (!in) return false;
  loaded_ = true;
  enabled_ = true;
  return true;
}

void SearchController::set_telemetry(const std::string& path) {
  std::lock_guard<std::mutex> lock(telemetry_mu_);
  if (telemetry_.is_open()) telemetry_.close();
  if (!path.empty() && path != "<empty>") {
    telemetry_.open(path, std::ios::app);
  }
}

void SearchController::log_decision(uint64_t key, int depth, int move_index, int reduce, int score, bool cutoff) {
  std::lock_guard<std::mutex> lock(telemetry_mu_);
  if (!telemetry_.is_open()) return;
  telemetry_ << std::hex << key << std::dec << ',' << depth << ',' << move_index << ',' << reduce << ',' << score
             << ',' << (cutoff ? 1 : 0) << '\n';
}

int SearchController::reduction_delta(int depth, int move_index, int static_eval, int alpha, int beta, bool is_quiet,
                                      int policy_score) const {
  if (!is_enabled()) return 0;
  int gap = std::abs(static_eval - (alpha + beta) / 2);
  int raw = bias + w_depth * depth / 8 + w_index * move_index / 4 + w_eval_gap * gap / 100 +
            (is_quiet ? w_quiet : 0) + w_policy * policy_score / 50;
  // Map to delta in [-1, +3]
  int delta = raw / 200;
  return std::clamp(delta, -1, 3);
}

int SearchController::prune_score(int depth, int move_index, int static_eval, int alpha) const {
  if (!is_enabled()) return 0;
  int raw = w_index * move_index + w_depth * depth + (static_eval < alpha - 100 ? 100 : 0);
  return std::clamp(raw, 0, 1000);
}

}  // namespace nsce
