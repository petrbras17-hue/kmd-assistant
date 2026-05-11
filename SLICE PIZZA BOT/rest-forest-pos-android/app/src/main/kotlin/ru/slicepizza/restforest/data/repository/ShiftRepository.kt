package ru.slicepizza.restforest.data.repository

import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.dao.ShiftDao
import ru.slicepizza.restforest.core.database.entity.ShiftEntity
import ru.slicepizza.restforest.core.domain.Money

@Singleton
class ShiftRepository @Inject constructor(
    private val dao: ShiftDao,
    private val orders: OrderRepository
) {

    suspend fun openShiftFor(cashierId: String): ShiftEntity? =
        dao.openShiftFor(cashierId)

    fun observeOpenShift(cashierId: String): Flow<ShiftEntity?> =
        dao.observeOpenShift(cashierId)

    suspend fun open(cashierId: String, opening: Money): ShiftEntity {
        // Return existing open shift if any — idempotent open.
        dao.openShiftFor(cashierId)?.let { return it }
        val shift = ShiftEntity(
            id = UUID.randomUUID().toString(),
            cashierId = cashierId,
            openedAt = System.currentTimeMillis(),
            closedAt = null,
            openingAmountKopecks = opening.kopecks,
            closingAmountKopecks = null,
            totalRevenueKopecks = 0L,
            totalCashKopecks = 0L,
            totalCardKopecks = 0L,
            totalSbpKopecks = 0L,
            orderCount = 0
        )
        dao.insert(shift)
        return shift
    }

    suspend fun close(shiftId: String): ShiftEntity? {
        val current = dao.findById(shiftId) ?: return null
        val cash = orders.totalsForShift(shiftId, "cash")
        val card = orders.totalsForShift(shiftId, "card")
        val sbp = orders.totalsForShift(shiftId, "sbp")
        val total = cash + card + sbp
        val count = orders.countShiftOrders(shiftId)
        val closed = current.copy(
            closedAt = System.currentTimeMillis(),
            closingAmountKopecks = total.kopecks,
            totalRevenueKopecks = total.kopecks,
            totalCashKopecks = cash.kopecks,
            totalCardKopecks = card.kopecks,
            totalSbpKopecks = sbp.kopecks,
            orderCount = count
        )
        dao.update(closed)
        return closed
    }
}
