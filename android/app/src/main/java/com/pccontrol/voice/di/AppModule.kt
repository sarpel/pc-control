package com.pccontrol.voice.di

import android.content.Context
import com.pccontrol.voice.audio.AudioProcessingService
import com.pccontrol.voice.data.database.AppDatabase
import com.pccontrol.voice.data.repository.PairingRepository
import com.pccontrol.voice.data.repository.VoiceCommandRepository
import com.pccontrol.voice.network.PCDiscovery
import com.pccontrol.voice.security.KeyStoreManager
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
    fun provideKeyStoreManager(
        @ApplicationContext context: Context
    ): KeyStoreManager {
        return KeyStoreManager.getInstance(context)
    }

    @Provides
    @Singleton
    fun provideWebSocketManager(
        @ApplicationContext context: Context
    ): WebSocketManager {
        return WebSocketManager.getInstance(context)
    }

    @Provides
    @Singleton
    fun providePCDiscovery(
        @ApplicationContext context: Context
    ): PCDiscovery {
        return PCDiscovery(context)
    }

    @Provides
    @Singleton
    fun provideAppDatabase(
        @ApplicationContext context: Context
    ): AppDatabase {
        return AppDatabase.getDatabase(context)
    }

    @Provides
    @Singleton
    fun providePairingRepository(
        @ApplicationContext context: Context,
        webSocketManager: WebSocketManager,
        keyStoreManager: KeyStoreManager,
        appDatabase: AppDatabase
    ): PairingRepository {
        return PairingRepository(context, webSocketManager, keyStoreManager, appDatabase)
    }
}
