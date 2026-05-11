package ru.slicepizza.restforest.data.repository

import javax.inject.Inject
import javax.inject.Singleton
import ru.slicepizza.restforest.core.network.BackendApi
import ru.slicepizza.restforest.core.network.dto.AvailabilityRequest
import ru.slicepizza.restforest.core.network.dto.DashboardResponse
import ru.slicepizza.restforest.core.network.dto.PrintReceiptItem
import ru.slicepizza.restforest.core.network.dto.PrintReceiptRequest
import ru.slicepizza.restforest.core.network.dto.PrintReceiptResponse
import ru.slicepizza.restforest.core.network.dto.ZReportResponse

/**
 * Thin wrapper around [BackendApi] that swallows exceptions and returns
 * Result<T> — the POS stays usable offline. Каждый вызов сетевого API
 * через этот фасад только.
 */
@Singleton
class BackendRepository @Inject constructor(
    private val api: BackendApi
) {
    suspend fun dashboard(period: String = "today"): Result<DashboardResponse> =
        runCatching { api.getDashboard(period) }

    suspend fun printReceipt(
        orderId: String,
        totalKopecks: Long,
        paymentMethod: String,
        cashierId: String,
        items: List<PrintReceiptItem>
    ): Result<PrintReceiptResponse> = runCatching {
        api.printReceipt(
            PrintReceiptRequest(
                orderId = orderId,
                totalKopecks = totalKopecks,
                paymentMethod = paymentMethod,
                cashierId = cashierId,
                items = items
            )
        )
    }

    suspend fun closeShift(): Result<ZReportResponse> =
        runCatching { api.closeShift() }

    suspend fun setAvailability(dishId: String, available: Boolean): Result<Unit> =
        runCatching { api.setAvailability(dishId, AvailabilityRequest(available)) }
}
