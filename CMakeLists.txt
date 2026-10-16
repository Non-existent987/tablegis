cmake_minimum_required(VERSION 3.15)
project(tablegis LANGUAGES C CXX)

find_package(pybind11 CONFIG REQUIRED)

# 内置 libdeflate（静态库，仅解压用）
set(LIBDEFLATE_BUILD_SHARED_LIB OFF CACHE BOOL "" FORCE)
set(LIBDEFLATE_BUILD_STATIC_LIB ON CACHE BOOL "" FORCE)
set(LIBDEFLATE_BUILD_GZIP OFF CACHE BOOL "" FORCE)
set(LIBDEFLATE_BUILD_TESTS OFF CACHE BOOL "" FORCE)
add_subdirectory(tablegis/src/libdeflate)

# 静态库需 fPIC，才能链接进 .so（Linux/macOS）
set_target_properties(libdeflate_static PROPERTIES POSITION_INDEPENDENT_CODE ON)

pybind11_add_module(_xlsx2csv tablegis/src/xlsx2csv_ext.cpp)
target_link_libraries(_xlsx2csv PRIVATE libdeflate::libdeflate_static)
target_compile_features(_xlsx2csv PRIVATE cxx_std_17)

if(MSVC)
    target_compile_options(_xlsx2csv PRIVATE /utf-8)
endif()

install(TARGETS _xlsx2csv DESTINATION tablegis)
