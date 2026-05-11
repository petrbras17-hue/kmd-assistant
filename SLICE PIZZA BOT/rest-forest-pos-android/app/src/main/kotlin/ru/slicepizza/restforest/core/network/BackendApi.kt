package ru.slicepizza.restforest.core.network

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import ru.slicepizza.restforest.core.network.dto.AvailabilityRequest
import ru.slicepizza.restforest.core.network.dto.DashboardResponse
import ru.slicepizza.restforest.core.network.dto.NewOrdersResponse
import ru.slicepizza.restforest.core.network.dto.PrintReceiptRequest
import ru.slicepizza.restforest.core.network.dto.PrintReceiptResponse
import ru.slicepizza.restforest.core.network.dto.ProductDto
import ru.slicepizza.restforest.core.network.dto.ZReportResponse

/**
 * Backend contract — calls endpoints under `https://slicepizza.ru/api/admin/` via Retrofit.
 * Auth via X-Admin-Token header injected by [interceptor.AdminTokenInterceptor].
 *
 * All endpoints are best-effort: if the backend is unreachable, the POS
 * stays usable offline (cart, cash, history, KDS still work). Reports
 * card-flow returns null and PrintReceiptResponse → fallback "OFFLINE".
 */
interface BackendApi {

    @GET("reports/dashboard")
    suspend fun getDashboard(@Query("period") period: String = "today"): DashboardResponse

    @GET("inventory/products")
    suspend fun getProducts(): List<ProductDto>

    // Absolute path — backend route lives under /api/pos, not /api/admin/pos.
    @POST("/api/pos/print-receipt")
    suspend fun printReceipt(@Body req: PrintReceiptRequest): PrintReceiptResponse

    @POST("lifepay/close-shift")
    suspend fun closeShift(): ZReportResponse

    @POST("menu/{dish_id}/availability")
    suspend fun setAvailability(
        @Path("dish_id") id: String,
        @Body req: AvailabilityRequest
    )

    /**
     * Sprint 14 — realtime new-order feed for the POS tablet.
     *
     * `since` is an ISO-8601 timestamp (`2026-05-12T02:00:00Z`) of the last
     * order the device has already processed. Backend returns every paid
     * order created strictly AFTER that moment. Empty `since` → backend
     * defaults to "last 60 seconds".
     *
     * Polled every 5 s from [NewOrdersForegroundService]. Returns 200 even
     * on no-new-orders (orders=[]). 4xx/5xx → swallowed by repository,
     * poller stays alive and tries again next tick.
     */
    @GET("orders/new")
    suspend fun getNewOrders(@Query("since") since: String? = null): NewOrdersResponse
}
