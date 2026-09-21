#include "nsce/board.hpp"
#include "nsce/context.hpp"
#include "nsce/nnue.hpp"
#include "nsce/movegen.hpp"
#include "nsce/zobrist.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/eval.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <vector>

using namespace nsce;

static void write_per1_net(const std::filesystem::path& path, const std::vector<int16_t>& w0,
                           const std::array<int16_t, NnueNet::kPer1Hidden>& b0,
                           const std::array<int32_t, NnueNet::kPer1Buckets>& l3b = {},
                           bool pattern_mlp = false) {
  std::ofstream out(path, std::ios::binary);
  out.write("NSCEPER1", 8);
  int32_t hdr[] = {NnueNet::kPer1Hidden, NnueNet::kFeatures, NnueNet::kPer1Buckets,
                   NnueNet::kPer1L2,     NnueNet::kPer1L3,   NnueNet::kPer1QA,
                   NnueNet::kPer1QB,     NnueNet::kPer1Scale};
  out.write(reinterpret_cast<const char*>(hdr), sizeof(hdr));
  out.write(reinterpret_cast<const char*>(w0.data()), static_cast<std::streamsize>(w0.size() * 2));
  out.write(reinterpret_cast<const char*>(b0.data()), sizeof(b0));
  auto fill16 = [&](std::size_t n) {
    std::vector<int16_t> v(n, 0);
    if (pattern_mlp)
      for (std::size_t i = 0; i < n; ++i)
        v[i] = static_cast<int16_t>(((static_cast<int>(i) % 41) * 400) - 8000);
    out.write(reinterpret_cast<const char*>(v.data()), static_cast<std::streamsize>(n * 2));
  };
  auto fill32 = [&](std::size_t n) {
    std::vector<int32_t> v(n, 0);
    if (pattern_mlp)
      for (std::size_t i = 0; i < n; ++i) v[i] = static_cast<int32_t>(i % 7) - 3;
    out.write(reinterpret_cast<const char*>(v.data()), static_cast<std::streamsize>(n * 4));
  };
  fill16(static_cast<std::size_t>(NnueNet::kPer1Buckets) * NnueNet::kPer1L2 * NnueNet::kPer1Hidden);
  fill32(static_cast<std::size_t>(NnueNet::kPer1Buckets) * NnueNet::kPer1L2);
  fill16(static_cast<std::size_t>(NnueNet::kPer1Buckets) * NnueNet::kPer1L3 * NnueNet::kPer1L2);
  fill32(static_cast<std::size_t>(NnueNet::kPer1Buckets) * NnueNet::kPer1L3);
  fill16(static_cast<std::size_t>(NnueNet::kPer1Buckets) * NnueNet::kPer1L3);
  out.write(reinterpret_cast<const char*>(l3b.data()), sizeof(l3b));
}

TEST(NnueTest, IncrementalMatchesRefresh) {
  init_bitboards();
  Zobrist::init();
  ASSERT_TRUE(Nnue::instance().load_default_from_hce());

  Position pos;
  pos.set_startpos();
  NnueAccumulator refreshed;
  Nnue::instance().refresh(pos, refreshed);
  for (int h = 0; h < NnueNet::kHidden; ++h) {
    EXPECT_EQ(pos.nnue_acc().v[h], refreshed.v[h]) << "h=" << h;
  }

  MoveList list;
  generate_legal(pos, list);
  ASSERT_GT(list.size, 0);
  StateInfo st;
  pos.do_move(list.moves[0], st);
  Nnue::instance().refresh(pos, refreshed);
  for (int h = 0; h < NnueNet::kHidden; ++h) {
    EXPECT_EQ(pos.nnue_acc().v[h], refreshed.v[h]) << "after move h=" << h;
  }
  pos.undo_move(list.moves[0], st);
  Nnue::instance().refresh(pos, refreshed);
  for (int h = 0; h < NnueNet::kHidden; ++h) {
    EXPECT_EQ(pos.nnue_acc().v[h], refreshed.v[h]) << "after undo h=" << h;
  }
}

