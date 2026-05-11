package ru.slicepizza.restforest.feature.printing

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import com.dantsu.escposprinter.EscPosPrinter
import com.dantsu.escposprinter.connection.bluetooth.BluetoothConnection
import com.dantsu.escposprinter.connection.tcp.TcpConnection
import com.dantsu.escposprinter.connection.usb.UsbConnection
import com.dantsu.escposprinter.exceptions.EscPosConnectionException
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

/**
 * Sprint 14 rewrite: dispatches each print job to USB / WiFi TCP / Bluetooth
 * based on the persisted [PrinterConfig] in [PrinterSettingsDataStore].
 *
 * DantSu's ESCPOS-ThermalPrinter exposes three matching connection types —
 * we plug them in behind a uniform [print] facade so [PrintQueueWorker]
 * (and the Sprint 14 settings "test print" button) don't care about wiring.
 *
 * Resilience contract: every backend ↔ printer hop is wrapped in runCatching
 * so a missing/offline printer never crashes the worker — failures bubble up
 * to WorkManager which retries with exponential backoff.
 */
@Singleton
class PrinterRepository @Inject constructor(
    @ApplicationContext private val ctx: Context,
    private val settings: PrinterSettingsDataStore
) {

    /** Print using the persisted [PrinterConfig]. */
    fun print(payload: String): Result<Unit> = runCatching {
        // The PrintQueueWorker runs on a background CoroutineWorker so blocking
        // here is fine — the worker thread already owns the suspend context.
        val cfg = runBlocking { settings.config.first() }
        printWith(cfg, payload).getOrThrow()
    }

    /** Print with an explicit config — used by the Settings "test print" UI. */
    fun printWith(cfg: PrinterConfig, payload: String): Result<Unit> = runCatching {
        if (!cfg.isConfigured()) {
            error("Printer not configured: interface=${cfg.interfaceType} address='${cfg.address}'")
        }
        when (cfg.interfaceType) {
            PrinterInterface.WIFI_TCP -> printOverTcp(cfg, payload)
            PrinterInterface.USB -> printOverUsb(cfg, payload)
            PrinterInterface.BLUETOOTH -> printOverBluetooth(cfg, payload)
        }
    }

    private fun printOverTcp(cfg: PrinterConfig, payload: String) {
        val connection = TcpConnection(cfg.address, cfg.port, 5)
        try {
            val printer = EscPosPrinter(connection, DPI, cfg.paperWidthMm.toFloat(), columnsFor(cfg.paperWidthMm))
            printer.printFormattedTextAndCut(payload)
        } finally {
            try { connection.disconnect() } catch (_: EscPosConnectionException) { /* ignore */ }
        }
    }

    private fun printOverUsb(cfg: PrinterConfig, payload: String) {
        val usbManager = ctx.getSystemService(Context.USB_SERVICE) as? android.hardware.usb.UsbManager
            ?: error("USB service unavailable on this device")
        // DantSu picks the first USB ESC/POS device automatically.
        val usbDevice = usbManager.deviceList.values.firstOrNull()
            ?: error("No USB device detected — plug the printer cable in")
        val connection = UsbConnection(usbManager, usbDevice)
        try {
            val printer = EscPosPrinter(connection, DPI, cfg.paperWidthMm.toFloat(), columnsFor(cfg.paperWidthMm))
            printer.printFormattedTextAndCut(payload)
        } finally {
            try { connection.disconnect() } catch (_: EscPosConnectionException) { /* ignore */ }
        }
    }

    @SuppressLint("MissingPermission") // permission gate enforced one line up
    private fun printOverBluetooth(cfg: PrinterConfig, payload: String) {
        if (!hasBluetoothConnectPermission()) {
            error("BLUETOOTH_CONNECT permission missing — open Settings and grant it")
        }
        val adapter: BluetoothAdapter? = (ctx.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter
            ?: BluetoothAdapter.getDefaultAdapter()
        val device = adapter?.bondedDevices?.firstOrNull { it.address.equals(cfg.address, ignoreCase = true) }
            ?: error("Bluetooth printer ${cfg.address} not paired — re-pair in Android Settings")
        val connection = BluetoothConnection(device)
        try {
            val printer = EscPosPrinter(connection, DPI, cfg.paperWidthMm.toFloat(), columnsFor(cfg.paperWidthMm))
            printer.printFormattedTextAndCut(payload)
        } finally {
            try { connection.disconnect() } catch (_: EscPosConnectionException) { /* ignore */ }
        }
    }

    private fun hasBluetoothConnectPermission(): Boolean {
        // Android 12+ uses BLUETOOTH_CONNECT runtime permission. Earlier APIs
        // get the legacy BLUETOOTH/BLUETOOTH_ADMIN which are install-time.
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            ContextCompat.checkSelfPermission(ctx, android.Manifest.permission.BLUETOOTH_CONNECT) ==
                PackageManager.PERMISSION_GRANTED
        } else {
            true
        }
    }

    private fun columnsFor(paperWidthMm: Int): Int = when {
        paperWidthMm >= 80 -> 32 // 80mm 203dpi → 32 ESC/POS columns
        paperWidthMm >= 58 -> 24 // 58mm legacy roll
        else -> 24
    }

    companion object {
        /** 203 DPI is the universal Epson TM / Xprinter / GP-58 default. */
        private const val DPI = 203
    }
}
