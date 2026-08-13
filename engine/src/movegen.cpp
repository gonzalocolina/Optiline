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
void generate_quiet_promotions(const Position& pos, MoveList& list) {
  constexpr int Up = Us == WHITE ? 8 : -8;
  Bitboard pawns = pos.pieces(Us, PAWN);
  Bitboard single = (Us == WHITE ? shift_north(pawns) : shift_south(pawns)) & ~pos.occupied();
  Bitboard promotions = single & (Us == WHITE ? Rank8BB : Rank1BB);
  while (promotions) {
    Square to = pop_lsb(promotions);
    Square from = static_cast<Square>(static_cast<int>(to) - Up);
    add_promo(list, from, to, MF_NONE);
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
      if ((pos.castling_rights() & WHITE_OO) && pos.piece_on(SQ_H1) == W_ROOK &&
          !(occ & (square_bb(SQ_F1) | square_bb(SQ_G1))) &&
          !pos.is_square_attacked(SQ_E1, BLACK, occ) && !pos.is_square_attacked(SQ_F1, BLACK, occ) &&
          !pos.is_square_attacked(SQ_G1, BLACK, occ)) {
        list.add(Move::make(SQ_E1, SQ_G1, NO_PIECE_TYPE, MF_CASTLE));
      }
      if ((pos.castling_rights() & WHITE_OOO) && pos.piece_on(SQ_A1) == W_ROOK &&
          !(occ & (square_bb(SQ_D1) | square_bb(SQ_C1) | square_bb(SQ_B1))) &&
          !pos.is_square_attacked(SQ_E1, BLACK, occ) && !pos.is_square_attacked(SQ_D1, BLACK, occ) &&
          !pos.is_square_attacked(SQ_C1, BLACK, occ)) {
        list.add(Move::make(SQ_E1, SQ_C1, NO_PIECE_TYPE, MF_CASTLE));
      }
    } else {
      if ((pos.castling_rights() & BLACK_OO) && pos.piece_on(SQ_H8) == B_ROOK &&
          !(occ & (square_bb(SQ_F8) | square_bb(SQ_G8))) &&
          !pos.is_square_attacked(SQ_E8, WHITE, occ) && !pos.is_square_attacked(SQ_F8, WHITE, occ) &&
          !pos.is_square_attacked(SQ_G8, WHITE, occ)) {
        list.add(Move::make(SQ_E8, SQ_G8, NO_PIECE_TYPE, MF_CASTLE));
      }
      if ((pos.castling_rights() & BLACK_OOO) && pos.piece_on(SQ_A8) == B_ROOK &&
          !(occ & (square_bb(SQ_D8) | square_bb(SQ_C8) | square_bb(SQ_B8))) &&
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

bool legal_king_move(const Position& pos, Move move) {
  Color us = pos.side_to_move();
  Color them = ~us;
  Square from = move.from();
  Square to = move.to();
  Bitboard occupied = pos.occupied();

  if (!move.is_castle()) {
    Bitboard occupied_after = (occupied & ~square_bb(from)) | square_bb(to);
    return !pos.is_square_attacked(to, them, occupied_after);
  }

  bool kingside = file_of(to) > file_of(from);
  Square transit = static_cast<Square>(from + (kingside ? 1 : -1));
  Bitboard transit_occupied = (occupied & ~square_bb(from)) | square_bb(transit);
  if (pos.is_square_attacked(transit, them, transit_occupied)) return false;

  Square rook_from = kingside ? (us == WHITE ? SQ_H1 : SQ_H8) : (us == WHITE ? SQ_A1 : SQ_A8);
  Square rook_to = kingside ? (us == WHITE ? SQ_F1 : SQ_F8) : (us == WHITE ? SQ_D1 : SQ_D8);
  Bitboard final_occupied = occupied & ~square_bb(from) & ~square_bb(rook_from);
  final_occupied |= square_bb(to) | square_bb(rook_to);
  return !pos.is_square_attacked(to, them, final_occupied);
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

void generate_noisy(const Position& pos, MoveList& list) {
  generate_captures(pos, list);
  if (pos.side_to_move() == WHITE)
    generate_quiet_promotions<WHITE>(pos, list);
  else
    generate_quiet_promotions<BLACK>(pos, list);
}

void filter_legal(const Position& pos, const MoveList& pseudo, MoveList& list) {
  list.size = 0;

  const Color us = pos.side_to_move();
  const Square king = pos.king_square(us);
  const Bitboard checkers = pos.checkers();
  const int check_count = popcount(checkers);
  const Bitboard pinned = pos.blockers_for_king();

  // Most search nodes are not in check, have no pinned piece, and do not
  // expose an en-passant discovered check. In that common case every
  // non-king pseudo move is legal; avoid the full filtering branch tree.
  if (check_count == 0 && pinned == 0 && pos.ep_square() == SQ_NONE) {
    for (int i = 0; i < pseudo.size; ++i) {
      Move move = pseudo.moves[i];
      if (type_of(pos.piece_on(move.from())) == KING && !legal_king_move(pos, move)) continue;
      list.add(move);
    }
    return;
  }

  Bitboard evasion_mask = ~Bitboard{0};
  Square checker = SQ_NONE;
  if (check_count == 1) {
    checker = lsb(checkers);
    evasion_mask = square_bb(checker) | between_bb(king, checker);
  }

  for (int i = 0; i < pseudo.size; ++i) {
    Move move = pseudo.moves[i];
    Piece moving = pos.piece_on(move.from());
    if (moving == NO_PIECE) continue;

    if (type_of(moving) == KING) {
      if (legal_king_move(pos, move)) list.add(move);
      continue;
    }

    if (check_count >= 2) continue;
    if ((pinned & square_bb(move.from())) && !(line_bb(king, move.from()) & square_bb(move.to()))) continue;

    if (check_count == 1) {
      bool evades = evasion_mask & square_bb(move.to());
      if (move.is_ep()) {
        Square captured = static_cast<Square>(move.to() + (us == WHITE ? -8 : 8));
        evades = evades || captured == checker;
      }
      if (!evades) continue;
    }

    if (move.is_ep()) {
      Position& mutable_pos = const_cast<Position&>(pos);
      if (leaves_king_in_check(mutable_pos, move)) continue;
    }
    list.add(move);
  }
}

void generate_legal(const Position& pos, MoveList& list) {
  MoveList pseudo;
  generate_pseudo_legal(pos, pseudo);
  filter_legal(pos, pseudo, list);
}

void generate_legal_noisy(const Position& pos, MoveList& list) {
  MoveList pseudo;
  generate_noisy(pos, pseudo);
  filter_legal(pos, pseudo, list);
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
      case 'n': case 'N': promo = KNIGHT; break;
      case 'b': case 'B': promo = BISHOP; break;
      case 'r': case 'R': promo = ROOK; break;
      case 'q': case 'Q': promo = QUEEN; break;
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
