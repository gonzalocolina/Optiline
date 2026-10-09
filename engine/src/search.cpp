#include "nsce/search.hpp"

#include "nsce/controller.hpp"
#include "nsce/eval.hpp"
#include "nsce/movegen.hpp"
#include "nsce/policy.hpp"
#include "nsce/see.hpp"
#include "nsce/tune.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <mutex>
#include <string>
#include <utility>

namespace nsce {
namespace {

#if defined(NSCE_STATS)
#define NSCE_STAT_INC(worker, field) (++(worker).stats.field)
#define NSCE_STAT_ADD(worker, field, value) ((worker).stats.field += static_cast<uint64_t>(value))
#else
#define NSCE_STAT_INC(worker, field) ((void)0)
#define NSCE_STAT_ADD(worker, field, value) ((void)0)
#endif

constexpr int kMateBound = VALUE_MATE - 256;
constexpr int kTTMoveScore = 1 << 30;
constexpr int kGoodNoisyScore = 1 << 28;
constexpr int kKillerScore = 1 << 27;
constexpr int kCorrGrain = 256;
constexpr int kCorrMax = 128 * kCorrGrain;

bool is_mate_score(int score) { return std::abs(score) >= kMateBound; }

int draw_score(const SearchWorker& w) { return 1 - static_cast<int>(w.nodes & 2); }

std::string uci_score(int score) {
  if (score >= kMateBound) return "mate " + std::to_string((VALUE_MATE - score + 1) / 2);
  if (score <= -kMateBound) return "mate -" + std::to_string((VALUE_MATE + score + 1) / 2);
  return "cp " + std::to_string(score);
}

int64_t steady_now_ns() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}

int from_to(Move m) { return static_cast<int>(m.from()) * SQUARE_NB + static_cast<int>(m.to()); }

bool is_noisy(Move m) { return m.is_capture() || m.is_ep() || m.is_promotion(); }

PieceType captured_type(const Position& pos, Move m) {
  if (m.is_ep()) return PAWN;
  if (m.is_capture()) {
    const Piece victim = pos.piece_on(m.to());
    if (victim != NO_PIECE) return type_of(victim);
  }
  return KING;
}

int captured_value(const Position& pos, Move m) {
  const PieceType victim = captured_type(pos, m);
  int value = victim == KING ? 0 : piece_value(victim);
  if (m.is_promotion()) value += piece_value(m.promotion()) - piece_value(PAWN);
  return value;
}

void history_update(int16_t& entry, int bonus) {
  const int clamped = std::clamp(bonus, -SearchWorker::kHistoryMax, SearchWorker::kHistoryMax);
  entry = static_cast<int16_t>(entry + clamped - entry * std::abs(clamped) / SearchWorker::kHistoryMax);
}

void corr_update(int& entry, int diff, int depth) {
  const int scaled = std::clamp(diff, -kCorrMax / kCorrGrain, kCorrMax / kCorrGrain) * kCorrGrain;
  const int weight = std::min(depth + 1, 16);
  entry = std::clamp((entry * (256 - weight) + scaled * weight) / 256, -kCorrMax, kCorrMax);
}

int corr_index(Key key) { return static_cast<int>(key & (SearchWorker::kCorrSize - 1)); }

// Direct and discovered checks; castling checks are ignored (only used for pruning exemptions).
bool gives_check(const Position& pos, Move m) {
  if (m.is_castle()) return false;
  const Color us = pos.side_to_move();
  const Square from = m.from();
  const Square to = m.to();
  const Square ksq = pos.king_square(~us);
  const Piece pc = pos.piece_on(from);
  if (pc == NO_PIECE) return false;
  const PieceType pt = m.is_promotion() ? m.promotion() : type_of(pc);
  Bitboard occ = (pos.occupied() ^ square_bb(from)) | square_bb(to);
  if (m.is_ep()) occ ^= square_bb(static_cast<Square>(static_cast<int>(to) ^ 8));
  const Bitboard king = square_bb(ksq);
  switch (pt) {
    case PAWN:
      if (pawn_attacks_bb(us, to) & king) return true;
      break;
    case KNIGHT:
      if (knight_attacks_bb(to) & king) return true;
      break;
    case BISHOP:
      if (bishop_attacks_bb(to, occ) & king) return true;
      break;
    case ROOK:
      if (rook_attacks_bb(to, occ) & king) return true;
      break;
    case QUEEN:
      if (queen_attacks_bb(to, occ) & king) return true;
      break;
    default:
      break;
  }
  const Bitboard queens = pos.pieces(us, QUEEN);
  const Bitboard rq = (pos.pieces(us, ROOK) | queens) & ~square_bb(from);
  const Bitboard bq = (pos.pieces(us, BISHOP) | queens) & ~square_bb(from);
  return (rook_attacks_bb(ksq, occ) & rq) || (bishop_attacks_bb(ksq, occ) & bq);
}

// Staged picker: moves in [0, end) are pre-scored (TT move, noisy, killers); the
// remaining quiets are scored only once the pre-scored stage is exhausted. Noisy
// moves that fail SEE are deferred until after the quiets.
struct MovePicker {
  MoveList list;
  int scores[MAX_MOVES];
  uint32_t bad[MAX_MOVES];
  int index = 0;
  int end = 0;
  int bad_count = 0;
  int bad_index = 0;
  bool quiets_done = false;

  template <typename ScoreFn>
  void prescore(ScoreFn&& score) {
    for (int i = 0; i < list.size; ++i) {
      int s = 0;
      if (!score(list.moves[i], s)) continue;
      std::swap(list.moves[i], list.moves[end]);
      scores[end++] = s;
    }
  }

  template <typename QuietFn>
  Move next(const Position& pos, bool lazy_see, bool skip_quiets, QuietFn&& quiet_score) {
    while (true) {
      if (index < end) {
        int best = index;
        for (int i = index + 1; i < end; ++i)
          if (scores[i] > scores[best]) best = i;
        std::swap(list.moves[index], list.moves[best]);
        std::swap(scores[index], scores[best]);
        const int s = scores[index];
        const Move m = list.moves[index++];
        if (lazy_see && s >= kGoodNoisyScore && s < kTTMoveScore && !see_ge(pos, m, -(s - kGoodNoisyScore) / 36)) {
          bad[bad_count++] = m.raw;
          continue;
        }
        return m;
      }
      if (!quiets_done) {
        quiets_done = true;
        if (skip_quiets) {
          index = end = list.size;
        } else {
          for (int i = end; i < list.size; ++i) scores[i] = quiet_score(list.moves[i]);
          end = list.size;
        }
        continue;
      }
      if (bad_index < bad_count) return Move{bad[bad_index++]};
      return Move{};
    }
  }
};

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
  NSCE_MERGE_STAT(eval_abs_sum);
  NSCE_MERGE_STAT(correction_abs_sum);
  NSCE_MERGE_STAT(tt_eval_substitutions);
  NSCE_MERGE_STAT(improving_nodes);
  NSCE_MERGE_STAT(halfmove_scaled_nodes);
  NSCE_MERGE_STAT(root_moves_claimed);
#undef NSCE_MERGE_STAT
  return *this;
}

