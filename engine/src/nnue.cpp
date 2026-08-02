#include "nsce/nnue.hpp"

#include "nsce/board.hpp"
#include "nsce/eval.hpp"

#include <algorithm>
#include <cstring>
#include <fstream>

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

inline int32_t affine_avx(const int16_t* acc, const int16_t* w1, int32_t bias) {
  __m256i sum32 = _mm256_setzero_si256();
  const __m256i zero = _mm256_setzero_si256();
  const int cap = 127 * NnueNet::kWeightScale;
  const __m256i vmax = _mm256_set1_epi16(static_cast<int16_t>(cap));
  for (int h = 0; h < NnueNet::kHidden; h += 16) {
    __m256i x = _mm256_load_si256(reinterpret_cast<const __m256i*>(acc + h));
    x = _mm256_max_epi16(x, zero);
    x = _mm256_min_epi16(x, vmax);
    __m256i w = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(w1 + h));
    __m256i xl = _mm256_cvtepi16_epi32(_mm256_castsi256_si128(x));
    __m256i xh = _mm256_cvtepi16_epi32(_mm256_extracti128_si256(x, 1));
    __m256i wl = _mm256_cvtepi16_epi32(_mm256_castsi256_si128(w));
    __m256i wh = _mm256_cvtepi16_epi32(_mm256_extracti128_si256(w, 1));
    sum32 = _mm256_add_epi32(sum32, _mm256_mullo_epi32(xl, wl));
    sum32 = _mm256_add_epi32(sum32, _mm256_mullo_epi32(xh, wh));
  }
  __m128i lo = _mm256_castsi256_si128(sum32);
  __m128i hi = _mm256_extracti128_si256(sum32, 1);
  __m128i s = _mm_add_epi32(lo, hi);
  __m128i shuf = _mm_shuffle_epi32(s, 0x4E);
  s = _mm_add_epi32(s, shuf);
  shuf = _mm_shuffle_epi32(s, 0xB1);
  s = _mm_add_epi32(s, shuf);
  return bias + _mm_cvtsi128_si32(s);
}
#endif

}  // namespace

int halfkp_king_bucket(Color perspective, Square king) {
  int oriented = perspective == WHITE ? static_cast<int>(king) : (static_cast<int>(king) ^ 56);
  return (rank_of(static_cast<Square>(oriented)) / 2) * 4 + file_of(static_cast<Square>(oriented)) / 2;
}

int halfkp_feature(Color perspective, int king_bucket, Piece pc, Square sq) {
  int oriented_sq = perspective == WHITE ? static_cast<int>(sq) : (static_cast<int>(sq) ^ 56);
  int oriented_pc = static_cast<int>(pc);
  if (perspective == BLACK) oriented_pc = oriented_pc < 6 ? oriented_pc + 6 : oriented_pc - 6;
  return king_bucket * NnueNet::kFeatures + oriented_pc * 64 + oriented_sq;
}

Nnue& Nnue::instance() {
  static Nnue n;
  return n;
}

bool Nnue::load_default_from_hce() {
  net_ = NnueNet{};
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
        net_.w0[pc * 64 + sq][h] = clamp_i16(w);
      }
    }
  }
  for (int h = 0; h < H; ++h) {
    net_.b0[h] = 0;
    net_.w1[h] = clamp_i16(NnueNet::kWeightScale);
  }
  net_.b1 = 0;
  net_.loaded = true;
  enabled_ = true;
  return true;
}

