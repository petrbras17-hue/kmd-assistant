package ru.slicepizza.restforest.feature.orders

import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.SharedFlow

/**
 * Tiny ViewModel that re-exposes the singleton [NewOrderEventBus] events to
 * Compose. Hilt manages the scope so the bus survives configuration changes.
 */
@HiltViewModel
class NewOrderOverlayViewModel @Inject constructor(
    bus: NewOrderEventBus
) : ViewModel() {
    val events: SharedFlow<NewOrderEvent> = bus.events
}
