package ru.slicepizza.restforest.core.database.entity

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room rejects `order` as a table name (reserved SQL keyword), so the SQL
 * table is `tab_order` even though the Kotlin class stays `OrderEntity`.
 */
@Entity(
    tableName = "tab_order",
    foreignKeys = [
        ForeignKey(
            entity = CashierEntity::class,
            parentColumns = ["id"],
            childColumns = ["cashierId"],
            onDelete = ForeignKey.RESTRICT
        )
    ],
    indices = [Index("cashierId"), Index("status"), Index("createdAt"), Index("shiftId")]
)
data class OrderEntity(
    @PrimaryKey val id: String,
    val cashierId: String,
    /** "draft" | "paid" | "refunded" | "void" */
    val status: String,
    val createdAt: Long,
    val updatedAt: Long,
    val totalKopecks: Long,
    /** "cash" | "card" | "sbp" — null while draft. */
    val paymentMethod: String?,
    val shiftId: String?,
    val discountKopecks: Long,
    val cashReceivedKopecks: Long?,
    val promoCode: String?,
    /** "dine_in" | "takeaway" | "delivery" */
    val orderType: String,
    /** LIFE PAY receipt id once printReceipt() returns. */
    val paymentId: String?,
    val paymentStatus: String?
)
