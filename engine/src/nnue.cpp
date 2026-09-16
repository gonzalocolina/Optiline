#include "nsce/nnue.hpp"

#include "nsce/board.hpp"
#include "nsce/eval.hpp"

#include <algorithm>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <utility>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

namespace nsce {
namespace {

constexpr int PieceValue[6] = {100, 320, 330, 500, 900, 0};

constexpr int PST[6][64] = {
    {0,0,0,0,0,0,0,0, 50,50,50,50,50,50,50,50, 10,10,20,30,30,20,10,10, 5,5,10,25,25,10,5,5,
     0,0,0,20,20,0,0,0, 5,-5,-10,0,0,-10,-5,5, 5,10,10,-20,-20,10,10,5, 0,0,0,0,0,0,0,0},
    {-50,-40,-30,-30,-30,-30,-40,-50,-40,-20,0,0,0,0,-20,-40,-30,0,10,15,15,10,0,-30,-30,5,15,20,20,15,5,-30,
     -30,0,15,20,20,15,0,-30,-30,5,10,15,15,10,5,-30,-40,-20,0,5,5,0,-20,-40,-50,-40,-30,-30,-30,-30,-40,-50},
    {-20,-10,-10,-10,-10,-10,-10,-20,-10,0,0,0,0,0,0,-10,-10,0,5,10,10,5,0,-10,-10,5,5,10,10,5,5,-10,
     -10,0,10,10,10,10,0,-10,-10,10,10,10,10,10,10,-10,-10,5,0,0,0,0,5,-10,-20,-10,-10,-10,-10,-10,-10,-20},
    {0,0,0,0,0,0,0,0, 5,10,10,10,10,10,10,5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
     -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, 0,0,0,5,5,0,0,0},
    {-20,-10,-10,-5,-5,-10,-10,-20,-10,0,0,0,0,0,0,-10,-10,0,5,5,5,5,0,-10,-5,0,5,5,5,5,0,-5,
     0,0,5,5,5,5,0,-5,-10,5,5,5,5,5,0,-10,-10,0,5,0,0,0,0,-10,-20,-10,-10,-5,-5,-10,-10,-20},
    {-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,
     -20,-30,-30,-40,-40,-30,-30,-20,-10,-20,-20,-20,-20,-20,-20,-10,20,20,0,0,0,0,20,20,20,30,10,0,0,10,30,20}};

int16_t clamp_i16(int v) {
  return static_cast<int16_t>(std::clamp(v, -32768, 32767));
}

#if defined(__AVX2__)
inline void acc_add_avx(int16_t* acc, const int16_t* col) {
  for (int h = 0; h < NnueNet::kHidden; h += 16) {
    __m256i a = _mm256_load_si256(reinterpret_cast<const __m256i*>(acc + h));
    __m256i b = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(col + h));
    _mm256_store_si256(reinterpret_cast<__m256i*>(acc + h), _mm256_adds_epi16(a, b));
  }
}

inline void acc_sub_avx(int16_t* acc, const int16_t* col) {
  for (int h = 0; h < NnueNet::kHidden; h += 16) {
    __m256i a = _mm256_load_si256(reinterpret_cast<const __m256i*>(acc + h));
    __m256i b = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(col + h));
    _mm256_store_si256(reinterpret_cast<__m256i*>(acc + h), _mm256_subs_epi16(a, b));
  }
}

inline int32_t hsum_epi32(__m256i sum32) {
  __m128i lo = _mm256_castsi256_si128(sum32);
  __m128i hi = _mm256_extracti128_si256(sum32, 1);
  __m128i s = _mm_add_epi32(lo, hi);
  s = _mm_add_epi32(s, _mm_shuffle_epi32(s, 0x4E));
  s = _mm_add_epi32(s, _mm_shuffle_epi32(s, 0xB1));
  return _mm_cvtsi128_si32(s);
}