TEST(NnueTest, IncrementalAccumulatorSurvivesAQuietAndTacticalSequence) {
  init_bitboards();
  Zobrist::init();
  ASSERT_TRUE(Nnue::instance().load_default_from_hce());
  Position pos;
  pos.set_startpos();
  std::vector<Move> moves;
  std::vector<StateInfo> states;
  for (int ply = 0; ply < 32; ++ply) {
    MoveList legal;
    generate_legal(pos, legal);
    ASSERT_GT(legal.size, 0);
    Move move = legal.moves[(ply * 11 + 3) % legal.size];
    moves.push_back(move);
    states.emplace_back();
    pos.do_move(move, states.back());
    NnueAccumulator refreshed;
    Nnue::instance().refresh(pos, refreshed);
    EXPECT_EQ(pos.nnue_acc().v, refreshed.v) << "after ply " << ply;
  }
  for (int ply = static_cast<int>(moves.size()) - 1; ply >= 0; --ply) {
    pos.undo_move(moves[ply], states[ply]);
    NnueAccumulator refreshed;
    Nnue::instance().refresh(pos, refreshed);
    EXPECT_EQ(pos.nnue_acc().v, refreshed.v) << "after undo ply " << ply;
  }
}

TEST(NnueTest, EvalFinite) {
  init_bitboards();
  Zobrist::init();
  Nnue::instance().load_default_from_hce();
  Position pos;
  pos.set_startpos();
  int e = evaluate(pos);
  EXPECT_GT(e, -5000);
  EXPECT_LT(e, 5000);
  pos.set_use_extras(false);
  EXPECT_EQ(evaluate(pos), Nnue::instance().evaluate(pos));
  pos.set_use_extras(true);
  EXPECT_NE(evaluate(pos), Nnue::instance().evaluate(pos));
}

TEST(NnueTest, InternalNetworkSerializationReconstructsExactly) {
  init_bitboards();
  Zobrist::init();
  ASSERT_TRUE(Nnue::instance().load_default_from_hce());
  Position pos;
  pos.set_startpos();
  const std::string fen = pos.fen();
  const int expected = Nnue::instance().evaluate(pos);
  auto path = std::filesystem::temp_directory_path() / "nsce_internal_roundtrip.bin";
  {
    const NnueNet& net = Nnue::instance().net();
    std::ofstream out(path, std::ios::binary);
    out.write("NSCENNUE", 8);
    int32_t features = NnueNet::kFeatures;
    int32_t hidden = NnueNet::kHidden;
    out.write(reinterpret_cast<const char*>(&features), sizeof(features));
    out.write(reinterpret_cast<const char*>(&hidden), sizeof(hidden));
    out.write(reinterpret_cast<const char*>(net.w0.data()), sizeof(net.w0));
    out.write(reinterpret_cast<const char*>(net.b0.data()), sizeof(net.b0));
    out.write(reinterpret_cast<const char*>(net.w1.data()), sizeof(net.w1));
    out.write(reinterpret_cast<const char*>(&net.b1), sizeof(net.b1));
  }
  ASSERT_TRUE(Nnue::instance().load(path.string()));
  pos.set_fen(fen);
  EXPECT_EQ(Nnue::instance().evaluate(pos), expected);
  std::filesystem::remove(path);
}

TEST(NnueTest, PositionCanUseIndependentEngineContext) {
  init_bitboards();
  Zobrist::init();
  EngineContext first;
  EngineContext second;
  ASSERT_TRUE(first.nnue.load_default_from_hce());
  ASSERT_TRUE(second.nnue.load_default_from_hce());

  Position a;
  Position b;
  a.set_nnue(&first.nnue);
  b.set_nnue(&second.nnue);
  a.set_startpos();
  b.set_startpos();
  EXPECT_EQ(a.nnue().net().loaded, b.nnue().net().loaded);
  EXPECT_EQ(evaluate(a), evaluate(b));
}

