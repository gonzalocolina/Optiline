#include "nsce/search.hpp"

#include "nsce/eval.hpp"
#include "nsce/movegen.hpp"
#include "nsce/policy.hpp"
#include "nsce/controller.hpp"
#include "nsce/see.hpp"

#include <algorithm>
#include <array>
#include <cstring>
#include <iostream>
#include <mutex>

namespace nsce {
namespace {

constexpr int FutilityMargin(int depth) { return 80 * depth; }
constexpr int RazorMargin = 300;
constexpr int RFPMargin(int depth) { return 100 * depth; }

int history_bonus(int depth) { return std::min(depth * depth, 400); }

void history_update(int& entry, int bonus) {
  entry += bonus - entry * std::abs(bonus) / 512;
}

}  // namespace

Search::Search() { tt_.resize(16); }

void Search::set_position(const Position& pos) { root_ = pos; }

void Search::set_threads(int n) { threads_ = std::clamp(n, 1, 64); }

bool Search::time_up() const {
  if (stop_.load(std::memory_order_relaxed)) return true;
  if (nodes_limit_ > 0 && static_cast<int64_t>(nodes_.load(std::memory_order_relaxed)) >= nodes_limit_)
    return true;
  if (maximum_ms_ <= 0) return false;
  auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start_).count();
  return ms >= maximum_ms_;
}

bool Search::count_node(SearchWorker& w) {
  ++w.nodes;
  if ((w.nodes & 1023ULL) != 0) return false;
  flush_nodes(w);
  return time_up();
}

void Search::flush_nodes(SearchWorker& w) {
  uint64_t pending = w.nodes - w.published_nodes;
  if (pending == 0) return;
  nodes_.fetch_add(pending, std::memory_order_relaxed);
  w.published_nodes = w.nodes;
}

