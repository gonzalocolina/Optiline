#include "nsce/board.hpp"
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

TEST(NnueTest, EvalFinite) {
  init_bitboards();
  Zobrist::init();
  Nnue::instance().load_default_from_hce();
  Position pos;
  pos.set_startpos();
  int e = evaluate(pos);
  EXPECT_GT(e, -5000);
  EXPECT_LT(e, 5000);
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
  std::filesystem::remove(path);
}
