#include "nsce/tt.hpp"

#include <algorithm>

namespace nsce {

void TranspositionTable::resize(std::size_t mb) {
  std::size_t bytes = mb * 1024ULL * 1024ULL;
  std::size_t entries = std::max<std::size_t>(1, bytes / sizeof(Cluster));
  // Round down to power of two for masking
  std::size_t n = 1;
  while (n * 2 <= entries) n *= 2;
  table_ = std::make_unique<Cluster[]>(n);
  size_ = n;
  generation_ = 0;
}

void TranspositionTable::clear() {
  for (std::size_t i = 0; i < size_; ++i) {
    for (Slot& slot : table_[i].slots) {
      slot.payload.store(0, std::memory_order_relaxed);
      slot.verification.store(0, std::memory_order_relaxed);
    }
  }
}

void TranspositionTable::new_search() {
  generation_ = static_cast<uint8_t>((generation_ + 1) & 0x3F);
  if (generation_ == 0) clear();
}

bool TranspositionTable::probe(Key key, TTEntry& entry) const {
  if (size_ == 0) return false;
  const Cluster& cluster = table_[key & (size_ - 1)];
#if defined(__GNUC__) || defined(__clang__)
  __builtin_prefetch(&cluster, 0, 3);
#endif
  for (const Slot& slot : cluster.slots) {
    const uint64_t verification = slot.verification.load(std::memory_order_acquire);
    const uint64_t payload = slot.payload.load(std::memory_order_relaxed);
    if (payload == 0 || (verification ^ payload) != key) continue;

    entry.move = static_cast<uint32_t>(payload);
    entry.score = static_cast<int16_t>(static_cast<uint16_t>(payload >> 32));
    entry.depth = static_cast<uint8_t>(payload >> 48);
    entry.bound = static_cast<uint8_t>((payload >> 56) & 0x3);
    entry.generation = static_cast<uint8_t>((payload >> 58) & 0x3F);
    return true;
  }
  return false;
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

  Cluster& cluster = table_[key & (size_ - 1)];
  Slot* replacement = nullptr;
  int replacement_value = 10000;

  for (Slot& slot : cluster.slots) {
    const uint64_t verification = slot.verification.load(std::memory_order_acquire);
    const uint64_t old_payload = slot.payload.load(std::memory_order_relaxed);
    if (old_payload == 0) {
      replacement = &slot;
      break;
    }

    if ((verification ^ old_payload) == key) {
      int old_depth = static_cast<uint8_t>(old_payload >> 48);
      if (depth + 2 < old_depth && bound != BOUND_EXACT) return;
      replacement = &slot;
      break;
    }

    int old_depth = static_cast<uint8_t>(old_payload >> 48);
    int old_bound = static_cast<uint8_t>((old_payload >> 56) & 0x3);
    int old_generation = static_cast<uint8_t>((old_payload >> 58) & 0x3F);
    int age = (generation_ - old_generation) & 0x3F;
    int value = old_depth + (old_bound == BOUND_EXACT ? 4 : 0) - 4 * age;
    if (value < replacement_value) {
      replacement_value = value;
      replacement = &slot;
    }
  }

  const uint64_t packed_score = static_cast<uint16_t>(score_to_tt(score, ply));
  const uint64_t packed_depth = static_cast<uint8_t>(std::clamp(depth, 0, 255));
  const uint64_t payload = static_cast<uint64_t>(move.raw) | (packed_score << 32) | (packed_depth << 48) |
                           (static_cast<uint64_t>(bound) << 56) |
                           (static_cast<uint64_t>(generation_) << 58);

  replacement->payload.store(payload, std::memory_order_relaxed);
  replacement->verification.store(key ^ payload, std::memory_order_release);
}

}  // namespace nsce
