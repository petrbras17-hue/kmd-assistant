package ru.slicepizza.restforest

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import dagger.hilt.android.AndroidEntryPoint
import ru.slicepizza.restforest.app.RestForestNavHost
import ru.slicepizza.restforest.core.design.RestForestTheme

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    /**
     * Sprint 14 — Android 13+ requires runtime POST_NOTIFICATIONS. Without
     * it, the heads-up "🔥 Новый заказ" notifications silently fail.
     * Bluetooth permissions are requested lazily by the Settings screen
     * (only when the cashier actually picks the BT interface).
     */
    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* ignore result — even if denied, in-app dialog still pops */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        maybeRequestPostNotifications()
        setContent {
            RestForestTheme {
                RestForestNavHost()
            }
        }
    }

    private fun maybeRequestPostNotifications() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED
        if (!granted) notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
}
