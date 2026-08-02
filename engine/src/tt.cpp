#include "nsce/tt.hpp"

#include <algorithm>

namespace nsce {

void TranspositionTable::resize(std::size_t mb) {
  std::size_t bytes = mb * 1024ULL * 1024ULL;
  std::size_t entries = std::max<std::size_t>(1, bytes / sizeof(Slot));
  // Round down to power of two for masking
  std::size_t n = 1;
  while (n * 2 <= entries) n *= 2;
  table_ = std::make_unique<Slot[]>(n);
  size_ = n;
}

void TranspositionTable::clear() {
  for (std::size_t i = 0; i < size_; ++i) {
    table_[i].payload.store(0, std::memory_order_relaxed);
    table_[i].verification.store(0, std::memory_order_relaxed);
  }
}

bool TranspositionTable::probe(Key key, TTEntry& entry) const {
  if (size_ == 0) return false;
  const Slot& slot = table_[key & (size_ - 1)];
#if defined(__GNUC__) || defined(__clang__)
  __builtin_prefetch(&slot, 0, 3);
#endif
  const uint64_t verification = slot.verification.load(std::memory_order_acquire);
  const uint64_t payload = slot.payload.load(std::memory_order_relaxed);
  if (payload == 0 || (verification ^ payload) != key) return false;

  entry.move = static_cast<uint32_t>(payload);
  entry.score = static_cast<int16_t>(static_cast<uint16_t>(payload >> 32));
  entry.depth = static_cast<uint8_t>(payload >> 48);
  entry.bound = static_cast<uint8_t>((payload >> 56) & 0x3);
  return true;
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

void TranspositionTable::store(Key key, int depth, int score, Bound bound, Move move, int ply) {
  if (size_ == 0) return;

  TTEntry current;
  if (probe(key, current) && depth + 2 < current.depth && bound != BOUND_EXACT) return;

  const uint64_t packed_score = static_cast<uint16_t>(score_to_tt(score, ply));
  const uint64_t packed_depth = static_cast<uint8_t>(std::clamp(depth, 0, 255));
  const uint64_t payload = static_cast<uint64_t>(move.raw) | (packed_score << 32) | (packed_depth << 48) |
                           (static_cast<uint64_t>(bound) << 56);

  Slot& slot = table_[key & (size_ - 1)];
  slot.payload.store(payload, std::memory_order_relaxed);
  slot.verification.store(key ^ payload, std::memory_order_release);
}

}  // namespace nsce
