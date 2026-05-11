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

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    override fun onCreate() {
        super.onCreate()
        appScope.launch { seeder.seedIfEmpty() }
    }
}
