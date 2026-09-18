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

// Pawn-only terms of extras(): doubled, passed (+ supported), isolated. They
// depend on the two pawn bitboards alone, so they are memoised per thread by
// the position's pawn key. The full 64-bit key is verified, so a hit returns
// exactly what recomputing would.
int pawn_structure(Bitboard wp, Bitboard bp) {
  int score = 0;
  const Bitboard w_pawn_att = shift_ne(wp) | shift_nw(wp);
  const Bitboard b_pawn_att = shift_se(bp) | shift_sw(bp);

  constexpr int kPassed[8] = {0, 8, 12, 20, 35, 60, 100, 0};
  for (int file = 0; file < 8; ++file) {
    const Bitboard file_bb = FileBB[file];
    const int wc = popcount(wp & file_bb);
    const int bc = popcount(bp & file_bb);
    if (wc > 1) score -= 12 * (wc - 1);
    if (bc > 1) score += 12 * (bc - 1);
  }
  Bitboard wpc = wp;
  while (wpc) {
    Square sq = pop_lsb(wpc);
    const int file = file_of(sq);
    const int rank = rank_of(sq);
    Bitboard span = FileBB[file];
    if (file > 0) span |= FileBB[file - 1];
    if (file < 7) span |= FileBB[file + 1];
    const Bitboard ahead = rank < 7 ? ~((1ULL << ((rank + 1) * 8)) - 1) : 0;
    if (!(bp & span & ahead)) {
      score += kPassed[rank];
      if (w_pawn_att & square_bb(sq)) score += kPassed[rank] / 4;
    }
    Bitboard adj = 0;
    if (file > 0) adj |= FileBB[file - 1];
    if (file < 7) adj |= FileBB[file + 1];
    if (!(wp & adj)) score -= 10;
  }
  Bitboard bpc = bp;
  while (bpc) {
    Square sq = pop_lsb(bpc);
    const int file = file_of(sq);
    const int rank = rank_of(sq);
    Bitboard span = FileBB[file];
    if (file > 0) span |= FileBB[file - 1];
    if (file < 7) span |= FileBB[file + 1];
    const Bitboard ahead = rank > 0 ? ((1ULL << (rank * 8)) - 1) : 0;
    if (!(wp & span & ahead)) {
      score -= kPassed[7 - rank];
      if (b_pawn_att & square_bb(sq)) score -= kPassed[7 - rank] / 4;
    }
    Bitboard adj = 0;
    if (file > 0) adj |= FileBB[file - 1];
    if (file < 7) adj |= FileBB[file + 1];
    if (!(bp & adj)) score += 10;
  }
  return score;
}

struct PawnCacheEntry {
  Key key = 0;
  int score = 0;
  bool valid = false;
};
constexpr std::size_t kPawnCacheSize = 8192;  // 8192 × 16 B = 128 KiB per thread
thread_local PawnCacheEntry pawn_cache[kPawnCacheSize];

int cached_pawn_structure(const Position& pos, Bitboard wp, Bitboard bp) {
  const Key key = pos.pawn_key();
  PawnCacheEntry& entry = pawn_cache[key & (kPawnCacheSize - 1)];
  if (entry.valid && entry.key == key) return entry.score;
  entry.key = key;
  entry.score = pawn_structure(wp, bp);
  entry.valid = true;
  return entry.score;
}

int extras_structure(const Position& pos) {
  int score = 10;  // tempo for the side that will move, applied in white-POV then flipped

  const Bitboard wp = pos.pieces(WHITE, PAWN);
  const Bitboard bp = pos.pieces(BLACK, PAWN);

  if (popcount(pos.pieces(WHITE, BISHOP)) >= 2) score += 35;
  if (popcount(pos.pieces(BLACK, BISHOP)) >= 2) score -= 35;

  score += cached_pawn_structure(pos, wp, bp);

  auto shield = [&](Color c) {
    Square king = pos.king_square(c);
    const int file = file_of(king);
    Bitboard files = FileBB[file];
    if (file > 0) files |= FileBB[file - 1];
    if (file < 7) files |= FileBB[file + 1];
    const Bitboard rank = (c == WHITE) ? Rank2BB : Rank7BB;
    return popcount(pos.pieces(c, PAWN) & files & rank);
  };
  score += 12 * (shield(WHITE) - shield(BLACK));
  return score;
}