TEST(NnueTest, LoadsHalfKpAndKeepsKingMoveAccumulatorIncremental) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_halfkp_test.bin";
  {
    std::ofstream out(path, std::ios::binary);
    out.write("NSCEHFKP", 8);
    int32_t features = NnueNet::kHalfKpFeatures;
    int32_t hidden = NnueNet::kHidden;
    out.write(reinterpret_cast<const char*>(&features), sizeof(features));
    out.write(reinterpret_cast<const char*>(&hidden), sizeof(hidden));
    std::vector<int16_t> zeros(static_cast<std::size_t>(NnueNet::kHalfKpFeatures) * NnueNet::kHidden);
    out.write(reinterpret_cast<const char*>(zeros.data()), static_cast<std::streamsize>(zeros.size() * 2));
    std::array<int16_t, NnueNet::kHidden> bias{};
    bias.fill(64);
    out.write(reinterpret_cast<const char*>(bias.data()), static_cast<std::streamsize>(bias.size() * 2));
    std::array<int16_t, 2 * NnueNet::kHidden> output{};
    out.write(reinterpret_cast<const char*>(output.data()), static_cast<std::streamsize>(output.size() * 2));
    int32_t output_bias = 0;
    out.write(reinterpret_cast<const char*>(&output_bias), sizeof(output_bias));
  }

  ASSERT_TRUE(Nnue::instance().load(path.string()));
  ASSERT_TRUE(Nnue::instance().uses_king_buckets());
  Position pos;
  pos.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1");
  Move king_move = Move::make(SQ_E1, SQ_D1);
  StateInfo state;
  pos.do_move(king_move, state);
  NnueAccumulator refreshed;
  Nnue::instance().refresh(pos, refreshed);
  EXPECT_EQ(pos.nnue_acc().half, refreshed.half);
  EXPECT_EQ(pos.nnue_acc().king_bucket, refreshed.king_bucket);
  pos.undo_move(king_move, state);
  Nnue::instance().refresh(pos, refreshed);
  EXPECT_EQ(pos.nnue_acc().half, refreshed.half);
  EXPECT_EQ(pos.nnue_acc().king_bucket, refreshed.king_bucket);
  std::filesystem::remove(path);
}

TEST(NnueTest, KatKingBucketsMirrorAFileOntoHFile) {
  int mirror = 0;
  EXPECT_EQ(kat_king_bucket(WHITE, SQ_E1, mirror), 0);
  EXPECT_EQ(mirror, 0);
  EXPECT_EQ(kat_king_bucket(WHITE, SQ_D1, mirror), 0);
  EXPECT_EQ(mirror, 7);
  EXPECT_EQ(kat_king_bucket(WHITE, SQ_H1, mirror), 3);
  EXPECT_EQ(mirror, 0);
  EXPECT_EQ(kat_king_bucket(WHITE, SQ_A1, mirror), 3);
  EXPECT_EQ(mirror, 7);
  EXPECT_EQ(kat_king_bucket(BLACK, SQ_E8, mirror), 0);
  EXPECT_EQ(mirror, 0);
}

TEST(NnueTest, KatThreatsCountAttackedPawnsAndKings) {
  init_bitboards();
  Zobrist::init();
  Position pos;
  pos.set_fen("4k3/8/8/8/8/8/4p3/3K4 w - - 0 1");
  int threats[NnueNet::kThreatDim]{};
  kat_threats(pos, WHITE, threats);
  EXPECT_EQ(threats[KING], 1);
  EXPECT_EQ(threats[6 + PAWN], 1);
  EXPECT_EQ(threats[PAWN], 0);
}

