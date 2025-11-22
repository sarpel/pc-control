#include "whisper.h"
#include <stdlib.h>

struct whisper_context { int dummy; };
// struct whisper_full_params is defined in whisper.h

struct whisper_context * whisper_init_from_file(const char * path_model) {
    struct whisper_context * ctx = (struct whisper_context *)malloc(sizeof(struct whisper_context));
    return ctx;
}

void whisper_free(struct whisper_context * ctx) {
    free(ctx);
}

struct whisper_full_params whisper_full_default_params(int strategy) {
    struct whisper_full_params params;
    params.strategy = strategy;
    params.print_progress = false;
    return params;
}

int whisper_full(struct whisper_context * ctx, struct whisper_full_params params, const float * samples, int n_samples) {
    return 0;
}

int whisper_full_n_segments(struct whisper_context * ctx) {
    return 1;
}

const char * whisper_full_get_segment_text(struct whisper_context * ctx, int i_segment) {
    return " [Dummy Transcription] ";
}
