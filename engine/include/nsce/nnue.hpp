#pragma once

#include "nsce/types.hpp"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace nsce {

class Position;

// Compact incremental NNUE: 768 PS features -> H hidden -> 1 (centipawns).
// King-aware variants:
//   NSCEHFKP — 16 king buckets × 768 (legacy HalfKA-lite)
//   NSCEKAT1 — 32 horizontally-mirrored buckets × 768 + 12-dim tactical residual
struct NnueNet {
  static constexpr int kFeatures = 12 * 64;
  static constexpr int kHidden = 128;
  static constexpr int kKingBuckets = 16;
  static constexpr int kKatBuckets = 32;
  static constexpr int kHalfKpFeatures = kKingBuckets * kFeatures;
  static constexpr int kKatFeatures = kKatBuckets * kFeatures;
  static constexpr int kThreatDim = 12;
  static constexpr int kWeightScale = 64;  // int16 weights; activate / scale

  bool loaded = false;
  bool halfkp = false;
  bool kat = false;
  std::array<std::array<int16_t, kHidden>, kFeatures> w0{};
  std::array<int16_t, kHidden> b0{};
  std::array<int16_t, kHidden> w1{};
  std::vector<std::array<int16_t, kHidden>> halfkp_w0{};
  std::array<int16_t, 2 * kHidden> halfkp_w1{};
  std::array<int16_t, kThreatDim> w_threat{};
  int32_t b1 = 0;
};

struct NnueAccumulator {
  alignas(32) std::array<int16_t, NnueNet::kHidden> v{};
  alignas(32) std::array<std::array<int16_t, NnueNet::kHidden>, 2> half{};
  std::array<uint8_t, 2> king_bucket{};
  std::array<uint8_t, 2> mirror{};
};

class Nnue {
 public:
  Nnue() = default;
  static Nnue& instance();

  bool load(const std::string& path);
  bool load_default_from_hce();  // PST-distilled linear init (no external file)
  bool enabled() const { return net_.loaded; }
  bool uses_king_buckets() const { return net_.loaded && (net_.halfkp || net_.kat); }
  bool uses_kat() const { return net_.loaded && net_.kat; }
  void set_enabled(bool on) { enabled_ = on && net_.loaded; }
  bool is_enabled() const { return enabled_ && net_.loaded; }

  void refresh(const Position& pos, NnueAccumulator& acc) const;
  void add_piece(NnueAccumulator& acc, Piece pc, Square sq) const;
  void remove_piece(NnueAccumulator& acc, Piece pc, Square sq) const;
  void update_king_move(NnueAccumulator& acc, const Position& pos, Piece king, Square from,
                        Square to) const;

  // Score from side-to-move perspective (centipawns).
  int evaluate(const NnueAccumulator& acc, Color stm) const;
  int evaluate(const Position& pos) const;

  const NnueNet& net() const { return net_; }

 private:
  void add_piece_for(NnueAccumulator& acc, Color perspective, Piece pc, Square sq) const;
  void remove_piece_for(NnueAccumulator& acc, Color perspective, Piece pc, Square sq) const;
  void refresh_perspective(const Position& pos, NnueAccumulator& acc, Color perspective) const;

  NnueNet net_{};
  bool enabled_ = true;
};

inline int nnue_feature(Piece pc, Square sq) {
  return static_cast<int>(pc) * 64 + static_cast<int>(sq);
}

int halfkp_king_bucket(Color perspective, Square king);
int halfkp_feature(Color perspective, int king_bucket, Piece pc, Square sq);
int kat_king_bucket(Color perspective, Square king, int& mirror);
int kat_feature(Color perspective, int king_bucket, int mirror, Piece pc, Square sq);
void kat_threats(const Position& pos, Color stm, int threats[NnueNet::kThreatDim]);

}  // namespace nsce