void SearchWorker::reset_search_state() {
  std::memset(main_history, 0, sizeof(main_history));
  std::memset(capture_history, 0, sizeof(capture_history));
  std::memset(continuation, 0, sizeof(continuation));
  std::memset(pawn_corr, 0, sizeof(pawn_corr));
  std::memset(nonpawn_corr, 0, sizeof(nonpawn_corr));
  std::memset(cont_corr, 0, sizeof(cont_corr));
  std::memset(killers, 0, sizeof(killers));
  std::memset(countermove, 0, sizeof(countermove));
  std::memset(root_move_nodes, 0, sizeof(root_move_nodes));
  pv_len[0] = 0;
  root_pv_len = 0;
  best_move = Move{};
  best_score = -VALUE_INFINITE;
  completed_depth = 0;
  nodes = 0;
  published_nodes = 0;
  stats = {};
}

Search::Search() : main_worker_(std::make_unique<SearchWorker>()) {
  policy_ = &PolicyNet::instance();
  controller_ = &SearchController::instance();
  tt_.resize(16);
  rebuild_lmr_tables();
}

Search::~Search() { stop_helper_pool(); }

void Search::rebuild_lmr_tables() {
  const double qbase = tune_.lmr_quiet_base_x100 / 100.0;
  const double qdiv = std::max(1, tune_.lmr_quiet_div_x100) / 100.0;
  const double cdiv = std::max(1, tune_.lmr_capture_div_x100) / 100.0;
  for (int depth = 0; depth < 64; ++depth)
    for (int moves = 0; moves < 64; ++moves) {
      if (depth == 0 || moves == 0) {
        lmr_quiet_[depth][moves] = lmr_capture_[depth][moves] = 0;
        continue;
      }
      const double logs = std::log(static_cast<double>(depth)) * std::log(static_cast<double>(moves));
      lmr_quiet_[depth][moves] = static_cast<int>(1024.0 * (qbase + logs / qdiv));
      lmr_capture_[depth][moves] = static_cast<int>(1024.0 * (logs / cdiv));
    }
}

bool Search::set_tune_param(const std::string& name, int value) {
  if (!set_tune_field(tune_, name, value)) return false;
  if (name.rfind("Lmr", 0) == 0) rebuild_lmr_tables();
  return true;
}

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

void Search::clear_search_state() {
  tt_.clear();
  main_worker_->reset_search_state();
  for (auto& worker : helper_workers_) worker->reset_search_state();
  last_stats_ = {};
}

void Search::set_leaf_telemetry(const std::string& path) {
  std::lock_guard<std::mutex> lock(leaf_mutex_);
  leaf_stream_.reset();
  if (!path.empty()) {
    auto stream = std::make_unique<std::ofstream>(path, std::ios::app);
    if (*stream) leaf_stream_ = std::move(stream);
  }
}

void Search::record_leaf(const Position& pos, const char* site, int depth, int ply, int score) {
  if (!leaf_stream_) return;
  std::lock_guard<std::mutex> lock(leaf_mutex_);
  if (!leaf_stream_) return;
  *leaf_stream_ << "{\"fen\":\"" << pos.fen() << "\",\"site\":\"" << site << "\",\"depth\":" << depth
                << ",\"ply\":" << ply << ",\"in_check\":" << (pos.in_check() ? 1 : 0)
                << ",\"halfmove\":" << pos.halfmove_clock() << ",\"pieces\":" << popcount(pos.occupied())
                << ",\"score_cp\":" << score << "}\n";
  leaf_stream_->flush();
}

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
  if (nodes_limit_ > 0) {
    // Threads=1 (datagen, UCI default): the worker counter is the limit. A CAS
    // on the shared atomic every node was several times the increment itself.
    if (threads_ <= 1) {
      if (w.nodes >= static_cast<uint64_t>(nodes_limit_)) {
        time_expired_.store(true, std::memory_order_relaxed);
        return true;
      }
      return cancelled_.load(std::memory_order_relaxed);
    }
    if ((w.nodes & 15ULL) != 0) return stopped();
    const uint64_t total = nodes_.fetch_add(w.nodes - w.published_nodes, std::memory_order_relaxed) +
                           (w.nodes - w.published_nodes);
    w.published_nodes = w.nodes;
    if (total >= static_cast<uint64_t>(nodes_limit_)) {
      time_expired_.store(true, std::memory_order_relaxed);
      return true;
    }
    return stopped();
  }
  if (stopped()) return true;
  if ((w.nodes & 255ULL) != 0) return false;
  if (pondering_.load(std::memory_order_relaxed) &&
      ponder_hit_requested_.exchange(false, std::memory_order_relaxed)) {
    pondering_.store(false, std::memory_order_relaxed);
    const int64_t now = steady_now_ns();
    start_ns_.store(now, std::memory_order_relaxed);
    deadline_ns_.store(now + static_cast<int64_t>(maximum_ms_) * 1'000'000LL, std::memory_order_relaxed);
  }
  flush_nodes(w);
  if (time_up()) {
    time_expired_.store(true, std::memory_order_relaxed);
    return true;
  }
  return false;
}

void Search::flush_nodes(SearchWorker& w) {
  const uint64_t pending = w.nodes - w.published_nodes;
  if (pending == 0) return;
  nodes_.fetch_add(pending, std::memory_order_relaxed);
  w.published_nodes = w.nodes;
}

int Search::evaluate_for_search(const Position& pos) const {
  const int score = evaluate(pos);
  if (eval_scale_permille_ == 1000 || is_mate_score(score)) return score;
  return score * eval_scale_permille_ / 1000;
}

int Search::correction(const SearchWorker& w, const Position& pos, const SearchStack* ss) const {
  const Color stm = pos.side_to_move();
  int sum = 2 * w.pawn_corr[stm][corr_index(pos.pawn_key())] + 2 * w.nonpawn_corr[stm][corr_index(pos.nonpawn_key())];
  const SearchStack* prev = ss - 1;
  if (prev->current_move && prev->moved_piece != NO_PIECE) sum += w.cont_corr[prev->moved_piece][prev->current_move.to()];
  return std::clamp(sum / (4 * kCorrGrain), -200, 200);
}

void Search::update_correction(SearchWorker& w, const Position& pos, const SearchStack* ss, int diff, int depth) {
  const Color stm = pos.side_to_move();
  corr_update(w.pawn_corr[stm][corr_index(pos.pawn_key())], diff, depth);
  corr_update(w.nonpawn_corr[stm][corr_index(pos.nonpawn_key())], diff, depth);
  const SearchStack* prev = ss - 1;
  if (prev->current_move && prev->moved_piece != NO_PIECE)
    corr_update(w.cont_corr[prev->moved_piece][prev->current_move.to()], diff, depth);
}