void Search::score_moves(SearchWorker& w, const Position& pos, MoveList& list, Move tt_move, Move counter, int ply,
                         int* scores) const {
  const bool use_policy = PolicyNet::instance().is_enabled();
  for (int i = 0; i < list.size; ++i) {
    Move m = list.moves[i];
    int s = 0;
    if (m == tt_move)
      s = 2'000'000;
    else if (m.is_promotion()) {
      Piece victim = m.is_capture() ? pos.piece_on(m.to()) : NO_PIECE;
      int victim_value = victim == NO_PIECE ? 0 : piece_value(type_of(victim));
      s = 1'100'000 + piece_value(m.promotion()) + victim_value;
    }
    else if (m.is_capture() || m.is_ep()) {
      Piece victim = m.is_ep() ? make_piece(~pos.side_to_move(), PAWN) : pos.piece_on(m.to());
      Piece attacker = pos.piece_on(m.from());
      int victim_value = victim == NO_PIECE ? 0 : piece_value(type_of(victim));
      int attacker_value = attacker == NO_PIECE ? 0 : piece_value(type_of(attacker));
      int see_score = victim_value <= attacker_value ? static_exchange_eval(pos, m) : 0;
      s = 1'000'000 + victim_value * 16 - attacker_value + std::clamp(see_score, -500, 500);
    } else if (ply < SearchWorker::kMaxPly && m == w.killers[ply][0])
      s = 900'000;
    else if (ply < SearchWorker::kMaxPly && m == w.killers[ply][1])
      s = 800'000;
    else if (m == counter)
      s = 700'000;
    else {
      Piece pc = pos.piece_on(m.from());
      if (pc != NO_PIECE) s = w.history[pc][m.to()];
      if (use_policy) s += PolicyNet::instance().score_move(pos, m) * 5 / 4;
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

void Search::update_quiet_stats(SearchWorker& w, const Position& pos, Move best, const Move* quiets,
                                int quiet_count, int depth, int ply, Move prev) {
  if (best.is_capture() || best.is_ep()) return;
  int bonus = history_bonus(depth);
  Piece pc = pos.piece_on(best.from());
  if (pc != NO_PIECE) history_update(w.history[pc][best.to()], bonus);

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
    if (qpc != NO_PIECE) history_update(w.history[qpc][m.to()], -bonus);
  }
}

int Search::quiescence(Position& pos, SearchWorker& w, SearchStack* ss, int alpha, int beta, int ply) {
  if (count_node(w)) return alpha;

  if (ply >= SearchWorker::kMaxPly - 1) return evaluate(pos);

  const bool in_check = pos.in_check();
  const bool draw = pos.is_draw();
  if (draw && !in_check) return VALUE_DRAW;
  int stand = in_check ? -VALUE_INFINITE : evaluate(pos);
  ss->static_eval = stand;
  if (!in_check) {
    if (stand >= beta) return stand;
    if (stand > alpha) alpha = stand;
  }

  MoveList legal;
  if (in_check) {
    generate_legal(pos, legal);
    if (legal.size == 0) return mated_in(ply);
    if (draw) return VALUE_DRAW;
  } else {
    MoveList all_legal;
    generate_legal(pos, all_legal);
    for (int i = 0; i < all_legal.size; ++i)
      if (all_legal.moves[i].is_capture() || all_legal.moves[i].is_ep() || all_legal.moves[i].is_promotion())
        legal.add(all_legal.moves[i]);
  }

  int scores[MAX_MOVES];
  score_moves(w, pos, legal, Move{}, Move{}, ply, scores);
  sort_moves(legal, scores);

  for (int i = 0; i < legal.size; ++i) {
    Move m = legal.moves[i];
    Piece victim = m.is_ep() ? make_piece(~pos.side_to_move(), PAWN) : pos.piece_on(m.to());
    int gain = (victim == NO_PIECE) ? 0 : piece_value(type_of(victim));
    Piece attacker = pos.piece_on(m.from());
    int attacker_value = attacker == NO_PIECE ? 0 : piece_value(type_of(attacker));
    // Skip clearly losing captures when not in check.
    if (!in_check && !m.is_promotion() && gain < attacker_value && static_exchange_eval(pos, m) < -80) continue;
    if (!in_check && !m.is_promotion() && stand + gain + 150 < alpha) continue;

    StateInfo st;
    pos.do_move(m, st);
    int score = -quiescence(pos, w, ss + 1, -beta, -alpha, ply + 1);
    pos.undo_move(m, st);
    if (time_up()) return alpha;
    if (score >= beta) return score;
    if (score > alpha) alpha = score;
  }
  return alpha;
}

int Search::search(Position& pos, SearchWorker& w, SearchStack* ss, int depth, int alpha, int beta, int ply,
                   bool cut_node) {
  if (count_node(w)) return alpha;

  const bool root_node = (ply == 0);
  const bool pv_node = (beta - alpha > 1);
  const bool in_check = pos.in_check();
  w.pv_len[ply] = 0;

  if (!root_node) {
    if (pos.is_draw()) {
      if (pos.halfmove_clock() >= 100 && in_check) {
        MoveList legal;
        generate_legal(pos, legal);
        if (legal.size == 0) return mated_in(ply);
      }
      return VALUE_DRAW;
    }
    alpha = std::max(alpha, mated_in(ply));
    beta = std::min(beta, mate_in(ply + 1));
    if (alpha >= beta) return alpha;
  }

  if (ply >= SearchWorker::kMaxPly - 1) return evaluate(pos);
  if (depth <= 0) return quiescence(pos, w, ss, alpha, beta, ply);

  if (in_check) depth = std::min(depth + 1, SearchWorker::kMaxPly - ply - 1);

  TTEntry tte;
  bool found = tt_.probe(pos.key(), tte);
  Move tt_move{};
  if (found) {
    tt_move = Move{tte.move};
    int tt_score = TranspositionTable::score_from_tt(tte.score, ply);
    if (!pv_node && tte.depth >= depth) {
      if (tte.bound == BOUND_EXACT) return tt_score;
      if (tte.bound == BOUND_LOWER && tt_score >= beta) return tt_score;
      if (tte.bound == BOUND_UPPER && tt_score <= alpha) return tt_score;
    }
  }

  int eval = in_check ? -VALUE_INFINITE : evaluate(pos);
  ss->static_eval = eval;

  bool improving = false;
  if (!in_check && ply >= 2) improving = eval > (ss - 2)->static_eval;

  if (!pv_node && !in_check && depth <= 3 && eval + RazorMargin * depth < alpha) {
    int ralpha = alpha - RazorMargin * depth;
    int score = quiescence(pos, w, ss, ralpha, ralpha + 1, ply);
    if (score <= ralpha) return score;
  }

  if (!pv_node && !in_check && depth <= 6 && eval - RFPMargin(depth) * (improving ? 1 : 2) / 2 >= beta &&
      eval < VALUE_MATE - 256)
    return eval;

  if (!root_node && !pv_node && !in_check && !ss->skip_null && depth >= 3 && eval >= beta &&
      non_pawn_material(pos, pos.side_to_move()) > 0) {
    int R = 3 + depth / 3 + std::min(3, (eval - beta) / 200);
    R = std::min(R, depth - 1);
    StateInfo st;
    pos.do_null_move(st);
    (ss + 1)->skip_null = true;
    int score = -search(pos, w, ss + 1, depth - R, -beta, -beta + 1, ply + 1, !cut_node);
    (ss + 1)->skip_null = false;
    pos.undo_null_move(st);
    if (time_up()) return alpha;
    if (score >= beta) {
      if (score >= VALUE_MATE - 256) score = beta;
      return score;
    }
  }

  MoveList list;
  generate_legal(pos, list);
  if (list.size == 0) {
    if (in_check) return mated_in(ply);
    return VALUE_DRAW;
  }

  Move prev = (ply > 0) ? (ss - 1)->current_move : Move{};
  Move counter = prev ? w.countermove[prev.from()][prev.to()] : Move{};

  int scores[MAX_MOVES];
  score_moves(w, pos, list, tt_move, counter, ply, scores);
  sort_moves(list, scores);

  int best_score = -VALUE_INFINITE;
  Move best_move{};
  Bound bound = BOUND_UPPER;
  Move quiets[64];
  int quiet_count = 0;
  int moves_searched = 0;

  for (int i = 0; i < list.size; ++i) {
    Move m = list.moves[i];
    const bool is_quiet = !m.is_capture() && !m.is_ep() && !m.is_promotion();

    if (!root_node && !in_check && is_quiet && depth <= 5 && !pv_node &&
        eval + FutilityMargin(depth) <= alpha && best_score > -VALUE_MATE + 256) {
      continue;
    }

    // Late move pruning (controller can raise threshold)
    int lmp_limit = 3 + depth * depth;
    if (SearchController::instance().is_enabled()) {
      int ps = SearchController::instance().prune_score(depth, moves_searched, eval, alpha);
      if (ps > 600) lmp_limit = std::max(2, lmp_limit - 1);
    }
    if (!root_node && !in_check && is_quiet && depth <= 4 && moves_searched >= lmp_limit &&
        best_score > -VALUE_MATE + 256) {
      continue;
    }

    ss->current_move = m;
    Piece moving = pos.piece_on(m.from());
    int pol = PolicyNet::instance().is_enabled() ? PolicyNet::instance().score_move(pos, m) : 0;
    Key key_before = pos.key();

    StateInfo st;
    pos.do_move(m, st);

    int new_depth = depth - 1;
    int score;

    if (depth >= 3 && moves_searched >= 1 + static_cast<int>(pv_node) && is_quiet && !in_check) {
      int R = 1 + (moves_searched > 6) + (depth > 6) + static_cast<int>(cut_node) - static_cast<int>(improving);
      if (moving != NO_PIECE) {
        int hist = w.history[moving][m.to()];
        if (hist > 400) --R;
        if (hist < -200) ++R;
      }
      if (SearchController::instance().is_enabled()) {
        R += SearchController::instance().reduction_delta(depth, moves_searched, eval, alpha, beta, is_quiet, pol);
      }
      R = std::clamp(R, 1, new_depth);
      score = -search(pos, w, ss + 1, new_depth - R, -alpha - 1, -alpha, ply + 1, true);
      if (score > alpha && R > 0)
        score = -search(pos, w, ss + 1, new_depth, -alpha - 1, -alpha, ply + 1, !cut_node);
      if (score > alpha && score < beta && pv_node)
        score = -search(pos, w, ss + 1, new_depth, -beta, -alpha, ply + 1, false);
      if (SearchController::instance().is_enabled())
        SearchController::instance().log_decision(key_before, depth, moves_searched, R, score, score >= beta);
    } else if (!pv_node || moves_searched > 0) {
      score = -search(pos, w, ss + 1, new_depth, -alpha - 1, -alpha, ply + 1, !cut_node);
      if (pv_node && score > alpha && score < beta)
        score = -search(pos, w, ss + 1, new_depth, -beta, -alpha, ply + 1, false);
    } else {
      score = -search(pos, w, ss + 1, new_depth, -beta, -alpha, ply + 1, false);
    }

    pos.undo_move(m, st);
    ++moves_searched;

    if (time_up()) return alpha;

    if (is_quiet && quiet_count < 64) quiets[quiet_count++] = m;

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
          bound = BOUND_LOWER;
          update_quiet_stats(w, pos, m, quiets, quiet_count, depth, ply, prev);
          break;
        }
      }
    }
  }

  if (bound != BOUND_LOWER && best_move && !best_move.is_capture() && !best_move.is_ep()) {
    Piece pc = pos.piece_on(best_move.from());
    if (pc != NO_PIECE) history_update(w.history[pc][best_move.to()], history_bonus(depth));
  }

  tt_.store(pos.key(), depth, best_score, bound, best_move, ply);
  return best_score;
}

