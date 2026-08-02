#include "nsce/board.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/zobrist.hpp"

#include <gtest/gtest.h>

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