int Search::quiet_score(const SearchWorker& w, const Position& pos, const SearchStack* ss, Move m) const {
  const Piece pc = pos.piece_on(m.from());
  const Square to = m.to();
  int s = 2 * w.main_history[pos.side_to_move()][from_to(m)];
  if (pc != NO_PIECE) {
    if ((ss - 1)->cont_hist) s += 2 * (*(ss - 1)->cont_hist)[pc][to];
    if ((ss - 2)->cont_hist) s += (*(ss - 2)->cont_hist)[pc][to];
    if ((ss - 4)->cont_hist) s += (*(ss - 4)->cont_hist)[pc][to];
    if ((ss - 6)->cont_hist) s += (*(ss - 6)->cont_hist)[pc][to] / 2;
  }
  if (policy_ && policy_->is_enabled()) s += policy_->score_move(pos, m) * 32;
  return s;
}

int Search::capture_score(const SearchWorker& w, const Position& pos, Move m) const {
  const Piece pc = pos.piece_on(m.from());
  const int hist = pc == NO_PIECE ? 0 : w.capture_history[pc][m.to()][captured_type(pos, m)];
  return 16 * captured_value(pos, m) + hist;
}

void Search::update_continuation(SearchStack* ss, Piece pc, Square to, int bonus) {
  if (pc == NO_PIECE) return;
  if ((ss - 1)->cont_hist) history_update((*(ss - 1)->cont_hist)[pc][to], bonus);
  if ((ss - 2)->cont_hist) history_update((*(ss - 2)->cont_hist)[pc][to], bonus);
  if ((ss - 4)->cont_hist) history_update((*(ss - 4)->cont_hist)[pc][to], bonus);
  if ((ss - 6)->cont_hist) history_update((*(ss - 6)->cont_hist)[pc][to], bonus / 2);
}

void Search::update_quiet_histories(SearchWorker& w, const Position& pos, SearchStack* ss, Move m, int bonus) {
  history_update(w.main_history[pos.side_to_move()][from_to(m)], bonus);
  update_continuation(ss, pos.piece_on(m.from()), m.to(), bonus);
}

void Search::update_capture_history(SearchWorker& w, const Position& pos, Move m, int bonus) {
  const Piece pc = pos.piece_on(m.from());
  if (pc == NO_PIECE) return;
  history_update(w.capture_history[pc][m.to()][captured_type(pos, m)], bonus);
}

int Search::quiescence(Position& pos, SearchWorker& w, SearchStack* ss, int alpha, int beta) {
  NSCE_STAT_INC(w, qnodes);
  if (count_node(w)) return 0;

  const bool pv_node = beta - alpha > 1;
  const int ply = ss->ply;
  const bool in_check = pos.in_check();
  ss->in_check = in_check;
  w.pv_len[ply] = 0;
  if (pv_node && ply + 1 > w.sel_depth) w.sel_depth = ply + 1;

  if (pos.is_draw_in_search(w.root_history_size)) {
    if (in_check && pos.halfmove_clock() >= 100) {
      MoveList evasions;
      generate_legal_evasions(pos, evasions);
      if (evasions.size == 0) return mated_in(ply);
    }
    return draw_score(w);
  }
  if (ply >= SearchWorker::kMaxPly - 1) return in_check ? 0 : evaluate_for_search(pos);

  TTEntry tte;
  if (use_tt_) NSCE_STAT_INC(w, tt_probes);
  const bool tt_hit = use_tt_ && tt_.probe(pos.key(), tte);
  const int tt_bound = tt_hit ? static_cast<int>(tte.bound) : static_cast<int>(BOUND_NONE);
  const int tt_score = tt_bound != BOUND_NONE ? TranspositionTable::score_from_tt(tte.score, ply) : VALUE_NONE;
  const Move tt_move = tt_hit ? Move{tte.move} : Move{};
  if (tt_hit) NSCE_STAT_INC(w, tt_hits);
  if (!pv_node && tt_score != VALUE_NONE && (tt_bound & (tt_score >= beta ? BOUND_LOWER : BOUND_UPPER))) {
    NSCE_STAT_INC(w, qs_tt_cutoffs);
    return tt_score;
  }

  int raw_eval = VALUE_NONE;
  int best_score = -VALUE_INFINITE;
  int futility_base = -VALUE_INFINITE;
  if (in_check) {
    ss->static_eval = VALUE_NONE;
  } else {
    raw_eval = raw_eval_from_tt(tt_hit, tte);
    if (raw_eval == VALUE_NONE) {
      NSCE_STAT_INC(w, evaluations);
      raw_eval = evaluate_for_search(pos);
    }
    const int static_eval = std::clamp(raw_eval + correction(w, pos, ss), -kMateBound + 1, kMateBound - 1);
    ss->static_eval = best_score = static_eval;
    NSCE_STAT_ADD(w, eval_abs_sum, std::abs(static_eval));
    if (tt_score != VALUE_NONE && (tt_bound & (tt_score > best_score ? BOUND_LOWER : BOUND_UPPER))) {
      best_score = tt_score;
      NSCE_STAT_INC(w, tt_eval_substitutions);
    }
    record_leaf(pos, "q_stand_pat", 0, ply, best_score);
    if (best_score >= beta) {
      if (!is_mate_score(best_score) && !pv_node) best_score = (best_score + beta) / 2;
      if (use_tt_ && !tt_hit) tt_.store(pos.key(), 0, best_score, BOUND_LOWER, Move{}, ply, raw_eval);
      return best_score;
    }
    alpha = std::max(alpha, best_score);
    futility_base = static_eval + tune_.qs_futility;
  }

  MovePicker mp;
  if (in_check)
    generate_legal_evasions(pos, mp.list);
  else
    generate_legal_noisy(pos, mp.list);
  if (in_check && mp.list.size == 0) return mated_in(ply);
  NSCE_STAT_ADD(w, generated_moves, mp.list.size);
  mp.prescore([&](Move m, int& s) {
    if (m == tt_move)
      s = kTTMoveScore;
    else if (is_noisy(m))
      s = kGoodNoisyScore + capture_score(w, pos, m);
    else
      return false;
    return true;
  });
  const auto score_quiet = [&](Move m) { return quiet_score(w, pos, ss, m); };

  Move best_move{};
  int move_count = 0;
  while (Move m = mp.next(pos, false, false, score_quiet)) {
    ++move_count;
    const bool capture = m.is_capture() || m.is_ep();
    if (best_score > -kMateBound) {
      if (!in_check && !m.is_promotion() && use_futility_ && !gives_check(pos, m)) {
        const int futility_value = futility_base + captured_value(pos, m);
        if (futility_value <= alpha) {
          best_score = std::max(best_score, futility_value);
          continue;
        }
        if (use_see_ && futility_base <= alpha && !see_ge(pos, m, 1)) {
          best_score = std::max(best_score, futility_base);
          continue;
        }
      }
      if (in_check && !capture && move_count > 2) continue;
      if (use_see_) {
        NSCE_STAT_INC(w, see_prune_calls);
        if (!see_ge(pos, m, -80)) {
          NSCE_STAT_INC(w, see_prunes);
          continue;
        }
      }
    }

    const Piece moving = pos.piece_on(m.from());
    ss->current_move = m;
    ss->moved_piece = moving;
    ss->cont_hist = &w.continuation[moving][m.to()];
    StateInfo st;
    pos.do_move(m, st);
    tt_.prefetch(pos.key());
    const int score = -quiescence(pos, w, ss + 1, -beta, -alpha);
    pos.undo_move(m, st);
    if (stopped()) return 0;

    if (score > best_score) {
      best_score = score;
      if (score > alpha) {
        best_move = m;
        if (pv_node && !silent_) {
          w.pv[ply][0] = m;
          for (int j = 0; j < w.pv_len[ply + 1]; ++j) w.pv[ply][j + 1] = w.pv[ply + 1][j];
          w.pv_len[ply] = w.pv_len[ply + 1] + 1;
        }
        if (score >= beta) {
          NSCE_STAT_INC(w, beta_cutoffs);
          if (move_count == 1) NSCE_STAT_INC(w, first_move_cutoffs);
          break;
        }
        alpha = score;
      }
    }
  }

  if (in_check && best_score == -VALUE_INFINITE) return mated_in(ply);
  if (best_score >= beta && !is_mate_score(best_score)) best_score = (3 * best_score + beta) / 4;
  if (use_tt_)
    tt_.store(pos.key(), 0, best_score, best_score >= beta ? BOUND_LOWER : BOUND_UPPER, best_move, ply, raw_eval);
  return best_score;
}