TEST(NnueTest, LoadsKatAndKeepsMirroredKingMoveIncremental) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_kat_test.bin";
  {
    std::ofstream out(path, std::ios::binary);
    out.write("NSCEKAT1", 8);
    int32_t features = NnueNet::kKatFeatures;
    int32_t hidden = NnueNet::kHidden;
    int32_t threat_dim = NnueNet::kThreatDim;
    out.write(reinterpret_cast<const char*>(&features), sizeof(features));
    out.write(reinterpret_cast<const char*>(&hidden), sizeof(hidden));
    out.write(reinterpret_cast<const char*>(&threat_dim), sizeof(threat_dim));
    std::vector<int16_t> zeros(static_cast<std::size_t>(NnueNet::kKatFeatures) * NnueNet::kHidden);
    out.write(reinterpret_cast<const char*>(zeros.data()),
              static_cast<std::streamsize>(zeros.size() * 2));
    std::array<int16_t, NnueNet::kHidden> bias{};
    bias.fill(64);
    out.write(reinterpret_cast<const char*>(bias.data()), static_cast<std::streamsize>(bias.size() * 2));
    std::array<int16_t, 2 * NnueNet::kHidden> output{};
    out.write(reinterpret_cast<const char*>(output.data()),
              static_cast<std::streamsize>(output.size() * 2));
    std::array<int16_t, NnueNet::kThreatDim> threats{};
    threats[6 + PAWN] = static_cast<int16_t>(NnueNet::kWeightScale);
    out.write(reinterpret_cast<const char*>(threats.data()),
              static_cast<std::streamsize>(threats.size() * 2));
    int32_t output_bias = 0;
    out.write(reinterpret_cast<const char*>(&output_bias), sizeof(output_bias));
  }

  ASSERT_TRUE(Nnue::instance().load(path.string()));
  ASSERT_TRUE(Nnue::instance().uses_kat());
  ASSERT_TRUE(Nnue::instance().uses_king_buckets());

  Position pos;
  pos.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1");
  EXPECT_EQ(Nnue::instance().evaluate(pos), 0);

  pos.set_fen("4k3/8/8/8/8/8/4p3/3K4 w - - 0 1");
  EXPECT_EQ(Nnue::instance().evaluate(pos), 1);
  const int cached_before = Nnue::instance().evaluate(pos);
  Move king_move_for_cache = Move::make(SQ_D1, SQ_E1);
  StateInfo cache_state;
  pos.do_move(king_move_for_cache, cache_state);
  const int cached_after = Nnue::instance().evaluate(pos);
  Position refreshed_position = pos;
  refreshed_position.set_nnue(&Nnue::instance());
  EXPECT_EQ(cached_after, Nnue::instance().evaluate(refreshed_position));
  pos.undo_move(king_move_for_cache, cache_state);
  EXPECT_EQ(Nnue::instance().evaluate(pos), cached_before);

  Move king_move = Move::make(SQ_E1, SQ_D1);
  pos.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1");
  StateInfo state;
  pos.do_move(king_move, state);
  NnueAccumulator refreshed;
  Nnue::instance().refresh(pos, refreshed);
  EXPECT_EQ(pos.nnue_acc().half, refreshed.half);
  EXPECT_EQ(pos.nnue_acc().king_bucket, refreshed.king_bucket);
  EXPECT_EQ(pos.nnue_acc().mirror, refreshed.mirror);
  pos.undo_move(king_move, state);
  Nnue::instance().refresh(pos, refreshed);
  EXPECT_EQ(pos.nnue_acc().half, refreshed.half);
  EXPECT_EQ(pos.nnue_acc().king_bucket, refreshed.king_bucket);
  EXPECT_EQ(pos.nnue_acc().mirror, refreshed.mirror);

  // King-bucket nets must not receive the classical extras residual.
  Nnue::instance().load_default_from_hce();
  pos.set_startpos();
  const int hce = evaluate(pos);
  ASSERT_TRUE(Nnue::instance().load(path.string()));
  pos.set_startpos();
  EXPECT_EQ(evaluate(pos), Nnue::instance().evaluate(pos));
  EXPECT_NE(hce, evaluate(pos));
  std::filesystem::remove(path);
}

