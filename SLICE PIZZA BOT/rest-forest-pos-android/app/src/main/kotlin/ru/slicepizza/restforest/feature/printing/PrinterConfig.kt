package ru.slicepizza.restforest.feature.printing

/**
 * Where the thermal printer is wired in.
 *
 * - [USB]          — direct cable to the tablet; auto-discovery via UsbManager.
 *                    Default before Sprint 14 — kept for backwards compatibility
 *                    with the dev mock printer.
 * - [WIFI_TCP]     — LAN-attached ESC/POS printer reachable over TCP/IP.
 *                    Address example: `192.168.1.50`, default port 9100.
 *                    Recommended for the real shop — no cable on Oksana's table.
 * - [BLUETOOTH]    — paired BT printer (MAC address). Slowest option, used as
 *                    fallback when the printer can't join Wi-Fi.
 */
enum class PrinterInterface {
    USB,
    WIFI_TCP,
    BLUETOOTH
}

/**
 * Persisted printer wiring. Lives in DataStore Preferences via
 * [PrinterSettingsDataStore]; backwards-default = WIFI_TCP with empty address
 * (Pyotr will key in the IP once the actual printer is unboxed).
 */
data class PrinterConfig(
    val interfaceType: PrinterInterface = PrinterInterface.WIFI_TCP,
    val address: String = "",
    val port: Int = DEFAULT_TCP_PORT,
    val paperWidthMm: Int = DEFAULT_PAPER_WIDTH_MM
) {
    fun isConfigured(): Boolean = when (interfaceType) {
        PrinterInterface.USB -> true // device detected via UsbManager at print time
        PrinterInterface.WIFI_TCP -> address.isNotBlank()
        PrinterInterface.BLUETOOTH -> address.isNotBlank()
    }

    companion object {
        const val DEFAULT_TCP_PORT = 9100
        const val DEFAULT_PAPER_WIDTH_MM = 80

        /** Mock TCP server in `tools/mock_kitchen_printer.py` for headless dev. */
        const val DEV_MOCK_HOST = "192.168.1.250"
    }
}
