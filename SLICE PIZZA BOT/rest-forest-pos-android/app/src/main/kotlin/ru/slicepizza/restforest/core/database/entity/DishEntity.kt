package ru.slicepizza.restforest.core.database.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "dish",
    foreignKeys = [
        ForeignKey(
            entity = CategoryEntity::class,
            parentColumns = ["id"],
            childColumns = ["categoryId"],
            onDelete = ForeignKey.RESTRICT
        )
    ],
    indices = [Index("categoryId"), Index("kitchen_section")]
)
data class DishEntity(
    @PrimaryKey val id: String,
    val categoryId: String,
    val name: String,
    val priceKopecks: Long,
    val imageUrl: String?,
    val isAvailable: Boolean,
    val sku: String?,
    /**
     * Which printer/section receives the kitchen ticket: "pizza" | "drinks" |
     * "kids" | "addons" | "service" | "none". Tickets for "none" don't route
     * to the kitchen (e.g. takeaway service line is cashier-only).
     */
    @ColumnInfo(name = "kitchen_section")
    val kitchenSection: String,
    val updatedAt: Long
)
