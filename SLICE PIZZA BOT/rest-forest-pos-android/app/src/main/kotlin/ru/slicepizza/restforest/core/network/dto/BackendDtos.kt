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
