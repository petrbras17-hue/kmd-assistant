package ru.slicepizza.restforest.data.repository

import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import ru.slicepizza.restforest.core.database.dao.DishDao
import ru.slicepizza.restforest.core.database.dao.OrderDao
import ru.slicepizza.restforest.core.database.dao.TopDishRow
import ru.slicepizza.restforest.core.database.entity.OrderEntity
import ru.slicepizza.restforest.core.database.entity.OrderItemEntity
import ru.slicepizza.restforest.core.domain.Money
import ru.slicepizza.restforest.feature.cart.CartLine

/**
 * Resolved kitchen line — `dishName` is the human-readable name from the
 * `dish` table (e.g. «Маргарита неаполитанская»). Used to fix Bug #1
 * where KitchenScreen showed raw dishId («dish-pizza-margherita»).
 */
data class KitchenLine(
    val itemId: String,
    val dishId: String,
    val dishName: String,
    val qty: Int
)

@Singleton
class OrderRepository @Inject constructor(
    private val dao: OrderDao,
    private val dishDao: DishDao,
    private val json: Json
) {

    suspend fun recordPaidOrder(
        cashierId: String,
        shiftId: String?,
        lines: List<CartLine>,
        paymentMethod: String,
        discount: Money,
        cashReceived: Money?,
        promoCode: String?,
        orderType: String,
        paymentId: String?
    ): OrderEntity {
        val now = System.currentTimeMillis()
        val total = lines.fold(Money.Zero) { acc, l -> acc + l.lineTotal } - discount
        val order = OrderEntity(
            id = UUID.randomUUID().toString(),
            cashierId = cashierId,
            status = "paid",
            createdAt = now,
            updatedAt = now,
            totalKopecks = total.kopecks.coerceAtLeast(0L),
            paymentMethod = paymentMethod,
            shiftId = shiftId,
            discountKopecks = discount.kopecks,
            cashReceivedKopecks = cashReceived?.kopecks,
            promoCode = promoCode,
            orderType = orderType,
            paymentId = paymentId,
            paymentStatus = if (paymentId != null) "succeeded" else "pending"
        )
        val items = lines.map { l ->
            OrderItemEntity(
                id = UUID.randomUUID().toString(),
                orderId = order.id,
                dishId = l.dish.id,
                qty = l.qty,
                modifiersJson = json.encodeToString(l.modifierIds),
                priceAtSaleKopecks = l.unitPriceWithMods.kopecks
            )
        }
        dao.saveOrder(order, items)
        return order
    }

    fun observeShiftOrders(shiftId: String): Flow<List<OrderEntity>> =
        dao.observeShiftOrders(shiftId)

    fun observePaidSince(since: Long): Flow<List<OrderEntity>> =
        dao.observePaidSince(since)

    suspend fun itemsFor(orderId: String): List<OrderItemEntity> =
        dao.itemsFor(orderId)

    /**
     * Sprint 14.1 (Bug #1 fix) — resolve every OrderItem to a human readable
     * KitchenLine by joining against the `dish` table. If a dish was deleted
     * we fall back to the dishId so the повар at least sees something.
     */
    suspend fun kitchenLinesFor(orderId: String): List<KitchenLine> {
        val items = dao.itemsFor(orderId)
        if (items.isEmpty()) return emptyList()
        return items.map { item ->
            val dish = dishDao.findById(item.dishId)
            KitchenLine(
                itemId = item.id,
                dishId = item.dishId,
                dishName = dish?.name?.takeIf { it.isNotBlank() } ?: item.dishId,
                qty = item.qty
            )
        }
    }

    suspend fun findOrder(orderId: String): OrderEntity? = dao.findById(orderId)

    suspend fun revenueSince(since: Long): Money =
        Money(dao.revenueSince(since))

    suspend fun countPaidSince(since: Long): Int = dao.countPaidSince(since)

    suspend fun countShiftOrders(shiftId: String): Int = dao.countShiftOrders(shiftId)

    suspend fun totalsForShift(shiftId: String, method: String): Money =
        Money(dao.totalsForShift(shiftId, method))

    suspend fun topDishes(shiftId: String, limit: Int = 5): List<TopDishRow> =
        dao.topDishesForShift(shiftId, limit)

    suspend fun setPaymentId(orderId: String, paymentId: String, status: String) {
        val o = dao.findById(orderId) ?: return
        dao.updateOrder(o.copy(paymentId = paymentId, paymentStatus = status, updatedAt = System.currentTimeMillis()))
    }

    /** Sprint 15 — mark an order as refunded (or partial) locally. */
    suspend fun markRefunded(
        orderId: String,
        mode: String,
        refundKopecks: Long
    ) {
        val o = dao.findById(orderId) ?: return
        val newStatus = if (mode == "full") "refunded" else "paid" // partial keeps paid state
        dao.updateOrder(
            o.copy(
                status = newStatus,
                paymentStatus = if (mode == "full") "refunded" else "partial_refund",
                updatedAt = System.currentTimeMillis()
            )
        )
    }
}
