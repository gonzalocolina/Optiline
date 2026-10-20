#include "nsce/datagen.hpp"

#include <gtest/gtest.h>

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <vector>

using namespace nsce;

namespace {

std::vector<char> read_file(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  return std::vector<char>(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}

}  // namespace

TEST(DatagenTest, SameSeedAndThreadsReproduceTheFile) {
  const auto dir = std::filesystem::temp_directory_path();
  const auto first = dir / "nsce_datagen_det_a.bin";
  const auto second = dir / "nsce_datagen_det_b.bin";
  std::filesystem::remove(first);
  std::filesystem::remove(second);
  DatagenOptions opt;
  opt.eval_file = "internal";
  opt.games = 6;
  opt.nodes = 40;
  opt.threads = 3;
  opt.hash_mb = 1;
  opt.random_plies = 4;
  opt.seed = 7;
  opt.max_plies = 40;
  opt.output = first.string();
  ASSERT_GT(run_datagen(opt), 0u);
  opt.output = second.string();
  ASSERT_GT(run_datagen(opt), 0u);
  const auto a = read_file(first);
  const auto b = read_file(second);
  EXPECT_FALSE(a.empty());
  EXPECT_EQ(a.size() % 32, 0u);
  EXPECT_EQ(a, b);
  std::filesystem::remove(first);
  std::filesystem::remove(second);
}
