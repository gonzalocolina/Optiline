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

TEST_F(EngineTest, PerftPosition4PinsAndPromotions) {
  Position pos;
  pos.set_fen("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1");
  EXPECT_EQ(perft(pos, 1), 6ULL);
  EXPECT_EQ(perft(pos, 2), 264ULL);
  EXPECT_EQ(perft(pos, 3), 9467ULL);
  EXPECT_EQ(perft(pos, 4), 422333ULL);
}

TEST_F(EngineTest, PerftPosition5ChecksAndCastling) {
  Position pos;
  pos.set_fen("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8");
  EXPECT_EQ(perft(pos, 1), 44ULL);
  EXPECT_EQ(perft(pos, 2), 1486ULL);
  EXPECT_EQ(perft(pos, 3), 62379ULL);
  EXPECT_EQ(perft(pos, 4), 2103487ULL);
}

TEST_F(EngineTest, PerftPosition6TacticalPins) {
  Position pos;
  pos.set_fen("r4rk1/1pp1qppp/p1np1n2/8/2B1P3/2N2Q1p/PPP2PPP/R1B2RK1 w - - 0 10");
  EXPECT_EQ(perft(pos, 1), 42ULL);
  EXPECT_EQ(perft(pos, 2), 1549ULL);
  EXPECT_EQ(perft(pos, 3), 66500ULL);
  EXPECT_EQ(perft(pos, 4), 2396676ULL);
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

TEST_F(EngineTest, LegalNoisyIsSubsetOfLegal) {
  Position pos;
  pos.set_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1");
  MoveList legal;
  MoveList noisy;
  generate_legal(pos, legal);
  generate_legal_noisy(pos, noisy);
  ASSERT_GT(noisy.size, 0);
  ASSERT_LE(noisy.size, legal.size);
  for (int i = 0; i < noisy.size; ++i) {
    bool found = false;
    for (int j = 0; j < legal.size; ++j) {
      if (legal.moves[j] == noisy.moves[i]) found = true;
    }
    EXPECT_TRUE(found);
    EXPECT_TRUE(noisy.moves[i].is_capture() || noisy.moves[i].is_ep() || noisy.moves[i].is_promotion());
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

TEST_F(EngineTest, EnPassantCannotExposeHorizontalRookCheck) {
  Position pos;
  pos.set_fen("8/8/8/r4pPK/8/8/8/7k w - f6 0 1");

  MoveList list;
  generate_legal(pos, list);

  EXPECT_EQ(list.size, 4);
  for (Move move : list) EXPECT_NE(move_to_uci(move), "g5f6");
}
