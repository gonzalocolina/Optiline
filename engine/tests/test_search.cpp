#include "nsce/bitboard.hpp"
#include "nsce/controller.hpp"
#include "nsce/movegen.hpp"
#include "nsce/search.hpp"
#include "nsce/zobrist.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <gtest/gtest.h>
#include <thread>

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

TEST(SearchTest, CheckmateTakesPrecedenceOverFiftyMoveDraw) {
  init_bitboards();
  Zobrist::init();

  Position pos;
  pos.set_fen("7k/5Q2/6K1/8/8/8/8/8 w - - 99 1");

  Search search;
  search.set_position(pos);
  SearchLimits limits;
  limits.depth = 1;
  SearchInfo info = search.go(limits);

  EXPECT_EQ(info.score, mate_in(1));
}

TEST(SearchTest, ParallelRootSplitPreservesForcedMate) {
  init_bitboards();
  Zobrist::init();

  Position pos;
  pos.set_fen("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1");
  Search search;
  search.set_position(pos);
  search.set_threads(4);
  SearchLimits limits;
  limits.depth = 3;

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

TEST(SearchTest, StopDuringParallelSearchReturns) {
  init_bitboards();
  Zobrist::init();

  Position pos;
  pos.set_startpos();
  Search search;
  search.set_position(pos);
  search.set_threads(4);
  search.set_silent(true);

  SearchLimits limits;
  limits.infinite = true;
  SearchInfo info;
  std::thread worker([&]() {
    search.prepare();
    info = search.go_prepared(limits);
  });
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
  search.stop();
  worker.join();
  EXPECT_TRUE(info.best_move);
}

TEST(SearchTest, RepeatedGoStopNoHang) {
  init_bitboards();
  Zobrist::init();

  Position pos;
  pos.set_startpos();
  Search search;
  search.set_position(pos);
  search.set_threads(4);
  search.set_silent(true);

  for (int i = 0; i < 12; ++i) {
    SearchLimits limits;
    limits.depth = 8;
    SearchInfo info;
    std::thread worker([&]() {
      search.prepare();
      info = search.go_prepared(limits);
    });
    if ((i & 1) != 0) {
      std::this_thread::sleep_for(std::chrono::milliseconds(8));
      search.stop();
    }
    worker.join();
    EXPECT_TRUE(info.best_move);
  }
}

TEST(SearchTest, AspirationWindowsReusePool) {
  init_bitboards();
  Zobrist::init();

  Position pos;
  pos.set_startpos();
  Search search;
  search.set_position(pos);
  search.set_threads(4);
  search.set_silent(true);

  SearchLimits limits;
  limits.depth = 8;
  SearchInfo info = search.go(limits);
  EXPECT_GT(info.depth, 0);
  EXPECT_TRUE(info.best_move);
}

TEST(SearchTest, FindsMateInTwoWithSingularSearch) {
  init_bitboards();
  Zobrist::init();

  Position pos;
  pos.set_fen("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4");
  Search search;
  search.set_position(pos);
  search.set_silent(true);
  SearchLimits limits;
  limits.depth = 6;
  SearchInfo info = search.go(limits);
  ASSERT_TRUE(info.best_move);
  EXPECT_EQ(move_to_uci(info.best_move), "h5f7");
}

TEST(SearchTest, SetThreadsResizePool) {
  init_bitboards();
  Zobrist::init();

  Position pos;
  pos.set_startpos();
  Search search;
  search.set_position(pos);
  search.set_silent(true);

  search.set_threads(2);
  SearchLimits shallow;
  shallow.depth = 4;
  EXPECT_TRUE(search.go(shallow).best_move);

  search.set_threads(6);
  EXPECT_TRUE(search.go(shallow).best_move);

  search.set_threads(1);
  SearchInfo info = search.go(shallow);
  EXPECT_TRUE(info.best_move);
  EXPECT_GT(info.depth, 0);
}

TEST(SearchTest, LoadsFittedControllerFormat) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_ctl2.bin";
  {
    std::ofstream out(path, std::ios::binary);
    out.write("NSCECTL2", 8);
    int32_t values[10] = {40, 50, 1, 20, -1, -120, 10, -8, 12, 0};
    out.write(reinterpret_cast<const char*>(values), sizeof(values));
  }
  ASSERT_TRUE(SearchController::instance().load(path.string()));
  const int delta = SearchController::instance().reduction_delta(8, 12, 40, -30, 70, true, 0, -800, false, true, -1);
  EXPECT_GE(delta, -1);
  EXPECT_LE(delta, 2);
  std::filesystem::remove(path);
}

TEST(SearchTest, HonorsSearchMovesAndNodeLimit) {
  init_bitboards();
  Zobrist::init();
  Position pos;
  pos.set_startpos();
  Search search;
  search.set_position(pos);
  search.set_silent(true);

  SearchLimits limits;
  limits.nodes = 2048;
  Move only = parse_uci_move(pos, "e2e4");
  ASSERT_TRUE(only);
  limits.searchmoves.push_back(only);
  SearchInfo info = search.go(limits);
  EXPECT_EQ(info.best_move, only);
  EXPECT_LE(info.nodes, 2080U);
}

TEST(SearchTest, TimeLimitStopsWithinBound) {
  init_bitboards();
  Zobrist::init();
  Position pos;
  pos.set_startpos();
  Search search;
  search.set_position(pos);
  search.set_threads(4);
  search.set_silent(true);
  SearchLimits limits;
  limits.movetime_ms = 20;
  SearchInfo info = search.go(limits);
  EXPECT_TRUE(info.best_move);
  EXPECT_LT(info.time_ms, 200);
}


