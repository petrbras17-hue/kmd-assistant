package ru.slicepizza.restforest.feature.pos

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.slicepizza.restforest.core.database.entity.CategoryEntity
import ru.slicepizza.restforest.core.database.entity.DishEntity
import ru.slicepizza.restforest.core.database.entity.DishModifierEntity
import ru.slicepizza.restforest.core.domain.Money
import ru.slicepizza.restforest.core.network.dto.PrintReceiptItem
import ru.slicepizza.restforest.data.repository.BackendRepository
import ru.slicepizza.restforest.data.repository.CashierRepository
import ru.slicepizza.restforest.data.repository.DishRepository
import ru.slicepizza.restforest.data.repository.OrderRepository
import ru.slicepizza.restforest.data.repository.PrintQueueRepository
import ru.slicepizza.restforest.data.repository.ShiftRepository
import ru.slicepizza.restforest.feature.cart.CartLine
import ru.slicepizza.restforest.feature.cart.cartLineKey
import ru.slicepizza.restforest.feature.printing.EscPosFormatter

data class KpiSnapshot(
    val revenue: Money = Money.Zero,
    val ordersCount: Int = 0,
    val avgCheck: Money = Money.Zero
)

data class PosUiState(
    val cashierId: String = "",
    val cashierName: String = "",
    val cashierRole: String = "cashier",
    val categories: List<CategoryEntity> = emptyList(),
    val selectedCategoryId: String? = null,
    val dishes: List<DishEntity> = emptyList(),
    val searchQuery: String = "",
    val cart: List<CartLine> = emptyList(),
    val kpi: KpiSnapshot = KpiSnapshot(),
    val shiftOpen: Boolean = false,
    val shiftId: String? = null,
    val discountKopecks: Long = 0L,
    val promoCode: String? = null,
    val orderType: String = "dine_in",
    val pendingDish: DishEntity? = null,
    val pendingDishModifiers: List<DishModifierEntity> = emptyList(),
    val paymentSheet: PaymentSheet? = null,
    val lastReceiptId: String? = null
) {
    val cartTotalBeforeDiscount: Money get() = cart.fold(Money.Zero) { acc, l -> acc + l.lineTotal }
    val cartTotal: Money get() {
        val raw = cartTotalBeforeDiscount - Money(discountKopecks)
        return if (raw.kopecks < 0L) Money.Zero else raw
    }
}

sealed interface PaymentSheet {
    data object Cash : PaymentSheet
    data object Card : PaymentSheet
    data object Sbp : PaymentSheet
}