inline int32_t affine_avx(const int16_t* acc, const int16_t* w1, int32_t bias) {
  __m256i sum32 = _mm256_setzero_si256();
  const __m256i zero = _mm256_setzero_si256();
  const __m256i vmax = _mm256_set1_epi16(static_cast<int16_t>(127 * NnueNet::kWeightScale));
  for (int h = 0; h < NnueNet::kHidden; h += 16) {
    __m256i x = _mm256_load_si256(reinterpret_cast<const __m256i*>(acc + h));
    x = _mm256_min_epi16(_mm256_max_epi16(x, zero), vmax);
    __m256i w = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(w1 + h));
    sum32 = _mm256_add_epi32(sum32, _mm256_madd_epi16(x, w));
  }
  return bias + hsum_epi32(sum32);
}

inline int32_t affine_dual_avx(const int16_t* own, const int16_t* opp, const int16_t* w1, int32_t bias) {
  __m256i sum32 = _mm256_setzero_si256();
  const __m256i zero = _mm256_setzero_si256();
  const __m256i vmax = _mm256_set1_epi16(static_cast<int16_t>(127 * NnueNet::kWeightScale));
  const int16_t* w_opp = w1 + NnueNet::kHidden;
  for (int h = 0; h < NnueNet::kHidden; h += 16) {
    __m256i x0 = _mm256_load_si256(reinterpret_cast<const __m256i*>(own + h));
    x0 = _mm256_min_epi16(_mm256_max_epi16(x0, zero), vmax);
    __m256i x1 = _mm256_load_si256(reinterpret_cast<const __m256i*>(opp + h));
    x1 = _mm256_min_epi16(_mm256_max_epi16(x1, zero), vmax);
    sum32 = _mm256_add_epi32(sum32, _mm256_madd_epi16(x0, _mm256_loadu_si256(reinterpret_cast<const __m256i*>(w1 + h))));
    sum32 = _mm256_add_epi32(sum32, _mm256_madd_epi16(x1, _mm256_loadu_si256(reinterpret_cast<const __m256i*>(w_opp + h))));
  }
  return bias + hsum_epi32(sum32);
}

inline void per1_acc_add2(int16_t* acc_w, int16_t* acc_b, const int16_t* col_w, const int16_t* col_b) {
  for (int h = 0; h < NnueNet::kPer1Hidden; h += 16) {
    __m256i aw = _mm256_load_si256(reinterpret_cast<const __m256i*>(acc_w + h));
    __m256i ab = _mm256_load_si256(reinterpret_cast<const __m256i*>(acc_b + h));
    __m256i cw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(col_w + h));
    __m256i cb = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(col_b + h));
    _mm256_store_si256(reinterpret_cast<__m256i*>(acc_w + h), _mm256_adds_epi16(aw, cw));
    _mm256_store_si256(reinterpret_cast<__m256i*>(acc_b + h), _mm256_adds_epi16(ab, cb));
  }
}

inline void per1_acc_sub2(int16_t* acc_w, int16_t* acc_b, const int16_t* col_w, const int16_t* col_b) {
  for (int h = 0; h < NnueNet::kPer1Hidden; h += 16) {
    __m256i aw = _mm256_load_si256(reinterpret_cast<const __m256i*>(acc_w + h));
    __m256i ab = _mm256_load_si256(reinterpret_cast<const __m256i*>(acc_b + h));
    __m256i cw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(col_w + h));
    __m256i cb = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(col_b + h));
    _mm256_store_si256(reinterpret_cast<__m256i*>(acc_w + h), _mm256_subs_epi16(aw, cw));
    _mm256_store_si256(reinterpret_cast<__m256i*>(acc_b + h), _mm256_subs_epi16(ab, cb));
  }
}

inline int64_t hsum_epi64(__m256i sum64) {
  const __m128i lo = _mm256_castsi256_si128(sum64);
  const __m128i hi = _mm256_extracti128_si256(sum64, 1);
  const __m128i s = _mm_add_epi64(lo, hi);
  return _mm_cvtsi128_si64(_mm_add_epi64(s, _mm_unpackhi_epi64(s, s)));
}

