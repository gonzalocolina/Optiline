#pragma once

#include "nsce/types.hpp"

namespace nsce {

namespace Zobrist {
extern Key psq[12][SQUARE_NB];
extern Key side;
extern Key castling[16];
extern Key enpassant[8];

void init();
}  // namespace Zobrist

}  // namespace nsce
