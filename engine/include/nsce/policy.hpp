#pragma once

#include "nsce/types.hpp"

#include <array>
#include <cstdint>
#include <string>

namespace nsce {

class Position;

// Compact move policy: scores (piece, from, to) for ordering. int16 weights.
class PolicyNet {
 public:
  static constexpr int kPieceTo = 12 * 64;  // piece on from-sq embedding target
  static PolicyNet& instance();

  bool load_default();
  bool load(const std::string& path);
  void set_enabled(bool on) { enabled_ = on && loaded_; }
  bool is_enabled() const { return enabled_ && loaded_; }

  // Higher is better. Side-to-move perspective using absolute piece ids.
  int score_move(const Position& pos, Move m) const;

 private:
  // score = w_piece_to[pc][to] + w_from_to[from][to]
  std::array<std::array<int16_t, 64>, 12> w_piece_to{};
  std::array<std::array<int16_t, 64>, 64> w_from_to{};
  bool loaded_ = false;
  bool enabled_ = true;
};

}  // namespace nsce
