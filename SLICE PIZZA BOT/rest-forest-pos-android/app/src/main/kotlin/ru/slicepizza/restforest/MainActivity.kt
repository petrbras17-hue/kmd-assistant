package ru.slicepizza.restforest

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import dagger.hilt.android.AndroidEntryPoint
import ru.slicepizza.restforest.app.RestForestNavHost
import ru.slicepizza.restforest.core.design.RestForestTheme

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        setContent {
            RestForestTheme {
                RestForestNavHost()
            }
        }
    }
}
