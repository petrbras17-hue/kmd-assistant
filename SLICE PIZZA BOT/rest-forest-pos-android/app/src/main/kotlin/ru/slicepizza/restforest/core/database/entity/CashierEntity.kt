package ru.slicepizza.restforest.core.database.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "cashier")
data class CashierEntity(
    @PrimaryKey val id: String,
    val name: String,
    /** BCrypt hash of the 4-digit PIN — verified constant-time. */
    val pinHash: String,
    /** "cashier" | "kitchen" | "courier" | "manager" */
    val role: String,
    val isActive: Boolean,
    val updatedAt: Long
)
