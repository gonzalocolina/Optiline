#include "nsce/bitboard.hpp"

#include <array>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <mutex>

namespace nsce {

namespace bb {
std::array<Bitboard, SQUARE_NB> KnightAttacks{};
std::array<Bitboard, SQUARE_NB> KingAttacks{};
std::array<std::array<Bitboard, SQUARE_NB>, COLOR_NB> PawnAttacks{};
std::array<std::array<Bitboard, SQUARE_NB>, SQUARE_NB> Between{};
std::array<std::array<Bitboard, SQUARE_NB>, SQUARE_NB> Line{};
std::array<Magic, SQUARE_NB> BishopMagic{};
std::array<Magic, SQUARE_NB> RookMagic{};
std::array<std::array<Bitboard, 512>, SQUARE_NB> BishopTable{};
std::array<std::array<Bitboard, 4096>, SQUARE_NB> RookTable{};
}  // namespace bb

namespace {

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

// Plain magics for shift = 64 - popcount(mask). Fixed so startup does not search.
constexpr Bitboard kBishopMagics[SQUARE_NB] = {
    0x10019001020060ULL, 0x6050300a0448c6c8ULL, 0x64501906c1181474ULL, 0x23442d0600116010ULL,
    0x1002061010080050ULL, 0x2041040640e83000ULL, 0x1006048420280a02ULL, 0x2262410403214040ULL,
    0x1000042002440900ULL, 0x445a012020e01a0ULL,  0x858590641482606aULL, 0xb040402901010ULL,
    0x12040420300000ULL,  0x370201e2837f0550ULL, 0x40aa20824443434ULL,  0x7998010b04900410ULL,
    0x2040006082040300ULL, 0x920c0006300c0908ULL, 0xc14808404682a080ULL, 0x803880802004000ULL,
    0x28130108200805caULL, 0xe002038308030408ULL, 0x72d2249780942040ULL, 0x20410c6460800ULL,
    0x9104024160c0440ULL,  0x2a0f384190d04300ULL, 0x4000900102092200ULL, 0x2006002008008020ULL,
    0x10030008200800ULL,   0x8148420105411000ULL, 0x5581020c042208ULL,   0x289006e104a00ULL,
    0x810d2002404800ULL,  0x1810aa082a200820ULL, 0x800a42800300288ULL,  0x1020020080080080ULL,
    0x4810104000e0020ULL,  0x8010500082044040ULL, 0x4008480100094110ULL, 0xa008020040012500ULL,
    0x8212050420064222ULL, 0xa000809088201060ULL, 0x2020026018400ULL,    0x101904a051000800ULL,
    0x800081009200400ULL,  0x24034859000200ULL,   0x4038c10802000080ULL, 0x20d8220082094322ULL,
    0xa02080e035000e8ULL,  0x264f048a101ad6a4ULL, 0xa8020a4404240000ULL, 0x100184620d0c0402ULL,
    0x2017440428a0858ULL,  0x805004218c030018ULL, 0x5040100408848000ULL, 0xa950510809828000ULL,
    0xcc22004608900888ULL, 0x1000100c8440484ULL,  0x200424020820ULL,     0x220040100940400ULL,
    0x2048a008700a0200ULL, 0xc0982b820180220ULL,  0x8950c8a001540104ULL, 0x1850048488104102ULL,
};

constexpr Bitboard kRookMagics[SQUARE_NB] = {
    0xa80008060144008ULL,  0x8400120001008c0ULL,  0x8100085040200302ULL, 0x2080040800801000ULL,
    0xa00042051281200ULL,  0x4080018002006400ULL, 0x2c00080090450604ULL, 0x680008000402100ULL,
    0xf408000400185b0ULL,  0x2402010004000ULL,    0x301002000110048ULL,   0x1081002030005900ULL,
    0x8001804400080080ULL, 0x808808004000200ULL,  0x1001100840200ULL,     0x2009000100084282ULL,
    0x20008080004000ULL,   0x4143404010012000ULL, 0x403010041102000ULL,   0x8080210058100100ULL,
    0x6004818004021800ULL, 0x1204808002000400ULL, 0x42734c008a011048ULL, 0x4029020000990844ULL,
    0x60c00080012080ULL,   0x240660200418100ULL,  0x600300104100ULL,      0x2004200200810ULL,
    0x590e801002210040ULL, 0x182002680040080ULL,  0x1030880c00018210ULL, 0x5950808a001b1444ULL,
    0x201400029800180ULL,  0x8020100120400640ULL, 0x202804a001020ULL,     0xa0210209001000ULL,
    0x101809800800400ULL,  0x4840080804200ULL,    0x8400102a04005108ULL,  0x32c04082001124ULL,
    0xc219400324808000ULL, 0x1000c020004008ULL,   0x20011001828020ULL,    0x10000800108080ULL,
    0x3000240008008080ULL, 0x60108a0004008080ULL, 0x408128100c0002ULL,    0x8728504095060024ULL,
    0x1038824022150200ULL, 0x2294528201012200ULL, 0x481005442200100ULL,   0x20092100100100ULL,
    0x1800180004008080ULL, 0x91000208040100ULL,   0x1800100020080ULL,     0x2442081004600ULL,
    0x42008410c0610202ULL, 0x2022c48062120502ULL, 0x308a40318a008022ULL,  0x20e1400b201a00b2ULL,
    0x20a001410204842ULL,  0x112600148d181002ULL, 0x11a08231081014ULL,    0x1b05494030032b2ULL,
};

template <std::size_t Size>
void init_magic(Square square, const int deltas[4][2], Bitboard magic_number, bb::Magic& magic,
                std::array<Bitboard, Size>& table) {
  const Bitboard mask = relevant_mask(square, deltas);
  const int shift = 64 - popcount(mask);
  magic.mask = mask;
  magic.magic = magic_number;
  magic.shift = shift;

  uint8_t seen[Size]{};
  Bitboard used[Size]{};
  Bitboard subset = 0;
  do {
    const unsigned index = static_cast<unsigned>((subset * magic_number) >> shift);
    if (index >= Size) {
      std::cerr << "nsce: slider magic index out of range on square " << static_cast<int>(square) << '\n';
      std::exit(1);
    }
    const Bitboard attack = sliding_attacks(square, subset, deltas);
    if (seen[index]) {
      if (used[index] != attack) {
        std::cerr << "nsce: slider magic collision on square " << static_cast<int>(square) << '\n';
        std::exit(1);
      }
    } else {
      seen[index] = 1;
      used[index] = attack;
      table[index] = attack;
    }
    subset = (subset - mask) & mask;
  } while (subset);
}

}  // namespace

void init_bitboards() {
  static std::once_flag once;
  std::call_once(once, [] {

  const int knight_d[8][2] = {{1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}};
  const int king_d[8][2] = {{1, 0}, {1, 1}, {0, 1}, {-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, -1}};

  for (int sq = 0; sq < SQUARE_NB; ++sq) {
    Square s = static_cast<Square>(sq);
    int f = file_of(s);
    int r = rank_of(s);

    for (auto& d : knight_d) {
      int nf = f + d[0], nr = r + d[1];
      if (nf >= 0 && nf <= 7 && nr >= 0 && nr <= 7) bb::KnightAttacks[s] |= square_bb(make_square(nf, nr));
    }
    for (auto& d : king_d) {
      int nf = f + d[0], nr = r + d[1];
      if (nf >= 0 && nf <= 7 && nr >= 0 && nr <= 7) bb::KingAttacks[s] |= square_bb(make_square(nf, nr));
    }

    if (f > 0 && r < 7) bb::PawnAttacks[WHITE][s] |= square_bb(make_square(f - 1, r + 1));
    if (f < 7 && r < 7) bb::PawnAttacks[WHITE][s] |= square_bb(make_square(f + 1, r + 1));
    if (f > 0 && r > 0) bb::PawnAttacks[BLACK][s] |= square_bb(make_square(f - 1, r - 1));
    if (f < 7 && r > 0) bb::PawnAttacks[BLACK][s] |= square_bb(make_square(f + 1, r - 1));

    init_magic(s, BishopDelta, kBishopMagics[s], bb::BishopMagic[s], bb::BishopTable[s]);
    init_magic(s, RookDelta, kRookMagics[s], bb::RookMagic[s], bb::RookTable[s]);
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
        bb::Between[from][to] = b;
        bb::Line[from][to] = (bishop_attacks_bb(from, 0) & square_bb(to))
                             ? (bishop_attacks_bb(from, 0) | square_bb(from)) & (bishop_attacks_bb(to, 0) | square_bb(to))
                             : (rook_attacks_bb(from, 0) | square_bb(from)) & (rook_attacks_bb(to, 0) | square_bb(to));
        bb::Line[from][to] |= square_bb(from) | square_bb(to);
      }
    }
  }
  });
}

}  // namespace nsce
