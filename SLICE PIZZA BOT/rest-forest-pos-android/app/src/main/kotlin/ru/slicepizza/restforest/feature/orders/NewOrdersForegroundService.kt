package ru.slicepizza.restforest.feature.orders

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.launch

/**
 * Runs [NewOrdersPoller] outside of the UI lifecycle so polling continues
 * when the cashier locks the tablet or switches to Telegram.
 *
 * Why a Foreground Service (and NOT WorkManager periodic):
 *   – WorkManager minimum period is 15 minutes; we need 5 seconds.
 *   – A regular background coroutine is killed within ~60 s of activity
 *     finish on Android 12+. Only a foregroundService with a persistent
 *     notification keeps the loop alive on a real MatePad.
 *
 * Why `foregroundServiceType=dataSync`: matches the API contract (Android
 * 14 requires the type to be declared in the manifest AND passed at
 * startForeground time).
 */
@AndroidEntryPoint
class NewOrdersForegroundService : Service() {

    @Inject lateinit var poller: NewOrdersPoller
    @Inject lateinit var notifier: NewOrderNotifier
    @Inject lateinit var eventBus: NewOrderEventBus

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var pollingJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        notifier.ensureChannel()
        promoteToForeground()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (pollingJob?.isActive != true) {
            pollingJob = scope.launch {
                poller.stream().collect { order ->
                    val event = NewOrderEvent(order)
                    eventBus.emit(event)
                    notifier.notify(event)
                }
            }
            Log.i(TAG, "Polling loop started.")
        }
        // START_STICKY → service is restarted by the OS after low-memory kill.
        return START_STICKY
    }

    private fun promoteToForeground() {
        val notification = notifier.buildForegroundNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                NewOrderNotifier.FOREGROUND_NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            startForeground(NewOrderNotifier.FOREGROUND_NOTIFICATION_ID, notification)
        }
    }

    override fun onDestroy() {
        pollingJob?.cancel()
        pollingJob = null
        scope.coroutineContext[Job]?.cancelChildren()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        private const val TAG = "NewOrdersService"

        fun start(ctx: Context) {
            val intent = Intent(ctx, NewOrdersForegroundService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ctx.startForegroundService(intent)
            } else {
                ctx.startService(intent)
            }
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, NewOrdersForegroundService::class.java))
        }
    }
}
