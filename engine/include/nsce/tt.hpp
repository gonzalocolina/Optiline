#pragma once

#include "nsce/types.hpp"

#include <cstdint>
#include <vector>

namespace nsce {

enum Bound : uint8_t { BOUND_NONE = 0, BOUND_UPPER = 1, BOUND_LOWER = 2, BOUND_EXACT = 3 };

struct TTEntry {
  Key key = 0;
  uint32_t move = 0;
  int16_t score = 0;
  int16_t eval = 0;
  uint8_t depth = 0;
  uint8_t bound = BOUND_NONE;
  uint8_t age = 0;
};

class TranspositionTable {
 public:
  void resize(std::size_t mb);
  void clear();
  void new_search() { ++age_; }

  TTEntry* probe(Key key, bool& found) const;
  void store(Key key, int depth, int score, Bound bound, Move move, int eval, int ply);

  static int score_to_tt(int score, int ply);
  static int score_from_tt(int score, int ply);

 private:
  std::vector<TTEntry> table_;
  uint8_t age_ = 0;
};

}  // namespace nsce
