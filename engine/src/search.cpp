#include "nsce/search.hpp"

#include "nsce/eval.hpp"
#include "nsce/movegen.hpp"
#include "nsce/policy.hpp"
#include "nsce/controller.hpp"
#include "nsce/see.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <mutex>
#include <string>
#include <utility>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

namespace nsce {
namespace {

#if defined(NSCE_STATS)
#define NSCE_STAT_INC(worker, field) (++(worker).stats.field)
#define NSCE_STAT_ADD(worker, field, value) ((worker).stats.field += static_cast<uint64_t>(value))
#else
#define NSCE_STAT_INC(worker, field) ((void)0)
#define NSCE_STAT_ADD(worker, field, value) ((void)0)
#endif

constexpr int FutilityMargin(int depth) { return 80 * depth; }
constexpr int RazorMargin = 300;
constexpr int RFPMargin(int depth) { return 100 * depth; }

int history_bonus(int depth) { return std::min(16 * depth * depth + 8 * depth, 1200); }

int draw_score(uint64_t nodes) { return static_cast<int>(1 - static_cast<int>(nodes & 2)); }

std::string uci_score(int score) {
  if (score >= VALUE_MATE - 256) {
    const int plies = VALUE_MATE - score;
    return "mate " + std::to_string((plies + 1) / 2);
  }
  if (score <= -VALUE_MATE + 256) {
    const int plies = VALUE_MATE + score;
    return "mate -" + std::to_string((plies + 1) / 2);
  }
  return "cp " + std::to_string(score);
}

int64_t steady_now_ns() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}

void history_update(int& entry, int bonus) {
  entry += bonus - entry * std::abs(bonus) / 512;
}

void history_update16(int16_t& entry, int bonus) {
  int next = static_cast<int>(entry) + bonus - static_cast<int>(entry) * std::abs(bonus) / 512;
  entry = static_cast<int16_t>(std::clamp(next, -16384, 16384));
}

int corr_index(Key key) { return static_cast<int>(key & (SearchWorker::kCorrSize - 1)); }

int continuation_score(const SearchWorker& w, const SearchStack* ss, int ply, Piece pc, Square to) {
  int score = 0;
  if (pc == NO_PIECE) return score;
  auto add_ply = [&](int back, int weight) {
    if (ply < back) return;
    const SearchStack* prev = ss - back;
    if (prev->moved_piece != NO_PIECE && prev->current_move)
      score += weight * w.continuation[prev->moved_piece][prev->current_move.to()][pc][to] / 4;
  };
  add_ply(1, 4);
  add_ply(2, 4);
  add_ply(4, 2);
  add_ply(6, 2);
  return score;
}

void age_i16(int16_t* data, std::size_t count) {
#if defined(__AVX2__)
  for (std::size_t i = 0; i < count; i += 16) {
    __m256i v = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(data + i));
    v = _mm256_sub_epi16(v, _mm256_srai_epi16(v, 15));
    _mm256_storeu_si256(reinterpret_cast<__m256i*>(data + i), _mm256_srai_epi16(v, 1));
  }
#else
  for (std::size_t i = 0; i < count; ++i) data[i] = static_cast<int16_t>(data[i] / 2);
#endif
}

void age_i32(int* data, std::size_t count) {
#if defined(__AVX2__)
  for (std::size_t i = 0; i < count; i += 8) {
    __m256i v = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(data + i));
    v = _mm256_sub_epi32(v, _mm256_srai_epi32(v, 31));
    _mm256_storeu_si256(reinterpret_cast<__m256i*>(data + i), _mm256_srai_epi32(v, 1));
  }
#else
  for (std::size_t i = 0; i < count; ++i) data[i] /= 2;
#endif
}

}  // namespace

SearchStats& SearchStats::operator+=(const SearchStats& other) {
#define NSCE_MERGE_STAT(field) field += other.field
  NSCE_MERGE_STAT(qnodes);
  NSCE_MERGE_STAT(evaluations);
  NSCE_MERGE_STAT(tt_probes);
  NSCE_MERGE_STAT(tt_hits);
  NSCE_MERGE_STAT(tt_cutoffs);
  NSCE_MERGE_STAT(generated_moves);
  NSCE_MERGE_STAT(beta_cutoffs);
  NSCE_MERGE_STAT(first_move_cutoffs);
  NSCE_MERGE_STAT(cutoff_index_sum);
  NSCE_MERGE_STAT(see_order_calls);
  NSCE_MERGE_STAT(see_prune_calls);
  NSCE_MERGE_STAT(see_prunes);
  NSCE_MERGE_STAT(lmr_attempts);
  NSCE_MERGE_STAT(lmr_researches);
  NSCE_MERGE_STAT(null_attempts);
  NSCE_MERGE_STAT(null_cutoffs);
  NSCE_MERGE_STAT(razor_attempts);
  NSCE_MERGE_STAT(razor_cutoffs);
  NSCE_MERGE_STAT(rfp_attempts);
  NSCE_MERGE_STAT(rfp_cutoffs);
  NSCE_MERGE_STAT(futility_prunes);
  NSCE_MERGE_STAT(lmp_prunes);
  NSCE_MERGE_STAT(see_search_prunes);
  NSCE_MERGE_STAT(singular_attempts);
  NSCE_MERGE_STAT(singular_extensions);
  NSCE_MERGE_STAT(iir_reductions);
  NSCE_MERGE_STAT(qs_tt_cutoffs);
  NSCE_MERGE_STAT(root_moves);
  NSCE_MERGE_STAT(probcut_attempts);
  NSCE_MERGE_STAT(probcut_cutoffs);
#undef NSCE_MERGE_STAT
  return *this;
}

Search::Search() {
  policy_ = &PolicyNet::instance();
  controller_ = &SearchController::instance();
  tt_.resize(16);
  for (int depth = 1; depth < 64; ++depth)
    for (int moves = 1; moves < 64; ++moves) {
      const double logs = std::log(static_cast<double>(depth)) * std::log(static_cast<double>(moves));
      lmr_quiet_[depth][moves] = static_cast<int>(0.25 + logs / 2.15);
      lmr_capture_[depth][moves] = static_cast<int>(0.10 + logs / 3.40);
    }
}

Search::~Search() { stop_helper_pool(); }

void Search::set_position(const Position& pos) { root_ = pos; }

void Search::set_policy(PolicyNet* policy) { policy_ = policy ? policy : &PolicyNet::instance(); }

void Search::set_controller(SearchController* controller) {
  controller_ = controller ? controller : &SearchController::instance();
}

void Search::prepare() {
  cancelled_.store(false, std::memory_order_relaxed);
  time_expired_.store(false, std::memory_order_relaxed);
  ponder_hit_requested_.store(false, std::memory_order_relaxed);
  pondering_.store(false, std::memory_order_relaxed);
}

