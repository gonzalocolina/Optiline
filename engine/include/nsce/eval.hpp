#pragma once

#include "nsce/board.hpp"

namespace nsce {

int evaluate(const Position& pos);
int piece_value(PieceType pt);
int non_pawn_material(const Position& pos, Color c);

}  // namespace nsce
