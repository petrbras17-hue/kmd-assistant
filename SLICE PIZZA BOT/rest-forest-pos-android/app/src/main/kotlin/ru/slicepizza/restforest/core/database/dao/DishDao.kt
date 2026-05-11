package ru.slicepizza.restforest.core.database.dao

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.entity.DishEntity
import ru.slicepizza.restforest.core.database.entity.DishModifierEntity

@Dao
interface DishDao {
    @Query("SELECT COUNT(*) FROM dish")
    suspend fun count(): Int

    @Query("SELECT * FROM dish ORDER BY name")
    fun observeAll(): Flow<List<DishEntity>>

    @Query("SELECT * FROM dish WHERE categoryId = :categoryId ORDER BY name")
    fun observeByCategory(categoryId: String): Flow<List<DishEntity>>

    @Query("SELECT * FROM dish WHERE name LIKE '%' || :query || '%' COLLATE NOCASE ORDER BY name LIMIT 60")
    fun search(query: String): Flow<List<DishEntity>>

    @Query("SELECT * FROM dish WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): DishEntity?

    @Query("SELECT * FROM dish_modifier WHERE dishId = :dishId ORDER BY sortOrder, name")
    fun modifiersFor(dishId: String): Flow<List<DishModifierEntity>>

    @Query("SELECT * FROM dish_modifier WHERE dishId = :dishId ORDER BY sortOrder, name")
    suspend fun modifiersForOnce(dishId: String): List<DishModifierEntity>

    @Upsert
    suspend fun upsertDishes(items: List<DishEntity>)

    @Upsert
    suspend fun upsertModifiers(items: List<DishModifierEntity>)

    @Query("UPDATE dish SET isAvailable = :available, updatedAt = :ts WHERE id = :id")
    suspend fun setAvailability(id: String, available: Boolean, ts: Long)
}
