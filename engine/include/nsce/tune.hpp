#pragma once

#include <algorithm>
#include <iterator>
#include <string>
#include <string_view>
#include <vector>

namespace nsce {

// Search constants used at runtime. Defaults match the 2026-09-15 source.
// UCI `spin` options are advertised only when compiled with -DNSCE_TUNE
// (CMake -DNSCE_TUNE=ON) for weather-factory SPSA.
struct SearchTune {
  int razor_margin = 300;
  int razor_max_depth = 3;
  int rfp_per_depth = 100;
  int rfp_max_depth = 6;
  int futility_per_depth = 80;
  int futility_improving = 40;
  int futility_max_depth = 6;
  int futility_hist = 400;
  int nmp_base = 3;
  int nmp_depth_div = 3;
  int nmp_eval_div = 200;
  int nmp_eval_cap = 3;
  int nmp_min_depth = 3;
  int nmp_verify_depth = 10;
  int probcut_margin = 170;
  int probcut_improving = 50;
  int probcut_min_depth = 4;
  int probcut_depth_sub = 4;
  int lmp_improving = 5;
  int lmp_not_improving = 3;
  int lmp_hist_bonus = 2;
  int lmp_max_depth = 6;
  int lmp_hist = 200;
  int see_quiet_per_depth = 10;
  int see_noisy_per_depth = 100;
  int see_max_depth = 8;
  int iir_tt_depth = 4;
  int iir_cut_depth = 8;
  int se_min_depth = 7;
  int se_tt_depth_sub = 3;
  int se_margin_base = 50;
  int se_margin_pv = 15;
  int se_double_margin = 3;
  int lmr_min_depth = 3;
  int lmr_quiet_div_x100 = 215;
  int lmr_capture_div_x100 = 340;
  int lmr_hist_reduce = 400;
  int lmr_hist_increase = 200;
  int hist_bonus_a = 16;
  int hist_bonus_b = 8;
  int hist_bonus_cap = 1200;
  int tm_iter_div = 2;
  int asp_delta_base = 20;
  int asp_delta_vol = 80;
};

struct TuneSpec {
  const char* name;
  int SearchTune::* field;
  int min_v;
  int max_v;
  int step;
};

inline constexpr TuneSpec kTuneSpecs[] = {
    {"RazorMargin", &SearchTune::razor_margin, 50, 800, 25},
    {"RazorMaxDepth", &SearchTune::razor_max_depth, 1, 8, 1},
    {"RfpPerDepth", &SearchTune::rfp_per_depth, 20, 250, 10},
    {"RfpMaxDepth", &SearchTune::rfp_max_depth, 2, 12, 1},
    {"FutilityPerDepth", &SearchTune::futility_per_depth, 20, 200, 10},
    {"FutilityImproving", &SearchTune::futility_improving, 0, 120, 5},
    {"FutilityMaxDepth", &SearchTune::futility_max_depth, 2, 12, 1},
    {"FutilityHist", &SearchTune::futility_hist, 50, 2000, 50},
    {"NmpBase", &SearchTune::nmp_base, 1, 6, 1},
    {"NmpDepthDiv", &SearchTune::nmp_depth_div, 1, 8, 1},
    {"NmpEvalDiv", &SearchTune::nmp_eval_div, 50, 400, 25},
    {"NmpEvalCap", &SearchTune::nmp_eval_cap, 1, 8, 1},
    {"NmpMinDepth", &SearchTune::nmp_min_depth, 1, 8, 1},
    {"NmpVerifyDepth", &SearchTune::nmp_verify_depth, 6, 16, 1},
    {"ProbCutMargin", &SearchTune::probcut_margin, 50, 400, 20},
    {"ProbCutImproving", &SearchTune::probcut_improving, 0, 150, 10},
    {"ProbCutMinDepth", &SearchTune::probcut_min_depth, 2, 8, 1},
    {"ProbCutDepthSub", &SearchTune::probcut_depth_sub, 2, 8, 1},
    {"LmpImproving", &SearchTune::lmp_improving, 1, 12, 1},
    {"LmpNotImproving", &SearchTune::lmp_not_improving, 1, 10, 1},
    {"LmpHistBonus", &SearchTune::lmp_hist_bonus, 0, 8, 1},
    {"LmpMaxDepth", &SearchTune::lmp_max_depth, 2, 12, 1},
    {"LmpHist", &SearchTune::lmp_hist, 50, 800, 25},
    {"SeeQuietPerDepth", &SearchTune::see_quiet_per_depth, 1, 40, 2},
    {"SeeNoisyPerDepth", &SearchTune::see_noisy_per_depth, 20, 250, 10},
    {"SeeMaxDepth", &SearchTune::see_max_depth, 2, 16, 1},
    {"IirTtDepth", &SearchTune::iir_tt_depth, 2, 10, 1},
    {"IirCutDepth", &SearchTune::iir_cut_depth, 4, 16, 1},
    {"SeMinDepth", &SearchTune::se_min_depth, 4, 12, 1},
    {"SeTtDepthSub", &SearchTune::se_tt_depth_sub, 1, 6, 1},
    {"SeMarginBase", &SearchTune::se_margin_base, 10, 120, 5},
    {"SeMarginPv", &SearchTune::se_margin_pv, 0, 40, 2},
    {"SeDoubleMargin", &SearchTune::se_double_margin, 1, 8, 1},
    {"LmrMinDepth", &SearchTune::lmr_min_depth, 2, 8, 1},
    {"LmrQuietDivX100", &SearchTune::lmr_quiet_div_x100, 80, 400, 15},
    {"LmrCaptureDivX100", &SearchTune::lmr_capture_div_x100, 150, 600, 20},
    {"LmrHistReduce", &SearchTune::lmr_hist_reduce, 50, 1200, 50},
    {"LmrHistIncrease", &SearchTune::lmr_hist_increase, 50, 800, 25},
    {"HistBonusA", &SearchTune::hist_bonus_a, 4, 40, 2},
    {"HistBonusB", &SearchTune::hist_bonus_b, 0, 24, 2},
    {"HistBonusCap", &SearchTune::hist_bonus_cap, 200, 4000, 100},
    {"TmIterDiv", &SearchTune::tm_iter_div, 1, 4, 1},
    {"AspDeltaBase", &SearchTune::asp_delta_base, 5, 60, 5},
    {"AspDeltaVol", &SearchTune::asp_delta_vol, 20, 200, 10},
};

inline bool set_tune_field(SearchTune& tune, std::string_view name, int value) {
  for (const TuneSpec& spec : kTuneSpecs) {
    if (name == spec.name) {
      tune.*(spec.field) = std::clamp(value, spec.min_v, spec.max_v);
      return true;
    }
  }
  return false;
}

inline std::vector<std::string> tune_uci_lines(const SearchTune& tune) {
  std::vector<std::string> lines;
  lines.reserve(std::size(kTuneSpecs));
  for (const TuneSpec& spec : kTuneSpecs) {
    lines.push_back("option name " + std::string(spec.name) + " type spin default " +
                    std::to_string(tune.*(spec.field)) + " min " + std::to_string(spec.min_v) + " max " +
                    std::to_string(spec.max_v));
  }
  return lines;
}

}  // namespace nsce
