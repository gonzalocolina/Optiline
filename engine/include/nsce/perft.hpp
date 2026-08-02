#pragma once

#include "nsce/board.hpp"

#include <cstdint>

namespace nsce {

uint64_t perft(Position& pos, int depth);
void perft_divide(Position& pos, int depth);

}  // namespace nsce
