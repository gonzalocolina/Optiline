#include "nsce/board.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/movegen.hpp"
#include "nsce/zobrist.hpp"

#include <gtest/gtest.h>

#include <stdexcept>
#include <thread>
#include <vector>

using namespace nsce;

TEST(BoardTest, PiecePlacement) {
  init_bitboards();
  Zobrist::init();
  Position pos;
  pos.set_startpos();
  EXPECT_EQ(pos.piece_on(SQ_E1), W_KING);
  EXPECT_EQ(pos.piece_on(SQ_E8), B_KING);
  EXPECT_EQ(pos.piece_on(SQ_A2), W_PAWN);
  EXPECT_EQ(popcount(pos.pieces(WHITE)), 16);
  EXPECT_EQ(popcount(pos.pieces(BLACK)), 16);
}

TEST(BoardTest, SideToMove) {
  init_bitboards();
  Zobrist::init();
  Position pos;
  pos.set_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1");
  EXPECT_EQ(pos.side_to_move(), BLACK);
  EXPECT_EQ(pos.ep_square(), SQ_E3);
}

TEST(BoardTest, DetectsBasicInsufficientMaterial) {
  Position pos;
  pos.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1");
  EXPECT_TRUE(pos.is_draw());

  pos.set_fen("4kb2/8/8/8/8/8/8/2B1K3 w - - 0 1");
  EXPECT_TRUE(pos.is_draw());

  pos.set_fen("2b1k3/8/8/8/8/8/8/2B1K3 w - - 0 1");
  EXPECT_FALSE(pos.is_draw());
}

TEST(BoardTest, DetectsThreefoldWithinReversibleWindow) {
  Position pos;
  pos.set_startpos();
  const char* moves[] = {"g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8"};
  StateInfo states[8];
  for (int i = 0; i < 8; ++i) {
    Move move = parse_uci_move(pos, moves[i]);
    ASSERT_TRUE(move);
    pos.do_move(move, states[i]);
  }
  EXPECT_TRUE(pos.is_draw());
}

TEST(BoardTest, PawnAndNonpawnKeysSurviveUndo) {
  Position pos;
  pos.set_startpos();
  const Key pawn0 = pos.pawn_key();
  const Key nonpawn0 = pos.nonpawn_key();
  Move move = parse_uci_move(pos, "e2e4");
  ASSERT_TRUE(move);
  StateInfo st;
  pos.do_move(move, st);
  EXPECT_NE(pos.pawn_key(), pawn0);
  EXPECT_EQ(pos.nonpawn_key(), nonpawn0);
  pos.undo_move(move, st);
  EXPECT_EQ(pos.pawn_key(), pawn0);
  EXPECT_EQ(pos.nonpawn_key(), nonpawn0);
}

TEST(BoardTest, RejectsMalformedFen) {
  Position pos;
  EXPECT_THROW(pos.set_fen("8/8/8/8/8/8/8 w - - 0 1"), std::runtime_error);
  EXPECT_THROW(pos.set_fen("8/8/8/8/8/8/8/8 x - - 0 1"), std::runtime_error);
  EXPECT_THROW(pos.set_fen("8/8/8/8/8/8/8/8 w - z9 0 1"), std::runtime_error);
}

TEST(BoardTest, ConcurrentInitializationProducesValidPositions) {
  std::vector<std::thread> workers;
  for (int i = 0; i < 8; ++i) {
    workers.emplace_back([] {
      Position pos;
      EXPECT_EQ(pos.fen(), "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    });
  }
  for (auto& worker : workers) worker.join();
}
