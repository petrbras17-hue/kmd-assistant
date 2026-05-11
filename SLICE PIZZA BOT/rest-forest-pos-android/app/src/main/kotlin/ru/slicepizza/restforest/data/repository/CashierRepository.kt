package ru.slicepizza.restforest.data.repository

import at.favre.lib.crypto.bcrypt.BCrypt
import javax.inject.Inject
import javax.inject.Singleton
import ru.slicepizza.restforest.core.database.dao.CashierDao
import ru.slicepizza.restforest.core.database.entity.CashierEntity

sealed interface AuthResult {
    data class Ok(val cashier: CashierEntity) : AuthResult
    data object UnknownPin : AuthResult
}

@Singleton
class CashierRepository @Inject constructor(
    private val dao: CashierDao
) {
    suspend fun verifyPin(pin: String): AuthResult {
        if (pin.length != PIN_LENGTH) return AuthResult.UnknownPin
        val all = dao.loadAllActive()
        val verifier = BCrypt.verifyer()
        for (c in all) {
            // Constant-time PIN verify per cashier — bcrypt does the heavy
            // lifting; outer loop is short (≤10 cashiers in practice).
            val r = verifier.verify(pin.toCharArray(), c.pinHash)
            if (r.verified) return AuthResult.Ok(c)
        }
        return AuthResult.UnknownPin
    }

    suspend fun findById(id: String): CashierEntity? = dao.findById(id)

    companion object {
        const val PIN_LENGTH = 4
    }
}
