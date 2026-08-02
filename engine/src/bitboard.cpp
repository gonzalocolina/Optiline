#include "nsce/bitboard.hpp"

#include <array>

#if defined(__BMI2__)
#include <immintrin.h>
#endif

namespace nsce {
namespace {

std::array<Bitboard, SQUARE_NB> KnightAttacks{};
std::array<Bitboard, SQUARE_NB> KingAttacks{};
std::array<std::array<Bitboard, SQUARE_NB>, COLOR_NB> PawnAttacks{};
std::array<std::array<Bitboard, SQUARE_NB>, SQUARE_NB> Between{};
std::array<std::array<Bitboard, SQUARE_NB>, SQUARE_NB> Line{};
std::array<Bitboard, SQUARE_NB> BishopMasks{};
std::array<Bitboard, SQUARE_NB> RookMasks{};
std::array<std::array<Bitboard, 512>, SQUARE_NB> BishopTable{};
std::array<std::array<Bitboard, 4096>, SQUARE_NB> RookTable{};

Bitboard sliding_attacks(Square s, Bitboard occupied, const int deltas[4][2]) {
  Bitboard attacks = 0;
  for (int i = 0; i < 4; ++i) {
    int f = file_of(s) + deltas[i][0];
    int r = rank_of(s) + deltas[i][1];
    while (f >= 0 && f <= 7 && r >= 0 && r <= 7) {
      Square to = make_square(f, r);
      attacks |= square_bb(to);
      if (occupied & square_bb(to)) break;
      f += deltas[i][0];
      r += deltas[i][1];
    }
  }
  return attacks;
}

constexpr int BishopDelta[4][2] = {{1, 1}, {1, -1}, {-1, 1}, {-1, -1}};
constexpr int RookDelta[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};

Bitboard relevant_mask(Square square, const int deltas[4][2]) {
  Bitboard mask = 0;
  for (int direction = 0; direction < 4; ++direction) {
    int file = file_of(square) + deltas[direction][0];
    int rank = rank_of(square) + deltas[direction][1];
    while (file >= 0 && file <= 7 && rank >= 0 && rank <= 7) {
      int next_file = file + deltas[direction][0];
      int next_rank = rank + deltas[direction][1];
      if (next_file < 0 || next_file > 7 || next_rank < 0 || next_rank > 7) break;
      mask |= square_bb(make_square(file, rank));
      file = next_file;
      rank = next_rank;
    }
  }
  return mask;
}

unsigned occupancy_index(Bitboard occupied, Bitboard mask) {
#if defined(__BMI2__)
  return static_cast<unsigned>(_pext_u64(occupied, mask));
#else
  unsigned index = 0;
  unsigned bit = 0;
  while (mask) {
    Bitboard least = mask & (~mask + 1);
    if (occupied & least) index |= 1U << bit;
    mask &= mask - 1;
    ++bit;
  }
  return index;
#endif
}

template <std::size_t Size>
void init_slider_table(Square square, Bitboard mask, const int deltas[4][2],
                       std::array<Bitboard, Size>& table) {
  Bitboard subset = 0;
  do {
    table[occupancy_index(subset, mask)] = sliding_attacks(square, subset, deltas);
    subset = (subset - mask) & mask;
  } while (subset);
}

}  // namespace

void init_bitboards() {
  static bool done = false;
  if (done) return;
  done = true;

  const int knight_d[8][2] = {{1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}};
  const int king_d[8][2] = {{1, 0}, {1, 1}, {0, 1}, {-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, -1}};

  for (int sq = 0; sq < SQUARE_NB; ++sq) {
    Square s = static_cast<Square>(sq);
    int f = file_of(s);
    int r = rank_of(s);

    for (auto& d : knight_d) {
      int nf = f + d[0], nr = r + d[1];
      if (nf >= 0 && nf <= 7 && nr >= 0 && nr <= 7) KnightAttacks[s] |= square_bb(make_square(nf, nr));
    }
    for (auto& d : king_d) {
      int nf = f + d[0], nr = r + d[1];
      if (nf >= 0 && nf <= 7 && nr >= 0 && nr <= 7) KingAttacks[s] |= square_bb(make_square(nf, nr));
    }

    if (f > 0 && r < 7) PawnAttacks[WHITE][s] |= square_bb(make_square(f - 1, r + 1));
    if (f < 7 && r < 7) PawnAttacks[WHITE][s] |= square_bb(make_square(f + 1, r + 1));
    if (f > 0 && r > 0) PawnAttacks[BLACK][s] |= square_bb(make_square(f - 1, r - 1));
    if (f < 7 && r > 0) PawnAttacks[BLACK][s] |= square_bb(make_square(f + 1, r - 1));

    BishopMasks[s] = relevant_mask(s, BishopDelta);
    RookMasks[s] = relevant_mask(s, RookDelta);
    init_slider_table(s, BishopMasks[s], BishopDelta, BishopTable[s]);
    init_slider_table(s, RookMasks[s], RookDelta, RookTable[s]);
  }

  for (int s1 = 0; s1 < SQUARE_NB; ++s1) {
    for (int s2 = 0; s2 < SQUARE_NB; ++s2) {
      if (s1 == s2) continue;
      Square from = static_cast<Square>(s1);
      Square to = static_cast<Square>(s2);
      Bitboard occ = square_bb(from) | square_bb(to);
      if ((bishop_attacks_bb(from, 0) & square_bb(to)) || (rook_attacks_bb(from, 0) & square_bb(to))) {
        Bitboard b = (bishop_attacks_bb(from, 0) & square_bb(to))
                         ? (bishop_attacks_bb(from, occ) & bishop_attacks_bb(to, occ))
                         : (rook_attacks_bb(from, occ) & rook_attacks_bb(to, occ));
        Between[from][to] = b;
        Line[from][to] = (bishop_attacks_bb(from, 0) & square_bb(to))
                             ? (bishop_attacks_bb(from, 0) | square_bb(from)) & (bishop_attacks_bb(to, 0) | square_bb(to))
                             : (rook_attacks_bb(from, 0) | square_bb(from)) & (rook_attacks_bb(to, 0) | square_bb(to));
        Line[from][to] |= square_bb(from) | square_bb(to);
      }
    }
  }
}

Bitboard pawn_attacks_bb(Color c, Square s) { return PawnAttacks[c][s]; }
Bitboard knight_attacks_bb(Square s) { return KnightAttacks[s]; }
Bitboard king_attacks_bb(Square s) { return KingAttacks[s]; }

Bitboard bishop_attacks_bb(Square s, Bitboard occupied) {
  return BishopTable[s][occupancy_index(occupied, BishopMasks[s])];
}

Bitboard rook_attacks_bb(Square s, Bitboard occupied) {
  return RookTable[s][occupancy_index(occupied, RookMasks[s])];
}

Bitboard queen_attacks_bb(Square s, Bitboard occupied) {
  return bishop_attacks_bb(s, occupied) | rook_attacks_bb(s, occupied);
}

Bitboard between_bb(Square s1, Square s2) { return Between[s1][s2]; }
Bitboard line_bb(Square s1, Square s2) { return Line[s1][s2]; }

}  // namespace nsce
