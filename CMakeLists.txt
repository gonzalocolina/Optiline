cmake_minimum_required(VERSION 3.16)
project(nsce VERSION 0.10.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

option(NSCE_NATIVE "Enable -march=native" ON)
option(NSCE_LTO "Enable link-time optimization" ON)
option(NSCE_AVX2 "Enable AVX2 NNUE kernels" ON)
option(NSCE_SANITIZE "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)
option(NSCE_TSAN "Enable ThreadSanitizer" OFF)
option(NSCE_STATS "Enable low-overhead search telemetry" OFF)

if(NSCE_SANITIZE AND NSCE_TSAN)
  message(FATAL_ERROR "NSCE_SANITIZE and NSCE_TSAN are mutually exclusive")
endif()
if((NSCE_SANITIZE OR NSCE_TSAN) AND NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  message(FATAL_ERROR "Sanitizer builds require GCC or Clang")
endif()
if(NSCE_SANITIZE)
  add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
elseif(NSCE_TSAN)
  add_compile_options(-fsanitize=thread -fno-omit-frame-pointer)
  add_link_options(-fsanitize=thread)
endif()

add_library(nsce_engine
  engine/src/bitboard.cpp
  engine/src/board.cpp
  engine/src/movegen.cpp
  engine/src/zobrist.cpp
  engine/src/tt.cpp
  engine/src/eval.cpp
  engine/src/nnue.cpp
  engine/src/policy.cpp
  engine/src/controller.cpp
  engine/src/see.cpp
  engine/src/search.cpp
  engine/src/uci.cpp
  engine/src/perft.cpp
)

target_include_directories(nsce_engine PUBLIC engine/include)

find_package(Threads REQUIRED)
target_link_libraries(nsce_engine PUBLIC Threads::Threads)

target_compile_options(nsce_engine PRIVATE
  $<$<CONFIG:Release>:-O3 -DNDEBUG>
  $<$<CONFIG:Debug>:-O0 -g>
  -Wall -Wextra -Wpedantic
)
if(NSCE_STATS)
  target_compile_definitions(nsce_engine PUBLIC NSCE_STATS=1)
endif()

if(NSCE_NATIVE)
  target_compile_options(nsce_engine PRIVATE -march=native)
endif()
if(NSCE_AVX2)
  include(CheckCXXCompilerFlag)
  check_cxx_compiler_flag("-mavx2" COMPILER_SUPPORTS_AVX2)
  if(COMPILER_SUPPORTS_AVX2)
    target_compile_options(nsce_engine PRIVATE -mavx2 -mfma)
    target_compile_definitions(nsce_engine PRIVATE NSCE_HAS_AVX2=1)
  endif()
endif()
if(NSCE_LTO)
  include(CheckIPOSupported)
  check_ipo_supported(RESULT ipo_ok OUTPUT ipo_err)
  if(ipo_ok)
    set_property(TARGET nsce_engine PROPERTY INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE)
  endif()
endif()

add_executable(nsce engine/src/main.cpp)
target_link_libraries(nsce PRIVATE nsce_engine)
if(NSCE_LTO AND ipo_ok)
  set_property(TARGET nsce PROPERTY INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE)
endif()

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

enable_testing()
add_executable(nsce_tests
  engine/tests/test_perft.cpp
  engine/tests/test_board.cpp
  engine/tests/test_nnue.cpp
  engine/tests/test_search.cpp
  engine/tests/test_see.cpp
  engine/tests/test_tt.cpp
)
target_link_libraries(nsce_tests PRIVATE nsce_engine GTest::gtest_main)
include(GoogleTest)
gtest_discover_tests(nsce_tests)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(
  NAME PythonExperimentTests
  COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tools/tests -p "test_*.py"
)
set_tests_properties(PythonExperimentTests PROPERTIES WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})
add_test(
  NAME UciSmoke
  COMMAND ${Python3_EXECUTABLE} tools/smoke_match.py --engine $<TARGET_FILE:nsce>
          --games 1 --depth-a 3 --depth-b 2 --max-plies 10
)
set_tests_properties(UciSmoke PROPERTIES WORKING_DIRECTORY ${CMAKE_SOURCE_DIR} TIMEOUT 30)

add_executable(nsce_bench engine/benches/bench_search.cpp)
target_link_libraries(nsce_bench PRIVATE nsce_engine)

add_executable(nsce_bench_nnue engine/benches/bench_nnue_latency.cpp)
target_link_libraries(nsce_bench_nnue PRIVATE nsce_engine)

# Optional PGO helpers (manual two-pass):
#   cmake -DNSCE_PGO_GENERATE=ON ... && build && ./nsce bench 8
#   cmake -DNSCE_PGO_USE=ON ... && rebuild
option(NSCE_PGO_GENERATE "Compile with -fprofile-generate" OFF)
option(NSCE_PGO_USE "Compile with -fprofile-use" OFF)
if(NSCE_PGO_GENERATE)
  target_compile_options(nsce_engine PRIVATE -fprofile-generate)
  target_link_options(nsce PRIVATE -fprofile-generate)
endif()
if(NSCE_PGO_USE)
  target_compile_options(nsce_engine PRIVATE -fprofile-use -fprofile-correction)
  target_link_options(nsce PRIVATE -fprofile-use)
endif()
