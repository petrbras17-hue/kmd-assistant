package ru.slicepizza.restforest.data.repository

import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import ru.slicepizza.restforest.core.database.dao.OrderDao
import ru.slicepizza.restforest.core.database.dao.TopDishRow
import ru.slicepizza.restforest.core.database.entity.OrderEntity
import ru.slicepizza.restforest.core.database.entity.OrderItemEntity
import ru.slicepizza.restforest.core.domain.Money
import ru.slicepizza.restforest.feature.cart.CartLine

@Singleton
class OrderRepository @Inject constructor(
    private val dao: OrderDao,
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
}