TEST(NnueTest, LoadDoesNotForceEnabledAndFailedLoadLeavesNet) {
  init_bitboards();
  Zobrist::init();
  Nnue nnue;
  nnue.set_enabled(false);
  ASSERT_TRUE(nnue.load_default_from_hce());
  EXPECT_FALSE(nnue.is_enabled());

  nnue.set_enabled(true);
  Position pos;
  pos.set_nnue(&nnue);
  pos.set_startpos();
  const int before = nnue.evaluate(pos);

  EXPECT_FALSE(nnue.load("/no/such/nsce-eval.bin"));
  EXPECT_TRUE(nnue.is_enabled());
  EXPECT_EQ(nnue.evaluate(pos), before);

  nnue.set_enabled(false);
  ASSERT_TRUE(nnue.load_default_from_hce());
  EXPECT_FALSE(nnue.is_enabled());
}

TEST(NnueTest, Per1LoadAndIncrementalMatchesRefresh) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_per1_synth.bin";
  {
    std::vector<int16_t> w0(static_cast<std::size_t>(NnueNet::kFeatures) * NnueNet::kPer1Hidden, 0);
    for (int h = 0; h < NnueNet::kPer1Hidden; ++h) w0[h] = 1;
    write_per1_net(path, w0, {});
  }
  Nnue nnue;
  ASSERT_TRUE(nnue.load(path.string()));
  EXPECT_TRUE(nnue.uses_per1());
  EXPECT_FALSE(nnue.uses_king_buckets());
  Position pos;
  pos.set_nnue(&nnue);
  pos.set_startpos();
  NnueAccumulator refreshed;
  nnue.refresh(pos, refreshed);
  EXPECT_EQ(pos.nnue_acc().per1, refreshed.per1);
  EXPECT_EQ(pos.nnue_acc().piece_count, 32);
  MoveList list;
  generate_legal(pos, list);
  ASSERT_GT(list.size, 0);
  StateInfo st;
  pos.do_move(list.moves[0], st);
  nnue.refresh(pos, refreshed);
  EXPECT_EQ(pos.nnue_acc().per1, refreshed.per1);
  const int score = nnue.evaluate(pos);
  EXPECT_EQ(score, nnue.evaluate(refreshed, pos.side_to_move()));
  std::filesystem::remove(path);
}

TEST(NnueTest, Per1IncrementalSurvivesCapturesAndUndo) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_per1_inc.bin";
  {
    std::vector<int16_t> w0(static_cast<std::size_t>(NnueNet::kFeatures) * NnueNet::kPer1Hidden);
    for (std::size_t i = 0; i < w0.size(); ++i)
      w0[i] = static_cast<int16_t>((static_cast<int>(i) % 7) - 3);
    std::array<int16_t, NnueNet::kPer1Hidden> b0{};
    for (int h = 0; h < NnueNet::kPer1Hidden; ++h) b0[h] = static_cast<int16_t>(h % 5);
    write_per1_net(path, w0, b0);
  }
  Nnue nnue;
  ASSERT_TRUE(nnue.load(path.string()));
  Position pos;
  pos.set_nnue(&nnue);
  pos.set_use_extras(false);
  pos.set_startpos();
  std::vector<Move> moves;
  std::vector<StateInfo> states;
  NnueAccumulator refreshed;
  auto check = [&](const char* tag) {
    nnue.refresh(pos, refreshed);
    EXPECT_EQ(pos.nnue_acc().per1, refreshed.per1) << tag;
    EXPECT_EQ(pos.nnue_acc().piece_count, refreshed.piece_count) << tag;
    EXPECT_EQ(nnue.evaluate(pos), nnue.evaluate(refreshed, pos.side_to_move())) << tag;
  };
  check("start");
  for (int ply = 0; ply < 48; ++ply) {
    MoveList legal;
    generate_legal(pos, legal);
    if (legal.size == 0) break;
    Move move = legal.moves[(ply * 13 + 7) % legal.size];
    moves.push_back(move);
    states.emplace_back();
    pos.do_move(move, states.back());
    check("after ply");
  }
  for (int ply = static_cast<int>(moves.size()) - 1; ply >= 0; --ply) {
    pos.undo_move(moves[ply], states[ply]);
    check("undo");
  }
  std::filesystem::remove(path);
}

