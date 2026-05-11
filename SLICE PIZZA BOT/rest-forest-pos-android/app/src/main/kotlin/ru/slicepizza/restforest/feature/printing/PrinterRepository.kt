package ru.slicepizza.restforest.feature.printing

import com.dantsu.escposprinter.EscPosPrinter
import com.dantsu.escposprinter.connection.tcp.TcpConnection
import com.dantsu.escposprinter.exceptions.EscPosConnectionException
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Wraps DantSu TcpConnection to a thermal printer. Defaults match the mock
 * server (`tools/mock_kitchen_printer.py` listens on 9100), so devs can run
 * the harness without real hardware.
 *
 * Real device IP / port land in DataStore in Sprint 6 (settings screen).
 */
@Singleton
class PrinterRepository @Inject constructor() {

    @Volatile
    private var host: String = DEFAULT_HOST

    @Volatile
    private var port: Int = DEFAULT_PORT

    fun configure(host: String, port: Int = DEFAULT_PORT) {
        this.host = host
        this.port = port
    }

    /**
     * Returns true on successful print. Caller is expected to enqueue retries
     * via WorkManager — printer hardware is finicky, especially over Wi-Fi.
     */
    fun print(payload: String): Result<Unit> = runCatching {
        val connection = TcpConnection(host, port, 5)
        try {
            val printer = EscPosPrinter(connection, 203, 80f, 32)
            printer.printFormattedTextAndCut(payload)
        } finally {
            try { connection.disconnect() } catch (_: EscPosConnectionException) { /* ignore */ }
        }
    }

    companion object {
        const val DEFAULT_HOST = "192.168.1.250"
        const val DEFAULT_PORT = 9100
    }
}
