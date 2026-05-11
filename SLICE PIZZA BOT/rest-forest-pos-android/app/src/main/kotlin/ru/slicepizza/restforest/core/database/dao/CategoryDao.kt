package ru.slicepizza.restforest.core.database.dao

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.entity.CategoryEntity

@Dao
interface CategoryDao {
    @Query("SELECT COUNT(*) FROM category")
    suspend fun count(): Int

    @Query("SELECT * FROM category ORDER BY sortOrder, name")
    fun observe(): Flow<List<CategoryEntity>>

    @Upsert
    suspend fun upsertAll(items: List<CategoryEntity>)
}
