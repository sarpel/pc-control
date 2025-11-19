package com.pccontrol.voice.di

import android.content.Context
import com.pccontrol.voice.audio.AudioProcessingService
import com.pccontrol.voice.data.repository.VoiceCommandRepository
import com.pccontrol.voice.services.WebSocketManager
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideVoiceCommandRepository(
        @ApplicationContext context: Context
    ): VoiceCommandRepository {
        return VoiceCommandRepository.getInstance(context)
    }

    @Provides
    @Singleton
    fun provideAudioProcessingService(
        @ApplicationContext context: Context
    ): AudioProcessingService {
        return AudioProcessingService.getInstance(context)
    }

    @Provides
    @Singleton
    fun provideWebSocketManager(
        @ApplicationContext context: Context
    ): WebSocketManager {
        return WebSocketManager.getInstance(context)
    }
}
