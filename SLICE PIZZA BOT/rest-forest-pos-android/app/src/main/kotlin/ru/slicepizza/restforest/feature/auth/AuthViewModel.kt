package ru.slicepizza.restforest.feature.auth

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
import ru.slicepizza.restforest.data.repository.AuthResult
import ru.slicepizza.restforest.data.repository.CashierRepository

data class AuthUiState(
    val pin: String = "",
    val error: Boolean = false,
    val verifying: Boolean = false
)

sealed interface AuthEvent {
    data class SignedIn(val cashierId: String, val role: String) : AuthEvent
}

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val cashiers: CashierRepository
) : ViewModel() {

    private val _state = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = _state.asStateFlow()

    private val _events = Channel<AuthEvent>(Channel.BUFFERED)
    val events = _events.receiveAsFlow()

    fun onDigit(d: Char) {
        if (_state.value.verifying) return
        val cur = _state.value
        if (cur.pin.length >= PIN_LENGTH) return
        val next = cur.pin + d
        _state.value = cur.copy(pin = next, error = false)
        if (next.length == PIN_LENGTH) verify(next)
    }

    fun onBackspace() {
        val cur = _state.value
        if (cur.verifying || cur.pin.isEmpty()) return
        _state.value = cur.copy(pin = cur.pin.dropLast(1), error = false)
    }

    fun onClearError() {
        _state.value = _state.value.copy(error = false, pin = "")
    }

    private fun verify(pin: String) {
        _state.value = _state.value.copy(verifying = true)
        viewModelScope.launch {
            when (val r = cashiers.verifyPin(pin)) {
                is AuthResult.Ok -> {
                    _state.value = AuthUiState()
                    _events.trySend(AuthEvent.SignedIn(r.cashier.id, r.cashier.role))
                }
                AuthResult.UnknownPin -> {
                    _state.value = AuthUiState(pin = pin, error = true, verifying = false)
                }
            }
        }
    }

    companion object {
        const val PIN_LENGTH = CashierRepository.PIN_LENGTH
    }
}