TEST(NnueTest, Per1BiasMatchesBulletScale) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_per1_bias.bin";
  {
    std::array<int32_t, NnueNet::kPer1Buckets> l3b{};
    l3b[7] = NnueNet::kPer1QA * NnueNet::kPer1QB;
    write_per1_net(path, std::vector<int16_t>(static_cast<std::size_t>(NnueNet::kFeatures) * NnueNet::kPer1Hidden, 0),
                   {}, l3b);
  }
  Nnue nnue;
  ASSERT_TRUE(nnue.load(path.string()));
  Position pos;
  pos.set_nnue(&nnue);
  pos.set_startpos();
  EXPECT_EQ(nnue.evaluate(pos), NnueNet::kPer1Scale);
  std::filesystem::remove(path);
}

TEST(NnueTest, Per1EvaluateMatchesIndependentScrelu) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_per1_screlu.bin";
  {
    std::vector<int16_t> w0(static_cast<std::size_t>(NnueNet::kFeatures) * NnueNet::kPer1Hidden);
    for (std::size_t i = 0; i < w0.size(); ++i)
      w0[i] = static_cast<int16_t>((static_cast<int>(i) % 51) - 25);
    std::array<int16_t, NnueNet::kPer1Hidden> b0{};
    for (int h = 0; h < NnueNet::kPer1Hidden; ++h) b0[h] = static_cast<int16_t>((h % 17) * 20 - 80);
    write_per1_net(path, w0, b0, {}, true);
  }
  Nnue nnue;
  ASSERT_TRUE(nnue.load(path.string()));
  Position pos;
  pos.set_nnue(&nnue);
  pos.set_use_extras(false);
  pos.set_startpos();
  auto expected = [&](const NnueAccumulator& acc, Color stm) {
    const NnueNet& net = nnue.net();
    const int bucket = per1_output_bucket(acc.piece_count);
    const int qa = net.per1_qa;
    const int qb = net.per1_qb;
    const int half = NnueNet::kPer1Hidden / 2;
    std::array<int32_t, NnueNet::kPer1Hidden> pair{};
    auto fill = [&](const int16_t* a, int off) {
      for (int i = 0; i < half; ++i) {
        const int x0 = std::clamp(static_cast<int>(a[i]), 0, qa);
        const int x1 = std::clamp(static_cast<int>(a[half + i]), 0, qa);
        pair[off + i] = x0 * x1 / qa;
      }
    };
    fill(acc.per1[stm].data(), 0);
    fill(acc.per1[~stm].data(), half);
    std::array<int32_t, NnueNet::kPer1L2> h2{};
    for (int j = 0; j < NnueNet::kPer1L2; ++j) {
      int64_t s = 0;
      for (int i = 0; i < NnueNet::kPer1Hidden; ++i)
        s += static_cast<int64_t>(pair[i]) * net.per1_l1w[bucket][j][i];
      s /= qa;
      s += net.per1_l1b[bucket][j];
      const int x = std::clamp(static_cast<int>(s / qb), 0, qa);
      h2[j] = x * x;
    }
    std::array<int32_t, NnueNet::kPer1L3> h3{};
    for (int j = 0; j < NnueNet::kPer1L3; ++j) {
      int64_t s = 0;
      for (int i = 0; i < NnueNet::kPer1L2; ++i)
        s += static_cast<int64_t>(h2[i]) * net.per1_l2w[bucket][j][i];
      s /= qa;
      s += net.per1_l2b[bucket][j];
      const int x = std::clamp(static_cast<int>(s / qb), 0, qa);
      h3[j] = x * x;
    }
    int64_t sum = 0;
    for (int i = 0; i < NnueNet::kPer1L3; ++i)
      sum += static_cast<int64_t>(h3[i]) * net.per1_l3w[bucket][i];
    sum /= qa;
    sum += net.per1_l3b[bucket];
    return static_cast<int>(sum * net.per1_scale / (static_cast<int64_t>(qa) * qb));
  };
  EXPECT_EQ(nnue.evaluate(pos), expected(pos.nnue_acc(), pos.side_to_move()));
  MoveList legal;
  generate_legal(pos, legal);
  ASSERT_GT(legal.size, 0);
  StateInfo st;
  pos.do_move(legal.moves[0], st);
  EXPECT_EQ(nnue.evaluate(pos), expected(pos.nnue_acc(), pos.side_to_move()));
  std::filesystem::remove(path);
}

