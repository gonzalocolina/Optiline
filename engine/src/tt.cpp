#include "nsce/tt.hpp"

#include <algorithm>

namespace nsce {
namespace {

// payload: move 24 | score 16 | depth 8 | bound 2 | generation 6 | pv 1 | used 1
// aux:     key[17..63] | eval_valid 1 | eval 16; verification = aux ^ payload
constexpr uint64_t kUsedBit = 1ULL << 57;
constexpr uint64_t kPvBit = 1ULL << 56;
constexpr uint64_t kKeyMask = ~0x1FFFFULL;
constexpr uint64_t kEvalValidBit = 1ULL << 16;

bool eval_storable(int eval) {
  return eval != VALUE_NONE && eval > -VALUE_MATE + 256 && eval < VALUE_MATE - 256;
}

int payload_depth(uint64_t payload) { return static_cast<uint8_t>(payload >> 40); }
int payload_generation(uint64_t payload) { return static_cast<int>((payload >> 50) & 63); }

}  // namespace

static_assert(Move::kEncodingBits <= 24, "TT payload reserves exactly 24 bits for Move");

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
  generation_ = static_cast<uint8_t>((generation_ + 1) & 63);
}

int TranspositionTable::hashfull() const {
  if (size_ == 0) return 0;
  const std::size_t clusters = std::min<std::size_t>(size_, 1000);
  std::size_t used = 0;
  for (std::size_t i = 0; i < clusters; ++i) {
    for (const Slot& slot : table_[i].slots) {
      const uint64_t payload = slot.payload.load(std::memory_order_relaxed);
      if ((payload & kUsedBit) && payload_generation(payload) == generation_) ++used;
    }
  }
  if (used == 0) return 0;
  return std::max(1, static_cast<int>((used * 1000) / (clusters * 4)));
}

void TranspositionTable::prefetch(Key key) const {
  if (size_ == 0) return;
#if defined(__GNUC__) || defined(__clang__)
  __builtin_prefetch(&table_[key & (size_ - 1)], 0, 3);
#else
  (void)key;
#endif
}

bool TranspositionTable::probe(Key key, TTEntry& entry) const {
  if (size_ == 0) return false;
  const Cluster& cluster = table_[key & (size_ - 1)];
#if defined(__GNUC__) || defined(__clang__)
  __builtin_prefetch(&cluster, 0, 3);
#endif
  for (const Slot& slot : cluster.slots) {
    const uint64_t payload = slot.payload.load(std::memory_order_relaxed);
    if (!(payload & kUsedBit)) continue;
    const uint64_t aux = slot.verification.load(std::memory_order_acquire) ^ payload;
    if ((aux & kKeyMask) != (key & kKeyMask)) continue;

    entry.move = static_cast<uint32_t>(payload) & Move::kEncodingMask;
    entry.score = static_cast<int16_t>(static_cast<uint16_t>(payload >> 24));
    entry.depth = static_cast<uint8_t>(payload_depth(payload));
    entry.bound = static_cast<uint8_t>((payload >> 48) & 0x3);
    entry.generation = static_cast<uint8_t>(payload_generation(payload));
    entry.is_pv = (payload & kPvBit) != 0;
    entry.eval_valid = (aux & kEvalValidBit) != 0;
    entry.eval = entry.eval_valid ? static_cast<int16_t>(static_cast<uint16_t>(aux)) : static_cast<int16_t>(VALUE_NONE);
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

void TranspositionTable::store(Key key, int depth, int score, Bound bound, Move move, int ply, int eval,
                               bool is_pv) {
  if (size_ == 0) return;

  Cluster& cluster = table_[key & (size_ - 1)];
  const int clamped_depth = std::clamp(depth, 0, 255);
  uint64_t packed_move = move.raw & Move::kEncodingMask;
  uint64_t eval_bits = eval_storable(eval) ? (static_cast<uint16_t>(eval) | kEvalValidBit) : 0;

  Slot* match = nullptr;
  Slot* empty = nullptr;
  Slot* worst = nullptr;
  int worst_value = 0;
  for (Slot& slot : cluster.slots) {
    const uint64_t old_payload = slot.payload.load(std::memory_order_relaxed);
    if (!(old_payload & kUsedBit)) {
      if (!empty) empty = &slot;
      continue;
    }
    const uint64_t old_aux = slot.verification.load(std::memory_order_acquire) ^ old_payload;
    const int old_depth = payload_depth(old_payload);
    const int old_generation = payload_generation(old_payload);
    if ((old_aux & kKeyMask) == (key & kKeyMask)) {
      if (bound != BOUND_EXACT && old_generation == generation_ &&
          clamped_depth + 4 + 2 * static_cast<int>(is_pv) <= old_depth)
        return;
      if (!packed_move) packed_move = old_payload & Move::kEncodingMask;
      if (!eval_bits) eval_bits = old_aux & (kEvalValidBit | 0xFFFFULL);
      match = &slot;
      break;
    }
    const int age = (generation_ - old_generation) & 63;
    const int value = old_depth - 8 * age;
    if (!worst || value < worst_value) {
      worst_value = value;
      worst = &slot;
    }
  }

  Slot* target = match ? match : (empty ? empty : worst);
  const uint64_t packed_score = static_cast<uint16_t>(score_to_tt(score, ply));
  const uint64_t payload = packed_move | (packed_score << 24) | (static_cast<uint64_t>(clamped_depth) << 40) |
                           (static_cast<uint64_t>(bound & 0x3) << 48) | (static_cast<uint64_t>(generation_ & 63) << 50) |
                           (is_pv ? kPvBit : 0) | kUsedBit;
  const uint64_t aux = (key & kKeyMask) | eval_bits;

  target->payload.store(payload, std::memory_order_relaxed);
  target->verification.store(aux ^ payload, std::memory_order_release);
}

}  // namespace nsce
