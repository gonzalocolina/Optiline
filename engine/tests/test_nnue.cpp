#include "nsce/board.hpp"
#include "nsce/nnue.hpp"
#include "nsce/movegen.hpp"
#include "nsce/zobrist.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/eval.hpp"

#include <gtest/gtest.h>

using namespace nsce;

TEST(NnueTest, IncrementalMatchesRefresh) {
  init_bitboards();
  Zobrist::init();
  ASSERT_TRUE(Nnue::instance().load_default_from_hce());

  Position pos;
  pos.set_startpos();
  NnueAccumulator refreshed;
  Nnue::instance().refresh(pos, refreshed);
  for (int h = 0; h < NnueNet::kHidden; ++h) {
    EXPECT_EQ(pos.nnue_acc().v[h], refreshed.v[h]) << "h=" << h;
  }

  MoveList list;
  generate_legal(pos, list);
  ASSERT_GT(list.size, 0);
  StateInfo st;
  pos.do_move(list.moves[0], st);
  Nnue::instance().refresh(pos, refreshed);
  for (int h = 0; h < NnueNet::kHidden; ++h) {
    EXPECT_EQ(pos.nnue_acc().v[h], refreshed.v[h]) << "after move h=" << h;
  }
  pos.undo_move(list.moves[0], st);
  Nnue::instance().refresh(pos, refreshed);
  for (int h = 0; h < NnueNet::kHidden; ++h) {
    EXPECT_EQ(pos.nnue_acc().v[h], refreshed.v[h]) << "after undo h=" << h;
  }
}

TEST(NnueTest, EvalFinite) {
  init_bitboards();
  Zobrist::init();
  Nnue::instance().load_default_from_hce();
  Position pos;
  pos.set_startpos();
  int e = evaluate(pos);
  EXPECT_GT(e, -5000);
  EXPECT_LT(e, 5000);
}
