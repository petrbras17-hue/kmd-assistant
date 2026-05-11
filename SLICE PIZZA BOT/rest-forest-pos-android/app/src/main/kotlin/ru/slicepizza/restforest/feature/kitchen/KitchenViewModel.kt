package ru.slicepizza.restforest.feature.kitchen

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import ru.slicepizza.restforest.core.database.entity.OrderEntity
import ru.slicepizza.restforest.core.database.entity.OrderItemEntity
import ru.slicepizza.restforest.data.repository.OrderRepository

data class KitchenCard(
    val order: OrderEntity,
    val items: List<OrderItemEntity>,
    val agedMinutes: Int,
    val status: KitchenStatus
)

enum class KitchenStatus { New, InProgress, Ready }

@HiltViewModel
class KitchenViewModel @Inject constructor(
    private val orders: OrderRepository
) : ViewModel() {

    /** Manual overlay of statuses set by the kitchen staff. Survives ViewModel lifetime only —
     *  Sprint 5 spec persists status into Room once iiko schema settles. */
    private val _statusOverrides = MutableStateFlow<Map<String, KitchenStatus>>(emptyMap())

    private val _cards = MutableStateFlow<List<KitchenCard>>(emptyList())
    val cards: StateFlow<List<KitchenCard>> = _cards.asStateFlow()

    private val _newOrderBeep = MutableStateFlow(0L)
    val newOrderBeep: StateFlow<Long> = _newOrderBeep.asStateFlow()

    init {
        // Show last 2 hours of paid orders not yet marked Ready.
        viewModelScope.launch {
            val since = System.currentTimeMillis() - 2 * 60 * 60 * 1000L
            combine(
                orders.observePaidSince(since),
                _statusOverrides
            ) { list, overrides -> list to overrides }
                .collect { (list, overrides) ->
                    val now = System.currentTimeMillis()
                    val previousIds = _cards.value.map { it.order.id }.toSet()
                    val cards = list.map { o ->
                        val items = orders.itemsFor(o.id)
                        val aged = ((now - o.createdAt) / 60_000L).toInt().coerceAtLeast(0)
                        KitchenCard(
                            order = o,
                            items = items,
                            agedMinutes = aged,
                            status = overrides[o.id] ?: KitchenStatus.New
                        )
                    }.filter { it.status != KitchenStatus.Ready }
                    _cards.value = cards
                    // Beep if any new order appeared.
                    val newIds = cards.map { it.order.id }.toSet() - previousIds
                    if (newIds.isNotEmpty() && previousIds.isNotEmpty()) {
                        _newOrderBeep.value = now
                    }
                }
        }
    }

    fun setStatus(orderId: String, status: KitchenStatus) {
        _statusOverrides.value = _statusOverrides.value + (orderId to status)
    }
}
