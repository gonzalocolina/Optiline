#pragma once

#include "nsce/types.hpp"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>

namespace nsce {

enum Bound : uint8_t { BOUND_NONE = 0, BOUND_UPPER = 1, BOUND_LOWER = 2, BOUND_EXACT = 3 };

struct TTEntry {
  uint32_t move = 0;
  int16_t score = 0;
  uint8_t depth = 0;
  uint8_t bound = BOUND_NONE;
};

class TranspositionTable {
 public:
  void resize(std::size_t mb);
  void clear();
  void new_search() {}

  bool probe(Key key, TTEntry& entry) const;
  void store(Key key, int depth, int score, Bound bound, Move move, int ply);

  static int score_to_tt(int score, int ply);
  static int score_from_tt(int score, int ply);

 private:
  struct Slot {
    std::atomic<uint64_t> verification{0};
    std::atomic<uint64_t> payload{0};
  };

  std::unique_ptr<Slot[]> table_;
  std::size_t size_ = 0;
};

}  // namespace nsce
