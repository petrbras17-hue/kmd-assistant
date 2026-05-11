package ru.slicepizza.restforest.feature.printing

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import ru.slicepizza.restforest.core.database.dao.PrintJobDao

/**
 * Drains print_job WHERE status='queued'. Hands each payload to
 * [PrinterRepository.print]; on failure increments retries and reschedules
 * via Result.retry() (WorkManager backs off automatically).
 *
 * The worker is `@HiltWorker` — RestForestApp's HiltWorkerFactory wires the
 * DAO + printer at construction time.
 */
@HiltWorker
class PrintQueueWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val dao: PrintJobDao,
    private val printer: PrinterRepository
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val pending = dao.queued()
        var anyFailed = false
        for (job in pending) {
            val now = System.currentTimeMillis()
            dao.setStatus(job.id, "printing", job.retries, null, now, null)
            val res = printer.print(job.contentBlob)
            res.fold(
                onSuccess = {
                    dao.setStatus(job.id, "done", job.retries, null, now, now)
                },
                onFailure = { ex ->
                    anyFailed = true
                    val retries = job.retries + 1
                    val status = if (retries >= MAX_RETRIES) "failed" else "queued"
                    dao.setStatus(job.id, status, retries, ex.message ?: ex::class.simpleName, now, null)
                }
            )
        }
        return if (anyFailed) Result.retry() else Result.success()
    }

    companion object {
        const val NAME = "rest-forest-print-queue"
        const val MAX_RETRIES = 5
    }
}
