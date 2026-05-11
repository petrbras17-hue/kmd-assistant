package ru.slicepizza.restforest.feature.stoplist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import ru.slicepizza.restforest.core.database.entity.DishEntity
import ru.slicepizza.restforest.data.repository.BackendRepository
import ru.slicepizza.restforest.data.repository.DishRepository

@HiltViewModel
class StopListViewModel @Inject constructor(
    private val dishes: DishRepository,
    private val backend: BackendRepository
) : ViewModel() {

    val dishesFlow: StateFlow<List<DishEntity>> = dishes.observeAllDishes()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    private val _saving = MutableStateFlow<String?>(null)
    val saving: StateFlow<String?> = _saving.asStateFlow()

    fun toggle(dish: DishEntity, available: Boolean) {
        viewModelScope.launch {
            _saving.value = dish.id
            dishes.setAvailability(dish.id, available)
            // Best-effort backend sync; ignore failure (local stop-list still
            // applied immediately so cashiers can't sell stopped items).
            backend.setAvailability(dish.id, available)
            _saving.value = null
        }
    }
}
