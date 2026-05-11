package ru.slicepizza.restforest.core.database.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.entity.PrintJobEntity

@Dao
interface PrintJobDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(job: PrintJobEntity)

    @Query("SELECT * FROM print_job WHERE status = 'queued' ORDER BY createdAt ASC")
    suspend fun queued(): List<PrintJobEntity>

    @Query("SELECT * FROM print_job ORDER BY createdAt DESC LIMIT 50")
    fun observeRecent(): Flow<List<PrintJobEntity>>

    @Query("UPDATE print_job SET status = :status, retries = :retries, error = :error, updatedAt = :ts, printedAt = :printedAt WHERE id = :id")
    suspend fun setStatus(id: String, status: String, retries: Int, error: String?, ts: Long, printedAt: Long?)

    @Query("SELECT * FROM print_job WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): PrintJobEntity?
}
