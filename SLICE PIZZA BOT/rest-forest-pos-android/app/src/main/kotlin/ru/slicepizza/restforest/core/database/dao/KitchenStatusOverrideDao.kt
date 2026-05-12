package ru.slicepizza.restforest.core.database.dao

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.entity.KitchenStatusOverrideEntity

/**
 * CRUD on persisted kitchen status overrides. Used by KitchenViewModel
 * to restore the «В работе» list after tablet reboot (Bug #2 fix).
 *
 * Cleanup: rows older than 24 hours are deleted by
 * `cleanupOlderThan(System.currentTimeMillis() - 24 * 60 * 60 * 1000)`
 * which the ViewModel calls on init. We do not store history — only
 * current state — because completed orders disappear from KDS anyway.
 */
@Dao
interface KitchenStatusOverrideDao {

    @Upsert
    suspend fun upsert(row: KitchenStatusOverrideEntity)

    @Query(
        "SELECT * FROM kitchen_status_override WHERE updatedAt >= :since ORDER BY updatedAt DESC"
    )
    fun observeRecent(since: Long): Flow<List<KitchenStatusOverrideEntity>>

    @Query(
        "SELECT * FROM kitchen_status_override WHERE updatedAt >= :since"
    )
    suspend fun loadRecent(since: Long): List<KitchenStatusOverrideEntity>

    @Query("SELECT * FROM kitchen_status_override WHERE orderId = :orderId")
    suspend fun forOrder(orderId: String): List<KitchenStatusOverrideEntity>

    @Query("DELETE FROM kitchen_status_override WHERE updatedAt < :before")
    suspend fun cleanupOlderThan(before: Long): Int

    @Query("DELETE FROM kitchen_status_override WHERE orderId = :orderId")
    suspend fun deleteForOrder(orderId: String): Int

    @Query("DELETE FROM kitchen_status_override")
    suspend fun clearAll(): Int
}