int Search::search(Position& pos, SearchWorker& w, SearchStack* ss, int depth, int alpha, int beta, bool cut_node) {
  const bool pv_node = beta - alpha > 1;
  const int ply = ss->ply;
  const bool root_node = ply == 0;

  if (depth <= 0) return quiescence(pos, w, ss, alpha, beta);
  if (count_node(w)) return 0;

  w.pv_len[ply] = 0;
  if (pv_node && ply + 1 > w.sel_depth) w.sel_depth = ply + 1;
  const bool in_check = pos.in_check();
  ss->in_check = in_check;

  if (!root_node) {
    if (pos.is_draw_in_search(w.root_history_size)) {
      if (in_check && pos.halfmove_clock() >= 100) {
        MoveList evasions;
        generate_legal_evasions(pos, evasions);
        if (evasions.size == 0) return mated_in(ply);
      }
      return draw_score(w);
    }
    if (ply >= SearchWorker::kMaxPly - 1) return in_check ? 0 : evaluate_for_search(pos);
    alpha = std::max(alpha, mated_in(ply));
    beta = std::min(beta, mate_in(ply + 1));
    if (alpha >= beta) return alpha;
  }

  if (in_check && tune_.check_ext) depth += 1;
  depth = std::min(depth, SearchWorker::kMaxPly - 1);

  (ss + 1)->excluded = Move{};
  (ss + 2)->cutoff_count = 0;
  if (ply + 2 < SearchWorker::kMaxPly) w.killers[ply + 2][0] = w.killers[ply + 2][1] = Move{};

  const Move excluded = ss->excluded;
  const Color us = pos.side_to_move();

  TTEntry tte;
  bool tt_hit = false;
  if (use_tt_ && !excluded) {
    NSCE_STAT_INC(w, tt_probes);
    tt_hit = tt_.probe(pos.key(), tte);
    if (tt_hit) NSCE_STAT_INC(w, tt_hits);
  }
  Move tt_move = tt_hit ? Move{tte.move} : Move{};
  if (root_node && w.best_move) tt_move = w.best_move;
  const int tt_bound = tt_hit ? static_cast<int>(tte.bound) : static_cast<int>(BOUND_NONE);
  const int tt_score = tt_bound != BOUND_NONE ? TranspositionTable::score_from_tt(tte.score, ply) : VALUE_NONE;
  const int tt_depth = tt_hit ? tte.depth : -1;
  if (!excluded) {
    ss->tt_pv = pv_node || (tt_hit && tte.is_pv);
    ss->tt_hit = tt_hit;
  }
  const bool tt_capture = tt_move && (tt_move.is_capture() || tt_move.is_ep());
  const Piece tt_piece = tt_move ? pos.piece_on(tt_move.from()) : NO_PIECE;
  const bool tt_move_sane = tt_piece != NO_PIECE && color_of(tt_piece) == us;

  if (!pv_node && !excluded && tt_score != VALUE_NONE && tt_depth >= depth && pos.halfmove_clock() < 90 &&
      (tt_bound & (tt_score >= beta ? BOUND_LOWER : BOUND_UPPER))) {
    if (tt_move_sane && tt_score >= beta && !is_noisy(tt_move))
      update_quiet_histories(w, pos, ss, tt_move, std::min(tune_.hist_bonus_mul * depth - tune_.hist_bonus_sub,
                                                           tune_.hist_bonus_cap));
    NSCE_STAT_INC(w, tt_cutoffs);
    return tt_score;
  }

  int raw_eval = VALUE_NONE;
  int eval = VALUE_NONE;
  bool improving = false;
  bool opp_worsening = false;
  if (in_check) {
    ss->static_eval = VALUE_NONE;
  } else if (excluded) {
    eval = ss->static_eval;
  } else {
    raw_eval = raw_eval_from_tt(tt_hit, tte);
    if (raw_eval == VALUE_NONE) {
      NSCE_STAT_INC(w, evaluations);
      raw_eval = evaluate_for_search(pos);
    }
    const int corr = correction(w, pos, ss);
    int static_eval = std::clamp(raw_eval + corr, -kMateBound + 1, kMateBound - 1);
    const int hm = pos.halfmove_clock();
    if (hm >= 8) {
      static_eval = static_eval * (256 - std::min(hm, 200)) / 256;
      NSCE_STAT_INC(w, halfmove_scaled_nodes);
    }
    ss->static_eval = eval = static_eval;
    record_leaf(pos, "static", depth, ply, static_eval);
    NSCE_STAT_ADD(w, eval_abs_sum, std::abs(raw_eval));
    NSCE_STAT_ADD(w, correction_abs_sum, std::abs(corr));
    if (tt_score != VALUE_NONE && (tt_bound & (tt_score > eval ? BOUND_LOWER : BOUND_UPPER))) {
      eval = tt_score;
      NSCE_STAT_INC(w, tt_eval_substitutions);
    }

    const Move prev = (ss - 1)->current_move;
    if (prev && !is_noisy(prev) && !(ss - 1)->in_check && (ss - 1)->static_eval != VALUE_NONE) {
      const int bonus = std::clamp(-10 * ((ss - 1)->static_eval + ss->static_eval), -1600, 1400) + 600;
      history_update(w.main_history[~us][from_to(prev)], bonus);
    }
  }

  if (!in_check) {
    if ((ss - 2)->static_eval != VALUE_NONE)
      improving = ss->static_eval > (ss - 2)->static_eval;
    else if ((ss - 4)->static_eval != VALUE_NONE)
      improving = ss->static_eval > (ss - 4)->static_eval;
    else
      improving = true;
    opp_worsening = (ss - 1)->static_eval != VALUE_NONE && ss->static_eval > -(ss - 1)->static_eval;
    if (improving) NSCE_STAT_INC(w, improving_nodes);
  }

  if (!in_check && !excluded) {
    if (use_razoring_ && !pv_node && depth <= 3 &&
        eval < alpha - tune_.razor_margin - tune_.razor_per_depth_sq * depth * depth) {
      NSCE_STAT_INC(w, razor_attempts);
      const int score = quiescence(pos, w, ss, alpha - 1, alpha);
      if (stopped()) return 0;
      if (score < alpha && !is_mate_score(score)) {
        NSCE_STAT_INC(w, razor_cutoffs);
        return score;
      }
    }

    const int rfp_margin = tune_.rfp_per_depth * (depth - static_cast<int>(improving)) -
                           (opp_worsening ? tune_.rfp_per_depth / 4 : 0);
    if (use_rfp_ && !ss->tt_pv && depth <= tune_.rfp_max_depth && eval >= beta && eval < kMateBound &&
        beta > -kMateBound && eval - rfp_margin >= beta) {
      NSCE_STAT_INC(w, rfp_cutoffs);
      return beta + (eval - beta) / 3;
    }

    if (use_null_move_ && !pv_node && (ss - 1)->current_move && eval >= beta &&
        ss->static_eval >= beta - 20 * depth + 160 && depth >= tune_.nmp_min_depth && ply >= w.nmp_min_ply &&
        beta > -kMateBound && non_pawn_material(pos, us) > 0) {
      NSCE_STAT_INC(w, null_attempts);
      const int R = tune_.nmp_base + depth / std::max(1, tune_.nmp_depth_div) +
                    std::min((eval - beta) / std::max(1, tune_.nmp_eval_div), tune_.nmp_eval_cap);
      ss->current_move = Move{};
      ss->moved_piece = NO_PIECE;
      ss->cont_hist = nullptr;
      StateInfo st;
      pos.do_null_move(st);
      tt_.prefetch(pos.key());
      int null_score = -search(pos, w, ss + 1, depth - R, -beta, -beta + 1, !cut_node);
      pos.undo_null_move(st);
      if (stopped()) return 0;
      if (null_score >= beta && null_score < kMateBound) {
        if (w.nmp_min_ply || depth < tune_.nmp_verify_depth) {
          NSCE_STAT_INC(w, null_cutoffs);
          return null_score;
        }
        w.nmp_min_ply = ply + 3 * (depth - R) / 4;
        const int verified = search(pos, w, ss, depth - R, beta - 1, beta, false);
        w.nmp_min_ply = 0;
        if (stopped()) return 0;
        if (verified >= beta) {
          NSCE_STAT_INC(w, null_cutoffs);
          return null_score;
        }
      }
    }
  }

  if (!excluded && !tt_move && depth >= tune_.iir_depth) {
    NSCE_STAT_INC(w, iir_reductions);
    depth -= 1;
  }

  const int pc_beta = beta + tune_.probcut_margin - tune_.probcut_improving * static_cast<int>(improving);
  if (use_probcut_ && !pv_node && !in_check && !excluded && depth >= tune_.probcut_min_depth &&
      !is_mate_score(beta) && !(tt_score != VALUE_NONE && tt_depth >= depth - 3 && tt_score < pc_beta)) {
    NSCE_STAT_INC(w, probcut_attempts);
    MovePicker pc;
    generate_legal_noisy(pos, pc.list);
    pc.prescore([&](Move m, int& s) {
      s = m == tt_move ? kTTMoveScore : capture_score(w, pos, m);
      return true;
    });
    const int pc_depth = depth - tune_.probcut_depth_sub;
    while (Move m = pc.next(pos, false, true, [](Move) { return 0; })) {
      if (use_see_ && !see_ge(pos, m, pc_beta - ss->static_eval)) continue;
      const Piece moving = pos.piece_on(m.from());
      ss->current_move = m;
      ss->moved_piece = moving;
      ss->cont_hist = &w.continuation[moving][m.to()];
      StateInfo st;
      pos.do_move(m, st);
      tt_.prefetch(pos.key());
      int score = -quiescence(pos, w, ss + 1, -pc_beta, -pc_beta + 1);
      if (score >= pc_beta && pc_depth > 0)
        score = -search(pos, w, ss + 1, pc_depth, -pc_beta, -pc_beta + 1, !cut_node);
      pos.undo_move(m, st);
      if (stopped()) return 0;
      if (score >= pc_beta) {
        NSCE_STAT_INC(w, probcut_cutoffs);
        if (use_tt_) tt_.store(pos.key(), pc_depth + 1, score, BOUND_LOWER, m, ply, raw_eval, ss->tt_pv);
        return score;
      }
    }
  }

  MovePicker mp;
  generate_legal(pos, mp.list);
  if (root_node && !root_moves_.empty()) {
    int kept = 0;
    for (int i = 0; i < mp.list.size; ++i)
      if (std::find(root_moves_.begin(), root_moves_.end(), mp.list.moves[i]) != root_moves_.end())
        mp.list.moves[kept++] = mp.list.moves[i];
    mp.list.size = kept;
  }
  NSCE_STAT_ADD(w, generated_moves, mp.list.size);
  if (root_node) NSCE_STAT_ADD(w, root_moves, mp.list.size);

  const Move prev = (ss - 1)->current_move;
  const Move counter =
      (prev && (ss - 1)->moved_piece != NO_PIECE) ? w.countermove[(ss - 1)->moved_piece][prev.to()] : Move{};
  const Move killer0 = w.killers[ply][0];
  const Move killer1 = w.killers[ply][1];
  mp.prescore([&](Move m, int& s) {
    if (m == tt_move)
      s = kTTMoveScore;
    else if (is_noisy(m))
      s = kGoodNoisyScore + capture_score(w, pos, m);
    else if (m == killer0)
      s = kKillerScore + 2;
    else if (m == killer1)
      s = kKillerScore + 1;
    else if (m == counter)
      s = kKillerScore;
    else
      return false;
    return true;
  });
  const auto score_quiet = [&](Move m) { return quiet_score(w, pos, ss, m); };

  const int alpha_orig = alpha;
  int best_score = -VALUE_INFINITE;
  Move best_move{};
  Move quiets[64];
  Move captures[32];
  int quiet_count = 0;
  int capture_count = 0;
  int move_count = 0;
  bool skip_quiets = false;
  const int lmp_limit = (tune_.lmp_base + depth * depth) / (2 - static_cast<int>(improving));
  const bool has_non_pawn = non_pawn_material(pos, us) > 0;
  const bool controller_on = controller_ && controller_->is_enabled();

  while (Move m = mp.next(pos, use_see_, skip_quiets, score_quiet)) {
    if (m == excluded) continue;
    const bool capture = m.is_capture() || m.is_ep();
    const bool quiet = !capture && !m.is_promotion();
    if (quiet && skip_quiets) continue;

    ++move_count;
    const Piece moving = pos.piece_on(m.from());
    const Square to = m.to();
    const bool check = gives_check(pos, m);
    int new_depth = depth - 1;

    int cont_hist = 0;
    int hist = 0;
    if (quiet) {
      if ((ss - 1)->cont_hist) cont_hist += (*(ss - 1)->cont_hist)[moving][to];
      if ((ss - 2)->cont_hist) cont_hist += (*(ss - 2)->cont_hist)[moving][to];
      hist = cont_hist + 2 * w.main_history[us][from_to(m)];
    } else {
      hist = w.capture_history[moving][to][captured_type(pos, m)];
    }

    const int base_r = quiet ? lmr_quiet_[std::min(depth, 63)][std::min(move_count, 63)]
                             : lmr_capture_[std::min(depth, 63)][std::min(move_count, 63)];

    if (!root_node && best_score > -kMateBound && has_non_pawn) {
      if (use_lmp_ && quiet && !check && move_count >= lmp_limit) {
        skip_quiets = true;
        NSCE_STAT_INC(w, lmp_prunes);
        continue;
      }
      int lmr_depth = new_depth - base_r / 1024;
      if (!quiet || check) {
        if (capture && !check && !in_check && use_futility_ && lmr_depth < 7 &&
            ss->static_eval + tune_.cap_futility_base + tune_.cap_futility_per_depth * lmr_depth +
                    captured_value(pos, m) + hist / 8 <=
                alpha) {
          NSCE_STAT_INC(w, futility_prunes);
          continue;
        }
        if (use_see_ && !see_ge(pos, m, -tune_.see_noisy_per_depth * depth)) {
          NSCE_STAT_INC(w, see_search_prunes);
          continue;
        }
      } else {
        if (lmr_depth < 6 && cont_hist < -tune_.hist_prune * depth) {
          NSCE_STAT_INC(w, lmp_prunes);
          continue;
        }
        lmr_depth += hist / 3600;
        if (use_futility_ && !in_check && lmr_depth < tune_.futility_max_depth &&
            ss->static_eval + tune_.futility_base + (best_move ? 0 : 60) + tune_.futility_per_depth * lmr_depth <=
                alpha) {
          NSCE_STAT_INC(w, futility_prunes);
          continue;
        }
        lmr_depth = std::max(lmr_depth, 0);
        if (use_see_ && !see_ge(pos, m, -tune_.see_quiet_per_depth * lmr_depth * lmr_depth)) {
          NSCE_STAT_INC(w, see_search_prunes);
          continue;
        }
      }
    }

    int extension = 0;
    if (!root_node && !excluded && m == tt_move && ply < 2 * w.root_depth &&
        depth >= tune_.se_min_depth + static_cast<int>(ss->tt_pv) && tt_score != VALUE_NONE &&
        !is_mate_score(tt_score) && (tt_bound & BOUND_LOWER) && tt_depth >= depth - tune_.se_tt_depth_sub) {
      NSCE_STAT_INC(w, singular_attempts);
      const int sbeta = tt_score - (tune_.se_margin + 64 * static_cast<int>(ss->tt_pv && !pv_node)) * depth / 64;
      ss->excluded = m;
      const int sscore = search(pos, w, ss, new_depth / 2, sbeta - 1, sbeta, cut_node);
      ss->excluded = Move{};
      if (stopped()) return 0;
      if (sscore < sbeta) {
        extension = 1;
        if (!pv_node && sscore < sbeta - tune_.se_double_margin && ss->double_extensions < 8) extension = 2;
        NSCE_STAT_INC(w, singular_extensions);
      } else if (sbeta >= beta) {
        return sbeta;
      } else if (tt_score >= beta) {
        extension = -2 + static_cast<int>(pv_node);
      } else if (cut_node) {
        extension = -2;
      }
    }
    (ss + 1)->double_extensions = ss->double_extensions + static_cast<int>(extension >= 2);
    new_depth += extension;

    ss->move_count = move_count;
    ss->current_move = m;
    ss->moved_piece = moving;
    ss->cont_hist = &w.continuation[moving][to];
    const uint64_t nodes_before = w.nodes;
    const Key key_before = pos.key();
    StateInfo st;
    pos.do_move(m, st);
    tt_.prefetch(pos.key());

    int score = -VALUE_INFINITE;
    if (use_lmr_ && depth >= 2 && move_count > 1 + static_cast<int>(root_node)) {
      NSCE_STAT_INC(w, lmr_attempts);
      int r = base_r;
      if (!improving) r += 512;
      if (ss->tt_pv) r -= 1024;
      if (cut_node) r += 2048;
      if (tt_capture && quiet) r += 1024;
      if ((ss + 1)->cutoff_count > 3) r += 1024;
      if (check) r -= 1024;
      if (m == killer0 || m == killer1 || m == counter) r -= 512;
      ss->stat_score = quiet ? hist - 4000 : hist;
      r -= ss->stat_score * 1024 / std::max(1, tune_.lmr_hist_div);
      if (controller_on) {
        const int see_sign = quiet ? 0 : 1;
        r += 1024 * controller_->reduction_delta(depth, move_count, ss->static_eval, alpha, beta, quiet, 0, hist,
                                                 improving, cut_node, see_sign);
      }
      const int reduced = std::max(1, std::min(new_depth - r / 1024, new_depth));
      score = -search(pos, w, ss + 1, reduced, -alpha - 1, -alpha, true);
      bool researched = false;
      if (score > alpha && reduced < new_depth) {
        const bool deeper = score > best_score + 40 + 2 * new_depth;
        const bool shallower = score < best_score + 10;
        new_depth += static_cast<int>(deeper) - static_cast<int>(shallower);
        if (new_depth > reduced) {
          NSCE_STAT_INC(w, lmr_researches);
          researched = true;
          score = -search(pos, w, ss + 1, new_depth, -alpha - 1, -alpha, !cut_node);
        }
        if (quiet) {
          const int b = score <= alpha ? -std::min(tune_.hist_malus_mul * new_depth, tune_.hist_malus_cap)
                        : score >= beta ? std::min(tune_.hist_bonus_mul * new_depth, tune_.hist_bonus_cap)
                                        : 0;
          if (b) update_continuation(ss, moving, to, b);
        }
      }
      if (controller_ && controller_->telemetry_open())
        controller_->log_decision(key_before, depth, move_count, r / 1024, score, score >= beta, hist, improving,
                                  cut_node, quiet, researched);
    } else if (!pv_node || move_count > 1) {
      score = -search(pos, w, ss + 1, new_depth, -alpha - 1, -alpha, !cut_node);
    }
    if (pv_node && (move_count == 1 || (score > alpha && (root_node || score < beta))))
      score = -search(pos, w, ss + 1, new_depth, -beta, -alpha, false);

    pos.undo_move(m, st);
    if (stopped()) return 0;
    if (root_node) w.root_move_nodes[from_to(m)] += w.nodes - nodes_before;

    if (score > best_score) {
      best_score = score;
      if (score > alpha) {
        best_move = m;
        w.pv[ply][0] = m;
        if (silent_ && !root_node) {
          w.pv_len[ply] = 1;
        } else {
          for (int j = 0; j < w.pv_len[ply + 1]; ++j) w.pv[ply][j + 1] = w.pv[ply + 1][j];
          w.pv_len[ply] = w.pv_len[ply + 1] + 1;
        }
        if (score >= beta) {
          ss->cutoff_count += 1 + static_cast<int>(!tt_move);
          NSCE_STAT_INC(w, beta_cutoffs);
          NSCE_STAT_ADD(w, cutoff_index_sum, move_count - 1);
          if (move_count == 1) NSCE_STAT_INC(w, first_move_cutoffs);
          break;
        }
        alpha = score;
      }
    }
    if (m != best_move) {
      if (quiet && quiet_count < 64)
        quiets[quiet_count++] = m;
      else if (capture && capture_count < 32)
        captures[capture_count++] = m;
    }
  }

  if (move_count == 0) {
    if (excluded) return alpha;
    return in_check ? mated_in(ply) : draw_score(w);
  }

  if (best_score >= beta) {
    const int bonus =
        std::min(tune_.hist_bonus_mul * (depth + static_cast<int>(best_score > beta + 100)) - tune_.hist_bonus_sub,
                 tune_.hist_bonus_cap);
    const int malus = std::min(tune_.hist_malus_mul * depth, tune_.hist_malus_cap);
    if (!is_noisy(best_move)) {
      update_quiet_histories(w, pos, ss, best_move, bonus);
      if (w.killers[ply][0] != best_move) {
        w.killers[ply][1] = w.killers[ply][0];
        w.killers[ply][0] = best_move;
      }
      if (prev && (ss - 1)->moved_piece != NO_PIECE) w.countermove[(ss - 1)->moved_piece][prev.to()] = best_move;
      for (int i = 0; i < quiet_count; ++i) update_quiet_histories(w, pos, ss, quiets[i], -malus);
    } else {
      update_capture_history(w, pos, best_move, bonus);
    }
    for (int i = 0; i < capture_count; ++i) update_capture_history(w, pos, captures[i], -malus);
    if (prev && !is_noisy(prev) && (ss - 1)->moved_piece != NO_PIECE &&
        (ss - 1)->move_count == 1 + static_cast<int>((ss - 1)->tt_hit))
      update_continuation(ss - 1, (ss - 1)->moved_piece, prev.to(), -malus);
  } else if (!best_move && prev && !is_noisy(prev) && (ss - 1)->moved_piece != NO_PIECE) {
    const int bonus = std::min(tune_.hist_bonus_mul * depth - tune_.hist_bonus_sub, tune_.hist_bonus_cap);
    update_continuation(ss - 1, (ss - 1)->moved_piece, prev.to(), bonus);
    history_update(w.main_history[~us][from_to(prev)], bonus / 2);
  }

  if (best_score >= beta && !pv_node && !is_mate_score(best_score) && !is_mate_score(beta))
    best_score = (best_score * depth + beta) / (depth + 1);

  if (!excluded) {
    const Bound bound = best_score >= beta ? BOUND_LOWER : (best_move && best_score > alpha_orig) ? BOUND_EXACT
                                                                                                : BOUND_UPPER;
    if (use_tt_) tt_.store(pos.key(), depth, best_score, bound, best_move, ply, raw_eval, ss->tt_pv);
    if (!in_check && !(best_move && (best_move.is_capture() || best_move.is_ep())) && !is_mate_score(best_score) &&
        !(bound == BOUND_LOWER && best_score <= ss->static_eval) &&
        !(bound == BOUND_UPPER && best_score >= ss->static_eval))
      update_correction(w, pos, ss, best_score - ss->static_eval, depth);
  }
  return best_score;
}

