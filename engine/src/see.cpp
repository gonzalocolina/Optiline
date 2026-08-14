#include "nsce/see.hpp"

#include "nsce/bitboard.hpp"
#include "nsce/eval.hpp"

#include <algorithm>

namespace nsce {
namespace {

constexpr int SeeValue[PIECE_TYPE_NB] = {100, 320, 330, 500, 900, 20000};

Bitboard attackers_to(Square target, Bitboard occupied, Bitboard pieces[COLOR_NB][PIECE_TYPE_NB]) {
  return (pawn_attacks_bb(BLACK, target) & pieces[WHITE][PAWN]) |
         (pawn_attacks_bb(WHITE, target) & pieces[BLACK][PAWN]) |
         (knight_attacks_bb(target) & (pieces[WHITE][KNIGHT] | pieces[BLACK][KNIGHT])) |
         (bishop_attacks_bb(target, occupied) &
          (pieces[WHITE][BISHOP] | pieces[BLACK][BISHOP] | pieces[WHITE][QUEEN] | pieces[BLACK][QUEEN])) |
         (rook_attacks_bb(target, occupied) &
          (pieces[WHITE][ROOK] | pieces[BLACK][ROOK] | pieces[WHITE][QUEEN] | pieces[BLACK][QUEEN])) |
         (king_attacks_bb(target) & (pieces[WHITE][KING] | pieces[BLACK][KING]));
}

}  // namespace

int static_exchange_eval(const Position& pos, Move move) {
  if (move.is_castle()) return 0;

  Bitboard pieces[COLOR_NB][PIECE_TYPE_NB]{};
  for (int color = 0; color < COLOR_NB; ++color)
    for (int type = 0; type < PIECE_TYPE_NB; ++type)
      pieces[color][type] = pos.pieces(static_cast<Color>(color), static_cast<PieceType>(type));

  const Color us = pos.side_to_move();
  const Square from = move.from();
  const Square target = move.to();
  const Bitboard target_bb = square_bb(target);
  Piece moving_piece = pos.piece_on(from);
  if (moving_piece == NO_PIECE) return 0;

  PieceType moving_type = type_of(moving_piece);
  PieceType target_type = moving_type;
  Piece captured_piece = NO_PIECE;
  Square captured_square = target;
  if (move.is_ep()) {
    captured_square = static_cast<Square>(target + (us == WHITE ? -8 : 8));
    captured_piece = pos.piece_on(captured_square);
  } else if (move.is_capture()) {
    captured_piece = pos.piece_on(target);
  }

  int gain[32]{};
  if (captured_piece != NO_PIECE) gain[0] = SeeValue[type_of(captured_piece)];
  if (move.is_promotion()) {
    target_type = move.promotion();
    gain[0] += SeeValue[target_type] - SeeValue[PAWN];
  }

  Bitboard occupied = pos.occupied();
  const Bitboard from_bb = square_bb(from);
  pieces[us][moving_type] &= ~from_bb;
  occupied &= ~from_bb;

  if (captured_piece != NO_PIECE) {
    Bitboard captured_bb = square_bb(captured_square);
    pieces[~us][type_of(captured_piece)] &= ~captured_bb;
    occupied &= ~captured_bb;
  }

  pieces[us][target_type] |= target_bb;
  occupied |= target_bb;

  Bitboard by_color[COLOR_NB] = {pos.pieces(WHITE), pos.pieces(BLACK)};
  by_color[us] ^= from_bb;
  by_color[us] |= target_bb;
  if (captured_piece != NO_PIECE) by_color[~us] &= ~square_bb(captured_square);

  Color side = ~us;
  Color occupant_color = us;
  int depth = 0;
  while (depth < 31) {
    Bitboard attackers = attackers_to(target, occupied, pieces) & by_color[side];
    if (!attackers) break;

    PieceType attacker_type = PAWN;
    Bitboard candidates = 0;
    for (int type = PAWN; type <= KING; ++type) {
      candidates = attackers & pieces[side][type];
      if (candidates) {
        attacker_type = static_cast<PieceType>(type);
        break;
      }
    }
    if (!candidates) break;

    Square attacker_square = lsb(candidates);
    Bitboard attacker_bb = square_bb(attacker_square);
    if (attacker_type == KING) {
      Bitboard occupied_after = occupied & ~attacker_bb;
      if (attackers_to(target, occupied_after, pieces) & by_color[~side]) break;
    }

    ++depth;
    int promotion_gain = 0;
    PieceType arriving_type = attacker_type;
    if (attacker_type == PAWN && ((side == WHITE && rank_of(target) == 7) ||
                                  (side == BLACK && rank_of(target) == 0))) {
      arriving_type = QUEEN;
      promotion_gain = SeeValue[QUEEN] - SeeValue[PAWN];
    }
    gain[depth] = SeeValue[target_type] + promotion_gain - gain[depth - 1];

    pieces[occupant_color][target_type] &= ~target_bb;
    pieces[side][attacker_type] &= ~attacker_bb;
    occupied &= ~attacker_bb;
    by_color[side] &= ~attacker_bb;
    pieces[side][arriving_type] |= target_bb;
    by_color[occupant_color] &= ~target_bb;
    by_color[side] |= target_bb;

    target_type = arriving_type;
    occupant_color = side;
    side = ~side;
  }

  while (depth > 0) {
    gain[depth - 1] = -std::max(-gain[depth - 1], gain[depth]);
    --depth;
  }
  return gain[0];
}

bool static_exchange_eval_ge(const Position& pos, Move move, int threshold) {
  if (move.is_castle()) return threshold <= 0;
  const Color us = pos.side_to_move();
  const Square from = move.from();
  const Square target = move.to();
  const Piece moving = pos.piece_on(from);
  if (moving == NO_PIECE) return false;

  int immediate_gain = 0;
  Square captured_square = target;
  Piece captured = NO_PIECE;
  if (move.is_ep()) {
    captured_square = static_cast<Square>(target + (us == WHITE ? -8 : 8));
    captured = pos.piece_on(captured_square);
  } else if (move.is_capture()) {
    captured = pos.piece_on(target);
  }
  if (captured != NO_PIECE) immediate_gain += SeeValue[type_of(captured)];
  if (move.is_promotion()) immediate_gain += SeeValue[move.promotion()] - SeeValue[PAWN];

  Bitboard occupied = pos.occupied() & ~square_bb(from);
  occupied |= square_bb(target);
  if (captured != NO_PIECE) occupied &= ~square_bb(captured_square);
  const Bitboard opponent_attackers = pos.attackers_to(target, occupied) & pos.pieces(~us);
  if (!opponent_attackers) return immediate_gain >= threshold;
  // If the opponent's best first recapture only removes the moving piece,
  // this is a conservative lower bound on the complete exchange. It avoids
  // the full swap list for the common clearly-safe threshold query.
  const PieceType arriving = move.is_promotion() ? move.promotion() : type_of(moving);
  if (immediate_gain - SeeValue[arriving] >= threshold) return true;

  return static_exchange_eval(pos, move) >= threshold;
}

}  // namespace nsce
