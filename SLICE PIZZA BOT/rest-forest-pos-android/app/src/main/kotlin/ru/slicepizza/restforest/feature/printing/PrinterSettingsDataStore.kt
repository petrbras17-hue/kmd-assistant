package ru.slicepizza.restforest.feature.printing

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/**
 * Single-source-of-truth for [PrinterConfig]. Stored in DataStore Preferences
 * so the choice survives reinstalls of the same APK and across cashier shifts.
 *
 * Pyotr configures the printer once via Settings → Printer; every subsequent
 * boot picks up the same wiring without re-prompting.
 */
private val Context.printerSettings by preferencesDataStore(name = "printer_settings")

@Singleton
class PrinterSettingsDataStore @Inject constructor(
    @ApplicationContext private val ctx: Context
) {

    private object Keys {
        val INTERFACE = stringPreferencesKey("printer_interface")
        val ADDRESS = stringPreferencesKey("printer_address")
        val PORT = intPreferencesKey("printer_port")
        val PAPER_WIDTH = intPreferencesKey("printer_paper_width_mm")
    }

    val config: Flow<PrinterConfig> = ctx.printerSettings.data.map { prefs ->
        val rawInterface = prefs[Keys.INTERFACE] ?: PrinterInterface.WIFI_TCP.name
        val iface = runCatching { PrinterInterface.valueOf(rawInterface) }
            .getOrDefault(PrinterInterface.WIFI_TCP)
        PrinterConfig(
            interfaceType = iface,
            address = prefs[Keys.ADDRESS].orEmpty(),
            port = prefs[Keys.PORT] ?: PrinterConfig.DEFAULT_TCP_PORT,
            paperWidthMm = prefs[Keys.PAPER_WIDTH] ?: PrinterConfig.DEFAULT_PAPER_WIDTH_MM
        )
    }

    suspend fun save(cfg: PrinterConfig) {
        ctx.printerSettings.edit { prefs ->
            prefs[Keys.INTERFACE] = cfg.interfaceType.name
            prefs[Keys.ADDRESS] = cfg.address
            prefs[Keys.PORT] = cfg.port
            prefs[Keys.PAPER_WIDTH] = cfg.paperWidthMm
        }
    }
}
