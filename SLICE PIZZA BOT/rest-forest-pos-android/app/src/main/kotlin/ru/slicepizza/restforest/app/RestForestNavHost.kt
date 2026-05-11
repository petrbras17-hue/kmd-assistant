package ru.slicepizza.restforest.app

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import ru.slicepizza.restforest.feature.auth.AuthScreen
import ru.slicepizza.restforest.feature.history.OrdersHistoryScreen
import ru.slicepizza.restforest.feature.kitchen.KitchenScreen
import ru.slicepizza.restforest.feature.pos.PosScreen
import ru.slicepizza.restforest.feature.settings.SettingsScreen
import ru.slicepizza.restforest.feature.shift.ShiftCloseScreen
import ru.slicepizza.restforest.feature.shift.ShiftOpenScreen
import ru.slicepizza.restforest.feature.stoplist.StopListScreen

object Routes {
    const val Auth = "auth"
    const val Pos = "pos/{cashierId}"
    const val Kitchen = "kitchen/{cashierId}"
    const val ShiftOpen = "shift-open/{cashierId}"
    const val ShiftClose = "shift-close/{cashierId}"
    const val History = "history?shiftId={shiftId}"
    const val StopList = "stoplist"
    const val Settings = "settings"

    fun pos(cashierId: String) = "pos/$cashierId"
    fun kitchen(cashierId: String) = "kitchen/$cashierId"
    fun shiftOpen(cashierId: String) = "shift-open/$cashierId"
    fun shiftClose(cashierId: String) = "shift-close/$cashierId"
    fun history(shiftId: String?) = "history" + (shiftId?.let { "?shiftId=$it" } ?: "")
}

@Composable
fun RestForestNavHost() {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = Routes.Auth) {
        composable(Routes.Auth) {
            AuthScreen(onSignedIn = { cashierId, role ->
                val target = when (role) {
                    "kitchen" -> Routes.kitchen(cashierId)
                    else -> Routes.pos(cashierId)
                }
                nav.navigate(target) {
                    popUpTo(Routes.Auth) { inclusive = true }
                }
            })
        }
        composable(
            route = Routes.Pos,
            arguments = listOf(navArgument("cashierId") { type = NavType.StringType })
        ) { entry ->
            val cashierId = entry.arguments?.getString("cashierId").orEmpty()
            PosScreen(
                onLogout = {
                    nav.navigate(Routes.Auth) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onOpenHistory = { shiftId -> nav.navigate(Routes.history(shiftId)) },
                onOpenStopList = { nav.navigate(Routes.StopList) },
                onOpenCloseShift = { nav.navigate(Routes.shiftClose(cashierId)) },
                onOpenSettings = { nav.navigate(Routes.Settings) },
                onShiftClosed = { /* unused — handled inside ShiftClose */ }
            )
        }
        composable(
            route = Routes.Kitchen,
            arguments = listOf(navArgument("cashierId") { type = NavType.StringType })
        ) {
            KitchenScreen(
                onLogout = { nav.navigate(Routes.Auth) { popUpTo(0) { inclusive = true } } }
            )
        }
        composable(
            route = Routes.ShiftOpen,
            arguments = listOf(navArgument("cashierId") { type = NavType.StringType })
        ) { entry ->
            val cashierId = entry.arguments?.getString("cashierId").orEmpty()
            ShiftOpenScreen(
                onOpened = { nav.navigate(Routes.pos(cashierId)) { popUpTo(Routes.ShiftOpen) { inclusive = true } } },
                onCancel = { nav.popBackStack() }
            )
        }
        composable(
            route = Routes.ShiftClose,
            arguments = listOf(navArgument("cashierId") { type = NavType.StringType })
        ) {
            ShiftCloseScreen(
                onClosed = { nav.popBackStack() },
                onCancel = { nav.popBackStack() }
            )
        }
        composable(
            route = Routes.History,
            arguments = listOf(navArgument("shiftId") {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            })
        ) {
            OrdersHistoryScreen(onBack = { nav.popBackStack() })
        }
        composable(Routes.StopList) {
            StopListScreen(onBack = { nav.popBackStack() })
        }
        composable(Routes.Settings) {
            SettingsScreen(onBack = { nav.popBackStack() })
        }
    }
}
