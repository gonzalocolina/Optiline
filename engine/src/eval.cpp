#include "nsce/eval.hpp"

#include "nsce/nnue.hpp"

namespace nsce {
namespace {

constexpr int PieceValue[PIECE_TYPE_NB] = {100, 320, 330, 500, 900, 0};

// Midgame piece-square tables (from white's perspective; flip for black).
constexpr int PST[PIECE_TYPE_NB][SQUARE_NB] = {
    // Pawn
    {0,  0,  0,  0,  0,  0,  0,  0,
     50, 50, 50, 50, 50, 50, 50, 50,
     10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0},
    // Knight
    {-50,-40,-30,-30,-30,-30,-40,-50,
     -40,-20,  0,  0,  0,  0,-20,-40,
     -30,  0, 10, 15, 15, 10,  0,-30,
     -30,  5, 15, 20, 20, 15,  5,-30,
     -30,  0, 15, 20, 20, 15,  0,-30,
     -30,  5, 10, 15, 15, 10,  5,-30,
     -40,-20,  0,  5,  5,  0,-20,-40,
     -50,-40,-30,-30,-30,-30,-40,-50},
    // Bishop
    {-20,-10,-10,-10,-10,-10,-10,-20,
     -10,  0,  0,  0,  0,  0,  0,-10,
     -10,  0,  5, 10, 10,  5,  0,-10,
     -10,  5,  5, 10, 10,  5,  5,-10,
     -10,  0, 10, 10, 10, 10,  0,-10,
     -10, 10, 10, 10, 10, 10, 10,-10,
     -10,  5,  0,  0,  0,  0,  5,-10,
     -20,-10,-10,-10,-10,-10,-10,-20},
    // Rook
    {0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0},
    // Queen
    {-20,-10,-10, -5, -5,-10,-10,-20,
     -10,  0,  0,  0,  0,  0,  0,-10,
     -10,  0,  5,  5,  5,  5,  0,-10,
      -5,  0,  5,  5,  5,  5,  0, -5,
       0,  0,  5,  5,  5,  5,  0, -5,
     -10,  5,  5,  5,  5,  5,  0,-10,
     -10,  0,  5,  0,  0,  0,  0,-10,
     -20,-10,-10, -5, -5,-10,-10,-20},
    // King midgame
    {-30,-40,-40,-50,-50,-40,-40,-30,
     -30,-40,-40,-50,-50,-40,-40,-30,
     -30,-40,-40,-50,-50,-40,-40,-30,
     -30,-40,-40,-50,-50,-40,-40,-30,
     -20,-30,-30,-40,-40,-30,-30,-20,
     -10,-20,-20,-20,-20,-20,-20,-10,
      20, 20,  0,  0,  0,  0, 20, 20,
      20, 30, 10,  0,  0, 10, 30, 20}};

Square flip(Square s) { return static_cast<Square>(static_cast<int>(s) ^ 56); }

}  // namespace

int evaluate(const Position& pos) {
  if (Nnue::instance().is_enabled()) {
    return Nnue::instance().evaluate(pos.nnue_acc(), pos.side_to_move());
  }
  int score = 0;
  for (int sq = 0; sq < SQUARE_NB; ++sq) {
    Piece pc = pos.piece_on(static_cast<Square>(sq));
    if (pc == NO_PIECE) continue;
    PieceType pt = type_of(pc);
    Color c = color_of(pc);
    int v = PieceValue[pt];
    Square pst_sq = (c == WHITE) ? static_cast<Square>(sq) : flip(static_cast<Square>(sq));
    v += PST[pt][pst_sq];
    score += (c == WHITE) ? v : -v;
  }
  return (pos.side_to_move() == WHITE) ? score : -score;
}

int piece_value(PieceType pt) {
  return PieceValue[pt];
}

int non_pawn_material(const Position& pos, Color c) {
  int npm = 0;
  for (PieceType pt : {KNIGHT, BISHOP, ROOK, QUEEN}) {
    npm += piece_value(pt) * popcount(pos.pieces(c, pt));
  }
  return npm;
}

}  // namespace nsce
