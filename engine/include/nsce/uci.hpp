#pragma once

#include "nsce/board.hpp"
#include "nsce/search.hpp"

#include <sstream>
#include <string>

namespace nsce {

class Uci {
 public:
  Uci();
  void loop();
  void bench(int depth = 6);

 private:
  void handle_command(const std::string& line);
  void handle_position(std::istringstream& is);
  void handle_go(std::istringstream& is);
  void handle_setoption(std::istringstream& is);

  Position pos_;
  Search search_;
};

}  // namespace nsce