TEST(EvalTest, ClampEvalStaysOutOfMateBand) {
  EXPECT_EQ(clamp_eval(0), 0);
  EXPECT_EQ(clamp_eval(kMaxEval + 50), kMaxEval);
  EXPECT_EQ(clamp_eval(-kMaxEval - 50), -kMaxEval);
  EXPECT_LT(kMaxEval, VALUE_MATE - 256);
}

TEST(EvalTest, SimpleEvalIsMaterialFromSideToMove) {
  init_bitboards();
  Zobrist::init();
  Position pos;
  pos.set_startpos();
  EXPECT_EQ(simple_eval(pos), 0);
  pos.set_fen("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1");
  EXPECT_EQ(simple_eval(pos), piece_value(QUEEN));
  pos.set_fen("4k3/8/8/8/8/8/4Q3/4K3 b - - 0 1");
  EXPECT_EQ(simple_eval(pos), -piece_value(QUEEN));
}

TEST(NnueTest, Frozen768AddsFullClassicalExtras) {
  init_bitboards();
  Zobrist::init();
  ASSERT_TRUE(Nnue::instance().load_default_from_hce());
  Position pos;
  pos.set_startpos();
  pos.set_use_extras(true);
  EXPECT_EQ(evaluate(pos), evaluate_nnue(pos) + classical_extras(pos));
  EXPECT_EQ(applied_extras(pos), classical_extras(pos));
}

TEST(NnueTest, Per1EvalMinmaxAndFadedExtras) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_per1_eval.bin";
  {
    std::array<int32_t, NnueNet::kPer1Buckets> l3b{};
    l3b[7] = NnueNet::kPer1QA * NnueNet::kPer1QB;
    write_per1_net(path, std::vector<int16_t>(static_cast<std::size_t>(NnueNet::kFeatures) * NnueNet::kPer1Hidden, 0),
                   {}, l3b);
  }
  Nnue nnue;
  ASSERT_TRUE(nnue.load(path.string()));
  Position pos;
  pos.set_nnue(&nnue);

  pos.set_startpos();
  pos.set_use_extras(false);
  EXPECT_EQ(evaluate(pos), NnueNet::kPer1Scale);
  EXPECT_EQ(simple_eval(pos), 0);

  pos.set_use_extras(true);
  const int faded = 10 * (32 - 8) / 96;
  EXPECT_EQ(evaluate(pos), NnueNet::kPer1Scale + faded);
  EXPECT_EQ(applied_extras(pos), faded);
  EXPECT_LT(std::abs(faded), std::abs(classical_extras(pos)));
  EXPECT_NE(evaluate(pos), NnueNet::kPer1Scale + classical_extras(pos));

  pos.set_fen("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1");
  EXPECT_GE(std::abs(simple_eval(pos)), kPer1SimpleSkip);
  const int nnue_score = evaluate_nnue(pos);
  const int blended = (3 * nnue_score + simple_eval(pos)) / 4;
  pos.set_use_extras(true);
  EXPECT_EQ(evaluate(pos), clamp_eval(blended));
  EXPECT_EQ(applied_extras(pos), 0);
  pos.set_use_extras(false);
  EXPECT_EQ(evaluate(pos), clamp_eval(blended));
  EXPECT_EQ(applied_extras(pos), 0);
  std::filesystem::remove(path);
}

