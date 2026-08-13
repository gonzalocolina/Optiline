#pragma once

#include <cstdint>
#include <string>

namespace nsce {

using Bitboard = uint64_t;
using Key = uint64_t;

enum Color : int { WHITE = 0, BLACK = 1, COLOR_NB = 2 };

inline Color operator~(Color c) { return c == WHITE ? BLACK : WHITE; }

enum PieceType : int {
  PAWN = 0,
  KNIGHT = 1,
  BISHOP = 2,
  ROOK = 3,
  QUEEN = 4,
  KING = 5,
  PIECE_TYPE_NB = 6,
  NO_PIECE_TYPE = 7
};

enum Piece : int {
  W_PAWN = 0,
  W_KNIGHT,
  W_BISHOP,
  W_ROOK,
  W_QUEEN,
  W_KING,
  B_PAWN,
  B_KNIGHT,
  B_BISHOP,
  B_ROOK,
  B_QUEEN,
  B_KING,
  NO_PIECE = 12
};

inline Piece make_piece(Color c, PieceType pt) {
  return static_cast<Piece>(static_cast<int>(c) * 6 + static_cast<int>(pt));
}

inline Color color_of(Piece pc) { return pc < B_PAWN ? WHITE : BLACK; }

inline PieceType type_of(Piece pc) {
  return static_cast<PieceType>(static_cast<int>(pc) % 6);
}

enum Square : int {
  SQ_A1, SQ_B1, SQ_C1, SQ_D1, SQ_E1, SQ_F1, SQ_G1, SQ_H1,
  SQ_A2, SQ_B2, SQ_C2, SQ_D2, SQ_E2, SQ_F2, SQ_G2, SQ_H2,
  SQ_A3, SQ_B3, SQ_C3, SQ_D3, SQ_E3, SQ_F3, SQ_G3, SQ_H3,
  SQ_A4, SQ_B4, SQ_C4, SQ_D4, SQ_E4, SQ_F4, SQ_G4, SQ_H4,
  SQ_A5, SQ_B5, SQ_C5, SQ_D5, SQ_E5, SQ_F5, SQ_G5, SQ_H5,
  SQ_A6, SQ_B6, SQ_C6, SQ_D6, SQ_E6, SQ_F6, SQ_G6, SQ_H6,
  SQ_A7, SQ_B7, SQ_C7, SQ_D7, SQ_E7, SQ_F7, SQ_G7, SQ_H7,
  SQ_A8, SQ_B8, SQ_C8, SQ_D8, SQ_E8, SQ_F8, SQ_G8, SQ_H8,
  SQ_NONE = 64,
  SQUARE_NB = 64
};

inline Square make_square(int file, int rank) {
  return static_cast<Square>(rank * 8 + file);
}

inline int file_of(Square s) { return static_cast<int>(s) & 7; }
inline int rank_of(Square s) { return static_cast<int>(s) >> 3; }

enum CastlingRights : int {
  NO_CASTLING = 0,
  WHITE_OO = 1,
  WHITE_OOO = 2,
  BLACK_OO = 4,
  BLACK_OOO = 8,
  ANY_CASTLING = 15
};

inline CastlingRights operator|(CastlingRights a, CastlingRights b) {
  return static_cast<CastlingRights>(static_cast<int>(a) | static_cast<int>(b));
}

inline CastlingRights& operator|=(CastlingRights& a, CastlingRights b) {
  return a = a | b;
}

inline CastlingRights operator&(CastlingRights a, CastlingRights b) {
  return static_cast<CastlingRights>(static_cast<int>(a) & static_cast<int>(b));
}

inline CastlingRights& operator&=(CastlingRights& a, int b) {
  return a = static_cast<CastlingRights>(static_cast<int>(a) & b);
}

enum MoveFlags : int {
  MF_NONE = 0,
  MF_CAPTURE = 1,
  MF_DOUBLE = 2,
  MF_EP = 4,
  MF_CASTLE = 8,
  MF_PROMO = 16
};

static_assert(NO_PIECE_TYPE < 16, "Move promotion field is four bits");
static_assert((MF_CAPTURE | MF_DOUBLE | MF_EP | MF_CASTLE | MF_PROMO) < 256,
              "Move flags field is eight bits");

struct Move {
  static constexpr int kEncodingBits = 24;
  static constexpr uint32_t kEncodingMask = (1U << kEncodingBits) - 1;

  uint32_t raw = 0;

  Move() = default;
  explicit Move(uint32_t r) : raw(r) {}

  static Move make(Square from, Square to, PieceType promo = NO_PIECE_TYPE, int flags = 0) {
    return Move{static_cast<uint32_t>(from) | (static_cast<uint32_t>(to) << 6) |
                (static_cast<uint32_t>(promo) << 12) | (static_cast<uint32_t>(flags) << 16)};
  }

  Square from() const { return static_cast<Square>(raw & 63); }
  Square to() const { return static_cast<Square>((raw >> 6) & 63); }
  PieceType promotion() const { return static_cast<PieceType>((raw >> 12) & 15); }
  int flags() const { return static_cast<int>((raw >> 16) & 0xFF); }

  bool is_capture() const { return flags() & MF_CAPTURE; }
  bool is_double_push() const { return flags() & MF_DOUBLE; }
  bool is_ep() const { return flags() & MF_EP; }
  bool is_castle() const { return flags() & MF_CASTLE; }
  bool is_promotion() const { return flags() & MF_PROMO; }

  bool operator==(Move o) const { return raw == o.raw; }
  bool operator!=(Move o) const { return raw != o.raw; }
  explicit operator bool() const { return raw != 0; }
};

constexpr int MAX_MOVES = 256;
constexpr int VALUE_MATE = 32000;
constexpr int VALUE_DRAW = 0;
constexpr int VALUE_INFINITE = 32001;
constexpr int VALUE_NONE = 32002;

inline int mate_in(int ply) { return VALUE_MATE - ply; }
inline int mated_in(int ply) { return -VALUE_MATE + ply; }

inline std::string square_to_string(Square s) {
  return std::string{static_cast<char>('a' + file_of(s)), static_cast<char>('1' + rank_of(s))};
}

inline Square string_to_square(const std::string& s) {
  if (s.size() < 2) return SQ_NONE;
  int f = s[0] - 'a';
  int r = s[1] - '1';
  if (f < 0 || f > 7 || r < 0 || r > 7) return SQ_NONE;
  return make_square(f, r);
}

}  // namespace nsce
