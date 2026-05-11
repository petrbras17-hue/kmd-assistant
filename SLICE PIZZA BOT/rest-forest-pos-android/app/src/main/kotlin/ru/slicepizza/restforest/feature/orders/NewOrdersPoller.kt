package ru.slicepizza.restforest.feature.orders

import android.util.Log
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import ru.slicepizza.restforest.core.network.dto.NewOrderDto
import ru.slicepizza.restforest.data.repository.BackendRepository

/**
 * Wraps the polling loop into a cold [Flow]. The caller (foreground service)
 * drives lifetime: when the flow is cancelled, polling stops.
 *
 * Design notes:
 *  - 5 s tick. Lower kills battery on a MatePad; higher is too slow for
 *    Oksana to confirm a delivery before the rider asks.
 *  - The poller tracks `since` in-memory — there is no Room cache for it.
 *    On service restart we start at `now()` (potential 5 s gap), which is
 *    fine: the parallel Telegram channel `-5031424054` is the backup.
 *  - We emit raw [NewOrderDto] (not the wrapped event) so this stays a
 *    pure data-producer; the service decides what to do (notify, dedup).
 *  - Errors are swallowed and logged — a transient 502 from the backend
 *    must NOT stop the loop. Persistent failures surface in adb logcat.
 */
@Singleton
class NewOrdersPoller @Inject constructor(
    private val backend: BackendRepository
) {

    private val isoFormatter = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }

    /**
     * Cold flow that emits each new order one-by-one. The poller dedupes
     * already-seen IDs across ticks so we never double-fire on a backend
     * that returns "last 5 orders" instead of strict-since.
     */
    fun stream(intervalMillis: Long = DEFAULT_INTERVAL_MS): Flow<NewOrderDto> = flow {
        val seenIds = HashSet<String>()
        var sinceTimestamp: String? = isoFormatter.format(Date(System.currentTimeMillis() - 30_000L))

        while (true) {
            val result = backend.newOrders(sinceTimestamp)
            result.onSuccess { resp ->
                resp.serverTime?.let { sinceTimestamp = it }
                for (order in resp.orders) {
                    if (seenIds.add(order.id)) {
                        emit(order)
                    }
                }
                // Garbage collect seen ids so they don't grow without bound —
                // 500 IDs ≈ 25 mins at 1 order/sec, plenty of dedup window.
                if (seenIds.size > 500) {
                    val drop = seenIds.size - 500
                    seenIds.iterator().let { it ->
                        var i = 0
                        while (it.hasNext() && i < drop) { it.next(); it.remove(); i++ }
                    }
                }
            }.onFailure { ex ->
                Log.w(TAG, "Poll failed: ${ex.message}")
            }
            delay(intervalMillis)
        }
    }

    companion object {
        private const val TAG = "NewOrdersPoller"
        const val DEFAULT_INTERVAL_MS: Long = 5_000L
    }
}
