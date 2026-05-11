package ru.slicepizza.restforest.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class DashboardResponse(
    @SerialName("revenue_kopecks") val revenueKopecks: Long = 0L,
    @SerialName("orders_count") val ordersCount: Int = 0,
    @SerialName("avg_check_kopecks") val avgCheckKopecks: Long = 0L,
    @SerialName("period") val period: String = "today"
)

@Serializable
data class ProductDto(
    val id: String,
    val name: String,
    @SerialName("price_kopecks") val priceKopecks: Long,
    @SerialName("category_id") val categoryId: String? = null,
    @SerialName("is_available") val isAvailable: Boolean = true
)

@Serializable
data class PrintReceiptRequest(
    @SerialName("order_id") val orderId: String,
    @SerialName("total_kopecks") val totalKopecks: Long,
    @SerialName("payment_method") val paymentMethod: String,
    @SerialName("cashier_id") val cashierId: String,
    val items: List<PrintReceiptItem>
)

@Serializable
data class PrintReceiptItem(
    val name: String,
    val qty: Int,
    @SerialName("price_kopecks") val priceKopecks: Long
)

@Serializable
data class PrintReceiptResponse(
    @SerialName("receipt_id") val receiptId: String,
    val status: String,
    @SerialName("printed_at") val printedAt: String? = null
)

@Serializable
data class ZReportResponse(
    @SerialName("shift_id") val shiftId: String,
    @SerialName("z_number") val zNumber: String? = null,
    val status: String,
    @SerialName("revenue_kopecks") val revenueKopecks: Long
)

@Serializable
data class AvailabilityRequest(
    @SerialName("is_available") val isAvailable: Boolean
)

// ---------------------------------------------------------------------------
// Sprint 14 — realtime polling of new orders from slicepizza.ru site /
// aggregators. Backend agent will expose GET /api/admin/orders/new?since=ISO8601.
// ---------------------------------------------------------------------------

@Serializable
data class NewOrdersResponse(
    val orders: List<NewOrderDto> = emptyList(),
    @SerialName("server_time") val serverTime: String? = null
)

@Serializable
data class NewOrderDto(
    val id: String,
    @SerialName("total_kopecks") val totalKopecks: Long,
    val items: List<NewOrderItemDto> = emptyList(),
    val address: String? = null,
    val phone: String? = null,
    /** "site" | "yandex" | "delivery_club" | "phone" | "walk_in" */
    val channel: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    /** "paid" | "pending" | "preparing" */
    val status: String? = null
)

@Serializable
data class NewOrderItemDto(
    val name: String,
    val qty: Int = 1,
    @SerialName("price_kopecks") val priceKopecks: Long = 0L
)
