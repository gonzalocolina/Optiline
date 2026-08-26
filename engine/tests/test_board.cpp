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

TEST(BoardTest, NullMoveDoesNotAdvanceGameDrawState) {
  Position pos;
  pos.set_fen("4k3/8/8/8/8/8/4R3/4K3 w - - 99 1");
  const std::string before = pos.fen();
  const Key key = pos.key();
  StateInfo st;
  pos.do_null_move(st);
  EXPECT_EQ(pos.halfmove_clock(), 99);
  EXPECT_FALSE(pos.is_draw());
  pos.undo_null_move(st);
  EXPECT_EQ(pos.fen(), before);
  EXPECT_EQ(pos.key(), key);
}

TEST(BoardTest, DirectEvasionsMatchLegalMoves) {
  const char* fens[] = {
      "4k3/8/8/8/4q3/8/R7/4K3 w - - 0 1",
      "4k3/8/8/8/8/8/2n1R3/4K3 w - - 0 1",
      "4k3/8/8/8/8/8/R3r3/4K3 w - - 0 1",
  };
  for (const char* fen : fens) {
    Position pos;
    pos.set_fen(fen);
    ASSERT_TRUE(pos.in_check()) << fen;
    MoveList legal;
    MoveList evasions;
    generate_legal(pos, legal);
    generate_legal_evasions(pos, evasions);
    ASSERT_EQ(legal.size, evasions.size) << fen;
    for (int i = 0; i < legal.size; ++i) {
      bool found = false;
      for (int j = 0; j < evasions.size; ++j) found = found || legal.moves[i] == evasions.moves[j];
      EXPECT_TRUE(found) << fen << " missing " << move_to_uci(legal.moves[i]);
    }
  }
}

TEST(BoardTest, DirectEvasionsMatchLegalMovesAlongRandomizedPlay) {
  Position pos;
  pos.set_startpos();
  for (int ply = 0; ply < 256; ++ply) {
    MoveList legal;
    generate_legal(pos, legal);
    if (legal.size == 0) break;
    if (pos.in_check()) {
      MoveList evasions;
      generate_legal_evasions(pos, evasions);
      ASSERT_EQ(legal.size, evasions.size) << "ply " << ply << " " << pos.fen();
      for (int i = 0; i < legal.size; ++i) {
        bool found = false;
        for (int j = 0; j < evasions.size; ++j) found = found || legal.moves[i] == evasions.moves[j];
        EXPECT_TRUE(found) << "ply " << ply << " missing " << move_to_uci(legal.moves[i]);
      }
    }
    StateInfo state;
    pos.do_move(legal.moves[(ply * 17 + 5) % legal.size], state);
  }
}

TEST(BoardTest, RejectsMalformedFen) {
  Position pos;
  EXPECT_THROW(pos.set_fen("8/8/8/8/8/8/8 w - - 0 1"), std::runtime_error);
  EXPECT_THROW(pos.set_fen("8/8/8/8/8/8/8/8 x - - 0 1"), std::runtime_error);
  EXPECT_THROW(pos.set_fen("8/8/8/8/8/8/8/8 w - z9 0 1"), std::runtime_error);
  EXPECT_THROW(pos.set_fen("8/8/8/8/8/8/8/8 w - - 0 1"), std::runtime_error);
  EXPECT_THROW(pos.set_fen("4k3/8/8/8/8/8/8/3KK3 w - - 0 1"), std::runtime_error);
  EXPECT_THROW(pos.set_fen("4k3/8/8/8/8/8/8/4K3 w KQkq - 0 1"), std::runtime_error);
}

TEST(BoardTest, StartposRoundTripsAndCanonicalizesIllegalEp) {
  Position pos;
  pos.set_startpos();
  EXPECT_EQ(pos.fen(), "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  pos.set_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e4 0 1");
  EXPECT_EQ(pos.ep_square(), SQ_NONE);
  pos.set_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1");
  EXPECT_EQ(pos.ep_square(), SQ_E3);
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
