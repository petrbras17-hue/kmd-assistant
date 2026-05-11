package ru.slicepizza.restforest.feature.orders

import ru.slicepizza.restforest.core.network.dto.NewOrderDto

/**
 * In-memory event channel for "fresh order from slicepizza.ru landed".
 *
 * Two consumers:
 *  - [NewOrderNotifier] — fires a heads-up Android notification + sound,
 *    works even if the activity is killed (we re-emit when the Service runs).
 *  - PoS Compose dialog (subscribed inside `PosScreen`) — pops a foreground
 *    "Принять / Открыть детали" overlay if the cashier is active.
 *
 * Held as a singleton in Hilt so both Service and ViewModel see the same flow.
 */
data class NewOrderEvent(
    val order: NewOrderDto,
    val receivedAt: Long = System.currentTimeMillis()
) {
    fun shortId(): String = order.id.takeLast(6).uppercase()
    fun totalRubles(): Long = order.totalKopecks / 100L
    fun summaryLine(): String {
        val firstItem = order.items.firstOrNull()
        val rest = (order.items.size - 1).coerceAtLeast(0)
        return when {
            firstItem == null -> "Заказ #${shortId()}"
            rest == 0 -> "${firstItem.qty}× ${firstItem.name}"
            else -> "${firstItem.qty}× ${firstItem.name} +ещё $rest поз."
        }
    }
}