void Search::stop() { cancelled_.store(true, std::memory_order_relaxed); }

void Search::ponder_hit() { ponder_hit_requested_.store(true, std::memory_order_relaxed); }

void Search::set_threads(int n) {
  stop_helper_pool();
  threads_ = std::clamp(n, 1, 64);
}

void Search::start_helper_pool() {
  if (threads_ <= 1) {
    stop_helper_pool();
    return;
  }
  if (static_cast<int>(helper_threads_.size()) == threads_ - 1 && !helper_exit_) return;
  stop_helper_pool();
  {
    std::lock_guard<std::mutex> lock(helper_mutex_);
    helper_exit_ = false;
    helper_generation_ = 0;
    helper_completed_ = 0;
    helper_job_ = {};
  }
  helper_workers_.reserve(static_cast<std::size_t>(threads_ - 1));
  helper_threads_.reserve(static_cast<std::size_t>(threads_ - 1));
  for (int i = 0; i < threads_ - 1; ++i) helper_workers_.push_back(std::make_unique<SearchWorker>());
  for (int i = 0; i < threads_ - 1; ++i)
    helper_threads_.emplace_back([this, i]() { helper_worker_loop(static_cast<std::size_t>(i)); });
}

void Search::stop_helper_pool() {
  {
    std::lock_guard<std::mutex> lock(helper_mutex_);
    helper_exit_ = true;
  }
  helper_start_cv_.notify_all();
  for (auto& thread : helper_threads_)
    if (thread.joinable()) thread.join();
  helper_threads_.clear();
  helper_workers_.clear();
  helper_job_ = {};
}

void Search::helper_worker_loop(std::size_t index) {
  uint64_t observed_generation = 0;
  while (true) {
    std::function<void(SearchWorker&)> job;
    {
      std::unique_lock<std::mutex> lock(helper_mutex_);
      helper_start_cv_.wait(lock, [&]() { return helper_exit_ || helper_generation_ != observed_generation; });
      if (helper_exit_) return;
      observed_generation = helper_generation_;
      job = helper_job_;
    }
    job(*helper_workers_[index]);
    {
      std::lock_guard<std::mutex> lock(helper_mutex_);
      ++helper_completed_;
      if (helper_completed_ == helper_workers_.size()) helper_done_cv_.notify_one();
    }
  }
}

void Search::launch_helper_job(std::function<void(SearchWorker&)> job) {
  if (helper_workers_.empty()) return;
  {
    std::lock_guard<std::mutex> lock(helper_mutex_);
    helper_job_ = std::move(job);
    helper_completed_ = 0;
    ++helper_generation_;
  }
  helper_start_cv_.notify_all();
}

void Search::wait_helper_job() {
  if (helper_workers_.empty()) return;
  std::unique_lock<std::mutex> lock(helper_mutex_);
  helper_done_cv_.wait(lock, [&]() { return helper_completed_ == helper_workers_.size(); });
}

bool Search::time_up() const {
  if (nodes_limit_ > 0 && static_cast<int64_t>(nodes_.load(std::memory_order_relaxed)) >= nodes_limit_)
    return true;
  if (pondering_.load(std::memory_order_relaxed)) return false;
  return maximum_ms_ > 0 && steady_now_ns() >= deadline_ns_.load(std::memory_order_relaxed);
}

bool Search::count_node(SearchWorker& w) {
  ++w.nodes;
  if (stopped()) return true;
  if (pondering_.load(std::memory_order_relaxed) &&
      ponder_hit_requested_.exchange(false, std::memory_order_relaxed)) {
    pondering_.store(false, std::memory_order_relaxed);
    const int64_t now = steady_now_ns();
    start_ns_.store(now, std::memory_order_relaxed);
    deadline_ns_.store(now + static_cast<int64_t>(maximum_ms_) * 1'000'000LL, std::memory_order_relaxed);
    time_expired_.store(false, std::memory_order_relaxed);
  }
  const uint64_t check_interval = nodes_limit_ > 0 ? 32ULL : 256ULL;
  if ((w.nodes & (check_interval - 1)) != 0) return false;
  flush_nodes(w);
  if (time_up()) {
    time_expired_.store(true, std::memory_order_relaxed);
    return true;
  }
  return false;
}

void Search::flush_nodes(SearchWorker& w) {
  uint64_t pending = w.nodes - w.published_nodes;
  if (pending == 0) return;
  nodes_.fetch_add(pending, std::memory_order_relaxed);
  w.published_nodes = w.nodes;
}

int Search::correction(const SearchWorker& w, const Position& pos) const {
  const Color stm = pos.side_to_move();
  const int pawn = w.pawn_corr[stm][corr_index(pos.pawn_key())];
  const int nonpawn = w.nonpawn_corr[stm][corr_index(pos.nonpawn_key())];
  return std::clamp((pawn + nonpawn) / 256, -200, 200);
}

int Search::correction(const SearchWorker& w, const Position& pos, const SearchStack* ss, int ply) const {
  int corr = correction(w, pos);
  if (ply > 0 && (ss - 1)->moved_piece != NO_PIECE && (ss - 1)->current_move)
    corr += std::clamp(w.cont_corr[(ss - 1)->moved_piece][(ss - 1)->current_move.to()] / 256, -80, 80);
  return std::clamp(corr, -220, 220);
}

int Search::pick_next_move(MoveList& list, int* scores, int start) const {
  int best = start;
  for (int i = start + 1; i < list.size; ++i)
    if (scores[i] > scores[best]) best = i;
  if (best != start) {
    std::swap(list.moves[start], list.moves[best]);
    std::swap(scores[start], scores[best]);
  }
  return start;
}

void Search::update_correction(SearchWorker& w, const Position& pos, int static_eval, int best_score, Bound bound,
                               int depth) {
  if (static_eval == VALUE_NONE || std::abs(best_score) >= VALUE_MATE - 256) return;
  const int diff = best_score - static_eval;
  if (!((bound == BOUND_EXACT) || (bound == BOUND_LOWER && diff > 0) || (bound == BOUND_UPPER && diff < 0))) return;
  const int bonus = std::clamp(diff * depth / 8, -256, 256);
  const Color stm = pos.side_to_move();
  history_update(w.pawn_corr[stm][corr_index(pos.pawn_key())], bonus);
  history_update(w.nonpawn_corr[stm][corr_index(pos.nonpawn_key())], bonus);
}

