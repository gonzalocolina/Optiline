#include "nsce/datagen.hpp"

#include "nsce/bitboard.hpp"
#include "nsce/eval.hpp"
#include "nsce/movegen.hpp"
#include "nsce/nnue.hpp"
#include "nsce/search.hpp"
#include "nsce/zobrist.hpp"

#include <algorithm>
#include <atomic>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <vector>

namespace nsce {
namespace {

#pragma pack(push, 1)
struct BulletChessBoard {
  uint64_t occ;
  uint8_t pcs[16];
  int16_t score;
  uint8_t result;
  uint8_t ksq;
  uint8_t opp_ksq;
  uint8_t extra[3];
};
#pragma pack(pop)
static_assert(sizeof(BulletChessBoard) == 32, "bulletformat ChessBoard is 32 bytes");

struct PendingRecord {
  uint64_t bbs[8];  // white, black, pawn, knight, bishop, rook, queen, king
  int stm;          // 0 white, 1 black
  int16_t score_white;
  std::string fen;  // only filled for text output
};

uint64_t byteswap64(uint64_t v) {
#if defined(__GNUC__) || defined(__clang__)
  return __builtin_bswap64(v);
#else
  uint64_t r = 0;
  for (int i = 0; i < 8; ++i) r |= ((v >> (8 * i)) & 0xFF) << (56 - 8 * i);
  return r;
#endif
}

// Mirrors bulletformat::ChessBoard::from_raw exactly.
BulletChessBoard to_bullet(const PendingRecord& rec, float result_white) {
  uint64_t bbs[8];
  std::memcpy(bbs, rec.bbs, sizeof(bbs));
  int score = rec.score_white;
  float result = result_white;
  if (rec.stm == 1) {
    for (uint64_t& bb : bbs) bb = byteswap64(bb);
    std::swap(bbs[0], bbs[1]);
    score = -score;
    result = 1.0f - result;
  }
  BulletChessBoard out{};
  out.occ = bbs[0] | bbs[1];
  uint64_t occ = out.occ;
  int idx = 0;
  while (occ) {
    const int sq = std::countr_zero(occ);
    const uint64_t bit = 1ULL << sq;
    occ &= occ - 1;
    const uint8_t colour = static_cast<uint8_t>((bit & bbs[1]) ? 1 : 0) << 3;
    uint8_t piece = 0;
    for (int p = 0; p < 6; ++p)
      if (bit & bbs[2 + p]) {
        piece = static_cast<uint8_t>(p);
        break;
      }
    const uint8_t pc = colour | piece;
    out.pcs[idx / 2] |= static_cast<uint8_t>(pc << (4 * (idx & 1)));
    ++idx;
  }
  out.score = static_cast<int16_t>(score);
  out.result = static_cast<uint8_t>(2.0f * result);
  out.ksq = static_cast<uint8_t>(std::countr_zero(bbs[0] & bbs[7]));
  out.opp_ksq = static_cast<uint8_t>(std::countr_zero(bbs[1] & bbs[7]) ^ 56);
  return out;
}

void fill_bitboards(const Position& pos, uint64_t bbs[8]) {
  bbs[0] = pos.pieces(WHITE);
  bbs[1] = pos.pieces(BLACK);
  for (int pt = 0; pt < 6; ++pt) bbs[2 + pt] = pos.pieces(static_cast<PieceType>(pt));
}

enum class GameEnd { None, WhiteWins, BlackWins, Draw, Discard };

constexpr std::size_t kWriteBufBytes = 1 << 20;

struct Shared {
  std::mutex out_mutex;
  std::ofstream out;
  std::vector<char> file_buf;
  std::atomic<uint64_t> games{0};
  std::atomic<uint64_t> positions{0};
  std::atomic<uint64_t> discarded{0};
  std::atomic<uint64_t> wins{0}, draws{0}, losses{0};
  std::atomic<bool> stop{false};
};

void flush_locked(Shared& shared) { shared.out.flush(); }

void write_records(Shared& shared, std::vector<char>& buf, bool force) {
  if (buf.empty() || (!force && buf.size() < kWriteBufBytes)) return;
  std::lock_guard<std::mutex> lock(shared.out_mutex);
  shared.out.write(buf.data(), static_cast<std::streamsize>(buf.size()));
  shared.out.flush();
  buf.clear();
}

void worker(int index, const DatagenOptions& opt, Shared& shared) {
  std::mt19937_64 rng(opt.seed * 0x9E3779B97F4A7C15ULL + static_cast<uint64_t>(index) * 0xD1B54A32D192ED03ULL + 1);
  Search search;
  search.set_silent(true);
  search.set_hash_mb(static_cast<std::size_t>(opt.hash_mb));
  search.set_threads(1);
  set_use_extras(opt.use_extras);

  std::vector<PendingRecord> pending;
  pending.reserve(512);
  std::vector<char> bytes;
  bytes.reserve(1 << 16);
  std::vector<char> write_buf;
  write_buf.reserve(kWriteBufBytes);
  auto last_force = std::chrono::steady_clock::now();

  while (!shared.stop.load(std::memory_order_relaxed)) {
    const uint64_t game_index = shared.games.fetch_add(1, std::memory_order_relaxed);
    if (game_index >= static_cast<uint64_t>(opt.games)) break;

    Position pos;
    pos.set_startpos();
    pos.set_use_extras(opt.use_extras);
    pending.clear();
    // Keep TT and history across games. Clearing 16 MB every game was measurable
    // and empty history made the next 5k-node search colder. go() still ages.

    // Random opening.
    bool aborted = false;
    const int random_plies = opt.random_plies + static_cast<int>(rng() & 1);
    for (int ply = 0; ply < random_plies; ++ply) {
      MoveList legal;
      generate_legal(pos, legal);
      if (legal.size == 0 || pos.is_draw()) {
        aborted = true;
        break;
      }
      StateInfo st;
      pos.do_move(legal.moves[static_cast<int>(rng() % static_cast<uint64_t>(legal.size))], st);
    }
    if (aborted) {
      shared.discarded.fetch_add(1, std::memory_order_relaxed);
      continue;
    }

    GameEnd end = GameEnd::None;
    int resign_sign = 0, resign_streak = 0, draw_streak = 0;
    for (int ply = 0; ply < opt.max_plies && end == GameEnd::None; ++ply) {
      MoveList legal;
      generate_legal(pos, legal);
      if (legal.size == 0) {
        end = pos.in_check() ? (pos.side_to_move() == WHITE ? GameEnd::BlackWins : GameEnd::WhiteWins)
                             : GameEnd::Draw;
        break;
      }
      if (pos.is_draw()) {
        end = GameEnd::Draw;
        break;
      }

      search.set_position(pos);
      SearchLimits limits;
      limits.nodes = opt.nodes;
      const SearchInfo info = search.go(limits);
      Move best = info.best_move;
      if (!best) best = legal.moves[0];
      const int score_stm = info.score;
      const int score_white = pos.side_to_move() == WHITE ? score_stm : -score_stm;
      const bool mate_score = std::abs(score_stm) >= VALUE_MATE - 256;

      if (ply == 0 && std::abs(score_white) > opt.max_start_imbalance_cp) {
        end = GameEnd::Discard;
        break;
      }

      const bool quiet_best = !best.is_capture() && !best.is_ep() && !best.is_promotion();
      if (!pos.in_check() && quiet_best && !mate_score) {
        PendingRecord rec{};
        fill_bitboards(pos, rec.bbs);
        rec.stm = pos.side_to_move() == WHITE ? 0 : 1;
        rec.score_white = static_cast<int16_t>(std::clamp(score_white, -30000, 30000));
        if (opt.text) rec.fen = pos.fen();
        pending.push_back(std::move(rec));
      }

      // Adjudication.
      const int sign = score_white >= opt.resign_cp ? 1 : score_white <= -opt.resign_cp ? -1 : 0;
      if (sign != 0 && sign == resign_sign) ++resign_streak;
      else resign_streak = sign != 0 ? 1 : 0;
      resign_sign = sign;
      if (mate_score && std::abs(score_stm) >= VALUE_MATE - 10) {
        // Forced mate found within a few plies: play it out, the rules decide.
      } else if (resign_streak >= opt.resign_plies) {
        end = sign > 0 ? GameEnd::WhiteWins : GameEnd::BlackWins;
        break;
      }
      if (ply >= opt.draw_min_ply && std::abs(score_white) <= opt.draw_cp) ++draw_streak;
      else draw_streak = 0;
      if (draw_streak >= opt.draw_plies) {
        end = GameEnd::Draw;
        break;
      }

      StateInfo st;
      pos.do_move(best, st);
    }
    if (end == GameEnd::None) end = GameEnd::Draw;  // max_plies
    if (end == GameEnd::Discard || pending.empty()) {
      shared.discarded.fetch_add(1, std::memory_order_relaxed);
      continue;
    }

    const float result_white = end == GameEnd::WhiteWins ? 1.0f : end == GameEnd::BlackWins ? 0.0f : 0.5f;
    if (end == GameEnd::WhiteWins) shared.wins.fetch_add(1, std::memory_order_relaxed);
    else if (end == GameEnd::BlackWins) shared.losses.fetch_add(1, std::memory_order_relaxed);
    else shared.draws.fetch_add(1, std::memory_order_relaxed);

    bytes.clear();
    if (opt.text) {
      std::string text;
      for (const PendingRecord& rec : pending) {
        text += rec.fen;
        text += " | ";
        text += std::to_string(rec.score_white);
        text += " | ";
        text += result_white == 1.0f ? "1.0" : result_white == 0.0f ? "0.0" : "0.5";
        text += '\n';
      }
      bytes.assign(text.begin(), text.end());
    } else {
      bytes.resize(pending.size() * sizeof(BulletChessBoard));
      for (std::size_t i = 0; i < pending.size(); ++i) {
        const BulletChessBoard board = to_bullet(pending[i], result_white);
        std::memcpy(bytes.data() + i * sizeof(BulletChessBoard), &board, sizeof(board));
      }
    }
    write_buf.insert(write_buf.end(), bytes.begin(), bytes.end());
    const auto now = std::chrono::steady_clock::now();
    const bool aged = now - last_force >= std::chrono::seconds(5);
    write_records(shared, write_buf, aged);
    if (aged) last_force = now;
    shared.positions.fetch_add(pending.size(), std::memory_order_relaxed);
  }
  write_records(shared, write_buf, true);
}

}  // namespace

uint64_t run_datagen(const DatagenOptions& opt) {
  init_bitboards();
  Zobrist::init();
  Nnue& nnue = Nnue::instance();
  if (opt.eval_file.empty() || opt.eval_file == "internal" || opt.eval_file == "hce") {
    nnue.load_default_from_hce();
  } else if (!nnue.load(opt.eval_file)) {
    std::cerr << "datagen: cannot load EvalFile " << opt.eval_file << '\n';
    return 0;
  }
  nnue.set_enabled(true);

  Shared shared;
  shared.file_buf.resize(kWriteBufBytes);
  shared.out.rdbuf()->pubsetbuf(shared.file_buf.data(), static_cast<std::streamsize>(shared.file_buf.size()));
  shared.out.open(opt.output, std::ios::binary | std::ios::app);
  if (!shared.out) {
    std::cerr << "datagen: cannot open " << opt.output << '\n';
    return 0;
  }

  const int threads = std::max(1, opt.threads);
  std::vector<std::thread> pool;
  pool.reserve(static_cast<std::size_t>(threads));
  const auto start = std::chrono::steady_clock::now();
  for (int i = 0; i < threads; ++i) pool.emplace_back(worker, i, std::cref(opt), std::ref(shared));

  auto report = [&](bool final) {
    const double secs =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    const uint64_t positions = shared.positions.load();
    const uint64_t finished = shared.wins.load() + shared.draws.load() + shared.losses.load();
    std::cerr << (final ? "datagen done: " : "datagen: ") << finished << " games (W " << shared.wins.load()
              << " D " << shared.draws.load() << " L " << shared.losses.load() << ", discarded "
              << shared.discarded.load() << "), " << positions << " positions, "
              << static_cast<uint64_t>(positions / std::max(secs, 1e-9)) << " pos/s, "
              << static_cast<uint64_t>(secs) << " s\n";
  };
  while (shared.games.load() < static_cast<uint64_t>(opt.games)) {
    std::this_thread::sleep_for(std::chrono::seconds(5));
    {
      std::lock_guard<std::mutex> lock(shared.out_mutex);
      flush_locked(shared);
    }
    report(false);
  }
  for (auto& t : pool) t.join();
  {
    std::lock_guard<std::mutex> lock(shared.out_mutex);
    flush_locked(shared);
  }
  report(true);
  return shared.positions.load();
}

}  // namespace nsce