// SCReLU: clamp to [0, qa], square, multiply by int16 weight.
// 255^2 * 32767 fits in int32; 16 of those do not, so widen to int64 per vector.
inline void screlu_fma16(const __m256i x_clamped, const __m256i w16, __m256i& sum64) {
  const __m256i x0 = _mm256_cvtepi16_epi32(_mm256_castsi256_si128(x_clamped));
  const __m256i x1 = _mm256_cvtepi16_epi32(_mm256_extracti128_si256(x_clamped, 1));
  const __m256i w0 = _mm256_cvtepi16_epi32(_mm256_castsi256_si128(w16));
  const __m256i w1 = _mm256_cvtepi16_epi32(_mm256_extracti128_si256(w16, 1));
  const __m256i p0 = _mm256_mullo_epi32(_mm256_mullo_epi32(x0, x0), w0);
  const __m256i p1 = _mm256_mullo_epi32(_mm256_mullo_epi32(x1, x1), w1);
  sum64 = _mm256_add_epi64(sum64, _mm256_cvtepi32_epi64(_mm256_castsi256_si128(p0)));
  sum64 = _mm256_add_epi64(sum64, _mm256_cvtepi32_epi64(_mm256_extracti128_si256(p0, 1)));
  sum64 = _mm256_add_epi64(sum64, _mm256_cvtepi32_epi64(_mm256_castsi256_si128(p1)));
  sum64 = _mm256_add_epi64(sum64, _mm256_cvtepi32_epi64(_mm256_extracti128_si256(p1, 1)));
}

inline int64_t per1_screlu_dual_avx(const int16_t* stm, const int16_t* nstm, const int16_t* w,
                                   int qa) {
  __m256i sum64 = _mm256_setzero_si256();
  const __m256i zero = _mm256_setzero_si256();
  const __m256i vqa = _mm256_set1_epi16(static_cast<int16_t>(qa));
  const int16_t* w_nstm = w + NnueNet::kPer1Hidden;
  for (int h = 0; h < NnueNet::kPer1Hidden; h += 16) {
    __m256i xs = _mm256_load_si256(reinterpret_cast<const __m256i*>(stm + h));
    xs = _mm256_min_epi16(_mm256_max_epi16(xs, zero), vqa);
    __m256i xn = _mm256_load_si256(reinterpret_cast<const __m256i*>(nstm + h));
    xn = _mm256_min_epi16(_mm256_max_epi16(xn, zero), vqa);
    screlu_fma16(xs, _mm256_load_si256(reinterpret_cast<const __m256i*>(w + h)), sum64);
    screlu_fma16(xn, _mm256_load_si256(reinterpret_cast<const __m256i*>(w_nstm + h)), sum64);
  }
  return hsum_epi64(sum64);
}
#endif

inline int64_t per1_screlu_dual_scalar(const int16_t* stm, const int16_t* nstm, const int16_t* w,
                                      int qa) {
  int64_t sum = 0;
  for (int h = 0; h < NnueNet::kPer1Hidden; ++h) {
    int x = std::clamp(static_cast<int>(stm[h]), 0, qa);
    sum += static_cast<int64_t>(x) * x * w[h];
    x = std::clamp(static_cast<int>(nstm[h]), 0, qa);
    sum += static_cast<int64_t>(x) * x * w[NnueNet::kPer1Hidden + h];
  }
  return sum;
}

}  // namespace

int halfkp_king_bucket(Color perspective, Square king) {
  int oriented = perspective == WHITE ? static_cast<int>(king) : (static_cast<int>(king) ^ 56);
  return (rank_of(static_cast<Square>(oriented)) / 2) * 4 + file_of(static_cast<Square>(oriented)) / 2;
}