bool Nnue::load(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) return false;
  char magic[8]{};
  in.read(magic, 8);
  const bool halfkp = std::strncmp(magic, "NSCEHFKP", 8) == 0;
  if (!halfkp && std::strncmp(magic, "NSCENNUE", 8) != 0) return false;
  int32_t hidden = 0, features = 0;
  in.read(reinterpret_cast<char*>(&features), 4);
  in.read(reinterpret_cast<char*>(&hidden), 4);
  int expected_features = halfkp ? NnueNet::kHalfKpFeatures : NnueNet::kFeatures;
  if (features != expected_features || hidden != NnueNet::kHidden) return false;
  net_ = NnueNet{};
  net_.halfkp = halfkp;
  if (halfkp) {
    net_.halfkp_w0.resize(NnueNet::kHalfKpFeatures);
    for (int f = 0; f < NnueNet::kHalfKpFeatures; ++f)
      in.read(reinterpret_cast<char*>(net_.halfkp_w0[f].data()), NnueNet::kHidden * 2);
  } else {
    for (int f = 0; f < NnueNet::kFeatures; ++f)
      in.read(reinterpret_cast<char*>(net_.w0[f].data()), NnueNet::kHidden * 2);
  }
  in.read(reinterpret_cast<char*>(net_.b0.data()), NnueNet::kHidden * 2);
  if (halfkp)
    in.read(reinterpret_cast<char*>(net_.halfkp_w1.data()), 2 * NnueNet::kHidden * 2);
  else
    in.read(reinterpret_cast<char*>(net_.w1.data()), NnueNet::kHidden * 2);
  in.read(reinterpret_cast<char*>(&net_.b1), 4);
  if (!in) return false;
  net_.loaded = true;
  enabled_ = true;
  return true;
}

void Nnue::add_piece(NnueAccumulator& acc, Piece pc, Square sq) const {
  if (pc == NO_PIECE) return;
  if (net_.halfkp) {
    for (int perspective = WHITE; perspective <= BLACK; ++perspective) {
      int feature =
          halfkp_feature(static_cast<Color>(perspective), acc.king_bucket[perspective], pc, sq);
      const auto& column = net_.halfkp_w0[feature];
#if defined(__AVX2__)
      acc_add_avx(acc.half[perspective].data(), column.data());
#else
      for (int h = 0; h < NnueNet::kHidden; ++h)
        acc.half[perspective][h] = clamp_i16(acc.half[perspective][h] + column[h]);
#endif
    }
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
  if (net_.halfkp) {
    for (int perspective = WHITE; perspective <= BLACK; ++perspective) {
      int feature =
          halfkp_feature(static_cast<Color>(perspective), acc.king_bucket[perspective], pc, sq);
      const auto& column = net_.halfkp_w0[feature];
#if defined(__AVX2__)
      acc_sub_avx(acc.half[perspective].data(), column.data());
#else
      for (int h = 0; h < NnueNet::kHidden; ++h)
        acc.half[perspective][h] = clamp_i16(acc.half[perspective][h] - column[h]);
#endif
    }
    return;
  }
  const auto& col = net_.w0[nnue_feature(pc, sq)];
#if defined(__AVX2__)
  acc_sub_avx(acc.v.data(), col.data());
#else
  for (int h = 0; h < NnueNet::kHidden; ++h) acc.v[h] = clamp_i16(acc.v[h] - col[h]);
#endif
}

void Nnue::refresh(const Position& pos, NnueAccumulator& acc) const {
  if (net_.halfkp) {
    for (int perspective = WHITE; perspective <= BLACK; ++perspective) {
      acc.king_bucket[perspective] =
          static_cast<uint8_t>(halfkp_king_bucket(static_cast<Color>(perspective),
                                                  pos.king_square(static_cast<Color>(perspective))));
      acc.half[perspective] = net_.b0;
    }
    for (int sq = 0; sq < SQUARE_NB; ++sq) {
      Piece pc = pos.piece_on(static_cast<Square>(sq));
      if (pc != NO_PIECE) add_piece(acc, pc, static_cast<Square>(sq));
    }
    return;
  }
  acc.v.fill(0);
  for (int h = 0; h < NnueNet::kHidden; ++h) acc.v[h] = net_.b0[h];
  for (int sq = 0; sq < SQUARE_NB; ++sq) {
    Piece pc = pos.piece_on(static_cast<Square>(sq));
    if (pc != NO_PIECE) add_piece(acc, pc, static_cast<Square>(sq));
  }
}

int Nnue::evaluate(const NnueAccumulator& acc, Color stm) const {
  if (net_.halfkp) {
    int32_t sum = net_.b1;
#if defined(__AVX2__)
    sum = affine_avx(acc.half[stm].data(), net_.halfkp_w1.data(), net_.b1);
    sum += affine_avx(acc.half[~stm].data(), net_.halfkp_w1.data() + NnueNet::kHidden, 0);
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

}  // namespace nsce
