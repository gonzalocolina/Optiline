#pragma once

#include "nsce/types.hpp"

#include <array>
#include <cstdint>
#include <string>

namespace nsce {

class Position;

// Compact incremental NNUE: 768 PS features -> H hidden -> 1 (centipawns).
struct NnueNet {
  static constexpr int kFeatures = 12 * 64;
  static constexpr int kHidden = 128;
  static constexpr int kWeightScale = 64;  // int16 weights; activate / scale

  bool loaded = false;
  std::array<std::array<int16_t, kHidden>, kFeatures> w0{};
  std::array<int16_t, kHidden> b0{};
  std::array<int16_t, kHidden> w1{};
  int32_t b1 = 0;
};

struct NnueAccumulator {
  alignas(32) std::array<int16_t, NnueNet::kHidden> v{};
};

class Nnue {
 public:
  static Nnue& instance();

  bool load(const std::string& path);
  bool load_default_from_hce();  // PST-distilled linear init (no external file)
  bool enabled() const { return net_.loaded; }
  void set_enabled(bool on) { enabled_ = on && net_.loaded; }
  bool is_enabled() const { return enabled_ && net_.loaded; }

  void refresh(const Position& pos, NnueAccumulator& acc) const;
  void add_piece(NnueAccumulator& acc, Piece pc, Square sq) const;
  void remove_piece(NnueAccumulator& acc, Piece pc, Square sq) const;

  // Score from side-to-move perspective (centipawns).
  int evaluate(const NnueAccumulator& acc, Color stm) const;

  const NnueNet& net() const { return net_; }

 private:
  Nnue() = default;
  NnueNet net_{};
  bool enabled_ = true;
};

inline int nnue_feature(Piece pc, Square sq) {
  return static_cast<int>(pc) * 64 + static_cast<int>(sq);
}

}  // namespace nsce
