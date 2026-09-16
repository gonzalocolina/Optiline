#include "nsce/board.hpp"
#include "nsce/context.hpp"
#include "nsce/nnue.hpp"
#include "nsce/movegen.hpp"
#include "nsce/zobrist.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/eval.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <vector>

using namespace nsce;

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
    std::ofstream out(path, std::ios::binary);
    out.write("NSCEPER1", 8);
    int32_t hidden = NnueNet::kPer1Hidden;
    int32_t features = NnueNet::kFeatures;
    int32_t buckets = NnueNet::kPer1Buckets;
    int32_t qa = NnueNet::kPer1QA;
    int32_t qb = NnueNet::kPer1QB;
    int32_t scale = NnueNet::kPer1Scale;
    out.write(reinterpret_cast<const char*>(&hidden), 4);
    out.write(reinterpret_cast<const char*>(&features), 4);
    out.write(reinterpret_cast<const char*>(&buckets), 4);
    out.write(reinterpret_cast<const char*>(&qa), 4);
    out.write(reinterpret_cast<const char*>(&qb), 4);
    out.write(reinterpret_cast<const char*>(&scale), 4);
    std::vector<int16_t> w0(static_cast<std::size_t>(features) * hidden, 0);
    for (int h = 0; h < hidden; ++h) w0[h] = 1;
    out.write(reinterpret_cast<const char*>(w0.data()), static_cast<std::streamsize>(w0.size() * 2));
    std::array<int16_t, NnueNet::kPer1Hidden> b0{};
    out.write(reinterpret_cast<const char*>(b0.data()), sizeof(b0));
    std::array<int16_t, 2 * NnueNet::kPer1Hidden> w1{};
    w1[0] = 1;
    for (int b = 0; b < buckets; ++b)
      out.write(reinterpret_cast<const char*>(w1.data()), sizeof(w1));
    std::array<int32_t, NnueNet::kPer1Buckets> b1{};
    out.write(reinterpret_cast<const char*>(b1.data()), sizeof(b1));
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
    std::ofstream out(path, std::ios::binary);
    out.write("NSCEPER1", 8);
    int32_t hidden = NnueNet::kPer1Hidden;
    int32_t features = NnueNet::kFeatures;
    int32_t buckets = NnueNet::kPer1Buckets;
    int32_t qa = NnueNet::kPer1QA;
    int32_t qb = NnueNet::kPer1QB;
    int32_t scale = NnueNet::kPer1Scale;
    out.write(reinterpret_cast<const char*>(&hidden), 4);
    out.write(reinterpret_cast<const char*>(&features), 4);
    out.write(reinterpret_cast<const char*>(&buckets), 4);
    out.write(reinterpret_cast<const char*>(&qa), 4);
    out.write(reinterpret_cast<const char*>(&qb), 4);
    out.write(reinterpret_cast<const char*>(&scale), 4);
    std::vector<int16_t> w0(static_cast<std::size_t>(features) * hidden);
    for (std::size_t i = 0; i < w0.size(); ++i)
      w0[i] = static_cast<int16_t>((static_cast<int>(i) % 7) - 3);
    out.write(reinterpret_cast<const char*>(w0.data()), static_cast<std::streamsize>(w0.size() * 2));
    std::array<int16_t, NnueNet::kPer1Hidden> b0{};
    for (int h = 0; h < hidden; ++h) b0[h] = static_cast<int16_t>(h % 5);
    out.write(reinterpret_cast<const char*>(b0.data()), sizeof(b0));
    std::array<int16_t, 2 * NnueNet::kPer1Hidden> w1{};
    for (int i = 0; i < 2 * hidden; ++i) w1[i] = static_cast<int16_t>((i % 5) - 2);
    for (int b = 0; b < buckets; ++b)
      out.write(reinterpret_cast<const char*>(w1.data()), sizeof(w1));
    std::array<int32_t, NnueNet::kPer1Buckets> b1{};
    out.write(reinterpret_cast<const char*>(b1.data()), sizeof(b1));
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
    std::ofstream out(path, std::ios::binary);
    out.write("NSCEPER1", 8);
    int32_t hidden = NnueNet::kPer1Hidden;
    int32_t features = NnueNet::kFeatures;
    int32_t buckets = NnueNet::kPer1Buckets;
    int32_t qa = NnueNet::kPer1QA;
    int32_t qb = NnueNet::kPer1QB;
    int32_t scale = NnueNet::kPer1Scale;
    out.write(reinterpret_cast<const char*>(&hidden), 4);
    out.write(reinterpret_cast<const char*>(&features), 4);
    out.write(reinterpret_cast<const char*>(&buckets), 4);
    out.write(reinterpret_cast<const char*>(&qa), 4);
    out.write(reinterpret_cast<const char*>(&qb), 4);
    out.write(reinterpret_cast<const char*>(&scale), 4);
    std::vector<int16_t> w0(static_cast<std::size_t>(features) * hidden, 0);
    out.write(reinterpret_cast<const char*>(w0.data()), static_cast<std::streamsize>(w0.size() * 2));
    std::array<int16_t, NnueNet::kPer1Hidden> b0{};
    out.write(reinterpret_cast<const char*>(b0.data()), sizeof(b0));
    std::array<int16_t, 2 * NnueNet::kPer1Hidden> w1{};
    for (int b = 0; b < buckets; ++b)
      out.write(reinterpret_cast<const char*>(w1.data()), sizeof(w1));
    std::array<int32_t, NnueNet::kPer1Buckets> b1{};
    b1[7] = NnueNet::kPer1QA * NnueNet::kPer1QB;
    out.write(reinterpret_cast<const char*>(b1.data()), sizeof(b1));
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
    std::ofstream out(path, std::ios::binary);
    out.write("NSCEPER1", 8);
    int32_t hidden = NnueNet::kPer1Hidden;
    int32_t features = NnueNet::kFeatures;
    int32_t buckets = NnueNet::kPer1Buckets;
    int32_t qa = NnueNet::kPer1QA;
    int32_t qb = NnueNet::kPer1QB;
    int32_t scale = NnueNet::kPer1Scale;
    out.write(reinterpret_cast<const char*>(&hidden), 4);
    out.write(reinterpret_cast<const char*>(&features), 4);
    out.write(reinterpret_cast<const char*>(&buckets), 4);
    out.write(reinterpret_cast<const char*>(&qa), 4);
    out.write(reinterpret_cast<const char*>(&qb), 4);
    out.write(reinterpret_cast<const char*>(&scale), 4);
    std::vector<int16_t> w0(static_cast<std::size_t>(features) * hidden);
    for (std::size_t i = 0; i < w0.size(); ++i)
      w0[i] = static_cast<int16_t>((static_cast<int>(i) % 51) - 25);
    out.write(reinterpret_cast<const char*>(w0.data()), static_cast<std::streamsize>(w0.size() * 2));
    std::array<int16_t, NnueNet::kPer1Hidden> b0{};
    for (int h = 0; h < hidden; ++h) b0[h] = static_cast<int16_t>((h % 17) * 20 - 80);
    out.write(reinterpret_cast<const char*>(b0.data()), sizeof(b0));
    for (int b = 0; b < buckets; ++b) {
      std::array<int16_t, 2 * NnueNet::kPer1Hidden> w1{};
      for (int i = 0; i < 2 * hidden; ++i)
        w1[i] = static_cast<int16_t>(((i + 13 * b) % 41) * 400 - 8000);
      out.write(reinterpret_cast<const char*>(w1.data()), sizeof(w1));
    }
    std::array<int32_t, NnueNet::kPer1Buckets> b1{};
    for (int b = 0; b < buckets; ++b) b1[b] = (b - 3) * qa * qb;
    out.write(reinterpret_cast<const char*>(b1.data()), sizeof(b1));
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
    const int16_t* w = net.per1_w1[bucket].data();
    int64_t sum = 0;
    for (int h = 0; h < NnueNet::kPer1Hidden; ++h) {
      int x = std::clamp(static_cast<int>(acc.per1[stm][h]), 0, qa);
      sum += static_cast<int64_t>(x) * x * w[h];
      x = std::clamp(static_cast<int>(acc.per1[~stm][h]), 0, qa);
      sum += static_cast<int64_t>(x) * x * w[NnueNet::kPer1Hidden + h];
    }
    sum /= qa;
    sum += net.per1_b1[bucket];
    return static_cast<int>(sum * net.per1_scale / (static_cast<int64_t>(qa) * net.per1_qb));
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

