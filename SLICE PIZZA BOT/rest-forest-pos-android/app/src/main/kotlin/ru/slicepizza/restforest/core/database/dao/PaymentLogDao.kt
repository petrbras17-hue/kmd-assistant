package ru.slicepizza.restforest.core.database.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.entity.PaymentLogEntity

@Dao
interface PaymentLogDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(log: PaymentLogEntity)

    @Query("SELECT * FROM payment_log WHERE orderId = :orderId ORDER BY createdAt DESC")
    fun observeForOrder(orderId: String): Flow<List<PaymentLogEntity>>
}
