package ru.slicepizza.restforest.feature.orders

import android.Manifest
import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.RingtoneManager
import android.media.ToneGenerator
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import ru.slicepizza.restforest.MainActivity
import ru.slicepizza.restforest.R

/**
 * Emits the "🔥 Новый заказ" Android heads-up notification together with a
 * short audible beep and a tactile vibration.
 *
 * Why three distinct channels at once:
 *  - **System notification** (HIGH importance) is mandatory — Oksana might be
 *    on a different app (Telegram, Yandex Eda console) when the order lands.
 *  - **Sound** via [RingtoneManager] default tone (or fallback [ToneGenerator]
 *    on devices where the system tone is muted) cuts through ambient kitchen
 *    noise on the MatePad speaker.
 *  - **Vibration** is a backup for screen-locked / silent-mode situations.
 *
 * The NotificationChannel is created lazily and is idempotent — recreating it
 * with the same id is a no-op on Android, so we can safely call this from the
 * Application onCreate or from the foreground service.
 */
@Singleton
class NewOrderNotifier @Inject constructor(
    @ApplicationContext private val ctx: Context
) {

    fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return

        val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        val audioAttrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION_EVENT)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()

        val channel = NotificationChannel(
            CHANNEL_ID,
            ctx.getString(R.string.notif_channel_new_orders_name),
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = ctx.getString(R.string.notif_channel_new_orders_description)
            enableVibration(true)
            vibrationPattern = longArrayOf(0L, 250L, 150L, 250L)
            enableLights(true)
            setSound(soundUri, audioAttrs)
            setShowBadge(true)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        }
        nm.createNotificationChannel(channel)
    }

    /**
     * Build the persistent notification that the [NewOrdersForegroundService]
     * needs to satisfy `startForeground()`. Quiet by default — the channel
     * is `LOW`, no sound; it just keeps the OS happy.
     */
    fun buildForegroundNotification(): Notification {
        ensureForegroundChannel()
        val pendingIntent = PendingIntent.getActivity(
            ctx,
            0,
            Intent(ctx, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(ctx, FOREGROUND_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(ctx.getString(R.string.notif_foreground_title))
            .setContentText(ctx.getString(R.string.notif_foreground_text))
            .setOngoing(true)
            .setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setContentIntent(pendingIntent)
            .build()
    }

    /** Fires the heads-up notification + beep + vibrate combo. */
    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS gated by hasPostNotificationsPermission()
    fun notify(event: NewOrderEvent) {
        ensureChannel()
        val title = ctx.getString(R.string.notif_new_order_title, event.shortId(), event.totalRubles())
        val text = event.summaryLine()

        val pendingIntent = PendingIntent.getActivity(
            ctx,
            event.order.id.hashCode(),
            Intent(ctx, MainActivity::class.java).addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            ),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val notification = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_chat)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setAutoCancel(true)
            .setDefaults(NotificationCompat.DEFAULT_ALL)
            .setVibrate(longArrayOf(0L, 250L, 150L, 250L))
            .setContentIntent(pendingIntent)
            .build()

        if (hasPostNotificationsPermission()) {
            runCatching {
                NotificationManagerCompat.from(ctx).notify(event.order.id.hashCode(), notification)
            }
        }

        // Belt-and-braces: also kick a tone generator beep in case the default
        // ringtone is muted by user policy (some MDM configs do that).
        runCatching {
            val tg = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 90)
            tg.startTone(ToneGenerator.TONE_PROP_BEEP2, 320)
            // Release after the tone window so resources aren't leaked.
            android.os.Handler(ctx.mainLooper).postDelayed({ tg.release() }, 500)
        }

        // Explicit vibration request (some devices ignore notification vibrate
        // when the screen is on and the app is in foreground).
        runCatching { vibrateShortPulse() }
    }

    private fun hasPostNotificationsPermission(): Boolean {
        // POST_NOTIFICATIONS is a runtime permission only on Android 13+.
        // On older devices the manifest declaration is sufficient.
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED
        } else {
            true
        }
    }

    private fun vibrateShortPulse() {
        val vib = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vm = ctx.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
            vm?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            ctx.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        } ?: return
        if (!vib.hasVibrator()) return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vib.vibrate(VibrationEffect.createWaveform(longArrayOf(0L, 250L, 150L, 250L), -1))
        } else {
            @Suppress("DEPRECATION")
            vib.vibrate(longArrayOf(0L, 250L, 150L, 250L), -1)
        }
    }

    private fun ensureForegroundChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(FOREGROUND_CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            FOREGROUND_CHANNEL_ID,
            ctx.getString(R.string.notif_channel_foreground_name),
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = ctx.getString(R.string.notif_channel_foreground_description)
            setShowBadge(false)
            enableVibration(false)
            setSound(null, null)
        }
        nm.createNotificationChannel(channel)
    }

    companion object {
        const val CHANNEL_ID = "new_orders"
        const val FOREGROUND_CHANNEL_ID = "orders_polling"
        const val FOREGROUND_NOTIFICATION_ID = 4242
    }
}