void Search::score_moves(SearchWorker& w, const Position& pos, const SearchStack* ss, MoveList& list, Move tt_move,
                         Move counter, int ply, int* scores) const {
  const bool use_policy = policy_ && policy_->is_enabled();
  for (int i = 0; i < list.size; ++i) {
    Move m = list.moves[i];
    int s = 0;
    if (m == tt_move)
      s = 2'000'000;
    else if (m.is_promotion()) {
      Piece victim = m.is_capture() ? pos.piece_on(m.to()) : NO_PIECE;
      int victim_value = victim == NO_PIECE ? 0 : piece_value(type_of(victim));
      s = 1'100'000 + piece_value(m.promotion()) + victim_value;
    } else if (m.is_capture() || m.is_ep()) {
      Piece victim = m.is_ep() ? make_piece(~pos.side_to_move(), PAWN) : pos.piece_on(m.to());
      Piece attacker = pos.piece_on(m.from());
      int victim_value = victim == NO_PIECE ? 0 : piece_value(type_of(victim));
      int attacker_value = attacker == NO_PIECE ? 0 : piece_value(type_of(attacker));
      int see_score = 0;
      if (use_see_ && victim_value <= attacker_value) {
        NSCE_STAT_INC(w, see_order_calls);
        see_score = static_exchange_eval(pos, m);
      }
      int cap_hist = 0;
      if (attacker != NO_PIECE && victim != NO_PIECE) cap_hist = w.capture_history[attacker][m.to()][type_of(victim)];
      s = 1'000'000 + victim_value * 16 - attacker_value + cap_hist + std::clamp(see_score, -500, 500);
    } else if (ply < SearchWorker::kMaxPly && m == w.killers[ply][0])
      s = 900'000;
    else if (ply < SearchWorker::kMaxPly && m == w.killers[ply][1])
      s = 800'000;
    else if (m == counter)
      s = 700'000;
    else {
      Piece pc = pos.piece_on(m.from());
      if (pc != NO_PIECE) {
        s = w.history[pc][m.to()];
        s += continuation_score(w, ss, ply, pc, m.to());
      }
      if (use_policy) s += policy_->score_move(pos, m) * 5 / 4;
    }
    scores[i] = s;
  }
}

void Search::sort_moves(MoveList& list, int* scores) const {
  for (int i = 1; i < list.size; ++i) {
    Move move = list.moves[i];
    int score = scores[i];
    int j = i;
    while (j > 0 && scores[j - 1] < score) {
      list.moves[j] = list.moves[j - 1];
      scores[j] = scores[j - 1];
      --j;
    }
    list.moves[j] = move;
    scores[j] = score;
  }
}

void Search::update_quiet_stats(SearchWorker& w, const Position& pos, SearchStack* ss, Move best, const Move* quiets,
                                int quiet_count, int depth, int ply, Move prev) {
  if (best.is_capture() || best.is_ep()) return;
  int bonus = history_bonus(depth);
  Piece pc = pos.piece_on(best.from());
  if (pc != NO_PIECE) {
    history_update(w.history[pc][best.to()], bonus);
    auto upd_cont = [&](int back) {
      if (ply < back) return;
      const SearchStack* prev = ss - back;
      if (prev->moved_piece != NO_PIECE && prev->current_move)
        history_update16(w.continuation[prev->moved_piece][prev->current_move.to()][pc][best.to()], bonus);
    };
    upd_cont(1);
    upd_cont(2);
    upd_cont(4);
    upd_cont(6);
    if (ply > 0 && (ss - 1)->moved_piece != NO_PIECE)
      history_update(w.cont_corr[(ss - 1)->moved_piece][(ss - 1)->current_move.to()], bonus / 8);
  }

  if (ply < SearchWorker::kMaxPly) {
    if (w.killers[ply][0] != best) {
      w.killers[ply][1] = w.killers[ply][0];
      w.killers[ply][0] = best;
    }
  }
  if (prev) w.countermove[prev.from()][prev.to()] = best;

  for (int i = 0; i < quiet_count; ++i) {
    Move m = quiets[i];
    if (m == best) continue;
    Piece qpc = pos.piece_on(m.from());
    if (qpc == NO_PIECE) continue;
    history_update(w.history[qpc][m.to()], -bonus);
    auto upd_cont = [&](int back) {
      if (ply < back) return;
      const SearchStack* prev_ss = ss - back;
      if (prev_ss->moved_piece != NO_PIECE && prev_ss->current_move)
        history_update16(w.continuation[prev_ss->moved_piece][prev_ss->current_move.to()][qpc][m.to()], -bonus);
    };
    upd_cont(1);
    upd_cont(2);
  }
}

void Search::update_capture_stats(SearchWorker& w, const Position& pos, Move best, const Move* captures,
                                  int capture_count, int depth) {
  if (!best.is_capture() && !best.is_ep()) return;
  int bonus = history_bonus(depth);
  Piece pc = pos.piece_on(best.from());
  Piece victim = best.is_ep() ? make_piece(~pos.side_to_move(), PAWN) : pos.piece_on(best.to());
  if (pc != NO_PIECE && victim != NO_PIECE)
    history_update(w.capture_history[pc][best.to()][type_of(victim)], bonus);
  for (int i = 0; i < capture_count; ++i) {
    Move m = captures[i];
    if (m == best) continue;
    Piece qpc = pos.piece_on(m.from());
    Piece qvic = m.is_ep() ? make_piece(~pos.side_to_move(), PAWN) : pos.piece_on(m.to());
    if (qpc != NO_PIECE && qvic != NO_PIECE)
      history_update(w.capture_history[qpc][m.to()][type_of(qvic)], -bonus);
  }
}