int halfkp_feature(Color perspective, int king_bucket, Piece pc, Square sq) {
  int oriented_sq = perspective == WHITE ? static_cast<int>(sq) : (static_cast<int>(sq) ^ 56);
  const int oriented_pc =
      perspective == BLACK ? static_cast<int>(pc) + (pc < 6 ? 6 : -6) : static_cast<int>(pc);
  return king_bucket * NnueNet::kFeatures + oriented_pc * 64 + oriented_sq;
}

int kat_king_bucket(Color perspective, Square king, int& mirror) {
  int oriented = perspective == WHITE ? static_cast<int>(king) : (static_cast<int>(king) ^ 56);
  mirror = 0;
  if (file_of(static_cast<Square>(oriented)) < 4) {
    mirror = 7;
    oriented ^= 7;
  }
  return rank_of(static_cast<Square>(oriented)) * 4 + (file_of(static_cast<Square>(oriented)) - 4);
}

int kat_feature(Color perspective, int king_bucket, int mirror, Piece pc, Square sq) {
  int oriented_sq = perspective == WHITE ? static_cast<int>(sq) : (static_cast<int>(sq) ^ 56);
  oriented_sq ^= mirror;
  const int oriented_pc =
      perspective == BLACK ? static_cast<int>(pc) + (pc < 6 ? 6 : -6) : static_cast<int>(pc);
  return king_bucket * NnueNet::kFeatures + oriented_pc * 64 + oriented_sq;
}

void kat_threats(const Position& pos, Color stm, int threats[NnueNet::kThreatDim]) {
  const Bitboard our_attacks = pos.attacks(stm);
  const Bitboard their_attacks = pos.attacks(~stm);
  for (int pt = 0; pt < 6; ++pt) {
    threats[pt] = popcount(pos.pieces(stm, static_cast<PieceType>(pt)) & their_attacks);
    threats[6 + pt] = popcount(pos.pieces(~stm, static_cast<PieceType>(pt)) & our_attacks);
  }
}

Nnue& Nnue::instance() {
  static Nnue n;
  return n;
}

bool Nnue::load_default_from_hce() {
  NnueNet next{};
  const int H = NnueNet::kHidden;
  for (int pc = 0; pc < 12; ++pc) {
    PieceType pt = type_of(static_cast<Piece>(pc));
    Color c = color_of(static_cast<Piece>(pc));
    for (int sq = 0; sq < 64; ++sq) {
      int pst_sq = (c == WHITE) ? sq : (sq ^ 56);
      int val = PieceValue[pt] + PST[pt][pst_sq];
      if (c == BLACK) val = -val;
      for (int h = 0; h < H; ++h) {
        int w = (val * NnueNet::kWeightScale) / H;
        w += ((h * 17 + sq * 3 + pc) & 7) - 3;
        next.w0[pc * 64 + sq][h] = clamp_i16(w);
      }
    }
  }
  for (int h = 0; h < H; ++h) {
    next.b0[h] = 0;
    next.w1[h] = clamp_i16(NnueNet::kWeightScale);
  }
  next.b1 = 0;
  next.loaded = true;
  net_ = std::move(next);
  set_enabled(enabled_);
  return true;
}

