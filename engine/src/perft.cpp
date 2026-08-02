#include "nsce/perft.hpp"

#include "nsce/movegen.hpp"

#include <iostream>

namespace nsce {

uint64_t perft(Position& pos, int depth) {
  if (depth == 0) return 1;
  MoveList list;
  generate_legal(pos, list);
  if (depth == 1) return static_cast<uint64_t>(list.size);

  uint64_t nodes = 0;
  for (int i = 0; i < list.size; ++i) {
    StateInfo st;
    pos.do_move(list.moves[i], st);
    nodes += perft(pos, depth - 1);
    pos.undo_move(list.moves[i], st);
  }
  return nodes;
}

void perft_divide(Position& pos, int depth) {
  MoveList list;
  generate_legal(pos, list);
  uint64_t total = 0;
  for (int i = 0; i < list.size; ++i) {
    StateInfo st;
    pos.do_move(list.moves[i], st);
    uint64_t n = depth <= 1 ? 1 : perft(pos, depth - 1);
    pos.undo_move(list.moves[i], st);
    std::cout << move_to_uci(list.moves[i]) << ": " << n << '\n';
    total += n;
  }
  std::cout << "Total: " << total << std::endl;
}

}  // namespace nsce
