package ru.slicepizza.restforest.core.database.entity

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "dish_modifier",
    foreignKeys = [
        ForeignKey(
            entity = DishEntity::class,
            parentColumns = ["id"],
            childColumns = ["dishId"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("dishId")]
)
data class DishModifierEntity(
    @PrimaryKey val id: String,
    val dishId: String,
    val name: String,
    val priceKopecks: Long,
    val isRequired: Boolean,
    val sortOrder: Int,
    val updatedAt: Long
)