int Search::quiescence(Position& pos, SearchWorker& w, SearchStack* ss, int alpha, int beta, int ply) {
  NSCE_STAT_INC(w, qnodes);
  if (count_node(w)) return alpha;

  if (ply >= SearchWorker::kMaxPly - 1) {
    NSCE_STAT_INC(w, evaluations);
    return evaluate(pos);
  }

  const bool in_check = pos.in_check();
  const bool draw = pos.is_draw();
  if (draw && !in_check) return draw_score(w.nodes);

  TTEntry tte;
  Move tt_move{};
  int tt_score = 0;
  if (use_tt_) NSCE_STAT_INC(w, tt_probes);
  const bool found = use_tt_ && tt_.probe(pos.key(), tte);
  if (found) {
    NSCE_STAT_INC(w, tt_hits);
    tt_move = Move{tte.move};
    tt_score = TranspositionTable::score_from_tt(tte.score, ply);
    if (tte.bound == BOUND_EXACT || (tte.bound == BOUND_LOWER && tt_score >= beta) ||
        (tte.bound == BOUND_UPPER && tt_score <= alpha)) {
      NSCE_STAT_INC(w, qs_tt_cutoffs);
      return tt_score;
    }
  }

  int stand = VALUE_NONE;
  if (!in_check) {
    if (found && tte.eval_valid) {
      stand = tte.eval + correction(w, pos, ss, ply);
    } else {
      NSCE_STAT_INC(w, evaluations);
      stand = evaluate(pos) + correction(w, pos, ss, ply);
    }
    if (found && std::abs(tt_score) < VALUE_MATE - 256) {
      if (tte.bound == BOUND_EXACT) stand = tt_score;
      else if (tte.bound == BOUND_LOWER && tt_score > stand) stand = tt_score;
      else if (tte.bound == BOUND_UPPER && tt_score < stand) stand = tt_score;
    }
    ss->static_eval = stand;
    if (stand >= beta) return stand;
    if (stand > alpha) alpha = stand;
  } else {
    ss->static_eval = VALUE_NONE;
  }

  MoveList legal;
  if (in_check) {
    generate_legal(pos, legal);
    if (legal.size == 0) return mated_in(ply);
    if (draw) return draw_score(w.nodes);
  } else {
    generate_legal_noisy(pos, legal);
  }

  int scores[MAX_MOVES];
  NSCE_STAT_ADD(w, generated_moves, legal.size);
  score_moves(w, pos, ss, legal, tt_move, Move{}, ply, scores);

  int best_score = in_check ? -VALUE_INFINITE : stand;
  Move best_move = tt_move;
  Bound bound = BOUND_UPPER;

  for (int i = 0; i < legal.size; ++i) {
    pick_next_move(legal, scores, i);
    Move m = legal.moves[i];
    Piece victim = m.is_ep() ? make_piece(~pos.side_to_move(), PAWN) : pos.piece_on(m.to());
    int gain = (victim == NO_PIECE) ? 0 : piece_value(type_of(victim));
    Piece attacker = pos.piece_on(m.from());
    int attacker_value = attacker == NO_PIECE ? 0 : piece_value(type_of(attacker));
    if (use_see_ && !in_check && !m.is_promotion() && gain < attacker_value) {
      NSCE_STAT_INC(w, see_prune_calls);
      if (!see_ge(pos, m, -80)) {
        NSCE_STAT_INC(w, see_prunes);
        continue;
      }
    }
    if (!in_check && !m.is_promotion() && stand + gain + 150 < alpha) {
      best_score = std::max(best_score, stand + gain + 150);
      continue;
    }

    ss->current_move = m;
    ss->moved_piece = attacker;
    StateInfo st;
    pos.do_move(m, st);
    int score = -quiescence(pos, w, ss + 1, -beta, -alpha, ply + 1);
    pos.undo_move(m, st);
    if (stopped()) return alpha;
    if (score > best_score) {
      best_score = score;
      best_move = m;
    }
    if (score >= beta) {
      NSCE_STAT_INC(w, beta_cutoffs);
      NSCE_STAT_ADD(w, cutoff_index_sum, i);
      if (i == 0) NSCE_STAT_INC(w, first_move_cutoffs);
      if (use_tt_) tt_.store(pos.key(), 0, score, BOUND_LOWER, m, ply, in_check ? VALUE_NONE : stand);
      return score;
    }
    if (score > alpha) {
      alpha = score;
      bound = BOUND_EXACT;
    }
  }

  if (in_check && best_score == -VALUE_INFINITE) return mated_in(ply);
  if (use_tt_)
    tt_.store(pos.key(), 0, best_score, bound, best_move, ply, in_check ? VALUE_NONE : stand);
  return best_score;
}