int Search::search_root_parallel(int depth, int alpha, int beta) {
  if (count_node(main_worker_)) return alpha;

  MoveList moves;
  generate_legal(root_, moves);
  if (moves.size == 0) return root_.in_check() ? mated_in(0) : VALUE_DRAW;

  TTEntry tte;
  Move tt_move{};
  if (tt_.probe(root_.key(), tte)) tt_move = Move{tte.move};
  int move_scores[MAX_MOVES];
  score_moves(main_worker_, root_, moves, tt_move, Move{}, 0, move_scores);
  sort_moves(moves, move_scores);

  const int original_alpha = alpha;
  std::atomic<int> next_move{1};
  std::atomic<int> shared_alpha{alpha};
  std::atomic<bool> cutoff{false};
  std::mutex best_mutex;
  int best_score = -VALUE_INFINITE;
  Move best_move{};
  std::array<Move, SearchWorker::kMaxPly> best_pv{};
  int best_pv_len = 0;

  auto search_move = [&](int index, SearchWorker& worker, bool first) {
    Position pos = root_;
    SearchStack stack[SearchWorker::kMaxPly + 4]{};
    SearchStack* ss = stack + 2;
    Move move = moves.moves[index];
    ss->current_move = move;
    StateInfo state;
    pos.do_move(move, state);

    int local_alpha = shared_alpha.load(std::memory_order_relaxed);
    int score;
    if (first) {
      score = -search(pos, worker, ss + 1, depth - 1, -beta, -local_alpha, 1, false);
    } else {
      score = -search(pos, worker, ss + 1, depth - 1, -local_alpha - 1, -local_alpha, 1, true);
      if (score > local_alpha && score < beta && !time_up()) {
        local_alpha = std::max(local_alpha, shared_alpha.load(std::memory_order_relaxed));
        score = -search(pos, worker, ss + 1, depth - 1, -beta, -local_alpha, 1, false);
      }
    }
    pos.undo_move(move, state);

    if (time_up()) return;
    {
      std::lock_guard<std::mutex> lock(best_mutex);
      if (score > best_score) {
        best_score = score;
        best_move = move;
        best_pv[0] = move;
        best_pv_len = 1;
        for (int i = 0; i < worker.pv_len[1] && best_pv_len < SearchWorker::kMaxPly; ++i)
          best_pv[best_pv_len++] = worker.pv[1][i];
      }
    }

    int observed = shared_alpha.load(std::memory_order_relaxed);
    while (score > observed &&
           !shared_alpha.compare_exchange_weak(observed, score, std::memory_order_relaxed)) {
    }
    if (score >= beta) cutoff.store(true, std::memory_order_relaxed);
  };

  search_move(0, main_worker_, true);

  auto claim_moves = [&](SearchWorker& worker) {
    while (!cutoff.load(std::memory_order_relaxed) && !time_up()) {
      int index = next_move.fetch_add(1, std::memory_order_relaxed);
      if (index >= moves.size) break;
      search_move(index, worker, false);
    }
    flush_nodes(worker);
  };

  std::vector<std::thread> helpers;
  if (!cutoff.load(std::memory_order_relaxed) && !time_up()) {
    int helper_count = std::min(threads_ - 1, moves.size - 1);
    helpers.reserve(helper_count);
    for (int id = 1; id <= helper_count; ++id) {
      helpers.emplace_back([&]() {
        SearchWorker worker{};
        claim_moves(worker);
      });
    }
    claim_moves(main_worker_);
  }
  for (auto& helper : helpers) helper.join();

  if (!time_up() && best_move) {
    main_worker_.pv_len[0] = best_pv_len;
    for (int i = 0; i < best_pv_len; ++i) main_worker_.pv[0][i] = best_pv[i];
    Bound bound = best_score >= beta ? BOUND_LOWER : best_score > original_alpha ? BOUND_EXACT : BOUND_UPPER;
    tt_.store(root_.key(), depth, best_score, bound, best_move, 0);
  }
  return best_move ? best_score : alpha;
}

