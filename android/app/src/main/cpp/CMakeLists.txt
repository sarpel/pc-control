cmake_minimum_required(VERSION 3.18.1)

project("whisper_jni")

# Define the library
add_library(
        whisper_jni
        SHARED
        whisper_jni.cpp
        whisper_dummy.c
)

target_include_directories(whisper_jni PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

find_library(
        log-lib
        log
)

target_link_libraries(
        whisper_jni
        ${log-lib}
)
