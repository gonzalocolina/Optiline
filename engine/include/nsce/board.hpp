#pragma once

#include "nsce/bitboard.hpp"
#include "nsce/nnue.hpp"
#include "nsce/types.hpp"

#include <array>
#include <string>
#include <vector>

namespace nsce {

struct StateInfo {
  CastlingRights castling = NO_CASTLING;
  Square ep_square = SQ_NONE;
  int halfmove_clock = 0;
  Piece captured = NO_PIECE;
  Key key = 0;
  Bitboard checkers = 0;
};

class Position {
 public:
  Position();

  void set_fen(const std::string& fen);
  void set_startpos();
  std::string fen() const;

  void do_move(Move m, StateInfo& st);
  void undo_move(Move m, const StateInfo& st);
  void do_null_move(StateInfo& st);
  void undo_null_move(const StateInfo& st);

  Bitboard pieces(Color c) const { return by_color_[c]; }
  Bitboard pieces(PieceType pt) const { return by_type_[pt]; }
  Bitboard pieces(Color c, PieceType pt) const { return by_color_[c] & by_type_[pt]; }
  Bitboard occupied() const { return occupied_; }
  Piece piece_on(Square s) const { return board_[s]; }
  Color side_to_move() const { return side_; }
  CastlingRights castling_rights() const { return castling_; }
  Square ep_square() const { return ep_square_; }
  int halfmove_clock() const { return halfmove_; }
  int fullmove_number() const { return fullmove_; }
  Key key() const { return key_; }
  Key pawn_key() const { return pawn_key_; }
  Key nonpawn_key() const { return nonpawn_key_; }
  Bitboard checkers() const { return checkers_; }
  Bitboard blockers_for_king() const;
  Square king_square(Color c) const { return lsb(pieces(c, KING)); }
  const NnueAccumulator& nnue_acc() const { return nnue_acc_; }

  bool in_check() const { return checkers_ != 0; }
  bool is_draw() const;
  bool is_capture(Move m) const;

  Bitboard attackers_to(Square s, Bitboard occ) const;
  Bitboard attackers_to(Square s) const { return attackers_to(s, occupied_); }
  bool is_square_attacked(Square s, Color by, Bitboard occ) const;

  void put_piece(Piece pc, Square s);
  void remove_piece(Square s);
  void move_piece(Square from, Square to);

 private:
  void clear();
  void update_checkers();
  Key compute_key() const;
  void refresh_nnue();
  Bitboard compute_blockers_for_king() const;

  std::array<Piece, SQUARE_NB> board_{};
  std::array<Bitboard, COLOR_NB> by_color_{};
  std::array<Bitboard, PIECE_TYPE_NB> by_type_{};
  Bitboard occupied_ = 0;
  Color side_ = WHITE;
  CastlingRights castling_ = NO_CASTLING;
  Square ep_square_ = SQ_NONE;
  int halfmove_ = 0;
  int fullmove_ = 1;
  Key key_ = 0;
  Key pawn_key_ = 0;
  Key nonpawn_key_ = 0;
  Bitboard checkers_ = 0;
  mutable Bitboard blockers_for_king_ = 0;
  mutable bool blockers_valid_ = false;
  std::vector<Key> history_keys_;
  NnueAccumulator nnue_acc_{};
  bool nnue_live_ = false;
};

}  // namespace nsce
