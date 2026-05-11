package ru.slicepizza.restforest.core.database.dao

import androidx.room.Dao
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.entity.CashierEntity

@Dao
interface CashierDao {
    @Query("SELECT COUNT(*) FROM cashier")
    suspend fun count(): Int

    @Query("SELECT * FROM cashier WHERE isActive = 1 ORDER BY name")
    fun observeActive(): Flow<List<CashierEntity>>

    @Query("SELECT * FROM cashier WHERE isActive = 1")
    suspend fun loadAllActive(): List<CashierEntity>

    @Query("SELECT * FROM cashier WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): CashierEntity?

    @Upsert
    suspend fun upsertAll(items: List<CashierEntity>)
}
