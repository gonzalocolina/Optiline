#include "nsce/tt.hpp"

#include <algorithm>

namespace nsce {
namespace {

constexpr int kEvalSentinel = -128;

int pack_eval(int eval) {
  if (eval == VALUE_NONE || eval <= -VALUE_MATE + 256 || eval >= VALUE_MATE - 256) return kEvalSentinel;
  return std::clamp(eval / 16, -127, 127);
}

int unpack_eval(int packed) {
  if (packed == kEvalSentinel) return VALUE_NONE;
  return packed * 16;
}

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
  ++generation_;
}

int TranspositionTable::hashfull() const {
  if (size_ == 0) return 0;
  const std::size_t clusters = std::min<std::size_t>(size_, 1000);
  std::size_t used = 0;
  for (std::size_t i = 0; i < clusters; ++i)
    for (const Slot& slot : table_[i].slots)
      if (slot.payload.load(std::memory_order_relaxed) != 0) ++used;
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
    if (payload == 0) continue;
    const uint64_t verification = slot.verification.load(std::memory_order_acquire);
    if ((verification ^ payload) != key) continue;

    entry.move = static_cast<uint32_t>(payload) & Move::kEncodingMask;
    entry.score = static_cast<int16_t>(static_cast<uint16_t>(payload >> 24));
    entry.depth = static_cast<uint8_t>(payload >> 40);
    entry.bound = static_cast<uint8_t>((payload >> 48) & 0x3);
    entry.generation = static_cast<uint8_t>((payload >> 50) & 63);
    const int packed = static_cast<int>(static_cast<int8_t>(payload >> 56));
    entry.eval = static_cast<int16_t>(unpack_eval(packed));
    entry.eval_valid = packed != kEvalSentinel;
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

void TranspositionTable::store(Key key, int depth, int score, Bound bound, Move move, int ply, int eval) {
  if (size_ == 0) return;

  Cluster& cluster = table_[key & (size_ - 1)];
  Slot* replacement = nullptr;
  int replacement_value = 10000;
  int preserved_eval = pack_eval(eval);

  for (Slot& slot : cluster.slots) {
    const uint64_t verification = slot.verification.load(std::memory_order_acquire);
    const uint64_t old_payload = slot.payload.load(std::memory_order_relaxed);
    if (old_payload == 0) {
      replacement = &slot;
      break;
    }

    if ((verification ^ old_payload) == key) {
      int old_depth = static_cast<uint8_t>(old_payload >> 40);
      if (depth + 2 < old_depth && bound != BOUND_EXACT) return;
      if (preserved_eval == kEvalSentinel) preserved_eval = static_cast<int>(static_cast<int8_t>(old_payload >> 56));
      replacement = &slot;
      break;
    }

    int old_depth = static_cast<uint8_t>(old_payload >> 40);
    int old_bound = static_cast<uint8_t>((old_payload >> 48) & 0x3);
    int old_generation = static_cast<uint8_t>((old_payload >> 50) & 63);
    int age = (static_cast<int>(generation_ & 63) - old_generation) & 63;
    int value = old_depth + (old_bound == BOUND_EXACT ? 4 : 0) - 4 * age;
    if (value < replacement_value) {
      replacement_value = value;
      replacement = &slot;
    }
  }

  const uint64_t packed_score = static_cast<uint16_t>(score_to_tt(score, ply));
  const uint64_t packed_depth = static_cast<uint8_t>(std::clamp(depth, 0, 255));
  const uint64_t packed_eval = static_cast<uint8_t>(preserved_eval);
  const uint64_t payload = (static_cast<uint64_t>(move.raw & Move::kEncodingMask)) | (packed_score << 24) |
                           (packed_depth << 40) | (static_cast<uint64_t>(bound) << 48) |
                           (static_cast<uint64_t>(generation_ & 63) << 50) | (packed_eval << 56);

  replacement->payload.store(payload, std::memory_order_relaxed);
  replacement->verification.store(key ^ payload, std::memory_order_release);
}

}  // namespace nsce
