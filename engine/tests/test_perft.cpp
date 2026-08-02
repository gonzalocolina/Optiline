#include "nsce/board.hpp"
#include "nsce/movegen.hpp"
#include "nsce/perft.hpp"
#include "nsce/zobrist.hpp"
#include "nsce/bitboard.hpp"

#include <gtest/gtest.h>

using namespace nsce;

class EngineTest : public ::testing::Test {
 protected:
  void SetUp() override {
    init_bitboards();
    Zobrist::init();
  }
};

TEST_F(EngineTest, StartPosFenRoundTrip) {
  Position pos;
  pos.set_startpos();
  EXPECT_EQ(pos.fen(), "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
}

TEST_F(EngineTest, StartPosLegalMoveCount) {
  Position pos;
  pos.set_startpos();
  MoveList list;
  generate_legal(pos, list);
  EXPECT_EQ(list.size, 20);
}

TEST_F(EngineTest, PerftStartPos) {
  Position pos;
  pos.set_startpos();
  EXPECT_EQ(perft(pos, 1), 20ULL);
  EXPECT_EQ(perft(pos, 2), 400ULL);
  EXPECT_EQ(perft(pos, 3), 8902ULL);
  EXPECT_EQ(perft(pos, 4), 197281ULL);
  EXPECT_EQ(perft(pos, 5), 4865609ULL);
}

TEST_F(EngineTest, PerftKiwipete) {
  Position pos;
  pos.set_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1");
  EXPECT_EQ(perft(pos, 1), 48ULL);
  EXPECT_EQ(perft(pos, 2), 2039ULL);
  EXPECT_EQ(perft(pos, 3), 97862ULL);
}

TEST_F(EngineTest, PerftPosition3) {
  Position pos;
  pos.set_fen("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1");
  EXPECT_EQ(perft(pos, 1), 14ULL);
  EXPECT_EQ(perft(pos, 2), 191ULL);
  EXPECT_EQ(perft(pos, 3), 2812ULL);
  EXPECT_EQ(perft(pos, 4), 43238ULL);
}

TEST_F(EngineTest, MakeUnmakeRestoresFen) {
  Position pos;
  pos.set_startpos();
  std::string before = pos.fen();
  MoveList list;
  generate_legal(pos, list);
  ASSERT_GT(list.size, 0);
  StateInfo st;
  pos.do_move(list.moves[0], st);
  pos.undo_move(list.moves[0], st);
  EXPECT_EQ(pos.fen(), before);
  Position check;
  check.set_fen(before);
  EXPECT_EQ(pos.key(), check.key());
}

TEST_F(EngineTest, NoisyMovesIncludeQuietPromotions) {
  Position pos;
  pos.set_fen("7k/P7/8/8/8/8/8/7K w - - 0 1");

  MoveList list;
  generate_noisy(pos, list);

  ASSERT_EQ(list.size, 4);
  for (Move move : list) {
    EXPECT_TRUE(move.is_promotion());
    EXPECT_FALSE(move.is_capture());
  }
}

TEST_F(EngineTest, CastlingRequiresTheRook) {
  Position pos;
  pos.set_fen("r3k2r/8/8/8/8/8/8/4K2R w KQkq - 0 1");

  MoveList list;
  generate_legal(pos, list);

  EXPECT_EQ(list.size, 15);
  for (Move move : list) EXPECT_NE(move_to_uci(move), "e1c1");
}