int extras_tactical(const Position& pos) {
  int score = 0;
  const Bitboard wp = pos.pieces(WHITE, PAWN);
  const Bitboard bp = pos.pieces(BLACK, PAWN);
  const Bitboard occ = pos.occupied();
  const Bitboard w_pawn_att = shift_ne(wp) | shift_nw(wp);
  const Bitboard b_pawn_att = shift_se(bp) | shift_sw(bp);

  int mobility[COLOR_NB]{};
  Bitboard att[COLOR_NB]{w_pawn_att, b_pawn_att};
  for (int c = 0; c < COLOR_NB; ++c) {
    const Color us = static_cast<Color>(c);
    const Bitboard enemy_pawn_att = (us == WHITE) ? b_pawn_att : w_pawn_att;
    const Bitboard usable = ~pos.pieces(us) & ~enemy_pawn_att;
    Bitboard kn = pos.pieces(us, KNIGHT);
    while (kn) {
      const Bitboard a = knight_attacks_bb(pop_lsb(kn));
      att[us] |= a;
      mobility[us] += 4 * popcount(a & usable);
    }
    Bitboard bi = pos.pieces(us, BISHOP);
    while (bi) {
      const Bitboard a = bishop_attacks_bb(pop_lsb(bi), occ);
      att[us] |= a;
      mobility[us] += 3 * popcount(a & usable);
    }
    Bitboard ro = pos.pieces(us, ROOK);
    while (ro) {
      const Square s = pop_lsb(ro);
      const Bitboard a = rook_attacks_bb(s, occ);
      att[us] |= a;
      mobility[us] += 2 * popcount(a & ~pos.pieces(us));
      const Bitboard file = FileBB[file_of(s)];
      const bool own_pawn = pos.pieces(us, PAWN) & file;
      const bool their_pawn = pos.pieces(~us, PAWN) & file;
      if (!own_pawn && !their_pawn) mobility[us] += 18;
      else if (!own_pawn) mobility[us] += 8;
      if ((us == WHITE && rank_of(s) >= 6) || (us == BLACK && rank_of(s) <= 1)) mobility[us] += 12;
    }
    Bitboard q = pos.pieces(us, QUEEN);
    while (q) {
      const Bitboard a = queen_attacks_bb(pop_lsb(q), occ);
      att[us] |= a;
      mobility[us] += popcount(a & ~pos.pieces(us));
    }
    att[us] |= king_attacks_bb(pos.king_square(us));
  }
  score += mobility[WHITE] - mobility[BLACK];

  auto outpost = [&](Color c, Bitboard our_pawn_att, Bitboard enemy_pawn_att) {
    int s = 0;
    const Bitboard minors = (pos.pieces(c, KNIGHT) | pos.pieces(c, BISHOP)) & our_pawn_att & ~enemy_pawn_att;
    Bitboard bb = minors;
    while (bb) {
      Square sq = pop_lsb(bb);
      const int r = rank_of(sq);
      if ((c == WHITE && r >= 4) || (c == BLACK && r <= 3))
        s += type_of(pos.piece_on(sq)) == KNIGHT ? 16 : 10;
    }
    return s;
  };
  score += outpost(WHITE, w_pawn_att, b_pawn_att) - outpost(BLACK, b_pawn_att, w_pawn_att);

  const Bitboard w_att = att[WHITE];
  const Bitboard b_att = att[BLACK];
  score -= 10 * popcount(king_attacks_bb(pos.king_square(WHITE)) & b_att);
  score += 10 * popcount(king_attacks_bb(pos.king_square(BLACK)) & w_att);

  const Bitboard w_hang = pos.pieces(WHITE) & ~pos.pieces(WHITE, KING) & ~pos.pieces(WHITE, PAWN) &
                          b_att & ~w_att;
  const Bitboard b_hang = pos.pieces(BLACK) & ~pos.pieces(BLACK, KING) & ~pos.pieces(BLACK, PAWN) &
                          w_att & ~b_att;
  score -= 12 * popcount(w_hang);
  score += 12 * popcount(b_hang);

  return score;
}

int extras(const Position& pos) { return extras_structure(pos) + extras_tactical(pos); }

int stm_sign(const Position& pos, int white_score) {
  return pos.side_to_move() == WHITE ? white_score : -white_score;
}

// Chess768 already sees piece lists. Slider mobility is ~20 % of every 768 node
// and fights a dual-perspective net trained on the full search coin. Keep a
// cheap faded structure nudge in close games; skip it once material is decided.
int per1_extras_white(const Position& pos) {
  const int n = popcount(pos.occupied());
  const int fade = std::max(0, n - 8);
  if (fade == 0) return 0;
  return extras_structure(pos) * fade / 96;
}

int finish_per1(const Position& pos, int nnue) {
  const int simple = simple_eval(pos);
  int v = nnue;
  if (std::abs(simple) >= kPer1SimpleSkip) {
    v = (3 * nnue + simple) / 4;
  } else if (pos.use_extras()) {
    v += stm_sign(pos, per1_extras_white(pos));
  }
  return clamp_eval(v);
}

}  // namespace

thread_local bool legacy_use_extras = true;

void set_use_extras(bool on) { legacy_use_extras = on; }
bool use_extras() { return legacy_use_extras; }

int evaluate(const Position& pos) {
  if (pos.nnue().is_enabled()) {
    const int nnue = pos.nnue().evaluate(pos);
    if (pos.nnue().uses_per1()) return finish_per1(pos, nnue);
    // Trained king-bucket nets already see structure/threats; HCE extras fight the net.
    if (pos.nnue().uses_king_buckets() || !pos.use_extras()) return nnue;
    return nnue + stm_sign(pos, extras(pos));
  }
  int score = extras(pos);
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

int evaluate_nnue(const Position& pos) {
  return pos.nnue().is_enabled() ? pos.nnue().evaluate(pos) : 0;
}

int classical_extras(const Position& pos) { return stm_sign(pos, extras(pos)); }

int applied_extras(const Position& pos) {
  if (pos.nnue().is_enabled() && pos.nnue().uses_per1()) {
    if (std::abs(simple_eval(pos)) >= kPer1SimpleSkip || !pos.use_extras()) return 0;
    return stm_sign(pos, per1_extras_white(pos));
  }
  if (pos.nnue().is_enabled() && (pos.nnue().uses_king_buckets() || !pos.use_extras())) return 0;
  return stm_sign(pos, extras(pos));
}

int simple_eval(const Position& pos) {
  int score = 0;
  for (PieceType pt : {PAWN, KNIGHT, BISHOP, ROOK, QUEEN}) {
    score += piece_value(pt) * (pos.piece_count(WHITE, pt) - pos.piece_count(BLACK, pt));
  }
  return stm_sign(pos, score);
}

int piece_value(PieceType pt) {
  return PieceValue[pt];
}

int non_pawn_material(const Position& pos, Color c) {
  int npm = 0;
  for (PieceType pt : {KNIGHT, BISHOP, ROOK, QUEEN}) {
    npm += piece_value(pt) * pos.piece_count(c, pt);
  }
  return npm;
}

}  // namespace nsce
