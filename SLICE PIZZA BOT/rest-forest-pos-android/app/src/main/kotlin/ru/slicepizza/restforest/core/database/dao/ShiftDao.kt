package ru.slicepizza.restforest.core.database.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.entity.ShiftEntity

@Dao
interface ShiftDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(shift: ShiftEntity)

    @Update
    suspend fun update(shift: ShiftEntity)

    @Query("SELECT * FROM cashier_shift WHERE cashierId = :cashierId AND closedAt IS NULL LIMIT 1")
    suspend fun openShiftFor(cashierId: String): ShiftEntity?

    @Query("SELECT * FROM cashier_shift WHERE cashierId = :cashierId AND closedAt IS NULL LIMIT 1")
    fun observeOpenShift(cashierId: String): Flow<ShiftEntity?>

    @Query("SELECT * FROM cashier_shift WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): ShiftEntity?
}