bool Nnue::load(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) return false;
  char magic[8]{};
  in.read(magic, 8);
  if (std::strncmp(magic, "NSCEPER1", 8) == 0) {
    int32_t hidden = 0, features = 0, buckets = 0, qa = 0, qb = 0, scale = 0;
    in.read(reinterpret_cast<char*>(&hidden), 4);
    in.read(reinterpret_cast<char*>(&features), 4);
    in.read(reinterpret_cast<char*>(&buckets), 4);
    in.read(reinterpret_cast<char*>(&qa), 4);
    in.read(reinterpret_cast<char*>(&qb), 4);
    in.read(reinterpret_cast<char*>(&scale), 4);
    if (!in || hidden != NnueNet::kPer1Hidden || features != NnueNet::kFeatures ||
        buckets != NnueNet::kPer1Buckets || qa <= 0 || qb <= 0 || scale <= 0)
      return false;
    std::error_code size_error;
    const uintmax_t file_size = std::filesystem::file_size(path, size_error);
    if (size_error) return false;
    const uintmax_t expected_size =
        8 + 6 * 4 + static_cast<uintmax_t>(features) * hidden * 2 + static_cast<uintmax_t>(hidden) * 2 +
        static_cast<uintmax_t>(buckets) * 2 * hidden * 2 + static_cast<uintmax_t>(buckets) * 4;
    if (file_size != expected_size) return false;
    NnueNet next{};
    next.per1 = true;
    next.per1_qa = qa;
    next.per1_qb = qb;
    next.per1_scale = scale;
    next.per1_w0.resize(static_cast<std::size_t>(features) * hidden);
    in.read(reinterpret_cast<char*>(next.per1_w0.data()),
            static_cast<std::streamsize>(next.per1_w0.size() * 2));
    in.read(reinterpret_cast<char*>(next.per1_b0.data()), NnueNet::kPer1Hidden * 2);
    for (int b = 0; b < NnueNet::kPer1Buckets; ++b)
      in.read(reinterpret_cast<char*>(next.per1_w1[b].data()), 2 * NnueNet::kPer1Hidden * 2);
    in.read(reinterpret_cast<char*>(next.per1_b1.data()), NnueNet::kPer1Buckets * 4);
    if (!in) return false;
    next.loaded = true;
    net_ = std::move(next);
    set_enabled(enabled_);
    return true;
  }
  const bool kat = std::strncmp(magic, "NSCEKAT1", 8) == 0;
  const bool halfkp = std::strncmp(magic, "NSCEHFKP", 8) == 0;
  if (!kat && !halfkp && std::strncmp(magic, "NSCENNUE", 8) != 0) return false;
  int32_t hidden = 0, features = 0;
  in.read(reinterpret_cast<char*>(&features), 4);
  in.read(reinterpret_cast<char*>(&hidden), 4);
  if (!in) return false;
  const int expected_features =
      kat ? NnueNet::kKatFeatures : halfkp ? NnueNet::kHalfKpFeatures : NnueNet::kFeatures;
  if (features != expected_features || hidden != NnueNet::kHidden) return false;
  int32_t threat_dim = 0;
  if (kat) {
    in.read(reinterpret_cast<char*>(&threat_dim), 4);
    if (threat_dim != NnueNet::kThreatDim) return false;
  }
  if (!in) return false;
  const int input_features = kat ? NnueNet::kKatFeatures : halfkp ? NnueNet::kHalfKpFeatures : 0;
  const int serialized_features = kat ? NnueNet::kKatFeatures : halfkp ? NnueNet::kHalfKpFeatures
                                                                         : NnueNet::kFeatures;
  std::error_code size_error;
  const uintmax_t file_size = std::filesystem::file_size(path, size_error);
  if (size_error) return false;
  const uintmax_t expected_size =
      8 + 4 + 4 + (kat ? 4 : 0) + static_cast<uintmax_t>(serialized_features) * NnueNet::kHidden * 2 +
      static_cast<uintmax_t>(NnueNet::kHidden) * 2 + static_cast<uintmax_t>(kat || halfkp ? 2 : 1) *
          NnueNet::kHidden * 2 + (kat ? NnueNet::kThreatDim * 2 : 0) + 4;
  if (file_size != expected_size) return false;
  NnueNet next{};
  next.kat = kat;
  next.halfkp = halfkp || kat;
  if (kat || halfkp) {
    next.halfkp_w0.resize(input_features);
    for (int f = 0; f < input_features; ++f)
      in.read(reinterpret_cast<char*>(next.halfkp_w0[f].data()), NnueNet::kHidden * 2);
  } else {
    for (int f = 0; f < NnueNet::kFeatures; ++f)
      in.read(reinterpret_cast<char*>(next.w0[f].data()), NnueNet::kHidden * 2);
  }
  in.read(reinterpret_cast<char*>(next.b0.data()), NnueNet::kHidden * 2);
  if (kat || halfkp)
    in.read(reinterpret_cast<char*>(next.halfkp_w1.data()), 2 * NnueNet::kHidden * 2);
  else
    in.read(reinterpret_cast<char*>(next.w1.data()), NnueNet::kHidden * 2);
  if (kat) in.read(reinterpret_cast<char*>(next.w_threat.data()), NnueNet::kThreatDim * 2);
  in.read(reinterpret_cast<char*>(&next.b1), 4);
  if (!in) return false;
  next.loaded = true;
  net_ = std::move(next);
  set_enabled(enabled_);
  return true;
}

