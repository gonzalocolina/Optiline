#pragma once

#include "nsce/types.hpp"

#include <algorithm>
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
// Dual-perspective bullet net (NSCEPER1):
//   MLP: Chess768 FT L1=128, pairwise CReLU, L2=16 SCReLU, L3=32 SCReLU, 8 buckets.
//   Simple: (768→512)×2 SCReLU → 1 (original P1 graph; header l2=l3=buckets=0).
//   HalfKA / threats / pawn-pairs stay a later generation.
struct NnueNet {
  static constexpr int kFeatures = 12 * 64;
  static constexpr int kHidden = 128;
  static constexpr int kKingBuckets = 16;
  static constexpr int kKatBuckets = 32;
  static constexpr int kHalfKpFeatures = kKingBuckets * kFeatures;
  static constexpr int kKatFeatures = kKatBuckets * kFeatures;
  static constexpr int kThreatDim = 12;
  static constexpr int kWeightScale = 64;  // int16 weights; activate / scale
  static constexpr int kPer1Hidden = 128;
  static constexpr int kPer1SimpleHidden = 512;
  static constexpr int kPer1Acc = 512;
  static constexpr int kPer1L2 = 16;
  static constexpr int kPer1L3 = 32;
  static_assert(kPer1Acc % 16 == 0, "PER1 accumulator AVX2 kernels step by 16");
  static_assert(kPer1Hidden <= kPer1Acc && kPer1SimpleHidden <= kPer1Acc);
  static_assert(kPer1L2 % 8 == 0 && kPer1L3 % 8 == 0, "PER1 GEMM AVX2 kernels step by 8");
  static constexpr int kPer1Buckets = 8;
  static constexpr int kPer1QA = 255;
  static constexpr int kPer1QB = 64;
  static constexpr int kPer1Scale = 400;

  bool loaded = false;
  bool halfkp = false;
  bool kat = false;
  bool per1 = false;
  bool per1_simple = false;
  int per1_ft = kPer1Hidden;
  std::array<std::array<int16_t, kHidden>, kFeatures> w0{};
  std::array<int16_t, kHidden> b0{};
  std::array<int16_t, kHidden> w1{};
  std::vector<std::array<int16_t, kHidden>> halfkp_w0{};
  std::array<int16_t, 2 * kHidden> halfkp_w1{};
  std::array<int16_t, kThreatDim> w_threat{};
  int32_t b1 = 0;
  std::vector<int16_t> per1_w0{};
  alignas(32) std::array<int16_t, kPer1Acc> per1_b0{};
  alignas(32) std::array<int16_t, 2 * kPer1SimpleHidden> per1_simple_w1{};
  int32_t per1_simple_b1 = 0;
  alignas(32) std::array<std::array<std::array<int16_t, kPer1Hidden>, kPer1L2>, kPer1Buckets> per1_l1w{};
  std::array<std::array<int32_t, kPer1L2>, kPer1Buckets> per1_l1b{};
  alignas(32) std::array<std::array<std::array<int16_t, kPer1L2>, kPer1L3>, kPer1Buckets> per1_l2w{};
  std::array<std::array<int32_t, kPer1L3>, kPer1Buckets> per1_l2b{};
  alignas(32) std::array<std::array<int16_t, kPer1L3>, kPer1Buckets> per1_l3w{};
  std::array<int32_t, kPer1Buckets> per1_l3b{};
  int per1_qa = kPer1QA;
  int per1_qb = kPer1QB;
  int per1_scale = kPer1Scale;
};

struct NnueAccumulator {
  alignas(32) std::array<int16_t, NnueNet::kHidden> v{};
  alignas(32) std::array<std::array<int16_t, NnueNet::kHidden>, 2> half{};
  alignas(32) std::array<std::array<int16_t, NnueNet::kPer1Acc>, 2> per1{};
  std::array<uint8_t, 2> king_bucket{};
  std::array<uint8_t, 2> mirror{};
  uint8_t piece_count = 0;
  mutable std::array<int16_t, NnueNet::kThreatDim> threats{};
  mutable uint8_t threats_stm = WHITE;
  mutable bool threats_valid = false;
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
  bool uses_per1() const { return net_.loaded && net_.per1; }
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

inline int per1_feature(Color perspective, Piece pc, Square sq) {
  int oriented_sq = perspective == WHITE ? static_cast<int>(sq) : (static_cast<int>(sq) ^ 56);
  int oriented_pc = static_cast<int>(pc);
  if (perspective == BLACK) oriented_pc += (pc < 6 ? 6 : -6);
  return oriented_pc * 64 + oriented_sq;
}

inline int per1_output_bucket(int piece_count) {
  const int n = std::clamp(piece_count, 2, 32);
  return (n - 2) / 4;
}

int halfkp_king_bucket(Color perspective, Square king);
int halfkp_feature(Color perspective, int king_bucket, Piece pc, Square sq);
int kat_king_bucket(Color perspective, Square king, int& mirror);
int kat_feature(Color perspective, int king_bucket, int mirror, Piece pc, Square sq);
void kat_threats(const Position& pos, Color stm, int threats[NnueNet::kThreatDim]);

}  // namespace nsce
