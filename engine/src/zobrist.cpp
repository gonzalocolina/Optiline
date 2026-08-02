#include "nsce/zobrist.hpp"

#include <random>

namespace nsce {
namespace Zobrist {

Key psq[12][SQUARE_NB];
Key side;
Key castling[16];
Key enpassant[8];

void init() {
  static bool done = false;
  if (done) return;
  done = true;

  std::mt19937_64 rng(0xA5A5A5A5A5A5A5A5ULL);
  for (int pc = 0; pc < 12; ++pc)
    for (int sq = 0; sq < SQUARE_NB; ++sq) psq[pc][sq] = rng();
  side = rng();
  for (int i = 0; i < 16; ++i) castling[i] = rng();
  for (int i = 0; i < 8; ++i) enpassant[i] = rng();
}

}  // namespace Zobrist
}  // namespace nsce