void Search::report_iteration(const SearchWorker& w, int depth, int score) const {
  if (silent_) return;
  const int64_t ms = (steady_now_ns() - start_ns_.load(std::memory_order_relaxed)) / 1'000'000LL;
  const uint64_t nodes = nodes_.load(std::memory_order_relaxed);
  const uint64_t nps = ms > 0 ? nodes * 1000ULL / static_cast<uint64_t>(ms) : nodes;
  std::string pv;
  for (int i = 0; i < w.root_pv_len; ++i) {
    if (i) pv += ' ';
    pv += move_to_uci(w.root_pv[i]);
  }
  std::cout << "info depth " << depth << " seldepth " << w.sel_depth << " score " << uci_score(score) << " nodes "
            << nodes << " nps " << nps << " hashfull " << tt_.hashfull() << " time " << ms << " pv " << pv
            << std::endl;
}

bool Search::soft_time_exceeded(const SearchWorker& w, int stable_iterations, int score_drop) const {
  const double elapsed =
      static_cast<double>(steady_now_ns() - start_ns_.load(std::memory_order_relaxed)) / 1'000'000.0;
  const double best_fraction =
      w.best_move ? static_cast<double>(w.root_move_nodes[from_to(w.best_move)]) / std::max<uint64_t>(1, w.nodes)
                  : 0.5;
  const double node_factor = (1.5 - best_fraction) * 1.35;
  const double stability_factor = 1.3 - 0.06 * std::min(stable_iterations, 8);
  const double score_factor = std::clamp(1.0 + score_drop * 0.012, 0.85, 1.5);
  const double soft = optimum_ms_ * node_factor * stability_factor * score_factor;
  return elapsed >= std::min(soft, static_cast<double>(maximum_ms_));
}

