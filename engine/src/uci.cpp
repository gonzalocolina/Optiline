#include "nsce/uci.hpp"

#include "nsce/bitboard.hpp"
#include "nsce/controller.hpp"
#include "nsce/eval.hpp"
#include "nsce/movegen.hpp"
#include "nsce/nnue.hpp"
#include "nsce/perft.hpp"
#include "nsce/policy.hpp"
#include "nsce/tune.hpp"
#include "nsce/zobrist.hpp"

#include <algorithm>
#include <chrono>
#include <exception>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>

namespace nsce {

Uci::Uci() {
  init_bitboards();
  Zobrist::init();
  if (!context_.nnue.load("nets/nnue_trained.bin")) context_.nnue.load_default_from_hce();
  context_.nnue.set_enabled(context_.nnue_wanted);
  context_.policy.load_default();
  context_.policy.set_enabled(false);
  context_.controller.load_default();
  context_.controller.set_enabled(false);
  pos_.set_startpos();
  pos_.set_nnue(&context_.nnue);
  pos_.set_use_extras(context_.use_extras);
  search_.set_policy(&context_.policy);
  search_.set_controller(&context_.controller);
  search_.set_hash_mb(16);
  search_.set_position(pos_);
}

Uci::~Uci() { stop_search(); }

void Uci::stop_search() {
  search_.stop();
  if (search_thread_.joinable()) search_thread_.join();
}

void Uci::loop() {
  std::string line;
  while (std::getline(std::cin, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty()) continue;
    handle_command(line);
    if (line == "quit") break;
  }
  stop_search();
}

void Uci::handle_command(const std::string& line) {
  std::istringstream is(line);
  std::string token;
  is >> token;

  if (token == "uci") {
    std::cout << "id name NSCE 0.10\n";
    std::cout << "id author Gonzalo\n";
    std::cout << "option name Hash type spin default 16 min 1 max 4096\n";
    std::cout << "option name Clear Hash type button\n";
    std::cout << "option name Threads type spin default 1 min 1 max 64\n";
    std::cout << "option name UseNNUE type check default true\n";
    std::cout << "option name UsePolicy type check default false\n";
    std::cout << "option name UseSearchController type check default false\n";
    std::cout << "option name UseTT type check default true\n";
    std::cout << "option name UseSEE type check default true\n";
    std::cout << "option name UseLMR type check default true\n";
    std::cout << "option name UseNullMove type check default true\n";
    std::cout << "option name UseFutility type check default true\n";
    std::cout << "option name UseLMP type check default true\n";
    std::cout << "option name UseRazoring type check default true\n";
    std::cout << "option name UseRFP type check default true\n";
    std::cout << "option name UseProbCut type check default true\n";
    std::cout << "option name UseExtras type check default true\n";
    std::cout << "option name EvalScale type spin default 1000 min 250 max 4000\n";
#if defined(NSCE_TUNE)
    for (const std::string& line : tune_uci_lines(search_.tune())) std::cout << line << '\n';
#endif
    std::cout << "option name EvalFile type string default nets/nnue_trained.bin\n";
    std::cout << "option name PolicyFile type string default <internal>\n";
    std::cout << "option name ControllerFile type string default <internal>\n";
    std::cout << "option name TelemetryFile type string default <empty>\n";
    std::cout << "option name LeafTelemetryFile type string default <empty>\n";
    std::cout << "uciok" << std::endl;
  } else if (token == "isready") {
    std::cout << "readyok" << std::endl;
  } else if (token == "ucinewgame") {
    stop_search();
    pos_.set_startpos();
    search_.clear_search_state();
    search_.set_position(pos_);
  } else if (token == "position") {
    stop_search();
    const std::string previous_fen = pos_.fen();
    try {
      handle_position(is);
    } catch (const std::exception& error) {
      pos_.set_fen(previous_fen);
      search_.set_position(pos_);
      std::cout << "info string invalid position: " << error.what() << std::endl;
    }
  } else if (token == "go") {
    handle_go(is);
  } else if (token == "stop") {
    stop_search();
  } else if (token == "ponderhit") {
    search_.ponder_hit();
  } else if (token == "setoption") {
    stop_search();
    handle_setoption(is);
  } else if (token == "bench") {
    stop_search();
    int depth = 5;
    is >> depth;
    bench(depth);
  } else if (token == "perft") {
    stop_search();
    int depth = 4;
    is >> depth;
    auto t0 = std::chrono::steady_clock::now();
    uint64_t nodes = perft(pos_, depth);
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
    std::cout << "perft(" << depth << ") = " << nodes << " time " << ms << " ms" << std::endl;
  } else if (token == "d") {
    std::cout << pos_.fen() << std::endl;
  } else if (token == "status") {
    MoveList list;
    generate_legal(pos_, list);
    if (list.size == 0) {
      std::cout << (pos_.in_check() ? "checkmate" : "stalemate") << std::endl;
    } else if (pos_.is_draw()) {
      std::cout << "draw" << std::endl;
    } else {
      std::cout << "ongoing" << std::endl;
    }
  } else if (token == "legalmoves") {
    MoveList list;
    generate_legal(pos_, list);
    std::cout << "legalmoves";
    for (Move move : list) std::cout << ' ' << move_to_uci(move);
    std::cout << std::endl;
  } else if (token == "eval") {
    std::string mode;
    is >> mode;
    if (mode == "details") {
      std::cout << "eval " << evaluate(pos_) << " nnue " << evaluate_nnue(pos_) << " extras "
                << applied_extras(pos_) << " simple " << simple_eval(pos_) << " use_extras "
                << (pos_.use_extras() ? 1 : 0) << std::endl;
    } else {
      std::cout << "eval " << evaluate(pos_) << std::endl;
    }
  } else if (token == "hashfull") {
    std::cout << "hashfull " << search_.hashfull() << std::endl;
  } else if (token == "quit") {
    stop_search();
  }
}

void Uci::handle_position(std::istringstream& is) {
  std::string token;
  is >> token;
  if (token == "startpos") {
    pos_.set_startpos();
    is >> token;  // optional "moves"
  } else if (token == "fen") {
    std::string fen, part;
    // fen has 6 fields
    for (int i = 0; i < 6 && is >> part; ++i) {
      if (i) fen += ' ';
      fen += part;
    }
    pos_.set_fen(fen);
    is >> token;  // optional "moves"
  }

  if (token == "moves") {
    while (is >> token) {
      Move m = parse_uci_move(pos_, token);
      if (!m) break;
      StateInfo st;
      pos_.do_move(m, st);
    }
  }
  search_.set_position(pos_);
}

void Uci::handle_go(std::istringstream& is) {
  stop_search();
  SearchLimits limits;
  std::string token;
  while (is >> token) {
    if (token == "depth")
      is >> limits.depth;
    else if (token == "nodes")
      is >> limits.nodes;
    else if (token == "movetime")
      is >> limits.movetime_ms;
    else if (token == "wtime")
      is >> limits.wtime;
    else if (token == "btime")
      is >> limits.btime;
    else if (token == "winc")
      is >> limits.winc;
    else if (token == "binc")
      is >> limits.binc;
    else if (token == "movestogo")
      is >> limits.movestogo;
    else if (token == "infinite")
      limits.infinite = true;
    else if (token == "ponder")
      limits.ponder = true;
    else if (token == "searchmoves") {
      while (is >> token) {
        Move move = parse_uci_move(pos_, token);
        if (move) limits.searchmoves.push_back(move);
      }
      break;
    }
  }
  if (limits.depth == 0 && limits.movetime_ms == 0 && limits.wtime == 0 && limits.btime == 0 && limits.nodes == 0 &&
      !limits.infinite && !limits.ponder)
    limits.depth = 6;

  search_.set_position(pos_);
  search_.prepare();
  search_thread_ = std::thread([this, limits]() {
    SearchInfo info = search_.go_prepared(limits);
    static std::mutex io_mu;
    std::lock_guard<std::mutex> lock(io_mu);
    std::cout << "bestmove " << (info.best_move ? move_to_uci(info.best_move) : "0000") << std::endl;
  });
}

void Uci::handle_setoption(std::istringstream& is) {
  std::string token, name, value;
  is >> token;  // name
  is >> name;
  while (is >> token && token != "value") {
    name += ' ';
    name += token;
  }
  is >> value;
  try {
    if (name == "Hash") {
      const auto hash = std::clamp<std::size_t>(std::stoul(value), 1, 4096);
      search_.set_hash_mb(hash);
    } else if (name == "Threads") {
      search_.set_threads(std::clamp(std::stoi(value), 1, 64));
    }
  else if (name == "UseNNUE") {
    context_.nnue_wanted = (value == "true" || value == "1");
    context_.nnue.set_enabled(context_.nnue_wanted);
    pos_.set_nnue(&context_.nnue);
    pos_.set_fen(pos_.fen());
    search_.clear_search_state();
    search_.set_position(pos_);
  } else if (name == "UsePolicy") {
    context_.policy.set_enabled(value == "true" || value == "1");
  } else if (name == "UseSearchController") {
    context_.controller.set_enabled(value == "true" || value == "1");
  } else if (name == "UseTT") {
    search_.set_use_tt(value == "true" || value == "1");
  } else if (name == "UseSEE") {
    search_.set_use_see(value == "true" || value == "1");
  } else if (name == "UseLMR") {
    search_.set_use_lmr(value == "true" || value == "1");
  } else if (name == "UseNullMove") {
    search_.set_use_null_move(value == "true" || value == "1");
  } else if (name == "UseFutility") {
    search_.set_use_futility(value == "true" || value == "1");
  } else if (name == "UseLMP") {
    search_.set_use_lmp(value == "true" || value == "1");
  } else if (name == "UseRazoring") {
    search_.set_use_razoring(value == "true" || value == "1");
  } else if (name == "UseRFP") {
    search_.set_use_rfp(value == "true" || value == "1");
  } else if (name == "UseProbCut") {
    search_.set_use_probcut(value == "true" || value == "1");
  } else if (name == "UseExtras") {
    context_.use_extras = value == "true" || value == "1";
    pos_.set_use_extras(context_.use_extras);
    search_.clear_search_state();
    search_.set_position(pos_);
  } else if (name == "EvalScale") {
    search_.set_eval_scale(std::stoi(value));
    search_.clear_search_state();
  } else if (name == "EvalFile") {
    if (value == "<internal>" || value == "internal" || value == "hce") {
      context_.nnue.load_default_from_hce();
    } else {
      if (!context_.nnue.load(value)) {
        std::cout << "info string error loading EvalFile " << value << std::endl;
        return;
      }
    }
    context_.nnue.set_enabled(context_.nnue_wanted);
    pos_.set_nnue(&context_.nnue);
    pos_.set_fen(pos_.fen());
    search_.clear_search_state();
    search_.set_position(pos_);
  } else if (name == "PolicyFile") {
    if (value == "<internal>" || value == "internal")
      context_.policy.load_default();
    else if (!context_.policy.load(value))
      std::cout << "info string error loading PolicyFile " << value << std::endl;
  } else if (name == "ControllerFile") {
    if (value == "<internal>" || value == "internal")
      context_.controller.load_default();
    else if (!context_.controller.load(value))
      std::cout << "info string error loading ControllerFile " << value << std::endl;
  } else if (name == "TelemetryFile") {
    context_.controller.set_telemetry(value);
  } else if (name == "LeafTelemetryFile") {
    search_.set_leaf_telemetry(value == "<empty>" ? "" : value);
  } else if (name == "Clear Hash") {
    search_.clear_hash();
#if defined(NSCE_TUNE)
  } else if (search_.set_tune_param(name, std::stoi(value))) {
    search_.clear_search_state();
#endif
  } else {
    std::cout << "info string unknown option " << name << std::endl;
  }
  } catch (const std::exception& error) {
    std::cout << "info string invalid option " << name << ": " << error.what() << std::endl;
  }
}

void Uci::bench(int depth) {
  uint64_t nodes = search_.bench(depth);
  std::cout << "Bench depth " << depth << ": " << nodes << " nodes" << std::endl;
}

}  // namespace nsce
