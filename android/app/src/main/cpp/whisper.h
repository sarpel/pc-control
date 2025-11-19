#ifndef WHISPER_H
#define WHISPER_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

    struct whisper_context;
    struct whisper_full_params;

    struct whisper_context * whisper_init_from_file(const char * path_model);
    void whisper_free(struct whisper_context * ctx);

    struct whisper_full_params whisper_full_default_params(int strategy);

    int whisper_full(
            struct whisper_context * ctx,
            struct whisper_full_params params,
            const float * samples,
            int n_samples);

    int whisper_full_n_segments(struct whisper_context * ctx);
    const char * whisper_full_get_segment_text(struct whisper_context * ctx, int i_segment);

#ifdef __cplusplus
}
#endif

#endif // WHISPER_H
