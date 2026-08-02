#pragma once

#include "nsce/types.hpp"

#include <bit>

namespace nsce {

constexpr Bitboard FileABB = 0x0101010101010101ULL;
constexpr Bitboard FileHBB = 0x8080808080808080ULL;
constexpr Bitboard Rank1BB = 0x00000000000000FFULL;
constexpr Bitboard Rank8BB = 0xFF00000000000000ULL;
constexpr Bitboard Rank2BB = 0x000000000000FF00ULL;
constexpr Bitboard Rank7BB = 0x00FF000000000000ULL;

inline Bitboard square_bb(Square s) { return 1ULL << static_cast<int>(s); }

inline int popcount(Bitboard b) { return std::popcount(b); }

inline Square lsb(Bitboard b) { return static_cast<Square>(std::countr_zero(b)); }

inline Square pop_lsb(Bitboard& b) {
  Square s = lsb(b);
  b &= b - 1;
  return s;
}

inline Bitboard shift_north(Bitboard b) { return b << 8; }
inline Bitboard shift_south(Bitboard b) { return b >> 8; }
inline Bitboard shift_east(Bitboard b) { return (b & ~FileHBB) << 1; }
inline Bitboard shift_west(Bitboard b) { return (b & ~FileABB) >> 1; }
inline Bitboard shift_ne(Bitboard b) { return (b & ~FileHBB) << 9; }
inline Bitboard shift_nw(Bitboard b) { return (b & ~FileABB) << 7; }
inline Bitboard shift_se(Bitboard b) { return (b & ~FileHBB) >> 7; }
inline Bitboard shift_sw(Bitboard b) { return (b & ~FileABB) >> 9; }

void init_bitboards();

Bitboard pawn_attacks_bb(Color c, Square s);
Bitboard knight_attacks_bb(Square s);
Bitboard king_attacks_bb(Square s);
Bitboard bishop_attacks_bb(Square s, Bitboard occupied);
Bitboard rook_attacks_bb(Square s, Bitboard occupied);
Bitboard queen_attacks_bb(Square s, Bitboard occupied);

Bitboard between_bb(Square s1, Square s2);
Bitboard line_bb(Square s1, Square s2);

}  // namespace nsce
