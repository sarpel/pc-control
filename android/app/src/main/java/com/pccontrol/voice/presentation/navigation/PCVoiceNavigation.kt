package com.pccontrol.voice.presentation.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pccontrol.voice.presentation.ui.screens.DevicePairingScreen
import com.pccontrol.voice.presentation.ui.screens.VoiceCommandScreen
import com.pccontrol.voice.presentation.ui.screens.ConnectionStatusScreen

/**
 * Navigation component for the PC Voice Controller app.
 */
@Composable
fun PCVoiceNavigation(
    navController: NavHostController = rememberNavController(),
    modifier: Modifier = Modifier
) {
    NavHost(
        navController = navController,
        startDestination = Screen.VoiceCommand.route,
        modifier = modifier
    ) {
        composable(Screen.VoiceCommand.route) {
            VoiceCommandScreen(
                onNavigateToPairing = {
                    navController.navigate(Screen.DevicePairing.route)
                },
                onNavigateToConnectionStatus = {
                    navController.navigate(Screen.ConnectionStatus.route)
                }
            )
        }

        composable(Screen.DevicePairing.route) {
            DevicePairingScreen(
                onNavigateBack = {
                    navController.popBackStack()
                }
            )
        }

        composable(Screen.ConnectionStatus.route) {
            ConnectionStatusScreen(
                onNavigateBack = {
                    navController.popBackStack()
                }
            )
        }
    }
}

/**
 * Screens available in the navigation graph.
 */
sealed class Screen(val route: String) {
    object VoiceCommand : Screen("voice_command")
    object DevicePairing : Screen("device_pairing")
    object ConnectionStatus : Screen("connection_status")
}