package ru.slicepizza.restforest.data.repository

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import ru.slicepizza.restforest.core.database.dao.PrintJobDao
import ru.slicepizza.restforest.core.database.entity.PrintJobEntity
import ru.slicepizza.restforest.feature.printing.PrintQueueWorker

@Singleton
class PrintQueueRepository @Inject constructor(
    @ApplicationContext private val ctx: Context,
    private val dao: PrintJobDao
) {

    suspend fun enqueueKitchenTicket(orderId: String, content: String) {
        val now = System.currentTimeMillis()
        dao.insert(
            PrintJobEntity(
                id = UUID.randomUUID().toString(),
                orderId = orderId,
                status = "queued",
                contentBlob = content,
                retries = 0,
                error = null,
                createdAt = now,
                updatedAt = now,
                printedAt = null
            )
        )
        WorkManager.getInstance(ctx).enqueueUniqueWork(
            PrintQueueWorker.NAME,
            ExistingWorkPolicy.APPEND_OR_REPLACE,
            OneTimeWorkRequestBuilder<PrintQueueWorker>()
                .setConstraints(Constraints.NONE)
                .build()
        )
    }

    fun observeRecent(): Flow<List<PrintJobEntity>> = dao.observeRecent()
}
