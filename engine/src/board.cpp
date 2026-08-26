#include "nsce/board.hpp"

#include "nsce/zobrist.hpp"

#include <algorithm>
#include <cctype>
#include <cstring>
#include <sstream>
#include <stdexcept>

namespace nsce {

namespace {

const char* PieceChars = "PNBRQKpnbrqk";

int castling_mask_for_square(Square s) {
  switch (s) {
    case SQ_A1: return WHITE_OOO;
    case SQ_E1: return WHITE_OO | WHITE_OOO;
    case SQ_H1: return WHITE_OO;
    case SQ_A8: return BLACK_OOO;
    case SQ_E8: return BLACK_OO | BLACK_OOO;
    case SQ_H8: return BLACK_OO;
    default: return 0;
  }
}

void validate_kings_and_castling(const Position& pos, CastlingRights cr) {
  if (pos.piece_count(WHITE, KING) != 1 || pos.piece_count(BLACK, KING) != 1)
    throw std::runtime_error("invalid fen kings");
  if ((cr & WHITE_OO) && (pos.piece_on(SQ_E1) != W_KING || pos.piece_on(SQ_H1) != W_ROOK))
    throw std::runtime_error("invalid fen castling");
  if ((cr & WHITE_OOO) && (pos.piece_on(SQ_E1) != W_KING || pos.piece_on(SQ_A1) != W_ROOK))
    throw std::runtime_error("invalid fen castling");
  if ((cr & BLACK_OO) && (pos.piece_on(SQ_E8) != B_KING || pos.piece_on(SQ_H8) != B_ROOK))
    throw std::runtime_error("invalid fen castling");
  if ((cr & BLACK_OOO) && (pos.piece_on(SQ_E8) != B_KING || pos.piece_on(SQ_A8) != B_ROOK))
    throw std::runtime_error("invalid fen castling");
}

Square canonicalize_ep(const Position& pos, Square ep, Color stm) {
  if (ep == SQ_NONE) return SQ_NONE;
  const int rank = rank_of(ep);
  if (pos.piece_on(ep) != NO_PIECE) return SQ_NONE;
  if (stm == WHITE) {
    if (rank != 5) return SQ_NONE;
    const Square origin = static_cast<Square>(static_cast<int>(ep) - 8);
    if (pos.piece_on(origin) != B_PAWN) return SQ_NONE;
  } else {
    if (rank != 2) return SQ_NONE;
    const Square origin = static_cast<Square>(static_cast<int>(ep) + 8);
    if (pos.piece_on(origin) != W_PAWN) return SQ_NONE;
  }
  return ep;
}

}  // namespace

Position::Position() {
  init_bitboards();
  Zobrist::init();
  nnue_ = &Nnue::instance();
  set_startpos();
}

void Position::clear() {
  board_.fill(NO_PIECE);
  by_color_.fill(0);
  by_type_.fill(0);
  for (auto& counts : piece_counts_) counts.fill(0);
  occupied_ = 0;
  side_ = WHITE;
  castling_ = NO_CASTLING;
  ep_square_ = SQ_NONE;
  halfmove_ = 0;
  fullmove_ = 1;
  key_ = 0;
  pawn_key_ = 0;
  nonpawn_key_ = 0;
  checkers_ = 0;
  blockers_for_king_ = 0;
  blockers_valid_ = false;
  attacks_cache_.fill(0);
  attacks_valid_ = false;
  history_keys_.clear();
  history_keys_.reserve(512);
  repetition_start_ = 0;
  nnue_live_ = false;
  nnue_acc_ = {};
}

void Position::put_piece(Piece pc, Square s) {
  attacks_valid_ = false;
  nnue_acc_.threats_valid = false;
  board_[s] = pc;
  Bitboard b = square_bb(s);
  by_color_[color_of(pc)] |= b;
  by_type_[type_of(pc)] |= b;
  ++piece_counts_[color_of(pc)][type_of(pc)];
  occupied_ |= b;
  const PieceType pt = type_of(pc);
  if (pt == PAWN) pawn_key_ ^= Zobrist::psq[pc][s];
  else if (pt != KING) nonpawn_key_ ^= Zobrist::psq[pc][s];
  if (nnue_live_ && nnue_ && nnue_->is_enabled()) nnue_->add_piece(nnue_acc_, pc, s);
}

void Position::remove_piece(Square s) {
  attacks_valid_ = false;
  nnue_acc_.threats_valid = false;
  Piece pc = board_[s];
  Bitboard b = square_bb(s);
  by_color_[color_of(pc)] &= ~b;
  by_type_[type_of(pc)] &= ~b;
  occupied_ &= ~b;
  board_[s] = NO_PIECE;
  if (pc != NO_PIECE) {
    const PieceType pt = type_of(pc);
    --piece_counts_[color_of(pc)][pt];
    if (pt == PAWN) pawn_key_ ^= Zobrist::psq[pc][s];
    else if (pt != KING) nonpawn_key_ ^= Zobrist::psq[pc][s];
  }
  if (nnue_live_ && nnue_ && nnue_->is_enabled() && pc != NO_PIECE)
    nnue_->remove_piece(nnue_acc_, pc, s);
}

void Position::move_piece(Square from, Square to) {
  attacks_valid_ = false;
  nnue_acc_.threats_valid = false;
  Piece pc = board_[from];
  const PieceType pt = type_of(pc);
  bool refresh_halfkp =
      nnue_ && nnue_->uses_king_buckets() && pt == KING;
  if (nnue_live_ && nnue_ && nnue_->is_enabled() && !refresh_halfkp) {
    nnue_->remove_piece(nnue_acc_, pc, from);
    nnue_->add_piece(nnue_acc_, pc, to);
  }
  if (pt == PAWN)
    pawn_key_ ^= Zobrist::psq[pc][from] ^ Zobrist::psq[pc][to];
  else if (pt != KING)
    nonpawn_key_ ^= Zobrist::psq[pc][from] ^ Zobrist::psq[pc][to];
  Bitboard from_to = square_bb(from) | square_bb(to);
  by_color_[color_of(pc)] ^= from_to;
  by_type_[type_of(pc)] ^= from_to;
  occupied_ ^= from_to;
  board_[to] = pc;
  board_[from] = NO_PIECE;
  if (refresh_halfkp) nnue_->update_king_move(nnue_acc_, *this, pc, from, to);
}

void Position::set_nnue(Nnue* nnue) {
  nnue_ = nnue ? nnue : &Nnue::instance();
  refresh_nnue();
}

void Position::refresh_nnue() {
  if (nnue_ && nnue_->is_enabled()) {
    nnue_->refresh(*this, nnue_acc_);
    nnue_live_ = true;
  } else {
    nnue_live_ = false;
  }
}

void Position::set_startpos() {
  set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
}

void Position::set_fen(const std::string& fen) {
  clear();
  std::istringstream ss(fen);
  std::string board, stm, castle, ep;
  int parsed_halfmove = 0;
  int parsed_fullmove = 1;
  if (!(ss >> board >> stm >> castle >> ep >> parsed_halfmove >> parsed_fullmove) || board.empty() ||
      parsed_halfmove < 0 || parsed_fullmove < 1)
    throw std::runtime_error("invalid fen fields");
  if (stm != "w" && stm != "b") throw std::runtime_error("invalid fen side");

  int file = 0;
  int rank = 7;
  for (char c : board) {
    if (c == '/') {
      if (file != 8 || rank == 0) throw std::runtime_error("invalid fen board");
      file = 0;
      --rank;
      continue;
    }
    if (std::isdigit(static_cast<unsigned char>(c))) {
      const int empty = c - '0';
      if (empty < 1 || empty > 8 || file + empty > 8) throw std::runtime_error("invalid fen board");
      file += empty;
      continue;
    }
    const char* p = std::strchr(PieceChars, c);
    if (!p) throw std::runtime_error("invalid fen piece");
    if (file >= 8) throw std::runtime_error("invalid fen board");
    put_piece(static_cast<Piece>(p - PieceChars), make_square(file, rank));
    ++file;
  }
  if (rank != 0 || file != 8) throw std::runtime_error("invalid fen board");

  side_ = stm == "b" ? BLACK : WHITE;

  castling_ = NO_CASTLING;
  if (castle != "-") {
    for (char right : castle) {
      if (right == 'K') castling_ |= WHITE_OO;
      else if (right == 'Q') castling_ |= WHITE_OOO;
      else if (right == 'k') castling_ |= BLACK_OO;
      else if (right == 'q') castling_ |= BLACK_OOO;
      else throw std::runtime_error("invalid fen castling");
    }
  }

  ep_square_ = ep == "-" ? SQ_NONE : string_to_square(ep);
  if (ep != "-" && ep_square_ == SQ_NONE) throw std::runtime_error("invalid fen en passant");
  validate_kings_and_castling(*this, castling_);
  ep_square_ = canonicalize_ep(*this, ep_square_, side_);
  halfmove_ = parsed_halfmove;
  fullmove_ = parsed_fullmove;
  key_ = compute_key();
  update_checkers();
  history_keys_.push_back(key_);
  refresh_nnue();
}

std::string Position::fen() const {
  std::ostringstream ss;
  for (int r = 7; r >= 0; --r) {
    int empty = 0;
    for (int f = 0; f < 8; ++f) {
      Piece pc = board_[make_square(f, r)];
      if (pc == NO_PIECE) {
        ++empty;
      } else {
        if (empty) {
          ss << empty;
          empty = 0;
        }
        ss << PieceChars[pc];
      }
    }
    if (empty) ss << empty;
    if (r) ss << '/';
  }
  ss << (side_ == WHITE ? " w " : " b ");
  std::string cr;
  if (castling_ & WHITE_OO) cr += 'K';
  if (castling_ & WHITE_OOO) cr += 'Q';
  if (castling_ & BLACK_OO) cr += 'k';
  if (castling_ & BLACK_OOO) cr += 'q';
  ss << (cr.empty() ? "-" : cr) << ' ';
  ss << (ep_square_ == SQ_NONE ? "-" : square_to_string(ep_square_)) << ' ';
  ss << halfmove_ << ' ' << fullmove_;
  return ss.str();
}

Key Position::compute_key() const {
  Key k = 0;
  for (int sq = 0; sq < SQUARE_NB; ++sq) {
    Piece pc = board_[sq];
    if (pc != NO_PIECE) k ^= Zobrist::psq[pc][sq];
  }
  if (side_ == BLACK) k ^= Zobrist::side;
  k ^= Zobrist::castling[castling_];
  if (ep_square_ != SQ_NONE) k ^= Zobrist::enpassant[file_of(ep_square_)];
  return k;
}

void Position::update_checkers() {
  checkers_ = attackers_to(king_square(side_)) & pieces(~side_);
  blockers_valid_ = false;
  attacks_valid_ = false;
}

Bitboard Position::attacks(Color c) const {
  if (!attacks_valid_) {
    const Bitboard occ = occupied_;
    for (int color = 0; color < COLOR_NB; ++color) {
      const Color side = static_cast<Color>(color);
      Bitboard attacks = (side == WHITE) ? (shift_ne(pieces(side, PAWN)) | shift_nw(pieces(side, PAWN)))
                                         : (shift_se(pieces(side, PAWN)) | shift_sw(pieces(side, PAWN)));
      Bitboard bb = pieces(side, KNIGHT);
      while (bb) attacks |= knight_attacks_bb(pop_lsb(bb));
      bb = pieces(side, BISHOP) | pieces(side, QUEEN);
      while (bb) attacks |= bishop_attacks_bb(pop_lsb(bb), occ);
      bb = pieces(side, ROOK) | pieces(side, QUEEN);
      while (bb) attacks |= rook_attacks_bb(pop_lsb(bb), occ);
      attacks |= king_attacks_bb(king_square(side));
      attacks_cache_[color] = attacks;
    }
    attacks_valid_ = true;
  }
  return attacks_cache_[c];
}

Bitboard Position::compute_blockers_for_king() const {
  const Color us = side_;
  const Square king = king_square(us);
  const Bitboard occupied = occupied_;
  Bitboard pinned = 0;
  Bitboard snipers = (bishop_attacks_bb(king, 0) & (pieces(~us, BISHOP) | pieces(~us, QUEEN))) |
                     (rook_attacks_bb(king, 0) & (pieces(~us, ROOK) | pieces(~us, QUEEN)));
  while (snipers) {
    const Square sniper = pop_lsb(snipers);
    const Bitboard blockers = between_bb(king, sniper) & occupied;
    if (popcount(blockers) == 1 && (blockers & pieces(us))) pinned |= blockers;
  }
  return pinned;
}

Bitboard Position::blockers_for_king() const {
  if (!blockers_valid_) {
    blockers_for_king_ = compute_blockers_for_king();
    blockers_valid_ = true;
  }
  return blockers_for_king_;
}

Bitboard Position::attackers_to(Square s, Bitboard occ) const {
  return (pawn_attacks_bb(WHITE, s) & pieces(BLACK, PAWN)) |
         (pawn_attacks_bb(BLACK, s) & pieces(WHITE, PAWN)) |
         (knight_attacks_bb(s) & pieces(KNIGHT)) |
         (bishop_attacks_bb(s, occ) & (pieces(BISHOP) | pieces(QUEEN))) |
         (rook_attacks_bb(s, occ) & (pieces(ROOK) | pieces(QUEEN))) |
         (king_attacks_bb(s) & pieces(KING));
}

bool Position::is_square_attacked(Square s, Color by, Bitboard occ) const {
  if (pawn_attacks_bb(~by, s) & pieces(by, PAWN)) return true;
  if (knight_attacks_bb(s) & pieces(by, KNIGHT)) return true;
  if (king_attacks_bb(s) & pieces(by, KING)) return true;
  if (bishop_attacks_bb(s, occ) & (pieces(by, BISHOP) | pieces(by, QUEEN))) return true;
  if (rook_attacks_bb(s, occ) & (pieces(by, ROOK) | pieces(by, QUEEN))) return true;
  return false;
}

bool Position::is_capture(Move m) const {
  return m.is_capture() || m.is_ep();
}

bool Position::is_draw() const {
  if (halfmove_ >= 100) return true;

  if (!(pieces(PAWN) | pieces(ROOK) | pieces(QUEEN))) {
    int knights = piece_counts_[WHITE][KNIGHT] + piece_counts_[BLACK][KNIGHT];
    int bishops = piece_counts_[WHITE][BISHOP] + piece_counts_[BLACK][BISHOP];
    if (knights + bishops <= 1) return true;
    if (knights == 0) {
      constexpr Bitboard DarkSquares = 0xAA55AA55AA55AA55ULL;
      Bitboard bishop_squares = pieces(BISHOP);
      if (!(bishop_squares & DarkSquares) || !(bishop_squares & ~DarkSquares)) return true;
    }
  }

  int reps = 1;
  int current = static_cast<int>(history_keys_.size()) - 1;
  int earliest = std::max(static_cast<int>(repetition_start_), current - halfmove_);
  for (int i = current - 2; i >= earliest; i -= 2) {
    if (history_keys_[i] == key_ && ++reps >= 3) return true;
  }
  return false;
}

void Position::do_move(Move m, StateInfo& st) {
  st.castling = castling_;
  st.ep_square = ep_square_;
  st.halfmove_clock = halfmove_;
  st.captured = NO_PIECE;
  st.key = key_;
  st.checkers = checkers_;
  st.repetition_start = repetition_start_;

  key_ ^= Zobrist::side;
  if (ep_square_ != SQ_NONE) {
    key_ ^= Zobrist::enpassant[file_of(ep_square_)];
    ep_square_ = SQ_NONE;
  }

  Square from = m.from();
  Square to = m.to();
  Piece pc = board_[from];
  Color us = side_;
  Color them = ~us;

  ++halfmove_;
  if (type_of(pc) == PAWN || m.is_capture() || m.is_ep()) halfmove_ = 0;

  if (m.is_castle()) {
    bool kingside = file_of(to) > file_of(from);
    Square rfrom = kingside ? (us == WHITE ? SQ_H1 : SQ_H8) : (us == WHITE ? SQ_A1 : SQ_A8);
    Square rto = kingside ? (us == WHITE ? SQ_F1 : SQ_F8) : (us == WHITE ? SQ_D1 : SQ_D8);
    key_ ^= Zobrist::psq[pc][from] ^ Zobrist::psq[pc][to];
    move_piece(from, to);
    Piece rook = board_[rfrom];
    key_ ^= Zobrist::psq[rook][rfrom] ^ Zobrist::psq[rook][rto];
    move_piece(rfrom, rto);
  } else {
    if (m.is_ep()) {
      Square cap_sq = static_cast<Square>(to + (us == WHITE ? -8 : 8));
      st.captured = board_[cap_sq];
      key_ ^= Zobrist::psq[st.captured][cap_sq];
      remove_piece(cap_sq);
    } else if (board_[to] != NO_PIECE) {
      st.captured = board_[to];
      key_ ^= Zobrist::psq[st.captured][to];
      remove_piece(to);
    }

    key_ ^= Zobrist::psq[pc][from];
    move_piece(from, to);

    if (m.is_promotion()) {
      remove_piece(to);
      Piece promo = make_piece(us, m.promotion());
      put_piece(promo, to);
      key_ ^= Zobrist::psq[promo][to];
    } else {
      key_ ^= Zobrist::psq[pc][to];
    }

    if (m.is_double_push()) {
      ep_square_ = static_cast<Square>((from + to) / 2);
      key_ ^= Zobrist::enpassant[file_of(ep_square_)];
    }
  }

  key_ ^= Zobrist::castling[castling_];
  castling_ &= ~castling_mask_for_square(from);
  castling_ &= ~castling_mask_for_square(to);
  if (st.captured != NO_PIECE) castling_ &= ~castling_mask_for_square(to);
  key_ ^= Zobrist::castling[castling_];
  if (type_of(pc) == PAWN || st.captured != NO_PIECE || m.is_ep() || castling_ != st.castling)
    repetition_start_ = history_keys_.size();

  side_ = them;
  if (us == BLACK) ++fullmove_;

  update_checkers();
  history_keys_.push_back(key_);
}

void Position::undo_move(Move m, const StateInfo& st) {
  history_keys_.pop_back();
  side_ = ~side_;
  if (side_ == BLACK) --fullmove_;

  Square from = m.from();
  Square to = m.to();
  Color us = side_;

  castling_ = st.castling;
  ep_square_ = st.ep_square;
  halfmove_ = st.halfmove_clock;
  key_ = st.key;
  checkers_ = st.checkers;
  blockers_valid_ = false;
  attacks_valid_ = false;
  repetition_start_ = st.repetition_start;

  if (m.is_castle()) {
    bool kingside = file_of(to) > file_of(from);
    Square rfrom = kingside ? (us == WHITE ? SQ_H1 : SQ_H8) : (us == WHITE ? SQ_A1 : SQ_A8);
    Square rto = kingside ? (us == WHITE ? SQ_F1 : SQ_F8) : (us == WHITE ? SQ_D1 : SQ_D8);
    move_piece(to, from);
    move_piece(rto, rfrom);
    return;
  }

  if (m.is_promotion()) {
    remove_piece(to);
    put_piece(make_piece(us, PAWN), to);
  }

  move_piece(to, from);

  if (m.is_ep()) {
    Square cap_sq = static_cast<Square>(to + (us == WHITE ? -8 : 8));
    put_piece(st.captured, cap_sq);
  } else if (st.captured != NO_PIECE) {
    put_piece(st.captured, to);
  }
}

void Position::do_null_move(StateInfo& st) {
  st.castling = castling_;
  st.ep_square = ep_square_;
  st.halfmove_clock = halfmove_;
  st.captured = NO_PIECE;
  st.key = key_;
  st.checkers = checkers_;

  key_ ^= Zobrist::side;
  if (ep_square_ != SQ_NONE) {
    key_ ^= Zobrist::enpassant[file_of(ep_square_)];
    ep_square_ = SQ_NONE;
  }
  // A null move is a search-only state transition. It must not advance
  // game-rule clocks or enter the repetition history: otherwise a null move
  // from halfmove 99 can manufacture a fifty-move draw.
  side_ = ~side_;
  checkers_ = 0;
  blockers_valid_ = false;
  attacks_valid_ = false;
  nnue_acc_.threats_valid = false;
}

void Position::undo_null_move(const StateInfo& st) {
  side_ = ~side_;
  castling_ = st.castling;
  ep_square_ = st.ep_square;
  halfmove_ = st.halfmove_clock;
  key_ = st.key;
  checkers_ = st.checkers;
  blockers_valid_ = false;
  attacks_valid_ = false;
  nnue_acc_.threats_valid = false;
}

}  // namespace nsce
