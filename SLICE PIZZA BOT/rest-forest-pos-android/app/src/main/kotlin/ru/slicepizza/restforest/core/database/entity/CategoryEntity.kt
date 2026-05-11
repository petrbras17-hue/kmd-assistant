package ru.slicepizza.restforest.core.database.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "category")
data class CategoryEntity(
    @PrimaryKey val id: String,
    val name: String,
    val sortOrder: Int,
    /** Material-friendly ARGB int (brand colour). */
    val colorArgb: Int,
    val updatedAt: Long
)
