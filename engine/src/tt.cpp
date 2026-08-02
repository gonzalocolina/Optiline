#include "nsce/tt.hpp"

#include <algorithm>
#include <cstring>

namespace nsce {

void TranspositionTable::resize(std::size_t mb) {
  std::size_t bytes = mb * 1024ULL * 1024ULL;
  std::size_t entries = std::max<std::size_t>(1, bytes / sizeof(TTEntry));
  // Round down to power of two for masking
  std::size_t n = 1;
  while (n * 2 <= entries) n *= 2;
  table_.assign(n, TTEntry{});
  age_ = 0;
}

void TranspositionTable::clear() {
  std::fill(table_.begin(), table_.end(), TTEntry{});
}

TTEntry* TranspositionTable::probe(Key key, bool& found) const {
  if (table_.empty()) {
    found = false;
    return nullptr;
  }
  auto* entry = const_cast<TTEntry*>(&table_[key & (table_.size() - 1)]);
#if defined(__GNUC__) || defined(__clang__)
  __builtin_prefetch(entry, 0, 3);
#endif
  found = entry->key == key;
  return entry;
}

int TranspositionTable::score_to_tt(int score, int ply) {
  if (score >= VALUE_MATE - 256) return score + ply;
  if (score <= -VALUE_MATE + 256) return score - ply;
  return score;
}

int TranspositionTable::score_from_tt(int score, int ply) {
  if (score >= VALUE_MATE - 256) return score - ply;
  if (score <= -VALUE_MATE + 256) return score + ply;
  return score;
}

void TranspositionTable::store(Key key, int depth, int score, Bound bound, Move move, int eval, int ply) {
  if (table_.empty()) return;
  TTEntry& e = table_[key & (table_.size() - 1)];
  if (e.key != key || depth + 2 >= e.depth || bound == BOUND_EXACT) {
    e.key = key;
    e.score = static_cast<int16_t>(score_to_tt(score, ply));
    e.eval = static_cast<int16_t>(eval);
    e.depth = static_cast<uint8_t>(std::clamp(depth, 0, 255));
    e.bound = static_cast<uint8_t>(bound);
    e.move = move.raw;
    e.age = age_;
  }
}

}  // namespace nsce
