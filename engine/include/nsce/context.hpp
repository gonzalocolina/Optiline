#pragma once

#include "nsce/controller.hpp"
#include "nsce/nnue.hpp"
#include "nsce/policy.hpp"

namespace nsce {

// Runtime-owned engine state. Keeping model/configuration instances together
// lets multiple UCI engines coexist without sharing mutable search state.
struct EngineContext {
  Nnue nnue;
  PolicyNet policy;
  SearchController controller;
  bool use_extras = true;
  bool nnue_wanted = true;
};

}  // namespace nsce
