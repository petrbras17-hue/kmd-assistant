package ru.slicepizza.restforest.feature.shift

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch
import ru.slicepizza.restforest.core.database.dao.TopDishRow
import ru.slicepizza.restforest.core.database.entity.ShiftEntity
import ru.slicepizza.restforest.core.domain.Money
import ru.slicepizza.restforest.data.repository.BackendRepository
import ru.slicepizza.restforest.data.repository.CashierRepository
import ru.slicepizza.restforest.data.repository.OrderRepository
import ru.slicepizza.restforest.data.repository.PrintQueueRepository
import ru.slicepizza.restforest.data.repository.ShiftRepository
import ru.slicepizza.restforest.feature.printing.EscPosFormatter

data class ShiftUiState(
    val cashierId: String = "",
    val cashierName: String = "",
    val openShift: ShiftEntity? = null,
    val z: ZSnapshot? = null,
    val saving: Boolean = false,
    val zReportPrinted: Boolean = false
)

data class ZSnapshot(
    val revenue: Money,
    val cash: Money,
    val card: Money,
    val sbp: Money,
    val orders: Int,
    val avg: Money,
    val top: List<TopDishRow>
)

sealed interface ShiftEvent {
    data object Opened : ShiftEvent
    data object Closed : ShiftEvent
}

@HiltViewModel
class ShiftViewModel @Inject constructor(
    private val savedState: SavedStateHandle,
    private val shifts: ShiftRepository,
    private val orders: OrderRepository,
    private val cashiers: CashierRepository,
    private val printQueue: PrintQueueRepository,
    private val backend: BackendRepository
) : ViewModel() {

    private val cashierId: String = savedState["cashierId"] ?: ""

    private val _state = MutableStateFlow(ShiftUiState())
    val state: StateFlow<ShiftUiState> = _state.asStateFlow()

    private val _events = Channel<ShiftEvent>(Channel.BUFFERED)
    val events = _events.receiveAsFlow()

    init {
        viewModelScope.launch {
            val c = cashiers.findById(cashierId)
            val open = shifts.openShiftFor(cashierId)
            _state.value = _state.value.copy(
                cashierId = cashierId,
                cashierName = c?.name ?: "—",
                openShift = open
            )
            if (open != null) hydrateZ(open)
        }
    }

    fun openShift(openingRubles: Long) {
        viewModelScope.launch {
            _state.value = _state.value.copy(saving = true)
            val s = shifts.open(cashierId, Money.rubles(openingRubles))
            _state.value = _state.value.copy(openShift = s, saving = false)
            _events.trySend(ShiftEvent.Opened)
        }
    }

    private suspend fun hydrateZ(s: ShiftEntity) {
        val cash = orders.totalsForShift(s.id, "cash")
        val card = orders.totalsForShift(s.id, "card")
        val sbp = orders.totalsForShift(s.id, "sbp")
        val revenue = cash + card + sbp
        val count = orders.countShiftOrders(s.id)
        val avg = if (count > 0) Money(revenue.kopecks / count) else Money.Zero
        val top = orders.topDishes(s.id, 5)
        _state.value = _state.value.copy(
            z = ZSnapshot(revenue, cash, card, sbp, count, avg, top)
        )
    }

    fun closeShift() {
        val s = _state.value.openShift ?: return
        val z = _state.value.z ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(saving = true)
            val closed = shifts.close(s.id)
            backend.closeShift() // best-effort

            // Print Z report ticket
            val ticket = EscPosFormatter.formatZReport(
                cashierName = _state.value.cashierName,
                openedAt = s.openedAt,
                closedAt = closed?.closedAt ?: System.currentTimeMillis(),
                revenue = z.revenue,
                cash = z.cash,
                card = z.card,
                sbp = z.sbp,
                orderCount = z.orders,
                avg = z.avg,
                top = z.top.map { it.dishName to it.qty }
            )
            printQueue.enqueueKitchenTicket(orderId = "z-${s.id}", content = ticket)

            _state.value = _state.value.copy(
                saving = false,
                openShift = null,
                zReportPrinted = true
            )
            _events.trySend(ShiftEvent.Closed)
        }
    }
}
