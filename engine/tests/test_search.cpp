#include "nsce/bitboard.hpp"
#include "nsce/movegen.hpp"
#include "nsce/search.hpp"
#include "nsce/zobrist.hpp"

#include <gtest/gtest.h>

using namespace nsce;

TEST(SearchTest, FindsMateInOneAtQuiescenceBoundary) {
  init_bitboards();
  Zobrist::init();

  Position pos;
  pos.set_fen("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1");

  Search search;
  search.set_position(pos);
  SearchLimits limits;
  limits.depth = 1;
  SearchInfo info = search.go(limits);

  ASSERT_TRUE(info.best_move);
  EXPECT_EQ(info.score, mate_in(1));

  StateInfo state;
  pos.do_move(info.best_move, state);
  MoveList replies;
  generate_legal(pos, replies);
  EXPECT_TRUE(pos.in_check());
  EXPECT_EQ(replies.size, 0);
}
