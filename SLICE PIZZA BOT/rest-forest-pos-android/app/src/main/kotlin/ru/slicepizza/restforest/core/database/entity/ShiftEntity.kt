package ru.slicepizza.restforest.core.database.entity

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "cashier_shift",
    foreignKeys = [
        ForeignKey(
            entity = CashierEntity::class,
            parentColumns = ["id"],
            childColumns = ["cashierId"],
            onDelete = ForeignKey.RESTRICT
        )
    ],
    indices = [Index("cashierId"), Index("openedAt"), Index("closedAt")]
)
data class ShiftEntity(
    @PrimaryKey val id: String,
    val cashierId: String,
    val openedAt: Long,
    val closedAt: Long?,
    val openingAmountKopecks: Long,
    val closingAmountKopecks: Long?,
    val totalRevenueKopecks: Long,
    val totalCashKopecks: Long,
    val totalCardKopecks: Long,
    val totalSbpKopecks: Long,
    val orderCount: Int
)
