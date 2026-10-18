#pragma once

#include "nsce/types.hpp"

#include <array>
#include <bit>

namespace nsce {

constexpr Bitboard FileABB = 0x0101010101010101ULL;
constexpr Bitboard FileHBB = 0x8080808080808080ULL;
constexpr Bitboard Rank1BB = 0x00000000000000FFULL;
constexpr Bitboard Rank8BB = 0xFF00000000000000ULL;
constexpr Bitboard Rank2BB = 0x000000000000FF00ULL;
constexpr Bitboard Rank7BB = 0x00FF000000000000ULL;

constexpr Bitboard FileBB[8] = {
    FileABB, FileABB << 1, FileABB << 2, FileABB << 3,
    FileABB << 4, FileABB << 5, FileABB << 6, FileABB << 7};
constexpr Bitboard RankBB[8] = {
    Rank1BB, Rank1BB << 8, Rank1BB << 16, Rank1BB << 24,
    Rank1BB << 32, Rank1BB << 40, Rank1BB << 48, Rank1BB << 56};

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

namespace bb {
extern std::array<Bitboard, SQUARE_NB> KnightAttacks;
extern std::array<Bitboard, SQUARE_NB> KingAttacks;
extern std::array<std::array<Bitboard, SQUARE_NB>, COLOR_NB> PawnAttacks;
// Plain magic: index = ((occ & mask) * magic) >> shift, with shift = 64 - popcount(mask).
// Same table sizes as a PEXT index (bishop <= 9 bits, rook <= 12). A multiply is used
// instead of PEXT because Zen 1/2 microcode PEXT (~18 cycles) and the multiply is
// also competitive on CPUs where PEXT is single-uop.
struct Magic {
  Bitboard mask = 0;
  Bitboard magic = 0;
  int shift = 0;
};

extern std::array<Magic, SQUARE_NB> BishopMagic;
extern std::array<Magic, SQUARE_NB> RookMagic;
extern std::array<std::array<Bitboard, 512>, SQUARE_NB> BishopTable;
extern std::array<std::array<Bitboard, 4096>, SQUARE_NB> RookTable;
extern std::array<std::array<Bitboard, SQUARE_NB>, SQUARE_NB> Between;
extern std::array<std::array<Bitboard, SQUARE_NB>, SQUARE_NB> Line;
}  // namespace bb

inline unsigned magic_index(const bb::Magic& magic, Bitboard occupied) {
  return static_cast<unsigned>(((occupied & magic.mask) * magic.magic) >> magic.shift);
}

inline Bitboard pawn_attacks_bb(Color c, Square s) { return bb::PawnAttacks[c][s]; }
inline Bitboard knight_attacks_bb(Square s) { return bb::KnightAttacks[s]; }
inline Bitboard king_attacks_bb(Square s) { return bb::KingAttacks[s]; }

inline Bitboard bishop_attacks_bb(Square s, Bitboard occupied) {
  return bb::BishopTable[s][magic_index(bb::BishopMagic[s], occupied)];
}

inline Bitboard rook_attacks_bb(Square s, Bitboard occupied) {
  return bb::RookTable[s][magic_index(bb::RookMagic[s], occupied)];
}

inline Bitboard queen_attacks_bb(Square s, Bitboard occupied) {
  return bishop_attacks_bb(s, occupied) | rook_attacks_bb(s, occupied);
}

inline Bitboard between_bb(Square s1, Square s2) { return bb::Between[s1][s2]; }
inline Bitboard line_bb(Square s1, Square s2) { return bb::Line[s1][s2]; }

}  // namespace nsce
