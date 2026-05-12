package ru.slicepizza.restforest.core.database.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Persistent override of the kitchen card status for a paid order — survives
 * tablet reboots (Bug #2 fix). Original `_statusOverrides` MutableStateFlow
 * was memory-only, so повар Салом lost the «В работе» list whenever Android
 * killed the process.
 *
 * Compound key (orderId, itemId) lets us scale to per-item statuses later
 * (e.g. courier flow «1 пицца готова, 1 ещё пекут»). For Sprint 14 we use
 * itemId = "*" to mean «весь заказ», which matches current UI behaviour.
 *
 * `startedAt` is when the повар first hit «В работе» — used for SLA timing.
 * `updatedAt` powers the 24-hour TTL cleanup (`statusOverrideDao.cleanupOlderThan`).
 */
@Entity(
    tableName = "kitchen_status_override",
    primaryKeys = ["orderId", "itemId"],
    indices = [Index("updatedAt"), Index("status")]
)
data class KitchenStatusOverrideEntity(
    val orderId: String,
    /** "*" — overall order, or a specific OrderItem.id for granular flows. */
    val itemId: String,
    /** "New" | "InProgress" | "Ready" — mirrors KitchenStatus enum names. */
    val status: String,
    /** Epoch ms when the override moved into InProgress (null until then). */
    val startedAt: Long?,
    val updatedAt: Long
)
