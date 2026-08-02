#include "nsce/uci.hpp"

#include "nsce/bitboard.hpp"
#include "nsce/controller.hpp"
#include "nsce/movegen.hpp"
#include "nsce/nnue.hpp"
#include "nsce/perft.hpp"
#include "nsce/policy.hpp"
#include "nsce/zobrist.hpp"

#include <chrono>
#include <iostream>
#include <sstream>
#include <string>

namespace nsce {

Uci::Uci() {
  init_bitboards();
  Zobrist::init();
  Nnue::instance().load_default_from_hce();
  PolicyNet::instance().load_default();
  SearchController::instance().load_default();
  pos_.set_startpos();
  search_.set_hash_mb(16);
  search_.set_position(pos_);
}

void Uci::loop() {
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.empty()) continue;
    handle_command(line);
    if (line == "quit") break;
  }
}

void Uci::handle_command(const std::string& line) {
  std::istringstream is(line);
  std::string token;
  is >> token;

  if (token == "uci") {
    std::cout << "id name NSCE 0.8\n";
    std::cout << "id author Gonzalo\n";
    std::cout << "option name Hash type spin default 16 min 1 max 4096\n";
    std::cout << "option name Threads type spin default 1 min 1 max 64\n";
    std::cout << "option name UseNNUE type check default true\n";
    std::cout << "option name UsePolicy type check default true\n";
    std::cout << "option name UseSearchController type check default true\n";
    std::cout << "option name EvalFile type string default <internal>\n";
    std::cout << "option name PolicyFile type string default <internal>\n";
    std::cout << "option name ControllerFile type string default <internal>\n";
    std::cout << "option name TelemetryFile type string default <empty>\n";
    std::cout << "uciok" << std::endl;
  } else if (token == "isready") {
    std::cout << "readyok" << std::endl;
  } else if (token == "ucinewgame") {
    pos_.set_startpos();
    search_.set_position(pos_);
  } else if (token == "position") {
    handle_position(is);
  } else if (token == "go") {
    handle_go(is);
  } else if (token == "stop") {
    search_.stop();
  } else if (token == "setoption") {
    handle_setoption(is);
  } else if (token == "bench") {
    int depth = 5;
    is >> depth;
    bench(depth);
  } else if (token == "perft") {
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
  } else if (token == "quit") {
    search_.stop();
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
  }
  if (limits.depth == 0 && limits.movetime_ms == 0 && limits.wtime == 0 && limits.btime == 0 && limits.nodes == 0 &&
      !limits.infinite)
    limits.depth = 6;

  search_.set_position(pos_);
  SearchInfo info = search_.go(limits);
  std::cout << "bestmove " << (info.best_move ? move_to_uci(info.best_move) : "0000") << std::endl;
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
  if (name == "Hash") search_.set_hash_mb(static_cast<std::size_t>(std::stoul(value)));
  else if (name == "Threads") search_.set_threads(std::stoi(value));
  else if (name == "UseNNUE") {
    bool on = (value == "true" || value == "1");
    Nnue::instance().set_enabled(on);
    pos_.set_fen(pos_.fen());
    search_.set_position(pos_);
  } else if (name == "UsePolicy") {
    PolicyNet::instance().set_enabled(value == "true" || value == "1");
  } else if (name == "UseSearchController") {
    SearchController::instance().set_enabled(value == "true" || value == "1");
  } else if (name == "EvalFile") {
    if (value == "<internal>" || value == "internal")
      Nnue::instance().load_default_from_hce();
    else
      Nnue::instance().load(value);
    pos_.set_fen(pos_.fen());
    search_.set_position(pos_);
  } else if (name == "PolicyFile") {
    if (value == "<internal>" || value == "internal")
      PolicyNet::instance().load_default();
    else
      PolicyNet::instance().load(value);
  } else if (name == "ControllerFile") {
    if (value == "<internal>" || value == "internal")
      SearchController::instance().load_default();
    else
      SearchController::instance().load(value);
  } else if (name == "TelemetryFile") {
    SearchController::instance().set_telemetry(value);
  }
}

void Uci::bench(int depth) {
  uint64_t nodes = search_.bench(depth);
  std::cout << "Bench depth " << depth << ": " << nodes << " nodes" << std::endl;
}

}  // namespace nsce
