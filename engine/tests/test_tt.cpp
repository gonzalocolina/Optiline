#include "nsce/tt.hpp"

#include <gtest/gtest.h>

using namespace nsce;

TEST(TranspositionTableTest, StoresAndProbesEntry) {
  TranspositionTable table;
  table.resize(1);
  const Key key = 0x123456789abcdef0ULL;
  const Move move = Move::make(SQ_E2, SQ_E4, NO_PIECE_TYPE, MF_DOUBLE);

  table.store(key, 8, 123, BOUND_EXACT, move, 0);

  TTEntry entry;
  ASSERT_TRUE(table.probe(key, entry));
  EXPECT_EQ(entry.move, move.raw);
  EXPECT_EQ(entry.score, 123);
  EXPECT_EQ(entry.depth, 8);
  EXPECT_EQ(entry.bound, BOUND_EXACT);
  EXPECT_FALSE(table.probe(key ^ 1, entry));
}

TEST(TranspositionTableTest, PreservesDeeperNonExactEntry) {
  TranspositionTable table;
  table.resize(1);
  const Key key = 0xfedcba9876543210ULL;
  const Move deep_move = Move::make(SQ_G1, SQ_F3);
  const Move shallow_move = Move::make(SQ_B1, SQ_C3);

  table.store(key, 10, 50, BOUND_LOWER, deep_move, 0);
  table.store(key, 3, 75, BOUND_UPPER, shallow_move, 0);

  TTEntry entry;
  ASSERT_TRUE(table.probe(key, entry));
  EXPECT_EQ(entry.move, deep_move.raw);
  EXPECT_EQ(entry.depth, 10);
  EXPECT_EQ(entry.score, 50);
}

TEST(TranspositionTableTest, NormalizesMateDistance) {
  TranspositionTable table;
  table.resize(1);
  const Key key = 42;
  constexpr int ply = 7;
  constexpr int score = VALUE_MATE - 12;

  table.store(key, 4, score, BOUND_EXACT, Move::make(SQ_A2, SQ_A3), ply);

  TTEntry entry;
  ASSERT_TRUE(table.probe(key, entry));
  EXPECT_EQ(TranspositionTable::score_from_tt(entry.score, ply), score);
}

TEST(TranspositionTableTest, KeepsFourCollidingEntriesInCluster) {
  TranspositionTable table;
  table.resize(1);
  constexpr Key stride = 1ULL << 20;
  constexpr Key base = 0x1234;

  for (int i = 0; i < 4; ++i) {
    table.store(base + stride * i, 6 + i, 10 * i, BOUND_LOWER,
                Move::make(SQ_A2, static_cast<Square>(SQ_A3 + i)), 0);
  }

  TTEntry entry;
  for (int i = 0; i < 4; ++i) {
    ASSERT_TRUE(table.probe(base + stride * i, entry));
    EXPECT_EQ(entry.depth, 6 + i);
    EXPECT_EQ(entry.score, 10 * i);
  }
}

TEST(TranspositionTableTest, PreservesFullMoveEncoding) {
  TranspositionTable table;
  table.resize(1);
  Move max_encoded{Move::kEncodingMask};
  constexpr Key key = 0xDEADBEEF;

  table.store(key, 12, -321, BOUND_EXACT, max_encoded, 0);

  TTEntry entry;
  ASSERT_TRUE(table.probe(key, entry));
  EXPECT_EQ(entry.move, max_encoded.raw);
}

TEST(TranspositionTableTest, GenerationWrapDoesNotClearTable) {
  TranspositionTable table;
  table.resize(1);
  constexpr Key key = 0xABCDEF;
  table.store(key, 20, 42, BOUND_EXACT, Move::make(SQ_E2, SQ_E4), 0);

  for (int i = 0; i < 64; ++i) table.new_search();

  TTEntry entry;
  ASSERT_TRUE(table.probe(key, entry));
  EXPECT_EQ(entry.score, 42);
}

TEST(TranspositionTableTest, StoresAndProbesStaticEval) {
  TranspositionTable table;
  table.resize(1);
  const Key key = 0x1111;
  table.store(key, 6, 40, BOUND_EXACT, Move::make(SQ_E2, SQ_E4), 0, 96);

  TTEntry entry;
  ASSERT_TRUE(table.probe(key, entry));
  EXPECT_TRUE(entry.eval_valid);
  EXPECT_EQ(entry.eval, 96);

  table.store(key, 7, 55, BOUND_LOWER, Move::make(SQ_D2, SQ_D4), 0, VALUE_NONE);
  ASSERT_TRUE(table.probe(key, entry));
  EXPECT_TRUE(entry.eval_valid);
  EXPECT_EQ(entry.eval, 96);
}
