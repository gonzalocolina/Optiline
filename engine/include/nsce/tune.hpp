#pragma once

#include <algorithm>
#include <iterator>
#include <string>
#include <string_view>
#include <vector>

namespace nsce {

// Search constants used at runtime. UCI `spin` options are advertised only
// when compiled with -DNSCE_TUNE (CMake -DNSCE_TUNE=ON) for weather-factory SPSA.
struct SearchTune {
  int razor_margin = 450;
  int razor_per_depth_sq = 260;
  int rfp_per_depth = 79;
  int rfp_max_depth = 8;
  int futility_base = 58;
  int futility_per_depth = 111;
  int futility_max_depth = 10;
  int cap_futility_base = 246;
  int cap_futility_per_depth = 249;
  int nmp_base = 4;
  int nmp_depth_div = 3;
  int nmp_eval_div = 201;
  int nmp_eval_cap = 4;
  int nmp_min_depth = 3;
  int nmp_verify_depth = 14;
  int probcut_margin = 196;
  int probcut_improving = 61;
  int probcut_min_depth = 5;
  int probcut_depth_sub = 4;
  int lmp_base = 3;
  int see_quiet_per_depth = 7;
  int see_noisy_per_depth = 66;
  int hist_prune = 3980;
  int iir_depth = 4;
  int se_min_depth = 10;
  int se_tt_depth_sub = 3;
  int se_margin = 67;
  int se_double_margin = 10;
  int lmr_quiet_base_x100 = 109;
  int lmr_quiet_div_x100 = 165;
  int lmr_capture_div_x100 = 306;
  int lmr_hist_div = 14951;
  int hist_bonus_mul = 179;
  int hist_bonus_sub = 129;
  int hist_bonus_cap = 1586;
  int hist_malus_mul = 343;
  int hist_malus_cap = 1386;
  int qs_futility = 298;
  int asp_delta_base = 21;
  int tm_moves_to_go = 20;
  int check_ext = 1;
  int lmr_not_improving = 1013;
  int lmr_tt_pv = 1017;
  int lmr_cut_node = 1981;
  int lmr_tt_capture = 887;
  int lmr_cutoff_count = 831;
  int lmr_check = 1069;
  int lmr_killer = 1035;
  int lmr_hist_offset = 4074;
  int lmr_deeper_base = 59;
  int lmr_shallower = 1;
  int nmp_eval_depth_mul = 0;
  int nmp_eval_base = 314;
  int futility_no_best = 33;
  int futility_hist_div = 3587;
  int se_tt_pv_margin = 62;
  int qs_see_margin = 79;
  int see_order_div = 60;
  int threat_order_scale = 104;
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
    {"RazorPerDepthSq", &SearchTune::razor_per_depth_sq, 50, 600, 20},
    {"RfpPerDepth", &SearchTune::rfp_per_depth, 20, 250, 8},
    {"RfpMaxDepth", &SearchTune::rfp_max_depth, 2, 14, 1},
    {"FutilityBase", &SearchTune::futility_base, 0, 400, 15},
    {"FutilityPerDepth", &SearchTune::futility_per_depth, 20, 300, 10},
    {"FutilityMaxDepth", &SearchTune::futility_max_depth, 2, 16, 1},
    {"CapFutilityBase", &SearchTune::cap_futility_base, 0, 600, 20},
    {"CapFutilityPerDepth", &SearchTune::cap_futility_per_depth, 50, 400, 15},
    {"NmpBase", &SearchTune::nmp_base, 1, 7, 1},
    {"NmpDepthDiv", &SearchTune::nmp_depth_div, 1, 8, 1},
    {"NmpEvalDiv", &SearchTune::nmp_eval_div, 50, 400, 20},
    {"NmpEvalCap", &SearchTune::nmp_eval_cap, 1, 8, 1},
    {"NmpMinDepth", &SearchTune::nmp_min_depth, 1, 8, 1},
    {"NmpVerifyDepth", &SearchTune::nmp_verify_depth, 6, 24, 1},
    {"ProbCutMargin", &SearchTune::probcut_margin, 50, 400, 15},
    {"ProbCutImproving", &SearchTune::probcut_improving, 0, 150, 10},
    {"ProbCutMinDepth", &SearchTune::probcut_min_depth, 2, 10, 1},
    {"ProbCutDepthSub", &SearchTune::probcut_depth_sub, 2, 8, 1},
    {"LmpBase", &SearchTune::lmp_base, 1, 10, 1},
    {"SeeQuietPerDepth", &SearchTune::see_quiet_per_depth, 5, 80, 4},
    {"SeeNoisyPerDepth", &SearchTune::see_noisy_per_depth, 20, 250, 10},
    {"HistPrune", &SearchTune::hist_prune, 500, 10000, 250},
    {"IirDepth", &SearchTune::iir_depth, 2, 10, 1},
    {"SeMinDepth", &SearchTune::se_min_depth, 4, 12, 1},
    {"SeTtDepthSub", &SearchTune::se_tt_depth_sub, 1, 6, 1},
    {"SeMargin", &SearchTune::se_margin, 16, 160, 6},
    {"SeDoubleMargin", &SearchTune::se_double_margin, 0, 80, 4},
    {"LmrQuietBaseX100", &SearchTune::lmr_quiet_base_x100, 0, 200, 8},
    {"LmrQuietDivX100", &SearchTune::lmr_quiet_div_x100, 80, 400, 15},
    {"LmrCaptureDivX100", &SearchTune::lmr_capture_div_x100, 150, 600, 20},
    {"LmrHistDiv", &SearchTune::lmr_hist_div, 2000, 20000, 500},
    {"HistBonusMul", &SearchTune::hist_bonus_mul, 50, 400, 15},
    {"HistBonusSub", &SearchTune::hist_bonus_sub, 0, 300, 15},
    {"HistBonusCap", &SearchTune::hist_bonus_cap, 400, 4000, 100},
    {"HistMalusMul", &SearchTune::hist_malus_mul, 50, 500, 15},
    {"HistMalusCap", &SearchTune::hist_malus_cap, 400, 4000, 100},
    {"QsFutility", &SearchTune::qs_futility, 50, 400, 15},
    {"AspDeltaBase", &SearchTune::asp_delta_base, 5, 60, 3},
    {"TmMovesToGo", &SearchTune::tm_moves_to_go, 10, 50, 2},
    {"CheckExt", &SearchTune::check_ext, 0, 1, 1},
    {"LmrNotImproving", &SearchTune::lmr_not_improving, 0, 2048, 128},
    {"LmrTtPv", &SearchTune::lmr_tt_pv, 0, 3072, 160},
    {"LmrCutNode", &SearchTune::lmr_cut_node, 0, 4096, 200},
    {"LmrTtCapture", &SearchTune::lmr_tt_capture, 0, 3072, 160},
    {"LmrCutoffCount", &SearchTune::lmr_cutoff_count, 0, 3072, 160},
    {"LmrCheck", &SearchTune::lmr_check, 0, 3072, 160},
    {"LmrKiller", &SearchTune::lmr_killer, 0, 2048, 128},
    {"LmrHistOffset", &SearchTune::lmr_hist_offset, 0, 12000, 500},
    {"LmrDeeperBase", &SearchTune::lmr_deeper_base, 0, 150, 8},
    {"LmrShallower", &SearchTune::lmr_shallower, 0, 60, 4},
    {"NmpEvalDepthMul", &SearchTune::nmp_eval_depth_mul, 0, 60, 4},
    {"NmpEvalBase", &SearchTune::nmp_eval_base, 0, 400, 20},
    {"FutilityNoBest", &SearchTune::futility_no_best, 0, 200, 12},
    {"FutilityHistDiv", &SearchTune::futility_hist_div, 1000, 12000, 300},
    {"SeTtPvMargin", &SearchTune::se_tt_pv_margin, 0, 160, 8},
    {"QsSeeMargin", &SearchTune::qs_see_margin, 0, 300, 12},
    {"SeeOrderDiv", &SearchTune::see_order_div, 8, 128, 4},
    {"ThreatOrderScale", &SearchTune::threat_order_scale, 0, 300, 12},
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