static void write_per1_simple_net(const std::filesystem::path& path, const std::vector<int16_t>& w0,
                                  const std::array<int16_t, NnueNet::kPer1SimpleHidden>& b0,
                                  const std::array<int16_t, 2 * NnueNet::kPer1SimpleHidden>& w1,
                                  int32_t b1) {
  std::ofstream out(path, std::ios::binary);
  out.write("NSCEPER1", 8);
  int32_t hdr[] = {NnueNet::kPer1SimpleHidden, NnueNet::kFeatures, 0, 0, 0,
                   NnueNet::kPer1QA,           NnueNet::kPer1QB,   NnueNet::kPer1Scale};
  out.write(reinterpret_cast<const char*>(hdr), sizeof(hdr));
  out.write(reinterpret_cast<const char*>(w0.data()), static_cast<std::streamsize>(w0.size() * 2));
  out.write(reinterpret_cast<const char*>(b0.data()), sizeof(b0));
  out.write(reinterpret_cast<const char*>(w1.data()), sizeof(w1));
  out.write(reinterpret_cast<const char*>(&b1), 4);
}

TEST(NnueTest, Per1SimpleBiasIsScaleCp) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_per1_simple_bias.bin";
  {
    std::vector<int16_t> w0(
        static_cast<std::size_t>(NnueNet::kFeatures) * NnueNet::kPer1SimpleHidden, 0);
    write_per1_simple_net(path, w0, {}, {}, NnueNet::kPer1QA * NnueNet::kPer1QB);
  }
  Nnue nnue;
  ASSERT_TRUE(nnue.load(path.string()));
  EXPECT_TRUE(nnue.uses_per1());
  EXPECT_TRUE(nnue.net().per1_simple);
  Position pos;
  pos.set_nnue(&nnue);
  pos.set_use_extras(false);
  pos.set_startpos();
  EXPECT_EQ(nnue.evaluate(pos), NnueNet::kPer1Scale);
  std::filesystem::remove(path);
}

TEST(NnueTest, Per1SimpleIncrementalMatchesRefresh) {
  init_bitboards();
  Zobrist::init();
  auto path = std::filesystem::temp_directory_path() / "nsce_per1_simple_inc.bin";
  {
    std::vector<int16_t> w0(
        static_cast<std::size_t>(NnueNet::kFeatures) * NnueNet::kPer1SimpleHidden, 0);
    for (int h = 0; h < NnueNet::kPer1SimpleHidden; ++h) w0[h] = 1;
    std::array<int16_t, 2 * NnueNet::kPer1SimpleHidden> w1{};
    w1[0] = 1;
    write_per1_simple_net(path, w0, {}, w1, 0);
  }
  Nnue nnue;
  ASSERT_TRUE(nnue.load(path.string()));
  Position pos;
  pos.set_nnue(&nnue);
  pos.set_startpos();
  NnueAccumulator refreshed;
  nnue.refresh(pos, refreshed);
  EXPECT_EQ(pos.nnue_acc().per1, refreshed.per1);
  MoveList list;
  generate_legal(pos, list);
  ASSERT_GT(list.size, 0);
  StateInfo st;
  pos.do_move(list.moves[0], st);
  nnue.refresh(pos, refreshed);
  EXPECT_EQ(pos.nnue_acc().per1, refreshed.per1);
  EXPECT_EQ(nnue.evaluate(pos), nnue.evaluate(refreshed, pos.side_to_move()));
  std::filesystem::remove(path);
}

