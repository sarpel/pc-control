package com.pccontrol.voice

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/**
 * Main Application class for PC Voice Assistant
 *
 * This class initializes Hilt dependency injection and sets up
 * the application-level configuration for the voice assistant.
 */
@HiltAndroidApp
class PCVoiceAssistantApplication : Application()