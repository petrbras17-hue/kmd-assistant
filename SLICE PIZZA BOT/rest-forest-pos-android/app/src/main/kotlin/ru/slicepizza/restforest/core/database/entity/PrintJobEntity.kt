package ru.slicepizza.restforest.core.database.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "print_job",
    indices = [Index("status"), Index("createdAt"), Index("orderId")]
)
data class PrintJobEntity(
    @PrimaryKey val id: String,
    val orderId: String,
    /** "queued" | "printing" | "done" | "failed" */
    val status: String,
    /** Plain-text ESC/POS payload — formatter renders the bitmap markup. */
    val contentBlob: String,
    val retries: Int,
    val error: String?,
    val createdAt: Long,
    val updatedAt: Long,
    val printedAt: Long?
)
