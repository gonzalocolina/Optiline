#include "nsce/movegen.hpp"
#include "nsce/see.hpp"

#include <gtest/gtest.h>

using namespace nsce;

TEST(StaticExchangeTest, DetectsWinningCapture) {
  Position pos;
  pos.set_fen("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1");

  Move move = parse_uci_move(pos, "e4d5");
  ASSERT_TRUE(move);
  EXPECT_EQ(static_exchange_eval(pos, move), 900);
}

TEST(StaticExchangeTest, DetectsLosingCaptureSequence) {
  Position pos;
  pos.set_fen("4k3/8/4p3/3p4/8/8/8/3QK3 w - - 0 1");

  Move move = parse_uci_move(pos, "d1d5");
  ASSERT_TRUE(move);
  EXPECT_EQ(static_exchange_eval(pos, move), -800);
}

TEST(StaticExchangeTest, ValuesQuietPromotion) {
  Position pos;
  pos.set_fen("7k/P7/8/8/8/8/8/7K w - - 0 1");

  Move move = parse_uci_move(pos, "a7a8q");
  ASSERT_TRUE(move);
  EXPECT_EQ(static_exchange_eval(pos, move), 800);
}

TEST(StaticExchangeTest, QuietHangingPieceIsNegative) {
  Position pos;
  pos.set_fen("4k3/8/8/8/3p4/8/8/3NK3 w - - 0 1");

  Move move = parse_uci_move(pos, "d1e3");
  ASSERT_TRUE(move);
  EXPECT_LT(static_exchange_eval(pos, move), 0);
}

TEST(StaticExchangeTest, SafeQuietIsZero) {
  Position pos;
  pos.set_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1");

  Move move = parse_uci_move(pos, "e2e4");
  ASSERT_TRUE(move);
  EXPECT_EQ(static_exchange_eval(pos, move), 0);
}

TEST(StaticExchangeTest, ThresholdMatchesExactForSimplePositions) {
  Position pos;
  pos.set_fen("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1");
  Move move = parse_uci_move(pos, "e4d5");
  ASSERT_TRUE(move);
  const int exact = static_exchange_eval(pos, move);
  for (int threshold = -1000; threshold <= 1000; threshold += 50)
    EXPECT_EQ(see_ge(pos, move, threshold), exact >= threshold) << "threshold=" << threshold;
}