void Search::iterative_deepening(SearchWorker& w, bool is_main, int max_depth) {
  Position pos = root_;
  w.root_history_size = pos.history_size();
  w.best_move = Move{};
  w.best_score = -VALUE_INFINITE;
  w.completed_depth = 0;
  w.root_pv_len = 0;
  w.nmp_min_ply = 0;
  std::memset(w.killers, 0, sizeof(w.killers));
  std::memset(w.root_move_nodes, 0, sizeof(w.root_move_nodes));

  constexpr int kStackSize = SearchWorker::kMaxPly + SearchWorker::kStackPad + 4;
  std::vector<SearchStack> stack(kStackSize);
  SearchStack* root_ss = stack.data() + SearchWorker::kStackPad;

  Move last_best{};
  int stable_iterations = 0;
  int previous_score = 0;

  for (int depth = 1; depth <= max_depth; ++depth) {
    if (stopped()) break;
    w.root_depth = depth;
    w.sel_depth = 0;

    int delta = tune_.asp_delta_base;
    int alpha = -VALUE_INFINITE;
    int beta = VALUE_INFINITE;
    if (depth >= 4 && !is_mate_score(w.best_score)) {
      delta += w.best_score * w.best_score / 20000;
      alpha = std::max(-VALUE_INFINITE, w.best_score - delta);
      beta = std::min(VALUE_INFINITE, w.best_score + delta);
    }

    int score = -VALUE_INFINITE;
    while (true) {
      for (int i = 0; i < kStackSize; ++i) {
        stack[i] = SearchStack{};
        stack[i].ply = i - SearchWorker::kStackPad;
      }
      score = search(pos, w, root_ss, depth, alpha, beta, false);
      if (w.pv_len[0] > 0) {
        w.best_move = w.pv[0][0];
        w.root_pv_len = w.pv_len[0];
        std::copy(w.pv[0], w.pv[0] + w.pv_len[0], w.root_pv);
      }
      if (stopped()) break;
      if (score <= alpha) {
        beta = (alpha + beta) / 2;
        alpha = std::max(-VALUE_INFINITE, score - delta);
      } else if (score >= beta) {
        beta = std::min(VALUE_INFINITE, score + delta);
      } else {
        break;
      }
      delta += delta / 2;
    }
    if (is_main) flush_nodes(w);
    if (stopped()) break;

    w.completed_depth = depth;
    w.best_score = score;
    if (!is_main) continue;

    report_iteration(w, depth, score);
    if (w.best_move == last_best)
      ++stable_iterations;
    else
      stable_iterations = 0;
    last_best = w.best_move;
    const int score_drop = depth > 1 ? previous_score - score : 0;
    previous_score = score;

    if (use_soft_time_ && !pondering_.load(std::memory_order_relaxed) && depth >= 4 &&
        soft_time_exceeded(w, stable_iterations, score_drop))
      break;
  }
}

