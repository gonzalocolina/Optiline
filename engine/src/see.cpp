#include "nsce/see.hpp"

#include "nsce/bitboard.hpp"
#include "nsce/eval.hpp"

#include <algorithm>

namespace nsce {
namespace {

constexpr int SeeValue[PIECE_TYPE_NB] = {100, 320, 330, 500, 900, 20000};

}  // namespace

// Swap-list SEE on the position's own bitboards. Squares that leave the board
// during the exchange (the mover's origin, the captured piece, every used
// attacker) are tracked in `occupied` only; the target square itself never
// attacks itself, so the piece sitting on it needs no bookkeeping. This is the
// same exchange sequence (least valuable attacker first, king only if it
// cannot be recaptured, pawn arrivals on the last rank promote) as the previous
// copy-the-board implementation, without materialising twelve bitboards per
// call.
int static_exchange_eval(const Position& pos, Move move) {
  if (move.is_castle()) return 0;

  const Color us = pos.side_to_move();
  const Square from = move.from();
  const Square target = move.to();
  const Piece moving_piece = pos.piece_on(from);
  if (moving_piece == NO_PIECE) return 0;

  PieceType target_type = type_of(moving_piece);
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

  Bitboard occupied = (pos.occupied() & ~square_bb(from)) | square_bb(target);
  if (captured_piece != NO_PIECE) occupied &= ~square_bb(captured_square);

  Color side = ~us;
  int depth = 0;
  while (depth < 31) {
    const Bitboard attackers = pos.attackers_to(target, occupied) & occupied & pos.pieces(side);
    if (!attackers) break;

    PieceType attacker_type = PAWN;
    Bitboard candidates = 0;
    for (int type = PAWN; type <= KING; ++type) {
      candidates = attackers & pos.pieces(side, static_cast<PieceType>(type));
      if (candidates) {
        attacker_type = static_cast<PieceType>(type);
        break;
      }
    }

    const Bitboard attacker_bb = square_bb(lsb(candidates));
    const Bitboard occupied_after = occupied & ~attacker_bb;
    if (attacker_type == KING && (pos.attackers_to(target, occupied_after) & occupied_after & pos.pieces(~side)))
      break;

    ++depth;
    int promotion_gain = 0;
    PieceType arriving_type = attacker_type;
    if (attacker_type == PAWN && ((side == WHITE && rank_of(target) == 7) ||
                                  (side == BLACK && rank_of(target) == 0))) {
      arriving_type = QUEEN;
      promotion_gain = SeeValue[QUEEN] - SeeValue[PAWN];
    }
    gain[depth] = SeeValue[target_type] + promotion_gain - gain[depth - 1];

    occupied = occupied_after;
    target_type = arriving_type;
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
