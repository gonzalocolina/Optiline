#pragma once

#include "nsce/board.hpp"
#include "nsce/types.hpp"

#include <algorithm>

namespace nsce {

void set_use_extras(bool on);
bool use_extras();

int evaluate(const Position& pos);
int evaluate_nnue(const Position& pos);
int classical_extras(const Position& pos);
int applied_extras(const Position& pos);
int simple_eval(const Position& pos);
int piece_value(PieceType pt);
int non_pawn_material(const Position& pos, Color c);

// Static eval must never look like a mate. Search treats |score| >= VALUE_MATE-256
// as a mate distance.
constexpr int kMaxEval = VALUE_MATE - 256 - 1;

// Dual-perspective nets (SCALE=400 WDL) saturate well below material in won
// games. Blend toward material once a queen ahead so minmax pruning still fires.
constexpr int kPer1SimpleSkip = 900;

inline int clamp_eval(int v) { return std::clamp(v, -kMaxEval, kMaxEval); }

}  // namespace nsce