SearchInfo Search::go(const SearchLimits& limits) {
  prepare();
  return go_prepared(limits);
}

SearchInfo Search::go_prepared(const SearchLimits& limits) {
  nodes_.store(0, std::memory_order_relaxed);
  const int64_t start_ns = steady_now_ns();
  start_ns_.store(start_ns, std::memory_order_relaxed);
  deadline_ns_.store(std::numeric_limits<int64_t>::max(), std::memory_order_relaxed);
  tt_.new_search();
  main_worker_->nodes = 0;
  main_worker_->published_nodes = 0;
  main_worker_->stats = {};
  last_stats_ = {};

  optimum_ms_ = 0;
  maximum_ms_ = 0;
  use_soft_time_ = false;
  nodes_limit_ = limits.nodes;
  root_moves_ = limits.searchmoves;
  if (!limits.infinite && limits.movetime_ms > 0) {
    optimum_ms_ = maximum_ms_ = std::max(1, limits.movetime_ms - move_overhead_ms_);
  } else if (!limits.infinite && (limits.wtime > 0 || limits.btime > 0)) {
    const int time = root_.side_to_move() == WHITE ? limits.wtime : limits.btime;
    const int inc = root_.side_to_move() == WHITE ? limits.winc : limits.binc;
    const int left = std::max(1, time - move_overhead_ms_);
    const int mtg = limits.movestogo > 0 ? std::min(limits.movestogo, 50) : tune_.tm_moves_to_go;
    optimum_ms_ = std::min(left / mtg + 3 * inc / 4, left / 2);
    maximum_ms_ = std::min(left * 4 / 5, optimum_ms_ * 4);
    optimum_ms_ = std::max(1, std::min(optimum_ms_, maximum_ms_));
    maximum_ms_ = std::max(1, maximum_ms_);
    MoveList legal;
    generate_legal(root_, legal);
    if (legal.size == 1) optimum_ms_ = std::max(1, optimum_ms_ / 8);
    use_soft_time_ = true;
  }
  if (limits.ponder) pondering_.store(true, std::memory_order_relaxed);
  if (maximum_ms_ > 0)
    deadline_ns_.store(start_ns + static_cast<int64_t>(maximum_ms_) * 1'000'000LL, std::memory_order_relaxed);

  const int max_depth = std::min(limits.depth > 0 ? limits.depth : SearchWorker::kMaxPly - 1,
                                 SearchWorker::kMaxPly - 1);
  start_helper_pool();
  for (auto& helper : helper_workers_) {
    helper->nodes = 0;
    helper->published_nodes = 0;
    helper->stats = {};
  }

  launch_helper_job([this, max_depth](SearchWorker& worker) {
    iterative_deepening(worker, false, max_depth);
    flush_nodes(worker);
  });
  iterative_deepening(*main_worker_, true, max_depth);

  while (!cancelled_.load(std::memory_order_relaxed)) {
    if (!limits.infinite && !pondering_.load(std::memory_order_relaxed)) break;
    if (pondering_.load(std::memory_order_relaxed) && ponder_hit_requested_.load(std::memory_order_relaxed)) break;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  cancelled_.store(true, std::memory_order_relaxed);
  wait_helper_job();
  flush_nodes(*main_worker_);

  last_stats_ = main_worker_->stats;
  for (const auto& worker : helper_workers_) last_stats_ += worker->stats;
#if defined(NSCE_STATS)
  if (!silent_) {
    const uint64_t final_nodes = nodes_.load(std::memory_order_relaxed);
    const double qnode_pct = final_nodes ? 100.0 * static_cast<double>(last_stats_.qnodes) / final_nodes : 0.0;
    const double first_cut_pct =
        last_stats_.beta_cutoffs ? 100.0 * static_cast<double>(last_stats_.first_move_cutoffs) / last_stats_.beta_cutoffs
                                 : 0.0;
    std::cout << "info string stats qnodes_pct " << qnode_pct << " evals " << last_stats_.evaluations << " tt "
              << last_stats_.tt_hits << '/' << last_stats_.tt_probes << " tt_cutoffs " << last_stats_.tt_cutoffs
              << " first_cut_pct " << first_cut_pct << " lmr " << last_stats_.lmr_attempts << " researches "
              << last_stats_.lmr_researches << " se " << last_stats_.singular_extensions << '/'
              << last_stats_.singular_attempts << " null " << last_stats_.null_cutoffs << '/'
              << last_stats_.null_attempts << " rfp " << last_stats_.rfp_cutoffs << " razor "
              << last_stats_.razor_cutoffs << '/' << last_stats_.razor_attempts << " probcut "
              << last_stats_.probcut_cutoffs << '/' << last_stats_.probcut_attempts << " futility "
              << last_stats_.futility_prunes << " lmp " << last_stats_.lmp_prunes << " see_prunes "
              << last_stats_.see_search_prunes << std::endl;
  }
#endif

  const SearchWorker& w = *main_worker_;
  SearchInfo info;
  info.best_move = w.best_move;
  info.score = w.best_score == -VALUE_INFINITE ? 0 : w.best_score;
  info.depth = w.completed_depth;
  if (w.root_pv_len > 1 && w.root_pv[0] == w.best_move) info.ponder_move = w.root_pv[1];
  info.nodes = nodes_.load(std::memory_order_relaxed);
  info.time_ms = static_cast<int>((steady_now_ns() - start_ns_.load(std::memory_order_relaxed)) / 1'000'000LL);
  if (!info.best_move) {
    MoveList list;
    generate_legal(root_, list);
    if (!root_moves_.empty()) {
      for (Move move : list)
        if (std::find(root_moves_.begin(), root_moves_.end(), move) != root_moves_.end()) {
          info.best_move = move;
          break;
        }
    }
    if (!info.best_move && list.size) info.best_move = list.moves[0];
  }
  return info;
}

uint64_t Search::bench(int depth) {
  root_.set_startpos();
  SearchLimits limits;
  limits.depth = depth;
  auto info = go(limits);
  return info.nodes;
}

}  // namespace nsce
