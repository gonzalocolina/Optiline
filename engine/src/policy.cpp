#include "nsce/policy.hpp"

#include "nsce/board.hpp"
#include "nsce/eval.hpp"

#include <algorithm>
#include <cstring>
#include <fstream>

namespace nsce {
namespace {

int16_t clamp_i16(int v) { return static_cast<int16_t>(std::clamp(v, -32768, 32767)); }

}  // namespace

PolicyNet& PolicyNet::instance() {
  static PolicyNet p;
  return p;
}

bool PolicyNet::load_default() {
  // Heuristic prior: prefer central to-squares, developing pieces, captures via caller.
  w_piece_to = {};
  w_from_to = {};
  for (int pc = 0; pc < 12; ++pc) {
    PieceType pt = type_of(static_cast<Piece>(pc));
    for (int to = 0; to < 64; ++to) {
      int f = to & 7, r = to >> 3;
      int center = 3 - std::abs(f - 3) - std::abs((r ^ (pc < 6 ? 0 : 7)) - 3);
      int v = center * 8 + piece_value(pt) / 50;
      w_piece_to[pc][to] = clamp_i16(v);
    }
  }
  for (int from = 0; from < 64; ++from) {
    for (int to = 0; to < 64; ++to) {
      int df = std::abs((from & 7) - (to & 7));
      int dr = std::abs((from >> 3) - (to >> 3));
      // Mild preference for forward / longer developing moves
      int v = (dr + df);
      w_from_to[from][to] = clamp_i16(v);
    }
  }
  loaded_ = true;
  enabled_ = true;
  return true;
}

bool PolicyNet::load(const std::string& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) return false;
  char magic[8]{};
  in.read(magic, 8);
  if (std::strncmp(magic, "NSCEPOLY", 8) != 0) return false;
  for (int pc = 0; pc < 12; ++pc) in.read(reinterpret_cast<char*>(w_piece_to[pc].data()), 64 * 2);
  for (int f = 0; f < 64; ++f) in.read(reinterpret_cast<char*>(w_from_to[f].data()), 64 * 2);
  if (!in) return false;
  loaded_ = true;
  enabled_ = true;
  return true;
}

int PolicyNet::score_move(const Position& pos, Move m) const {
  Piece pc = pos.piece_on(m.from());
  if (pc == NO_PIECE) return 0;
  int s = w_piece_to[pc][m.to()] + w_from_to[m.from()][m.to()];
  if (m.is_promotion()) s += 200 + static_cast<int>(m.promotion()) * 20;
  if (m.is_castle()) s += 50;
  return s;
}

}  // namespace nsce
