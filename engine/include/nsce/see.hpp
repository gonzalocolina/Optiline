#pragma once

#include "nsce/board.hpp"
#include "nsce/types.hpp"

namespace nsce {

// Static exchange evaluation in centipawns from the side-to-move perspective.
int static_exchange_eval(const Position& pos, Move move);
inline bool see_ge(const Position& pos, Move move, int threshold) {
  return static_exchange_eval(pos, move) >= threshold;
}

}  // namespace nsce
