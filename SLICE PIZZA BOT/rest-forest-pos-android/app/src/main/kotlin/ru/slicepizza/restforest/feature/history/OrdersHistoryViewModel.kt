package ru.slicepizza.restforest.feature.history

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.launch
import ru.slicepizza.restforest.core.database.entity.OrderEntity
import ru.slicepizza.restforest.core.database.entity.OrderItemEntity
import ru.slicepizza.restforest.data.repository.OrderRepository

data class HistoryUiState(
    val orders: List<OrderEntity> = emptyList(),
    val filter: HistoryFilter = HistoryFilter.Shift,
    val query: String = "",
    val detailsFor: OrderEntity? = null,
    val detailItems: List<OrderItemEntity> = emptyList()
)

enum class HistoryFilter { Shift, Today }

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class OrdersHistoryViewModel @Inject constructor(
    private val savedState: SavedStateHandle,
    private val orders: OrderRepository
) : ViewModel() {

    private val shiftId: String? = savedState["shiftId"]

    private val _state = MutableStateFlow(HistoryUiState())
    val state: StateFlow<HistoryUiState> = _state.asStateFlow()

    init {
        refreshList()
    }

    fun setFilter(f: HistoryFilter) {
        _state.value = _state.value.copy(filter = f)
        refreshList()
    }

    fun setQuery(q: String) {
        _state.value = _state.value.copy(query = q)
    }

    private fun refreshList() {
        viewModelScope.launch {
            val flow = when (_state.value.filter) {
                HistoryFilter.Shift -> if (shiftId != null) orders.observeShiftOrders(shiftId)
                                       else orders.observePaidSince(startOfTodayMillis())
                HistoryFilter.Today -> orders.observePaidSince(startOfTodayMillis())
            }
            flow.collect { list -> _state.value = _state.value.copy(orders = filtered(list)) }
        }
    }

    private fun filtered(list: List<OrderEntity>): List<OrderEntity> {
        val q = _state.value.query.trim()
        if (q.isEmpty()) return list
        val byNum = q.toLongOrNull()
        return list.filter { o ->
            o.id.contains(q, ignoreCase = true) ||
                (byNum != null && o.totalKopecks / 100 == byNum)
        }
    }

    fun openDetails(order: OrderEntity) {
        viewModelScope.launch {
            val items = orders.itemsFor(order.id)
            _state.value = _state.value.copy(detailsFor = order, detailItems = items)
        }
    }

    fun closeDetails() {
        _state.value = _state.value.copy(detailsFor = null, detailItems = emptyList())
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
