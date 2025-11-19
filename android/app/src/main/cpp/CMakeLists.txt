cmake_minimum_required(VERSION 3.18.1)

project("whisper_jni")

# Define the library
add_library(
        whisper_jni
        SHARED
        whisper_jni.cpp
        # In a real project, you would include whisper.cpp source here
        # whisper.cpp 
        # ggml.c
)

# Since we don't have the actual whisper.cpp implementation, we create a dummy one
# to allow linking.
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/whisper_dummy.c 
    "#include \"whisper.h\"
    #include <stdlib.h>
    
    struct whisper_context { int dummy; };
    struct whisper_full_params { int strategy; bool print_progress; };
    
    struct whisper_context * whisper_init_from_file(const char * path_model) {
        struct whisper_context * ctx = (struct whisper_context *)malloc(sizeof(struct whisper_context));
        return ctx;
    }
    
    void whisper_free(struct whisper_context * ctx) {
        free(ctx);
    }
    
    struct whisper_full_params whisper_full_default_params(int strategy) {
        struct whisper_full_params params = { strategy, false };
        return params;
    }
    
    int whisper_full(struct whisper_context * ctx, struct whisper_full_params params, const float * samples, int n_samples) {
        return 0;
    }
    
    int whisper_full_n_segments(struct whisper_context * ctx) {
        return 1;
    }
    
    const char * whisper_full_get_segment_text(struct whisper_context * ctx, int i_segment) {
        return \" [Dummy Transcription] \";
    }
    "
)

target_sources(whisper_jni PRIVATE ${CMAKE_CURRENT_BINARY_DIR}/whisper_dummy.c)

find_library(
        log-lib
        log
)

target_link_libraries(
        whisper_jni
        ${log-lib}
)