void Nnue::add_piece_for(NnueAccumulator& acc, Color perspective, Piece pc, Square sq) const {
  if (pc == NO_PIECE) return;
  const int feature = net_.kat ? kat_feature(perspective, acc.king_bucket[perspective],
                                             acc.mirror[perspective], pc, sq)
                               : halfkp_feature(perspective, acc.king_bucket[perspective], pc, sq);
  const auto& column = net_.halfkp_w0[feature];
#if defined(__AVX2__)
  acc_add_avx(acc.half[perspective].data(), column.data());
#else
  for (int h = 0; h < NnueNet::kHidden; ++h)
    acc.half[perspective][h] = clamp_i16(acc.half[perspective][h] + column[h]);
#endif
}

void Nnue::remove_piece_for(NnueAccumulator& acc, Color perspective, Piece pc, Square sq) const {
  if (pc == NO_PIECE) return;
  const int feature = net_.kat ? kat_feature(perspective, acc.king_bucket[perspective],
                                             acc.mirror[perspective], pc, sq)
                               : halfkp_feature(perspective, acc.king_bucket[perspective], pc, sq);
  const auto& column = net_.halfkp_w0[feature];
#if defined(__AVX2__)
  acc_sub_avx(acc.half[perspective].data(), column.data());
#else
  for (int h = 0; h < NnueNet::kHidden; ++h)
    acc.half[perspective][h] = clamp_i16(acc.half[perspective][h] - column[h]);
#endif
}

void Nnue::refresh_perspective(const Position& pos, NnueAccumulator& acc, Color perspective) const {
  int mirror = 0;
  acc.king_bucket[perspective] = static_cast<uint8_t>(
      net_.kat ? kat_king_bucket(perspective, pos.king_square(perspective), mirror)
               : halfkp_king_bucket(perspective, pos.king_square(perspective)));
  acc.mirror[perspective] = static_cast<uint8_t>(mirror);
  acc.half[perspective] = net_.b0;
  Bitboard occ = pos.occupied();
  while (occ) {
    const Square sq = pop_lsb(occ);
    add_piece_for(acc, perspective, pos.piece_on(sq), sq);
  }
}

void Nnue::add_piece(NnueAccumulator& acc, Piece pc, Square sq) const {
  if (pc == NO_PIECE) return;
  if (net_.per1) {
    ++acc.piece_count;
    const int16_t* col_w = net_.per1_w0.data() + per1_feature(WHITE, pc, sq) * NnueNet::kPer1Hidden;
    const int16_t* col_b = net_.per1_w0.data() + per1_feature(BLACK, pc, sq) * NnueNet::kPer1Hidden;
#if defined(__AVX2__)
    per1_acc_add2(acc.per1[WHITE].data(), acc.per1[BLACK].data(), col_w, col_b);
#else
    for (int h = 0; h < NnueNet::kPer1Hidden; ++h) {
      acc.per1[WHITE][h] = clamp_i16(acc.per1[WHITE][h] + col_w[h]);
      acc.per1[BLACK][h] = clamp_i16(acc.per1[BLACK][h] + col_b[h]);
    }
#endif
    return;
  }
  if (net_.halfkp) {
    add_piece_for(acc, WHITE, pc, sq);
    add_piece_for(acc, BLACK, pc, sq);
    return;
  }
  const auto& col = net_.w0[nnue_feature(pc, sq)];
#if defined(__AVX2__)
  acc_add_avx(acc.v.data(), col.data());
#else
  for (int h = 0; h < NnueNet::kHidden; ++h) acc.v[h] = clamp_i16(acc.v[h] + col[h]);
#endif
}