sealed interface PosEvent {
    data class ShowReceipt(val receiptId: String) : PosEvent
    data class Error(val message: String) : PosEvent
}

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class PosViewModel @Inject constructor(
    private val savedState: SavedStateHandle,
    private val dishes: DishRepository,
    private val orders: OrderRepository,
    private val shifts: ShiftRepository,
    private val cashiers: CashierRepository,
    private val backend: BackendRepository,
    private val printQueue: PrintQueueRepository
) : ViewModel() {

    private val _state = MutableStateFlow(PosUiState())
    val state: StateFlow<PosUiState> = _state.asStateFlow()

    private val _events = Channel<PosEvent>(Channel.BUFFERED)
    val events = _events.receiveAsFlow()

    private val cashierId: String = savedState["cashierId"] ?: ""

    init {
        viewModelScope.launch {
            val c = cashiers.findById(cashierId)
            if (c != null) {
                _state.value = _state.value.copy(
                    cashierId = c.id,
                    cashierName = c.name,
                    cashierRole = c.role
                )
            }
        }
        // Observe an open shift if it exists.
        viewModelScope.launch {
            shifts.observeOpenShift(cashierId).collect { shift ->
                _state.value = _state.value.copy(
                    shiftOpen = shift != null,
                    shiftId = shift?.id
                )
            }
        }
        // Observe categories.
        viewModelScope.launch {
            dishes.observeCategories().collect { cats ->
                val current = _state.value.selectedCategoryId
                _state.value = _state.value.copy(
                    categories = cats,
                    selectedCategoryId = current ?: cats.firstOrNull()?.id
                )
            }
        }
        // Observe dishes — flatMap on (category, query).
        viewModelScope.launch {
            combine(
                _state.map { it.selectedCategoryId }.distinctUntilChanged(),
                _state.map { it.searchQuery }.distinctUntilChanged()
            ) { cat, q -> cat to q }
                .flatMapLatest { (cat, q) ->
                    when {
                        q.isNotBlank() -> dishes.search(q.trim())
                        cat != null -> dishes.observeByCategory(cat)
                        else -> flowOf(emptyList())
                    }
                }
                .collect { list -> _state.value = _state.value.copy(dishes = list) }
        }
        // KPI refresh — fire on construction.
        viewModelScope.launch { refreshKpi() }
    }

    fun selectCategory(id: String) {
        _state.value = _state.value.copy(selectedCategoryId = id, searchQuery = "")
    }

    fun onSearchChange(q: String) {
        _state.value = _state.value.copy(searchQuery = q)
    }

    fun onDishTap(dish: DishEntity) {
        viewModelScope.launch {
            val mods = dishes.modifiersFor(dish.id)
            if (mods.isEmpty()) {
                addToCart(dish, emptyList())
            } else {
                _state.value = _state.value.copy(
                    pendingDish = dish,
                    pendingDishModifiers = mods
                )
            }
        }
    }

    fun confirmPendingDish(selectedModifierIds: Set<String>) {
        val cur = _state.value
        val d = cur.pendingDish ?: return
        val mods = cur.pendingDishModifiers.filter { it.id in selectedModifierIds }
        addToCart(d, mods)
        _state.value = cur.copy(pendingDish = null, pendingDishModifiers = emptyList())
    }

    fun dismissPendingDish() {
        _state.value = _state.value.copy(pendingDish = null, pendingDishModifiers = emptyList())
    }

    private fun addToCart(d: DishEntity, mods: List<DishModifierEntity>) {
        val key = cartLineKey(d.id, mods.map { it.id })
        val cart = _state.value.cart.toMutableList()
        val idx = cart.indexOfFirst { it.key == key }
        if (idx >= 0) {
            cart[idx] = cart[idx].copy(qty = cart[idx].qty + 1)
        } else {
            cart.add(CartLine(key = key, dish = d, modifiers = mods, qty = 1))
        }
        _state.value = _state.value.copy(cart = cart)
    }

    fun incrementLine(key: String) {
        val cart = _state.value.cart.map { if (it.key == key) it.copy(qty = it.qty + 1) else it }
        _state.value = _state.value.copy(cart = cart)
    }

    fun decrementLine(key: String) {
        val cart = _state.value.cart.mapNotNull {
            if (it.key == key) {
                if (it.qty <= 1) null else it.copy(qty = it.qty - 1)
            } else it
        }
        _state.value = _state.value.copy(cart = cart)
    }

    fun removeLine(key: String) {
        _state.value = _state.value.copy(cart = _state.value.cart.filter { it.key != key })
    }

    fun applyDiscountAbsolute(kopecks: Long) {
        _state.value = _state.value.copy(discountKopecks = kopecks.coerceAtLeast(0L))
    }

    fun applyDiscountPercent(percent: Int) {
        val pct = percent.coerceIn(0, 100)
        val cur = _state.value
        val cut = cur.cartTotalBeforeDiscount.kopecks * pct / 100
        _state.value = cur.copy(discountKopecks = cut)
    }

    fun applyPromoCode(code: String): Boolean {
        val pct = when (code.uppercase().trim()) {
            "SLICE10" -> 10
            "NEWCUST" -> 15
            "KO20" -> 20
            else -> 0
        }
        if (pct == 0) return false
        applyDiscountPercent(pct)
        _state.value = _state.value.copy(promoCode = code.uppercase().trim())
        return true
    }

    fun setOrderType(type: String) {
        _state.value = _state.value.copy(orderType = type)
    }

    /** Quick action: +200 ₽ takeaway service line. */
    fun addQuickService(dishId: String) {
        viewModelScope.launch {
            val d = dishes.findDish(dishId) ?: return@launch
            addToCart(d, emptyList())
        }
    }

    fun doubleLastLine() {
        val cart = _state.value.cart
        if (cart.isEmpty()) return
        val last = cart.last()
        _state.value = _state.value.copy(
            cart = cart.dropLast(1) + last.copy(qty = last.qty + last.qty)
        )
    }

    fun openPayment(method: PaymentSheet) {
        if (_state.value.cart.isEmpty()) return
        _state.value = _state.value.copy(paymentSheet = method)
    }

    fun dismissPayment() {
        _state.value = _state.value.copy(paymentSheet = null)
    }

    fun confirmPayment(method: String, cashReceived: Money? = null) {
        val cur = _state.value
        if (cur.cart.isEmpty()) return
        viewModelScope.launch {
            // 1) persist order locally first (cash flow always works even offline)
            val order = orders.recordPaidOrder(
                cashierId = cur.cashierId,
                shiftId = cur.shiftId,
                lines = cur.cart,
                paymentMethod = method,
                discount = Money(cur.discountKopecks),
                cashReceived = cashReceived,
                promoCode = cur.promoCode,
                orderType = cur.orderType,
                paymentId = null
            )

            // 2) fire off LIFE PAY Cloud fiscal print (best-effort)
            val items = cur.cart.map {
                PrintReceiptItem(
                    name = it.dish.name + if (it.modifiers.isNotEmpty()) " (+${it.modifiers.size} мод.)" else "",
                    qty = it.qty,
                    priceKopecks = it.unitPriceWithMods.kopecks
                )
            }
            val receipt = backend.printReceipt(
                orderId = order.id,
                totalKopecks = order.totalKopecks,
                paymentMethod = method,
                cashierId = cur.cashierId,
                items = items
            )
            val receiptId = receipt.getOrNull()?.receiptId ?: "OFFLINE-${order.id.take(6)}"
            orders.setPaymentId(order.id, receiptId, receipt.getOrNull()?.status ?: "offline")

            // 3) enqueue kitchen tickets per section
            val tickets = EscPosFormatter.formatKitchenTickets(
                orderShortId = order.id.take(6).uppercase(),
                cashierName = cur.cashierName,
                lines = cur.cart,
                orderType = cur.orderType
            )
            withContext(Dispatchers.IO) {
                tickets.values.forEach { content ->
                    printQueue.enqueueKitchenTicket(order.id, content)
                }
            }

            // 4) UI state — clear cart, show receipt id
            _state.value = cur.copy(
                cart = emptyList(),
                discountKopecks = 0L,
                promoCode = null,
                orderType = "dine_in",
                paymentSheet = null,
                lastReceiptId = receiptId
            )
            _events.trySend(PosEvent.ShowReceipt(receiptId))
            refreshKpi()
        }
    }

    fun acknowledgeReceipt() {
        _state.value = _state.value.copy(lastReceiptId = null)
    }

    suspend fun refreshKpi() {
        val today0 = startOfTodayMillis()
        val revenue = orders.revenueSince(today0)
        val count = orders.countPaidSince(today0)
        val avg = if (count > 0) Money(revenue.kopecks / count) else Money.Zero
        _state.value = _state.value.copy(kpi = KpiSnapshot(revenue, count, avg))
        // Best-effort backend KPI hydrates with cross-device aggregate.
        viewModelScope.launch {
            backend.dashboard("today").onSuccess { d ->
                _state.value = _state.value.copy(
                    kpi = KpiSnapshot(
                        revenue = Money(maxOf(d.revenueKopecks, revenue.kopecks)),
                        ordersCount = maxOf(d.ordersCount, count),
                        avgCheck = Money(maxOf(d.avgCheckKopecks, avg.kopecks))
                    )
                )
            }
        }
    }

    private fun startOfTodayMillis(): Long {
        val cal = java.util.Calendar.getInstance()
        cal.set(java.util.Calendar.HOUR_OF_DAY, 0)
        cal.set(java.util.Calendar.MINUTE, 0)
        cal.set(java.util.Calendar.SECOND, 0)
        cal.set(java.util.Calendar.MILLISECOND, 0)
        return cal.timeInMillis
    }
}

