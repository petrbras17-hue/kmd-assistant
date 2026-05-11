package ru.slicepizza.restforest.core.database.entity

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "order_item",
    foreignKeys = [
        ForeignKey(
            entity = OrderEntity::class,
            parentColumns = ["id"],
            childColumns = ["orderId"],
            onDelete = ForeignKey.CASCADE
        ),
        ForeignKey(
            entity = DishEntity::class,
            parentColumns = ["id"],
            childColumns = ["dishId"],
            onDelete = ForeignKey.RESTRICT
        )
    ],
    indices = [Index("orderId"), Index("dishId")]
)
data class OrderItemEntity(
    @PrimaryKey val id: String,
    val orderId: String,
    val dishId: String,
    val qty: Int,
    /** JSON-encoded list of selected modifier ids — keeps line idempotent. */
    val modifiersJson: String,
    val priceAtSaleKopecks: Long
)
