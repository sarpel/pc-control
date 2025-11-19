#include <jni.h>
#include <string>
#include <vector>
#include <android/log.h>
#include "whisper.h"

#define TAG "WhisperJNI"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_pccontrol_voice_audio_SpeechToTextService_00024WhisperModel_init(
        JNIEnv *env,
        jobject thiz,
        jstring modelPath,
        jstring language,
        jint threads) {
    
    const char *model_path_str = env->GetStringUTFChars(modelPath, nullptr);
    
    LOGI("Initializing Whisper model from %s", model_path_str);
    
    struct whisper_context *ctx = whisper_init_from_file(model_path_str);
    
    env->ReleaseStringUTFChars(modelPath, model_path_str);
    
    if (ctx == nullptr) {
        LOGE("Failed to initialize Whisper context");
        return 0;
    }
    
    return (jlong) ctx;
}

JNIEXPORT void JNICALL
Java_com_pccontrol_voice_audio_SpeechToTextService_00024WhisperModel_free(
        JNIEnv *env,
        jobject thiz,
        jlong contextPtr) {
    
    struct whisper_context *ctx = (struct whisper_context *) contextPtr;
    if (ctx != nullptr) {
        whisper_free(ctx);
    }
}

JNIEXPORT jstring JNICALL
Java_com_pccontrol_voice_audio_SpeechToTextService_00024WhisperModel_fullTranscribe(
        JNIEnv *env,
        jobject thiz,
        jlong contextPtr,
        jfloatArray audioData) {
    
    struct whisper_context *ctx = (struct whisper_context *) contextPtr;
    if (ctx == nullptr) {
        return env->NewStringUTF("");
    }
    
    jsize len = env->GetArrayLength(audioData);
    jfloat *samples = env->GetFloatArrayElements(audioData, nullptr);
    
    // 0 = WHISPER_SAMPLING_GREEDY
    struct whisper_full_params params = whisper_full_default_params(0); 
    params.print_progress = false;
    
    LOGI("Starting transcription of %d samples", len);
    
    if (whisper_full(ctx, params, samples, len) != 0) {
        LOGE("Whisper full transcription failed");
        env->ReleaseFloatArrayElements(audioData, samples, 0);
        return env->NewStringUTF("");
    }
    
    std::string result;
    int n_segments = whisper_full_n_segments(ctx);
    for (int i = 0; i < n_segments; ++i) {
        const char *text = whisper_full_get_segment_text(ctx, i);
        result += text;
    }
    
    env->ReleaseFloatArrayElements(audioData, samples, 0);
    
    return env->NewStringUTF(result.c_str());
}

} // extern "C"
