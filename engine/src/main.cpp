#include "nsce/uci.hpp"

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
      // Handled via UCI stdin normally; allow: nsce perft N
      int depth = argc > 2 ? std::atoi(argv[2]) : 4;
      std::cout << "perft " << depth << std::endl;
    }
  }

  uci.loop();
  return 0;
}