void Nnue::remove_piece(NnueAccumulator& acc, Piece pc, Square sq) const {
  if (pc == NO_PIECE) return;
  if (net_.per1) {
    if (acc.piece_count) --acc.piece_count;
    const int16_t* col_w = net_.per1_w0.data() + per1_feature(WHITE, pc, sq) * NnueNet::kPer1Hidden;
    const int16_t* col_b = net_.per1_w0.data() + per1_feature(BLACK, pc, sq) * NnueNet::kPer1Hidden;
#if defined(__AVX2__)
    per1_acc_sub2(acc.per1[WHITE].data(), acc.per1[BLACK].data(), col_w, col_b);
#else
    for (int h = 0; h < NnueNet::kPer1Hidden; ++h) {
      acc.per1[WHITE][h] = clamp_i16(acc.per1[WHITE][h] - col_w[h]);
      acc.per1[BLACK][h] = clamp_i16(acc.per1[BLACK][h] - col_b[h]);
    }
#endif
    return;
  }
  if (net_.halfkp) {
    remove_piece_for(acc, WHITE, pc, sq);
    remove_piece_for(acc, BLACK, pc, sq);
    return;
  }
  const auto& col = net_.w0[nnue_feature(pc, sq)];
#if defined(__AVX2__)
  acc_sub_avx(acc.v.data(), col.data());
#else
  for (int h = 0; h < NnueNet::kHidden; ++h) acc.v[h] = clamp_i16(acc.v[h] - col[h]);
#endif
}

void Nnue::update_king_move(NnueAccumulator& acc, const Position& pos, Piece king, Square from,
                            Square to) const {
  const Color us = color_of(king);
  const Color them = ~us;
  int mirror = 0;
  const int bucket =
      net_.kat ? kat_king_bucket(us, to, mirror) : halfkp_king_bucket(us, to);
  remove_piece_for(acc, them, king, from);
  add_piece_for(acc, them, king, to);
  if (bucket == acc.king_bucket[us] && static_cast<uint8_t>(mirror) == acc.mirror[us]) {
    remove_piece_for(acc, us, king, from);
    add_piece_for(acc, us, king, to);
    return;
  }
  refresh_perspective(pos, acc, us);
}

void Nnue::refresh(const Position& pos, NnueAccumulator& acc) const {
  acc.threats_valid = false;
  if (net_.per1) {
    acc.piece_count = 0;
    acc.per1[WHITE] = net_.per1_b0;
    acc.per1[BLACK] = net_.per1_b0;
    Bitboard occ = pos.occupied();
    while (occ) {
      const Square sq = pop_lsb(occ);
      add_piece(acc, pos.piece_on(sq), sq);
    }
    return;
  }
  if (net_.halfkp) {
    for (int perspective = WHITE; perspective <= BLACK; ++perspective) {
      int mirror = 0;
      acc.king_bucket[perspective] = static_cast<uint8_t>(
          net_.kat ? kat_king_bucket(static_cast<Color>(perspective),
                                     pos.king_square(static_cast<Color>(perspective)), mirror)
                   : halfkp_king_bucket(static_cast<Color>(perspective),
                                        pos.king_square(static_cast<Color>(perspective))));
      acc.mirror[perspective] = static_cast<uint8_t>(mirror);
      acc.half[perspective] = net_.b0;
    }
    Bitboard occ = pos.occupied();
    while (occ) {
      const Square sq = pop_lsb(occ);
      add_piece(acc, pos.piece_on(sq), sq);
    }
    return;
  }
  acc.v.fill(0);
  for (int h = 0; h < NnueNet::kHidden; ++h) acc.v[h] = net_.b0[h];
  Bitboard occ = pos.occupied();
  while (occ) {
    const Square sq = pop_lsb(occ);
    add_piece(acc, pos.piece_on(sq), sq);
  }
}