int Search::search(Position& pos, SearchWorker& w, SearchStack* ss, int depth, int alpha, int beta, int ply,
                   bool cut_node) {
  if (count_node(w)) return alpha;

  const bool root_node = (ply == 0);
  const bool pv_node = (beta - alpha > 1);
  const bool in_check = pos.in_check();
  const Move excluded = ss->excluded;
  w.pv_len[ply] = 0;

  if (!root_node) {
    if (pos.is_draw()) {
      if (pos.halfmove_clock() >= 100 && in_check) {
        MoveList legal;
        generate_legal(pos, legal);
        if (legal.size == 0) return mated_in(ply);
      }
      return draw_score(w.nodes);
    }
    alpha = std::max(alpha, mated_in(ply));
    beta = std::min(beta, mate_in(ply + 1));
    if (alpha >= beta) return alpha;
  }

  if (ply >= SearchWorker::kMaxPly - 1) {
    NSCE_STAT_INC(w, evaluations);
    return evaluate(pos);
  }
  if (depth <= 0) return quiescence(pos, w, ss, alpha, beta, ply);

  if (in_check) depth = std::min(depth + 1, SearchWorker::kMaxPly - ply - 1);

  TTEntry tte;
  if (use_tt_) NSCE_STAT_INC(w, tt_probes);
  bool found = use_tt_ && tt_.probe(pos.key(), tte);
  Move tt_move{};
  int tt_score = 0;
  if (found) {
    NSCE_STAT_INC(w, tt_hits);
    tt_move = Move{tte.move};
    tt_score = TranspositionTable::score_from_tt(tte.score, ply);
    if (!excluded && !pv_node && tte.depth >= depth) {
      if (tte.bound == BOUND_EXACT) {
        NSCE_STAT_INC(w, tt_cutoffs);
        return tt_score;
      }
      if (tte.bound == BOUND_LOWER && tt_score >= beta) {
        NSCE_STAT_INC(w, tt_cutoffs);
        return tt_score;
      }
      if (tte.bound == BOUND_UPPER && tt_score <= alpha) {
        NSCE_STAT_INC(w, tt_cutoffs);
        return tt_score;
      }
    }
  }

  if (!excluded) {
    if (!in_check && !tt_move && depth >= 4) {
      NSCE_STAT_INC(w, iir_reductions);
      depth -= 1;
    } else if (cut_node && depth >= 8) {
      NSCE_STAT_INC(w, iir_reductions);
      depth -= 1;
    }
    if (depth <= 0) return quiescence(pos, w, ss, alpha, beta, ply);
  }

  int raw_eval = VALUE_NONE;
  int eval = VALUE_NONE;
  if (in_check) {
    ss->static_eval = VALUE_NONE;
  } else {
    if (found && tte.eval_valid) {
      raw_eval = tte.eval;
    } else {
      NSCE_STAT_INC(w, evaluations);
      raw_eval = evaluate(pos);
    }
    ss->static_eval = raw_eval;
    eval = raw_eval + correction(w, pos, ss, ply);
    const int hm = pos.halfmove_clock();
    if (hm >= 8) eval = eval * (256 - std::min(hm, 200)) / 256;
    if (found && std::abs(tt_score) < VALUE_MATE - 256) {
      if (tte.bound == BOUND_EXACT) eval = tt_score;
      else if (tte.bound == BOUND_LOWER && tt_score > eval) eval = tt_score;
      else if (tte.bound == BOUND_UPPER && tt_score < eval) eval = tt_score;
    }
  }

  bool improving = false;
  if (!in_check && ply >= 2 && (ss - 2)->static_eval != VALUE_NONE)
    improving = eval > (ss - 2)->static_eval;
  else if (!in_check && ply >= 4 && (ss - 4)->static_eval != VALUE_NONE)
    improving = eval > (ss - 4)->static_eval;

  if (use_razoring_ && !excluded && !pv_node && !in_check && depth <= 3 && eval + RazorMargin * depth < alpha) {
    NSCE_STAT_INC(w, razor_attempts);
    int ralpha = alpha - RazorMargin * depth;
    int score = quiescence(pos, w, ss, ralpha, ralpha + 1, ply);
    if (score <= ralpha) {
      NSCE_STAT_INC(w, razor_cutoffs);
      return score;
    }
  }

  if (use_rfp_ && !excluded && !pv_node && !in_check && depth <= 6 &&
      eval - RFPMargin(depth) * (improving ? 1 : 2) / 2 >= beta && eval < VALUE_MATE - 256) {
    NSCE_STAT_INC(w, rfp_attempts);
    NSCE_STAT_INC(w, rfp_cutoffs);
    return eval;
  }

  if (use_null_move_ && !excluded && !root_node && !pv_node && !in_check && !ss->skip_null && depth >= 3 &&
      eval >= beta && non_pawn_material(pos, pos.side_to_move()) > 0) {
    NSCE_STAT_INC(w, null_attempts);
    int R = 3 + depth / 3 + std::min(3, (eval - beta) / 200);
    R = std::min(R, depth - 1);
    StateInfo st;
    pos.do_null_move(st);
    (ss + 1)->skip_null = true;
    (ss + 1)->current_move = Move{};
    (ss + 1)->moved_piece = NO_PIECE;
    int score = -search(pos, w, ss + 1, depth - R, -beta, -beta + 1, ply + 1, !cut_node);
    (ss + 1)->skip_null = false;
    pos.undo_null_move(st);
    if (stopped()) return alpha;
    if (score >= beta) {
      if (score >= VALUE_MATE - 256) score = beta;
      if (depth >= 10) {
        ss->skip_null = true;
        const int verified = search(pos, w, ss, depth - R, beta - 1, beta, ply, false);
        ss->skip_null = false;
        if (stopped()) return alpha;
        if (verified < beta) {
          improving = true;
        } else {
          NSCE_STAT_INC(w, null_cutoffs);
          return score;
        }
      } else {
        NSCE_STAT_INC(w, null_cutoffs);
        return score;
      }
    }
  }

  MoveList list;
  generate_legal(pos, list);
  if (root_node && !root_moves_.empty()) {
    MoveList restricted;
    for (Move move : list)
      if (std::find(root_moves_.begin(), root_moves_.end(), move) != root_moves_.end()) restricted.add(move);
    list = restricted;
  }
  NSCE_STAT_ADD(w, generated_moves, list.size);
  if (root_node) NSCE_STAT_ADD(w, root_moves, list.size);

  if (use_probcut_ && !excluded && !root_node && !pv_node && !in_check && depth >= 4 &&
      eval < VALUE_MATE - 256 && beta < VALUE_MATE - 256) {
    const int pc_beta = beta + 170 - 50 * static_cast<int>(improving);
    if (!(found && tte.bound == BOUND_UPPER && tt_score < pc_beta)) {
      NSCE_STAT_INC(w, probcut_attempts);
      MoveList noisy;
      for (Move move : list)
        if (move.is_capture() || move.is_ep() || move.is_promotion()) noisy.add(move);
      int pc_scores[MAX_MOVES];
      score_moves(w, pos, ss, noisy, tt_move, Move{}, ply, pc_scores);
      const int pc_depth = std::max(1, depth - 4 - static_cast<int>(improving));
      for (int i = 0; i < noisy.size; ++i) {
        pick_next_move(noisy, pc_scores, i);
        Move m = noisy.moves[i];
        if (excluded && m == excluded) continue;
        if (use_see_ && !see_ge(pos, m, pc_beta - eval)) continue;
        ss->current_move = m;
        ss->moved_piece = pos.piece_on(m.from());
        StateInfo st;
        pos.do_move(m, st);
        int score = -quiescence(pos, w, ss + 1, -pc_beta, -pc_beta + 1, ply + 1);
        if (score >= pc_beta) score = -search(pos, w, ss + 1, pc_depth, -pc_beta, -pc_beta + 1, ply + 1, !cut_node);
        pos.undo_move(m, st);
        if (stopped()) return alpha;
        if (score >= pc_beta) {
          NSCE_STAT_INC(w, probcut_cutoffs);
          if (use_tt_) tt_.store(pos.key(), pc_depth + 1, score, BOUND_LOWER, m, ply, ss->static_eval);
          return score;
        }
      }
    }
  }

  if (list.size == 0) {
    if (in_check) return mated_in(ply);
    return draw_score(w.nodes);
  }

  Move prev = (ply > 0) ? (ss - 1)->current_move : Move{};
  Move counter = prev ? w.countermove[prev.from()][prev.to()] : Move{};
  const bool tt_capture = tt_move && (tt_move.is_capture() || tt_move.is_ep());

  int scores[MAX_MOVES];
  score_moves(w, pos, ss, list, tt_move, counter, ply, scores);

  int best_score = -VALUE_INFINITE;
  Move best_move{};
  Bound bound = BOUND_UPPER;
  Move quiets[64];
  Move captures[64];
  int quiet_count = 0;
  int capture_count = 0;
  int moves_searched = 0;

  for (int i = 0; i < list.size; ++i) {
    pick_next_move(list, scores, i);
    Move m = list.moves[i];
    if (excluded && m == excluded) continue;

    const bool is_quiet = !m.is_capture() && !m.is_ep() && !m.is_promotion();
    Piece moving = pos.piece_on(m.from());
    int hist = 0;
    if (moving != NO_PIECE) {
      hist = is_quiet ? w.history[moving][m.to()] + continuation_score(w, ss, ply, moving, m.to())
                      : (pos.piece_on(m.to()) == NO_PIECE ? 0
                                                         : w.capture_history[moving][m.to()][type_of(pos.piece_on(m.to()))]);
    }

    const int fut_margin = FutilityMargin(depth) - (improving ? 40 : 0);
    if (use_futility_ && !root_node && !in_check && is_quiet && depth <= 6 && !pv_node &&
        eval + fut_margin <= alpha && best_score > -VALUE_MATE + 256 && hist < 400) {
      NSCE_STAT_INC(w, futility_prunes);
      continue;
    }

    int lmp_limit = improving ? (5 + depth * depth) : (3 + depth * depth);
    if (hist > 0) lmp_limit += 2;
    if (controller_ && controller_->is_enabled()) {
      int ps = controller_->prune_score(depth, moves_searched, eval, alpha);
      if (ps > 600) lmp_limit = std::max(2, lmp_limit - 1);
    }
    if (use_lmp_ && !root_node && !in_check && is_quiet && depth <= 6 && moves_searched >= lmp_limit &&
        best_score > -VALUE_MATE + 256 && hist < 200) {
      NSCE_STAT_INC(w, lmp_prunes);
      continue;
    }

    if (use_see_ && !root_node && !pv_node && !in_check && moves_searched > 0 && depth <= 8 &&
        !m.is_promotion()) {
      const int margin = is_quiet ? -10 * depth : -100 * depth;
      NSCE_STAT_INC(w, see_prune_calls);
      if (!see_ge(pos, m, margin)) {
        NSCE_STAT_INC(w, see_search_prunes);
        continue;
      }
      if (is_quiet && depth <= 5 && hist < -3500 * depth) {
        NSCE_STAT_INC(w, lmp_prunes);
        continue;
      }
    }

    int extension = 0;
    if (!root_node && !excluded && m == tt_move && depth >= 7 && found && tte.depth >= depth - 3 &&
        (tte.bound == BOUND_LOWER || tte.bound == BOUND_EXACT) && std::abs(tt_score) < VALUE_MATE - 256) {
      NSCE_STAT_INC(w, singular_attempts);
      const int sbeta = tt_score - (50 + 15 * static_cast<int>(pv_node)) * depth / 64;
      const int sdepth = std::max(1, (depth - 1) / 2);
      ss->excluded = m;
      const int sscore = search(pos, w, ss, sdepth, sbeta - 1, sbeta, ply, cut_node);
      ss->excluded = {};
      if (stopped()) return alpha;
      if (sscore < sbeta) {
        extension = 1;
        if (pv_node && sscore < sbeta - 3 * depth && ss->double_extensions < 2 && ply < 2 * root_depth_) {
          extension = 2;
          (ss + 1)->double_extensions = ss->double_extensions + 1;
        }
        NSCE_STAT_INC(w, singular_extensions);
      } else if (!pv_node && sscore >= beta) {
        return sscore;
      } else if (cut_node) {
        extension = -1;
      }
    }

    ss->current_move = m;
    ss->moved_piece = moving;
    if (extension < 2) (ss + 1)->double_extensions = ss->double_extensions;
    int pol = policy_ && policy_->is_enabled() ? policy_->score_move(pos, m) : 0;
    Key key_before = pos.key();
    const int controller_see_sign =
        (controller_ && controller_->is_enabled() && !is_quiet) ? (see_ge(pos, m, 0) ? 1 : -1) : 0;

    StateInfo st;
    pos.do_move(m, st);
    tt_.prefetch(pos.key());

    int new_depth = std::max(0, depth - 1 + extension);
    int score;
    const bool gives_check = pos.in_check();
    const bool killer = ply < SearchWorker::kMaxPly && (m == w.killers[ply][0] || m == w.killers[ply][1]);
    const bool do_lmr = use_lmr_ && extension <= 0 && depth >= 3 && moves_searched >= 1 + static_cast<int>(pv_node) &&
                        !in_check && (is_quiet || hist < 0);

    if (do_lmr) {
      NSCE_STAT_INC(w, lmr_attempts);
      int R = is_quiet ? lmr_quiet_[std::min(depth, 63)][std::min(moves_searched, 63)]
                       : lmr_capture_[std::min(depth, 63)][std::min(moves_searched, 63)];
      R += static_cast<int>(cut_node);
      R -= static_cast<int>(pv_node);
      R -= static_cast<int>(improving);
      R -= static_cast<int>(gives_check);
      if (killer || m == counter) --R;
      if (tt_capture && is_quiet) ++R;
      if (hist > 400) --R;
      if (hist < -200) ++R;
      if (controller_ && controller_->is_enabled()) {
        R += controller_->reduction_delta(depth, moves_searched, eval, alpha, beta, is_quiet, pol, hist,
                                           improving, cut_node, controller_see_sign);
      }
      R = std::clamp(R, 1, new_depth);
      score = -search(pos, w, ss + 1, new_depth - R, -alpha - 1, -alpha, ply + 1, true);
      bool researched = false;
      if (score > alpha && R > 0) {
        NSCE_STAT_INC(w, lmr_researches);
        researched = true;
        score = -search(pos, w, ss + 1, new_depth, -alpha - 1, -alpha, ply + 1, !cut_node);
      }
      if (score > alpha && score < beta && pv_node)
        score = -search(pos, w, ss + 1, new_depth, -beta, -alpha, ply + 1, false);
      if (controller_ && controller_->telemetry_open())
        controller_->log_decision(key_before, depth, moves_searched, R, score, score >= beta, hist, improving,
                                  cut_node, is_quiet, researched);
    } else if (!pv_node || moves_searched > 0) {
      score = -search(pos, w, ss + 1, new_depth, -alpha - 1, -alpha, ply + 1, !cut_node);
      if (pv_node && score > alpha && score < beta)
        score = -search(pos, w, ss + 1, new_depth, -beta, -alpha, ply + 1, false);
    } else {
      score = -search(pos, w, ss + 1, new_depth, -beta, -alpha, ply + 1, false);
    }

    pos.undo_move(m, st);
    ++moves_searched;

    if (stopped()) return alpha;

    if (is_quiet && quiet_count < 64) quiets[quiet_count++] = m;
    else if (!is_quiet && capture_count < 64) captures[capture_count++] = m;

    if (score > best_score) {
      best_score = score;
      best_move = m;
      if (score > alpha) {
        alpha = score;
        bound = BOUND_EXACT;
        w.pv[ply][0] = m;
        for (int j = 0; j < w.pv_len[ply + 1]; ++j) w.pv[ply][j + 1] = w.pv[ply + 1][j];
        w.pv_len[ply] = w.pv_len[ply + 1] + 1;

        if (score >= beta) {
          NSCE_STAT_INC(w, beta_cutoffs);
          NSCE_STAT_ADD(w, cutoff_index_sum, i);
          if (i == 0) NSCE_STAT_INC(w, first_move_cutoffs);
          bound = BOUND_LOWER;
          update_quiet_stats(w, pos, ss, m, quiets, quiet_count, depth, ply, prev);
          update_capture_stats(w, pos, m, captures, capture_count, depth);
          break;
        }
      }
    }
  }

  if (moves_searched == 0) {
    if (excluded) return eval == VALUE_NONE ? alpha : eval;
    return in_check ? mated_in(ply) : (eval == VALUE_NONE ? draw_score(w.nodes) : eval);
  }

  if (bound != BOUND_LOWER && best_move && !best_move.is_capture() && !best_move.is_ep()) {
    Piece pc = pos.piece_on(best_move.from());
    if (pc != NO_PIECE) history_update(w.history[pc][best_move.to()], history_bonus(depth));
  }

  if (!excluded) update_correction(w, pos, ss->static_eval, best_score, bound, depth);
  if (use_tt_ && !excluded) tt_.store(pos.key(), depth, best_score, bound, best_move, ply, ss->static_eval);
  return best_score;
}

