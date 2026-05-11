package ru.slicepizza.restforest.data.repository

import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.dao.CategoryDao
import ru.slicepizza.restforest.core.database.dao.DishDao
import ru.slicepizza.restforest.core.database.entity.CategoryEntity
import ru.slicepizza.restforest.core.database.entity.DishEntity
import ru.slicepizza.restforest.core.database.entity.DishModifierEntity

@Singleton
class DishRepository @Inject constructor(
    private val dishDao: DishDao,
    private val categoryDao: CategoryDao
) {
    fun observeCategories(): Flow<List<CategoryEntity>> = categoryDao.observe()

    fun observeAllDishes(): Flow<List<DishEntity>> = dishDao.observeAll()

    fun observeByCategory(categoryId: String): Flow<List<DishEntity>> =
        dishDao.observeByCategory(categoryId)

    fun search(query: String): Flow<List<DishEntity>> = dishDao.search(query)

    suspend fun findDish(id: String): DishEntity? = dishDao.findById(id)

    suspend fun modifiersFor(dishId: String): List<DishModifierEntity> =
        dishDao.modifiersForOnce(dishId)

    suspend fun setAvailability(id: String, available: Boolean) {
        dishDao.setAvailability(id, available, System.currentTimeMillis())
    }
}