int Nnue::evaluate(const NnueAccumulator& acc, Color stm) const {
  if (net_.per1) {
    const int bucket = per1_output_bucket(acc.piece_count);
    const int qa = net_.per1_qa;
    const int16_t* w = net_.per1_w1[bucket].data();
    const auto& stm_acc = acc.per1[stm];
    const auto& nstm_acc = acc.per1[~stm];
    int64_t sum = 0;
#if defined(__AVX2__)
    if (qa > 0 && qa <= 32767)
      sum = per1_screlu_dual_avx(stm_acc.data(), nstm_acc.data(), w, qa);
    else
#endif
      sum = per1_screlu_dual_scalar(stm_acc.data(), nstm_acc.data(), w, qa);
    // Match bullet: SCReLU is QA^2, first divide restores QA*QB, then add bias
    // (stored at QA*QB) before the final SCALE/(QA*QB).
    sum /= qa;
    sum += net_.per1_b1[bucket];
    return static_cast<int>(sum * net_.per1_scale / (static_cast<int64_t>(qa) * net_.per1_qb));
  }
  if (net_.halfkp) {
    int32_t sum = net_.b1;
#if defined(__AVX2__)
    sum = affine_dual_avx(acc.half[stm].data(), acc.half[~stm].data(), net_.halfkp_w1.data(), net_.b1);
#else
    for (int side = 0; side < 2; ++side) {
      Color perspective = side == 0 ? stm : ~stm;
      const int16_t* weights = net_.halfkp_w1.data() + side * NnueNet::kHidden;
      for (int h = 0; h < NnueNet::kHidden; ++h) {
        int16_t x = acc.half[perspective][h];
        x = std::clamp<int16_t>(x, 0, 127 * NnueNet::kWeightScale);
        sum += static_cast<int32_t>(x) * weights[h];
      }
    }
#endif
    return static_cast<int>(sum / (NnueNet::kWeightScale * NnueNet::kWeightScale));
  }
  int32_t sum = net_.b1;
#if defined(__AVX2__)
  sum = affine_avx(acc.v.data(), net_.w1.data(), net_.b1);
#else
  for (int h = 0; h < NnueNet::kHidden; ++h) {
    int16_t x = acc.v[h];
    if (x < 0) x = 0;
    if (x > 127 * NnueNet::kWeightScale) x = static_cast<int16_t>(127 * NnueNet::kWeightScale);
    sum += static_cast<int32_t>(x) * net_.w1[h];
  }
#endif
  int score = static_cast<int>(sum / (NnueNet::kWeightScale * NnueNet::kWeightScale));
  return (stm == WHITE) ? score : -score;
}

int Nnue::evaluate(const Position& pos) const {
  int score = evaluate(pos.nnue_acc(), pos.side_to_move());
  if (!net_.kat) return score;
  const Color stm = pos.side_to_move();
  auto& acc = const_cast<NnueAccumulator&>(pos.nnue_acc());
  if (!acc.threats_valid || acc.threats_stm != static_cast<uint8_t>(stm)) {
    int threat_values[NnueNet::kThreatDim]{};
    kat_threats(pos, stm, threat_values);
    for (int i = 0; i < NnueNet::kThreatDim; ++i) acc.threats[i] = static_cast<int16_t>(threat_values[i]);
    acc.threats_stm = static_cast<uint8_t>(stm);
    acc.threats_valid = true;
  }
  const int16_t* w = net_.w_threat.data();
  int32_t extra = 0;
  for (int pt = 0; pt < 6; ++pt) {
    extra += acc.threats[pt] * w[pt];
    extra += acc.threats[6 + pt] * w[6 + pt];
  }
  return score + static_cast<int>(extra / NnueNet::kWeightScale);
}

}  // namespace nsce
