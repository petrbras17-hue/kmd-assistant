package ru.slicepizza.restforest.core.database.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Update
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.entity.OrderEntity
import ru.slicepizza.restforest.core.database.entity.OrderItemEntity

@Dao
interface OrderDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOrder(order: OrderEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertItems(items: List<OrderItemEntity>)

    @Update
    suspend fun updateOrder(order: OrderEntity)

    @Transaction
    suspend fun saveOrder(order: OrderEntity, items: List<OrderItemEntity>) {
        insertOrder(order)
        if (items.isNotEmpty()) insertItems(items)
    }

    @Query("SELECT * FROM tab_order WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): OrderEntity?

    @Query("SELECT * FROM order_item WHERE orderId = :id ORDER BY id")
    suspend fun itemsFor(id: String): List<OrderItemEntity>

    @Query("SELECT * FROM order_item WHERE orderId = :id ORDER BY id")
    fun observeItemsFor(id: String): Flow<List<OrderItemEntity>>

    @Query("SELECT * FROM tab_order WHERE shiftId = :shiftId AND status = 'paid' ORDER BY createdAt DESC")
    fun observeShiftOrders(shiftId: String): Flow<List<OrderEntity>>

    @Query("SELECT * FROM tab_order WHERE status = 'paid' AND createdAt >= :since ORDER BY createdAt DESC LIMIT 200")
    fun observePaidSince(since: Long): Flow<List<OrderEntity>>

    @Query("SELECT COUNT(*) FROM tab_order WHERE status = 'paid' AND createdAt >= :since")
    suspend fun countPaidSince(since: Long): Int

    @Query("SELECT COUNT(*) FROM tab_order WHERE shiftId = :shiftId AND status = 'paid'")
    suspend fun countShiftOrders(shiftId: String): Int

    @Query(
        """
        SELECT IFNULL(SUM(totalKopecks), 0) FROM tab_order
        WHERE status = 'paid' AND createdAt >= :since
        """
    )
    suspend fun revenueSince(since: Long): Long

    @Query(
        """
        SELECT IFNULL(SUM(totalKopecks), 0) FROM tab_order
        WHERE shiftId = :shiftId AND status = 'paid' AND paymentMethod = :method
        """
    )
    suspend fun totalsForShift(shiftId: String, method: String): Long

    @Query(
        """
        SELECT d.id AS dishId, d.name AS dishName, SUM(oi.qty) AS qty,
               SUM(oi.qty * oi.priceAtSaleKopecks) AS totalKopecks
        FROM order_item oi
        JOIN tab_order o ON o.id = oi.orderId
        JOIN dish d ON d.id = oi.dishId
        WHERE o.shiftId = :shiftId AND o.status = 'paid'
        GROUP BY d.id, d.name
        ORDER BY qty DESC
        LIMIT :limit
        """
    )
    suspend fun topDishesForShift(shiftId: String, limit: Int = 5): List<TopDishRow>
}

data class TopDishRow(
    val dishId: String,
    val dishName: String,
    val qty: Int,
    val totalKopecks: Long
)
