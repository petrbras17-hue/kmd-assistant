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
import ru.slicepizza.restforest.core.database.dao.KitchenStatusOverrideDao
import ru.slicepizza.restforest.core.database.entity.KitchenStatusOverrideEntity
import ru.slicepizza.restforest.core.database.entity.OrderEntity
import ru.slicepizza.restforest.data.repository.KitchenLine
import ru.slicepizza.restforest.data.repository.OrderRepository
import ru.slicepizza.restforest.feature.printing.PrintQueue

/**
 * Bug #1 fix: each card now carries `lines` with resolved `dishName`, so
 *  повар Салом sees «Маргарита неаполитанская» instead of
 *  «dish-pizza-margherita».
 *
 * Bug #2 fix: `status` is sourced from the persisted
 *  `kitchen_status_override` table (DAO-backed), so the «В работе» list
 *  survives tablet reboots.
 */
data class KitchenCard(
    val order: OrderEntity,
    val lines: List<KitchenLine>,
    val agedMinutes: Int,
    val status: KitchenStatus
)

enum class KitchenStatus { New, InProgress, Ready }

@HiltViewModel
class KitchenViewModel @Inject constructor(
    private val orders: OrderRepository,
    private val overrideDao: KitchenStatusOverrideDao,
    printQueue: PrintQueue
) : ViewModel() {

    /** In-memory mirror of persisted overrides — replayed from `overrideDao`
     *  at init() so повар reboot doesn't wipe «В работе». Writes go through
     *  `setStatus()` which both updates this Flow and persists to Room. */
    private val _statusOverrides = MutableStateFlow<Map<String, KitchenStatus>>(emptyMap())

    private val _cards = MutableStateFlow<List<KitchenCard>>(emptyList())
    val cards: StateFlow<List<KitchenCard>> = _cards.asStateFlow()

    private val _newOrderBeep = MutableStateFlow(0L)
    val newOrderBeep: StateFlow<Long> = _newOrderBeep.asStateFlow()

    /** "N orders in print queue" badge — non-zero means tickets are
     *  retrying or failed (BT printer flaky, paper out, etc.). */
    val pendingPrintCount: StateFlow<Int> = printQueue.observePendingCount()
        .stateIn(viewModelScope, SharingStarted.Eagerly, 0)

    init {
        // Bug #2 fix — restore persisted overrides + cleanup stale 24h+ rows.
        viewModelScope.launch {
            val nowInit = System.currentTimeMillis()
            val cutoff = nowInit - OVERRIDE_TTL_MS
            // Best-effort: failure here is non-fatal (e.g. fresh install).
            runCatching { overrideDao.cleanupOlderThan(cutoff) }
            val rows = runCatching { overrideDao.loadRecent(cutoff) }
                .getOrDefault(emptyList())
            _statusOverrides.value = rows.associate { row ->
                row.orderId to parseStatus(row.status)
            }
        }

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
                        // Bug #1 fix — resolve dish names via JOIN with `dish`.
                        val lines = orders.kitchenLinesFor(o.id)
                        val aged = ((now - o.createdAt) / 60_000L).toInt().coerceAtLeast(0)
                        KitchenCard(
                            order = o,
                            lines = lines,
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

    /**
     * Sets status both in-memory (for fast UI) AND persists to Room (so reboot
     * is survivable — Bug #2 fix). itemId = "*" means «весь заказ»; future
     * granular flows can pass real OrderItem.id.
     */
    fun setStatus(orderId: String, status: KitchenStatus) {
        _statusOverrides.value = _statusOverrides.value + (orderId to status)
        viewModelScope.launch {
            val now = System.currentTimeMillis()
            val prevStarted = runCatching { overrideDao.forOrder(orderId) }
                .getOrDefault(emptyList())
                .firstOrNull()
                ?.startedAt
            val startedAt = when (status) {
                KitchenStatus.InProgress -> prevStarted ?: now
                KitchenStatus.Ready -> prevStarted
                KitchenStatus.New -> null
            }
            runCatching {
                overrideDao.upsert(
                    KitchenStatusOverrideEntity(
                        orderId = orderId,
                        itemId = ALL_ITEMS_KEY,
                        status = status.name,
                        startedAt = startedAt,
                        updatedAt = now
                    )
                )
            }
        }
    }

    companion object {
        /** 24 hours — keep overrides only while they could still affect the
         *  active shift; older rows are 54-FZ-irrelevant. */
        const val OVERRIDE_TTL_MS: Long = 24 * 60 * 60 * 1000L

        /** Wildcard item id meaning «весь заказ». */
        const val ALL_ITEMS_KEY: String = "*"

        internal fun parseStatus(raw: String): KitchenStatus =
            runCatching { KitchenStatus.valueOf(raw) }.getOrDefault(KitchenStatus.New)
    }
}
