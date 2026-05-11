package ru.slicepizza.restforest

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import ru.slicepizza.restforest.core.database.seed.DatabaseSeeder
import ru.slicepizza.restforest.feature.orders.NewOrderNotifier
import ru.slicepizza.restforest.feature.orders.NewOrdersForegroundService

/**
 * Application entry point. Hilt graph root + WorkManager Configuration.Provider
 * — WorkManager needs Hilt-aware factory so [PrintQueueWorker] can be
 * @AssistedInject-ed.
 *
 * First-run seed (52 menu items + 3 cashiers) runs on an IO scope so the
 * splash screen doesn't block.
 */
@HiltAndroidApp
class RestForestApp : Application(), Configuration.Provider {

    @Inject lateinit var workerFactory: HiltWorkerFactory
    @Inject lateinit var seeder: DatabaseSeeder
    @Inject lateinit var newOrderNotifier: NewOrderNotifier

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    override fun onCreate() {
        super.onCreate()
        appScope.launch { seeder.seedIfEmpty() }

        // Sprint 14 — wake up notification channels eagerly so the first
        // poll-tick can use them without a per-call createChannel call.
        newOrderNotifier.ensureChannel()
        // Start the realtime polling foreground service. It is safe to call
        // even if it's already running — Android collapses duplicates.
        NewOrdersForegroundService.start(this)
    }
}