int Search::search_root_parallel(int depth, int alpha, int beta) {
  std::mutex best_mutex;
  int best_score = -VALUE_INFINITE;
  int best_depth = -1;
  Move best_move{};
  std::array<Move, SearchWorker::kMaxPly> best_pv{};
  int best_pv_len = 0;
  const int original_alpha = alpha;

  auto run = [&](SearchWorker& worker, int depth_offset) {
    Position pos = root_;
    SearchStack stack[SearchWorker::kMaxPly + SearchWorker::kStackPad + 2]{};
    SearchStack* ss = stack + SearchWorker::kStackPad;
    const int local_depth = std::max(1, depth + depth_offset);
    const int score = search(pos, worker, ss, local_depth, alpha, beta, 0, false);
    flush_nodes(worker);
    if (stopped() || worker.pv_len[0] <= 0) return;
    std::lock_guard<std::mutex> lock(best_mutex);
    if (local_depth > best_depth || (local_depth == best_depth && score > best_score)) {
      best_depth = local_depth;
      best_score = score;
      best_move = worker.pv[0][0];
      best_pv_len = worker.pv_len[0];
      for (int i = 0; i < best_pv_len; ++i) best_pv[i] = worker.pv[0][i];
    }
  };

  launch_helper_job([&](SearchWorker& worker) {
    int index = 0;
    for (std::size_t i = 0; i < helper_workers_.size(); ++i) {
      if (helper_workers_[i].get() == &worker) {
        index = static_cast<int>(i);
        break;
      }
    }
    constexpr int offsets[] = {-1, 0, 1, -2, 2};
    run(worker, offsets[index % (sizeof(offsets) / sizeof(offsets[0]))]);
  });
  run(main_worker_, 0);
  wait_helper_job();

  if (best_move) {
    main_worker_.pv_len[0] = best_pv_len;
    for (int i = 0; i < best_pv_len; ++i) main_worker_.pv[0][i] = best_pv[i];
    Bound bound = best_score >= beta ? BOUND_LOWER : best_score > original_alpha ? BOUND_EXACT : BOUND_UPPER;
    if (use_tt_) tt_.store(root_.key(), depth, best_score, bound, best_move, 0);
  }
  return best_move ? best_score : alpha;
}

