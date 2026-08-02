#include "nsce/movegen.hpp"

namespace nsce {
namespace {

void add_promo(MoveList& list, Square from, Square to, int flags) {
  for (PieceType pt : {QUEEN, ROOK, BISHOP, KNIGHT}) {
    list.add(Move::make(from, to, pt, flags | MF_PROMO));
  }
}

template <Color Us>
void generate_pawn_moves(const Position& pos, MoveList& list, bool captures_only) {
  constexpr Color Them = Us == WHITE ? BLACK : WHITE;
  constexpr Bitboard Rank3 = Us == WHITE ? 0x0000000000FF0000ULL : 0x0000FF0000000000ULL;
  constexpr int Up = Us == WHITE ? 8 : -8;

  Bitboard pawns = pos.pieces(Us, PAWN);
  Bitboard empty = ~pos.occupied();
  Bitboard enemies = pos.pieces(Them);

  if (!captures_only) {
    Bitboard single = (Us == WHITE ? shift_north(pawns) : shift_south(pawns)) & empty;
    Bitboard doubles = (Us == WHITE ? shift_north(single & Rank3) : shift_south(single & Rank3)) & empty;

    Bitboard promo = single & (Us == WHITE ? Rank8BB : Rank1BB);
    Bitboard quiet = single & ~promo;

    while (quiet) {
      Square to = pop_lsb(quiet);
      Square from = static_cast<Square>(static_cast<int>(to) - Up);
      list.add(Move::make(from, to));
    }
    while (doubles) {
      Square to = pop_lsb(doubles);
      Square from = static_cast<Square>(static_cast<int>(to) - 2 * Up);
      list.add(Move::make(from, to, NO_PIECE_TYPE, MF_DOUBLE));
    }
    while (promo) {
      Square to = pop_lsb(promo);
      Square from = static_cast<Square>(static_cast<int>(to) - Up);
      add_promo(list, from, to, MF_NONE);
    }
  }

  Bitboard cap_left = (Us == WHITE ? shift_nw(pawns) : shift_sw(pawns)) & enemies;
  Bitboard cap_right = (Us == WHITE ? shift_ne(pawns) : shift_se(pawns)) & enemies;

  Bitboard promo_left = cap_left & (Us == WHITE ? Rank8BB : Rank1BB);
  Bitboard promo_right = cap_right & (Us == WHITE ? Rank8BB : Rank1BB);
  cap_left &= ~promo_left;
  cap_right &= ~promo_right;

  // White NW: +7, Black SW: -9; White NE: +9, Black SE: -7
  constexpr int LeftDelta = Us == WHITE ? 7 : -9;
  constexpr int RightDelta = Us == WHITE ? 9 : -7;

  while (cap_left) {
    Square to = pop_lsb(cap_left);
    Square from = static_cast<Square>(static_cast<int>(to) - LeftDelta);
    list.add(Move::make(from, to, NO_PIECE_TYPE, MF_CAPTURE));
  }
  while (cap_right) {
    Square to = pop_lsb(cap_right);
    Square from = static_cast<Square>(static_cast<int>(to) - RightDelta);
    list.add(Move::make(from, to, NO_PIECE_TYPE, MF_CAPTURE));
  }
  while (promo_left) {
    Square to = pop_lsb(promo_left);
    Square from = static_cast<Square>(static_cast<int>(to) - LeftDelta);
    add_promo(list, from, to, MF_CAPTURE);
  }
  while (promo_right) {
    Square to = pop_lsb(promo_right);
    Square from = static_cast<Square>(static_cast<int>(to) - RightDelta);
    add_promo(list, from, to, MF_CAPTURE);
  }

  Square ep = pos.ep_square();
  if (ep != SQ_NONE) {
    Bitboard ep_attackers = pawn_attacks_bb(Them, ep) & pawns;
    while (ep_attackers) {
      Square from = pop_lsb(ep_attackers);
      list.add(Move::make(from, ep, NO_PIECE_TYPE, MF_CAPTURE | MF_EP));
    }
  }
}

template <Color Us>
void generate_piece_moves(const Position& pos, MoveList& list, bool captures_only) {
  Bitboard us = pos.pieces(Us);
  Bitboard targets = captures_only ? pos.pieces(~Us) : ~us;

  Bitboard knights = pos.pieces(Us, KNIGHT);
  while (knights) {
    Square from = pop_lsb(knights);
    Bitboard att = knight_attacks_bb(from) & targets;
    while (att) {
      Square to = pop_lsb(att);
      int flags = (pos.piece_on(to) != NO_PIECE) ? MF_CAPTURE : MF_NONE;
      list.add(Move::make(from, to, NO_PIECE_TYPE, flags));
    }
  }

  auto emit_slider = [&](Bitboard pieces, auto attacks_fn) {
    while (pieces) {
      Square from = pop_lsb(pieces);
      Bitboard att = attacks_fn(from, pos.occupied()) & targets;
      while (att) {
        Square to = pop_lsb(att);
        int flags = (pos.piece_on(to) != NO_PIECE) ? MF_CAPTURE : MF_NONE;
        list.add(Move::make(from, to, NO_PIECE_TYPE, flags));
      }
    }
  };

  emit_slider(pos.pieces(Us, BISHOP), bishop_attacks_bb);
  emit_slider(pos.pieces(Us, ROOK), rook_attacks_bb);
  emit_slider(pos.pieces(Us, QUEEN), queen_attacks_bb);

  Square ksq = pos.king_square(Us);
  Bitboard katt = king_attacks_bb(ksq) & targets;
  while (katt) {
    Square to = pop_lsb(katt);
    int flags = (pos.piece_on(to) != NO_PIECE) ? MF_CAPTURE : MF_NONE;
    list.add(Move::make(ksq, to, NO_PIECE_TYPE, flags));
  }

  if (!captures_only && !pos.in_check()) {
    Bitboard occ = pos.occupied();
    if constexpr (Us == WHITE) {
      if ((pos.castling_rights() & WHITE_OO) && !(occ & (square_bb(SQ_F1) | square_bb(SQ_G1))) &&
          !pos.is_square_attacked(SQ_E1, BLACK, occ) && !pos.is_square_attacked(SQ_F1, BLACK, occ) &&
          !pos.is_square_attacked(SQ_G1, BLACK, occ)) {
        list.add(Move::make(SQ_E1, SQ_G1, NO_PIECE_TYPE, MF_CASTLE));
      }
      if ((pos.castling_rights() & WHITE_OOO) && !(occ & (square_bb(SQ_D1) | square_bb(SQ_C1) | square_bb(SQ_B1))) &&
          !pos.is_square_attacked(SQ_E1, BLACK, occ) && !pos.is_square_attacked(SQ_D1, BLACK, occ) &&
          !pos.is_square_attacked(SQ_C1, BLACK, occ)) {
        list.add(Move::make(SQ_E1, SQ_C1, NO_PIECE_TYPE, MF_CASTLE));
      }
    } else {
      if ((pos.castling_rights() & BLACK_OO) && !(occ & (square_bb(SQ_F8) | square_bb(SQ_G8))) &&
          !pos.is_square_attacked(SQ_E8, WHITE, occ) && !pos.is_square_attacked(SQ_F8, WHITE, occ) &&
          !pos.is_square_attacked(SQ_G8, WHITE, occ)) {
        list.add(Move::make(SQ_E8, SQ_G8, NO_PIECE_TYPE, MF_CASTLE));
      }
      if ((pos.castling_rights() & BLACK_OOO) && !(occ & (square_bb(SQ_D8) | square_bb(SQ_C8) | square_bb(SQ_B8))) &&
          !pos.is_square_attacked(SQ_E8, WHITE, occ) && !pos.is_square_attacked(SQ_D8, WHITE, occ) &&
          !pos.is_square_attacked(SQ_C8, WHITE, occ)) {
        list.add(Move::make(SQ_E8, SQ_C8, NO_PIECE_TYPE, MF_CASTLE));
      }
    }
  }
}

bool leaves_king_in_check(Position& pos, Move m) {
  StateInfo st;
  Color us = pos.side_to_move();
  pos.do_move(m, st);
  bool bad = pos.is_square_attacked(pos.king_square(us), ~us, pos.occupied());
  pos.undo_move(m, st);
  return bad;
}

}  // namespace

void generate_pseudo_legal(const Position& pos, MoveList& list) {
  list.size = 0;
  if (pos.side_to_move() == WHITE) {
    generate_pawn_moves<WHITE>(pos, list, false);
    generate_piece_moves<WHITE>(pos, list, false);
  } else {
    generate_pawn_moves<BLACK>(pos, list, false);
    generate_piece_moves<BLACK>(pos, list, false);
  }
}

void generate_captures(const Position& pos, MoveList& list) {
  list.size = 0;
  if (pos.side_to_move() == WHITE) {
    generate_pawn_moves<WHITE>(pos, list, true);
    generate_piece_moves<WHITE>(pos, list, true);
  } else {
    generate_pawn_moves<BLACK>(pos, list, true);
    generate_piece_moves<BLACK>(pos, list, true);
  }
}

void generate_legal(const Position& pos, MoveList& list) {
  MoveList pseudo;
  generate_pseudo_legal(pos, pseudo);
  list.size = 0;
  Position& mutable_pos = const_cast<Position&>(pos);
  for (int i = 0; i < pseudo.size; ++i) {
    if (!leaves_king_in_check(mutable_pos, pseudo.moves[i])) list.add(pseudo.moves[i]);
  }
}

std::string move_to_uci(Move m) {
  std::string s = square_to_string(m.from()) + square_to_string(m.to());
  if (m.is_promotion()) {
    const char chars[] = "pnbrqk";
    s += chars[m.promotion()];
  }
  return s;
}

Move parse_uci_move(const Position& pos, const std::string& uci) {
  if (uci.size() < 4) return Move{};
  Square from = string_to_square(uci.substr(0, 2));
  Square to = string_to_square(uci.substr(2, 2));
  PieceType promo = NO_PIECE_TYPE;
  if (uci.size() >= 5) {
    switch (uci[4]) {
      case 'n': promo = KNIGHT; break;
      case 'b': promo = BISHOP; break;
      case 'r': promo = ROOK; break;
      case 'q': promo = QUEEN; break;
      default: break;
    }
  }
  MoveList list;
  generate_legal(pos, list);
  for (int i = 0; i < list.size; ++i) {
    Move m = list.moves[i];
    if (m.from() == from && m.to() == to) {
      if (!m.is_promotion() || m.promotion() == promo) return m;
    }
  }
  return Move{};
}

}  // namespace nsce
