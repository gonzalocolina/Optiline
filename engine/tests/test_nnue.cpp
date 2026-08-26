#include "nsce/board.hpp"
#include "nsce/context.hpp"
#include "nsce/nnue.hpp"
#include "nsce/movegen.hpp"
#include "nsce/zobrist.hpp"
#include "nsce/bitboard.hpp"
#include "nsce/eval.hpp"

#include <gtest/gtest.h>

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
