# Windows x86_64 cross toolchain.
# Prefers a local llvm-mingw tree; falls back to system MinGW-w64 GCC
# (Debian/Ubuntu: g++-mingw-w64-x86-64, posix threads).

set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

get_filename_component(_llvm_mingw "${CMAKE_CURRENT_LIST_DIR}/../third_party/llvm-mingw" ABSOLUTE)
if(EXISTS "${_llvm_mingw}/bin/x86_64-w64-mingw32-clang++")
  set(CMAKE_C_COMPILER "${_llvm_mingw}/bin/x86_64-w64-mingw32-clang")
  set(CMAKE_CXX_COMPILER "${_llvm_mingw}/bin/x86_64-w64-mingw32-clang++")
  set(CMAKE_RC_COMPILER "${_llvm_mingw}/bin/x86_64-w64-mingw32-windres")
  set(CMAKE_AR "${_llvm_mingw}/bin/x86_64-w64-mingw32-ar")
  set(CMAKE_RANLIB "${_llvm_mingw}/bin/x86_64-w64-mingw32-ranlib")
  set(CMAKE_FIND_ROOT_PATH "${_llvm_mingw}/x86_64-w64-mingw32")
else()
  find_program(NSCE_MINGW_CC NAMES x86_64-w64-mingw32-gcc-posix x86_64-w64-mingw32-gcc)
  find_program(NSCE_MINGW_CXX NAMES x86_64-w64-mingw32-g++-posix x86_64-w64-mingw32-g++)
  find_program(NSCE_MINGW_RC NAMES x86_64-w64-mingw32-windres)
  find_program(NSCE_MINGW_AR NAMES x86_64-w64-mingw32-gcc-ar x86_64-w64-mingw32-ar)
  find_program(NSCE_MINGW_RANLIB NAMES x86_64-w64-mingw32-gcc-ranlib x86_64-w64-mingw32-ranlib)
  if(NOT NSCE_MINGW_CC OR NOT NSCE_MINGW_CXX)
    message(FATAL_ERROR
      "Windows cross-compiler not found. Unpack llvm-mingw into third_party/llvm-mingw "
      "or install g++-mingw-w64-x86-64.")
  endif()
  set(CMAKE_C_COMPILER "${NSCE_MINGW_CC}")
  set(CMAKE_CXX_COMPILER "${NSCE_MINGW_CXX}")
  if(NSCE_MINGW_RC)
    set(CMAKE_RC_COMPILER "${NSCE_MINGW_RC}")
  endif()
  if(NSCE_MINGW_AR)
    set(CMAKE_AR "${NSCE_MINGW_AR}")
  endif()
  if(NSCE_MINGW_RANLIB)
    set(CMAKE_RANLIB "${NSCE_MINGW_RANLIB}")
  endif()
  set(CMAKE_FIND_ROOT_PATH "/usr/x86_64-w64-mingw32")
endif()

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
