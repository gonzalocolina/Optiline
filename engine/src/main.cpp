#include "nsce/perft.hpp"
#include "nsce/uci.hpp"

#include <chrono>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
  using namespace nsce;
  Uci uci;

  if (argc > 1) {
    std::string cmd = argv[1];
    if (cmd == "bench") {
      int depth = argc > 2 ? std::atoi(argv[2]) : 5;
      uci.bench(depth);
      return 0;
    }
    if (cmd == "perft") {
      int depth = argc > 2 ? std::atoi(argv[2]) : 4;
      Position pos;
      pos.set_startpos();
      auto start = std::chrono::steady_clock::now();
      uint64_t nodes = perft(pos, depth);
      auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
          std::chrono::steady_clock::now() - start);
      std::cout << "perft(" << depth << ") = " << nodes << " time " << elapsed.count() << " ms\n";
      return 0;
    }
  }

  uci.loop();
  return 0;
}
