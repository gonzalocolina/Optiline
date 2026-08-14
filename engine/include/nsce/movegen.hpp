#pragma once

#include "nsce/board.hpp"
#include "nsce/types.hpp"

namespace nsce {

struct MoveList {
  Move moves[MAX_MOVES];
  int size = 0;

  void add(Move m) { moves[size++] = m; }
  Move* begin() { return moves; }
  Move* end() { return moves + size; }
  const Move* begin() const { return moves; }
  const Move* end() const { return moves + size; }
};

void generate_legal(const Position& pos, MoveList& list);
void generate_legal_evasions(const Position& pos, MoveList& list);
void generate_legal_noisy(const Position& pos, MoveList& list);
void generate_captures(const Position& pos, MoveList& list);
void generate_noisy(const Position& pos, MoveList& list);
void generate_pseudo_legal(const Position& pos, MoveList& list);

std::string move_to_uci(Move m);
Move parse_uci_move(const Position& pos, const std::string& uci);

}  // namespace nsce
