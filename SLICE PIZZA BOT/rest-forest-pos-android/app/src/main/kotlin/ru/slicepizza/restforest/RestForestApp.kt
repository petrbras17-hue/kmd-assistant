package ru.slicepizza.restforest

import android.app.Application
import android.content.Context
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import io.sentry.Sentry
import io.sentry.android.core.SentryAndroid
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import javax.inject.Inject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import ru.slicepizza.restforest.core.database.seed.DatabaseSeeder
import ru.slicepizza.restforest.core.logging.FileLoggingTree
import ru.slicepizza.restforest.data.inventory.InventorySyncWorker
import ru.slicepizza.restforest.feature.orders.NewOrderNotifier
import timber.log.Timber

/**
 * Application entry point. Hilt graph root + WorkManager Configuration.Provider
 * — WorkManager needs Hilt-aware factory so [PrintQueueWorker] can be
 * @AssistedInject-ed.
 *
 * SAFE-START: every init stage runs inside [runCatching]; failures are written
 * to `<filesDir>/boot_crash.log` so Пётр can grab the file even if the app keeps
 * starting normally. Цель — никогда не позволять одному init-кому положить весь
 * процесс при холодном старте.
 *
 * Note: NewOrdersForegroundService.start() is deliberately NOT called here.
 * Android 12+ throws `ForegroundServiceStartNotAllowedException` if a FGS is
 * started from Application.onCreate before an Activity is visible. The service
 * is started from [MainActivity.onCreate] instead.
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

        runCatching { initLogging() }.onFailure { writeBootError("logging", it) }
        runCatching { initSentryIfConfigured() }.onFailure { writeBootError("sentry", it) }

        runCatching {
            appScope.launch {
                runCatching { seeder.seedIfEmpty() }.onFailure { writeBootError("db_seed", it) }
            }
        }.onFailure { writeBootError("db_seed_launch", it) }

        // Sprint 14 — pre-create notification channels so the first poll-tick
        // can use them without a per-call createChannel.
        runCatching { newOrderNotifier.ensureChannel() }.onFailure { writeBootError("notif_channel", it) }

        // Sprint 16 — periodic 4h inventory sync. Wrapped because WorkManager
        // can fail to initialise on devices where Hilt graph timing is off.
        runCatching {
            InventorySyncWorker.enqueuePeriodic(applicationContext)
            InventorySyncWorker.enqueueOneShot(applicationContext)
        }.onFailure { writeBootError("inventory_sync_enqueue", it) }
    }

    private fun initLogging() {
        if (BuildConfig.DEBUG_MODE) {
            Timber.plant(Timber.DebugTree())
        } else {
            // Persistent file log — admin can export from Settings for diagnostics.
            Timber.plant(FileLoggingTree(applicationContext))
        }
    }

    /**
     * Sentry init guarded against empty / malformed DSN and Sentry SDK errors.
     * If the DSN environment variable wasn't set at build time the call becomes
     * a no-op. Any thrown exception from the Sentry SDK itself is swallowed
     * (boot must never depend on telemetry).
     */
    private fun initSentryIfConfigured() {
        val dsn = (BuildConfig.SENTRY_DSN ?: "").trim()
        if (dsn.isEmpty()) {
            Timber.i("Sentry DSN not set — skipping init")
            return
        }
        // Sanity check — Sentry DSN must look like a URL (https://key@host/path).
        if (!dsn.startsWith("http://") && !dsn.startsWith("https://")) {
            Timber.w("Sentry DSN doesn't look like a URL, skipping init")
            return
        }
        try {
            val env = (BuildConfig.SENTRY_ENVIRONMENT ?: "")
                .ifBlank { if (BuildConfig.DEBUG_MODE) "debug" else "production" }
            SentryAndroid.init(this) { options ->
                options.dsn = dsn
                options.environment = env
                options.release = "ru.slicepizza.restforest@${BuildConfig.VERSION_NAME}+${BuildConfig.VERSION_CODE}"
                // Sprint 40: explicit sampling — errors 100%, traces 10%.
                options.sampleRate = 1.0
                options.tracesSampleRate = 0.1
                options.profilesSampleRate = 0.1
                options.isAnrEnabled = true
                options.anrTimeoutIntervalMillis = 5_000L
                options.isEnableNdk = true
                options.isAttachThreads = true
                options.isAttachStacktrace = true
                options.isEnableAutoSessionTracking = true
                options.isSendDefaultPii = true
                options.isEnableUserInteractionTracing = true
                options.isEnableAutoActivityLifecycleTracing = true
                options.setTag("service", "rest-forest-pos")
                options.setTag("component", "android-app")
                options.beforeSend = io.sentry.SentryOptions.BeforeSendCallback { event, _ ->
                    val msg = event.message?.formatted ?: event.throwable?.message ?: ""
                    if (msg.contains("CancellationException", ignoreCase = true)) null else event
                }
            }
            Sentry.configureScope { scope ->
                scope.setTag("device_model", android.os.Build.MODEL ?: "unknown")
                scope.setTag("android_sdk", android.os.Build.VERSION.SDK_INT.toString())
            }
            Timber.i("Sentry initialized (env=$env)")
            // Sprint 40: smoke-test ping at boot so Пётр видит свежий event в UI
            // после каждого APK launch без необходимости ломать процесс.
            try {
                Sentry.captureMessage(
                    "Slice Pizza Android POS booted (env=$env, version=${BuildConfig.VERSION_NAME})",
                    io.sentry.SentryLevel.INFO
                )
            } catch (e: Throwable) {
                Timber.w(e, "Sentry boot ping failed")
            }
        } catch (e: Throwable) {
            Timber.e(e, "Sentry init failed — continuing without crash reporting")
        }
    }

    /**
     * Writes a single line + full stack to boot_crash.log on external files dir
     * (so it shows up in Android/data/<pkg>/files/ when MTP-mounted). Triple
     * try/catch so the logger itself can never crash the process.
     */
    private fun writeBootError(stage: String, t: Throwable) {
        try {
            val dir: File = try {
                getExternalFilesDir(null) ?: filesDir
            } catch (_: Throwable) {
                filesDir
            }
            try { dir.mkdirs() } catch (_: Throwable) { /* ignore */ }
            val file = File(dir, "boot_crash.log")
            val stamp = try {
                SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US).format(Date())
            } catch (_: Throwable) {
                System.currentTimeMillis().toString()
            }
            val sw = StringWriter()
            try {
                PrintWriter(sw).use { pw -> t.printStackTrace(pw) }
            } catch (_: Throwable) { /* swallow */ }
            file.appendText(
                "\n[$stamp] stage=$stage  ${t.javaClass.name}: ${t.message}\n$sw\n"
            )
            try {
                android.util.Log.e(TAG, "boot stage '$stage' failed", t)
            } catch (_: Throwable) { /* swallow */ }
        } catch (_: Throwable) {
            // Last-resort: don't let logging fail the boot.
        }
    }

    companion object {
        private const val TAG = "RestForestApp"

        /**
         * Helper for components that start outside Application.onCreate (e.g.
         * Activities) when they want to log boot-phase issues to the same file.
         */
        fun logBootError(ctx: Context, stage: String, t: Throwable) {
            try {
                val dir: File = try {
                    ctx.getExternalFilesDir(null) ?: ctx.filesDir
                } catch (_: Throwable) {
                    ctx.filesDir
                }
                try { dir.mkdirs() } catch (_: Throwable) {}
                val file = File(dir, "boot_crash.log")
                val stamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US).format(Date())
                val sw = StringWriter()
                PrintWriter(sw).use { pw -> t.printStackTrace(pw) }
                file.appendText(
                    "\n[$stamp] stage=$stage  ${t.javaClass.name}: ${t.message}\n$sw\n"
                )
            } catch (_: Throwable) { /* swallow */ }
        }
    }
}
