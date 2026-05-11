package ru.slicepizza.restforest.feature.orders

import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Hot, app-singleton stream of new-order events.
 *
 * Tuning: `replay = 1` so a freshly subscribed Compose UI (e.g. cashier just
 * opened the PoS screen after a backgrounded poll) still sees the latest order
 * one extra time. `extraBufferCapacity = 16` swallows bursts (multiple paid
 * carts arriving in one poll tick) without dropping events.
 */
@Singleton
class NewOrderEventBus @Inject constructor() {

    private val _events = MutableSharedFlow<NewOrderEvent>(
        replay = 1,
        extraBufferCapacity = 16
    )
    val events: SharedFlow<NewOrderEvent> = _events.asSharedFlow()

    fun emit(event: NewOrderEvent) {
        _events.tryEmit(event)
    }
}