SearchInfo Search::go(const SearchLimits& limits) {
  prepare();
  return go_prepared(limits);
}

SearchInfo Search::go_prepared(const SearchLimits& limits) {
  prepare();
  nodes_.store(0, std::memory_order_relaxed);
  const int64_t start_ns = steady_now_ns();
  start_ns_.store(start_ns, std::memory_order_relaxed);
  deadline_ns_.store(std::numeric_limits<int64_t>::max(), std::memory_order_relaxed);
  tt_.new_search();
  std::memset(main_worker_.killers, 0, sizeof(main_worker_.killers));
  main_worker_.nodes = 0;
  main_worker_.published_nodes = 0;
  main_worker_.stats = {};
  last_stats_ = {};
  age_i32(&main_worker_.history[0][0], 12 * SQUARE_NB);
  age_i32(&main_worker_.capture_history[0][0][0], 12 * SQUARE_NB * PIECE_TYPE_NB);
  age_i32(&main_worker_.pawn_corr[0][0], COLOR_NB * SearchWorker::kCorrSize);
  age_i32(&main_worker_.nonpawn_corr[0][0], COLOR_NB * SearchWorker::kCorrSize);
  age_i32(&main_worker_.cont_corr[0][0], 12 * SQUARE_NB);
  age_i16(&main_worker_.continuation[0][0][0][0], 12ULL * SQUARE_NB * 12ULL * SQUARE_NB);

  optimum_ms_ = 0;
  maximum_ms_ = 0;
  use_soft_time_ = false;
  nodes_limit_ = limits.nodes;
  root_moves_ = limits.searchmoves;
  if (!limits.infinite && limits.movetime_ms > 0) {
    optimum_ms_ = limits.movetime_ms;
    maximum_ms_ = limits.movetime_ms;
  } else if (!limits.infinite && (limits.wtime > 0 || limits.btime > 0)) {
    int time = root_.side_to_move() == WHITE ? limits.wtime : limits.btime;
    int inc = root_.side_to_move() == WHITE ? limits.winc : limits.binc;
    int mtg = limits.movestogo > 0 ? limits.movestogo : 30;
    int reserve = std::min(time / 2, std::max(20, time / 50));
    int available = std::max(1, time - reserve);
    optimum_ms_ = std::min(available, std::max(1, time / mtg + 3 * inc / 4));
    maximum_ms_ = std::min(available, std::max(3 * optimum_ms_, optimum_ms_ + 50));
    use_soft_time_ = true;
  }
  if (limits.ponder) pondering_.store(true, std::memory_order_relaxed);
  if (maximum_ms_ > 0)
    deadline_ns_.store(start_ns + static_cast<int64_t>(maximum_ms_) * 1'000'000LL, std::memory_order_relaxed);

  int max_depth = limits.depth > 0 ? limits.depth : 64;
  start_helper_pool();
  for (auto& helper : helper_workers_) {
    std::memcpy(helper->history, main_worker_.history, sizeof(helper->history));
    std::memcpy(helper->capture_history, main_worker_.capture_history, sizeof(helper->capture_history));
    std::memcpy(helper->continuation, main_worker_.continuation, sizeof(helper->continuation));
    std::memcpy(helper->pawn_corr, main_worker_.pawn_corr, sizeof(helper->pawn_corr));
    std::memcpy(helper->nonpawn_corr, main_worker_.nonpawn_corr, sizeof(helper->nonpawn_corr));
    std::memcpy(helper->cont_corr, main_worker_.cont_corr, sizeof(helper->cont_corr));
    std::memcpy(helper->countermove, main_worker_.countermove, sizeof(helper->countermove));
    std::memset(helper->killers, 0, sizeof(helper->killers));
    helper->nodes = 0;
    helper->published_nodes = 0;
    helper->stats = {};
  }

  SearchInfo info;
  Position pos = root_;
  Move best{};
  Move previous_iteration_best{};
  int stable_best_iterations = 0;
  int prev_score = 0;
  int64_t prev_ms = 0;

  SearchStack stack[SearchWorker::kMaxPly + SearchWorker::kStackPad + 2]{};

  for (int depth = 1; depth <= max_depth; ++depth) {
    root_depth_ = depth;
    int alpha = -VALUE_INFINITE;
    int beta = VALUE_INFINITE;
    int delta = 20;

    if (depth >= 4) {
      alpha = std::max(-VALUE_INFINITE, prev_score - delta);
      beta = std::min(VALUE_INFINITE, prev_score + delta);
    }

    int score = 0;
    while (true) {
      pos = root_;
      std::fill(std::begin(stack), std::end(stack), SearchStack{});
      score = threads_ > 1 ? search_root_parallel(depth, alpha, beta)
                           : search(pos, main_worker_, stack + SearchWorker::kStackPad, depth, alpha, beta, 0, false);
      flush_nodes(main_worker_);
      if (stopped() && depth > 1) break;

      if (score <= alpha) {
        beta = (alpha + beta) / 2;
        alpha = std::max(-VALUE_INFINITE, score - delta);
        delta += delta / 2 + 5;
      } else if (score >= beta) {
        beta = std::min(VALUE_INFINITE, score + delta);
        delta += delta / 2 + 5;
      } else {
        break;
      }
      if (delta > 800) {
        alpha = -VALUE_INFINITE;
        beta = VALUE_INFINITE;
      }
    }

    if (stopped() && depth > 1) break;

    prev_score = score;
    if (main_worker_.pv_len[0] > 0) best = main_worker_.pv[0][0];
    if (!best && use_tt_) {
      TTEntry tte;
      if (tt_.probe(root_.key(), tte) && tte.move) best = Move{tte.move};
    }
    if (!best) {
      MoveList list;
      generate_legal(root_, list);
      if (list.size) best = list.moves[0];
    }
    if (best && best == previous_iteration_best)
      ++stable_best_iterations;
    else {
      previous_iteration_best = best;
      stable_best_iterations = 0;
    }

    const int64_t ms =
        (steady_now_ns() - start_ns_.load(std::memory_order_relaxed)) / 1'000'000LL;
    uint64_t nodes = nodes_.load(std::memory_order_relaxed);
    uint64_t nps = ms > 0 ? nodes * 1000ULL / static_cast<uint64_t>(ms) : nodes;

    std::string pv_str;
    for (int i = 0; i < main_worker_.pv_len[0]; ++i) {
      if (i) pv_str += ' ';
      pv_str += move_to_uci(main_worker_.pv[0][i]);
    }
    if (pv_str.empty() && best) pv_str = move_to_uci(best);

    if (!silent_)
      std::cout << "info depth " << depth << " score " << uci_score(score) << " nodes " << nodes << " nps " << nps
                << " time " << ms << " pv " << pv_str << std::endl;

    info.best_move = best;
    info.score = score;
    info.depth = depth;
    info.nodes = nodes;
    info.time_ms = static_cast<int>(ms);

    if (limits.depth == 0 && maximum_ms_ > 0 && best && !pondering_.load(std::memory_order_relaxed)) {
      const int last_iter = static_cast<int>(ms - prev_ms);
      const int remaining = maximum_ms_ - static_cast<int>(ms);
      prev_ms = ms;
      if (last_iter > 0 && remaining < last_iter / 2) break;
    } else {
      prev_ms = ms;
    }

    if (limits.nodes > 0 && static_cast<int64_t>(nodes) >= limits.nodes) break;
    if (!pondering_.load(std::memory_order_relaxed) && maximum_ms_ > 0 && ms >= maximum_ms_) break;
    if (!pondering_.load(std::memory_order_relaxed) && use_soft_time_ && optimum_ms_ > 0) {
      int soft_limit = optimum_ms_;
      if (stable_best_iterations >= 2)
        soft_limit = std::max(1, 4 * optimum_ms_ / 5);
      else if (stable_best_iterations == 0)
        soft_limit = std::min(maximum_ms_, 6 * optimum_ms_ / 5);
      if (ms >= soft_limit) break;
    }
    if (limits.depth > 0 && depth >= limits.depth) break;
  }

  cancelled_.store(true, std::memory_order_relaxed);
  flush_nodes(main_worker_);
  last_stats_ = main_worker_.stats;
  for (const auto& worker : helper_workers_) last_stats_ += worker->stats;
#if defined(NSCE_STATS)
  uint64_t final_nodes = nodes_.load(std::memory_order_relaxed);
  double qnode_pct = final_nodes ? 100.0 * static_cast<double>(last_stats_.qnodes) / final_nodes : 0.0;
  double first_cut_pct = last_stats_.beta_cutoffs
                             ? 100.0 * static_cast<double>(last_stats_.first_move_cutoffs) / last_stats_.beta_cutoffs
                             : 0.0;
  double avg_cutoff_index =
      last_stats_.beta_cutoffs ? static_cast<double>(last_stats_.cutoff_index_sum) / last_stats_.beta_cutoffs : 0.0;
  if (!silent_)
    std::cout << "info string stats qnodes_pct " << qnode_pct << " evals " << last_stats_.evaluations << " tt "
              << last_stats_.tt_hits << '/' << last_stats_.tt_probes << " tt_cutoffs " << last_stats_.tt_cutoffs
              << " first_cut_pct " << first_cut_pct << " avg_cut_index " << avg_cutoff_index << " lmr "
              << last_stats_.lmr_attempts << " researches " << last_stats_.lmr_researches << " see "
              << last_stats_.see_order_calls + last_stats_.see_prune_calls << " see_prunes " << last_stats_.see_prunes
              << " se " << last_stats_.singular_extensions << '/' << last_stats_.singular_attempts << " iir "
              << last_stats_.iir_reductions << " qs_tt " << last_stats_.qs_tt_cutoffs << " root_moves "
              << last_stats_.root_moves << " probcut " << last_stats_.probcut_cutoffs << '/'
              << last_stats_.probcut_attempts << std::endl;
#endif
  info.nodes = nodes_.load(std::memory_order_relaxed);
  info.time_ms = static_cast<int>((steady_now_ns() - start_ns_.load(std::memory_order_relaxed)) / 1'000'000LL);

  if (!info.best_move) {
    MoveList list;
    generate_legal(root_, list);
    if (list.size) info.best_move = list.moves[0];
  }
  return info;
}

uint64_t Search::bench(int depth) {
  root_.set_startpos();
  SearchLimits limits;
  limits.depth = depth;
  prepare();
  auto info = go(limits);
  return info.nodes;
}

}  // namespace nsce