SearchInfo Search::go(const SearchLimits& limits) {
  prepare();
  return go_prepared(limits);
}

SearchInfo Search::go_prepared(const SearchLimits& limits) {
  nodes_.store(0, std::memory_order_relaxed);
  start_ = std::chrono::steady_clock::now();
  tt_.new_search();
  std::memset(main_worker_.killers, 0, sizeof(main_worker_.killers));
  main_worker_.nodes = 0;
  main_worker_.published_nodes = 0;
  for (auto& row : main_worker_.history)
    for (int& h : row) h /= 2;

  optimum_ms_ = 0;
  maximum_ms_ = 0;
  use_soft_time_ = false;
  nodes_limit_ = limits.nodes;
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

  int max_depth = limits.depth > 0 ? limits.depth : 64;
  SearchInfo info;
  Position pos = root_;
  Move best{};
  Move previous_iteration_best{};
  int stable_best_iterations = 0;
  int prev_score = 0;

  SearchStack stack[SearchWorker::kMaxPly + 4]{};

  for (int depth = 1; depth <= max_depth; ++depth) {
    int alpha = -VALUE_INFINITE;
    int beta = VALUE_INFINITE;
    int delta = 25;

    if (depth >= 5) {
      alpha = std::max(-VALUE_INFINITE, prev_score - delta);
      beta = std::min(VALUE_INFINITE, prev_score + delta);
    }

    int score = 0;
    while (true) {
      pos = root_;
      std::fill(std::begin(stack), std::end(stack), SearchStack{});
      score = threads_ > 1 ? search_root_parallel(depth, alpha, beta)
                           : search(pos, main_worker_, stack + 2, depth, alpha, beta, 0, false);
      flush_nodes(main_worker_);
      if (time_up() && depth > 1) break;

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

    if (time_up() && depth > 1) break;

    prev_score = score;
    if (main_worker_.pv_len[0] > 0) best = main_worker_.pv[0][0];
    if (!best) {
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

    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start_).count();
    uint64_t nodes = nodes_.load(std::memory_order_relaxed);
    uint64_t nps = ms > 0 ? nodes * 1000ULL / static_cast<uint64_t>(ms) : nodes;

    std::string pv_str;
    for (int i = 0; i < main_worker_.pv_len[0]; ++i) {
      if (i) pv_str += ' ';
      pv_str += move_to_uci(main_worker_.pv[0][i]);
    }
    if (pv_str.empty() && best) pv_str = move_to_uci(best);

    std::cout << "info depth " << depth << " score cp " << score << " nodes " << nodes << " nps " << nps
              << " time " << ms << " pv " << pv_str << std::endl;

    info.best_move = best;
    info.score = score;
    info.depth = depth;
    info.nodes = nodes;
    info.time_ms = static_cast<int>(ms);

    if (limits.nodes > 0 && static_cast<int64_t>(nodes) >= limits.nodes) break;
    if (maximum_ms_ > 0 && ms >= maximum_ms_) break;
    if (use_soft_time_ && optimum_ms_ > 0) {
      int soft_limit = optimum_ms_;
      if (stable_best_iterations >= 2)
        soft_limit = std::max(1, 4 * optimum_ms_ / 5);
      else if (stable_best_iterations == 0)
        soft_limit = std::min(maximum_ms_, 6 * optimum_ms_ / 5);
      if (ms >= soft_limit) break;
    }
    if (limits.depth > 0 && depth >= limits.depth) break;
  }

  stop_.store(true, std::memory_order_relaxed);
  flush_nodes(main_worker_);
  info.nodes = nodes_.load(std::memory_order_relaxed);
  info.time_ms = static_cast<int>(
      std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start_).count());

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
  stop_.store(false);
  auto info = go(limits);
  return info.nodes;
}

}  // namespace nsce
