# Sprint 14 — Realtime Order Polling + WiFi/BT Printer Config

**Date:** 2026-05-12
**APK:** `/Users/braslavskii/SLICE PIZZA BOT/rest-forest-pos-android/app/build/outputs/apk/debug/app-debug.apk` (**19 MB**, same envelope as Sprint 3.2 — no bloat from the new dependencies)
**Build:** `BUILD SUCCESSFUL` for both `:app:assembleDebug` and `:app:lintDebug` on Kotlin 2.0.21 / AGP 8.7.3 / JDK 21 / compileSdk 35

---

## 1. What landed

### Realtime new-order notifications (the headline change)
- **`feature/orders/NewOrdersPoller.kt`** — cold Kotlin `Flow` driving a 5 s tick against `GET /api/admin/orders/new?since=…`, with in-memory de-dup of order IDs (up to 500-deep window) and ISO-8601 timestamp tracking.
- **`feature/orders/NewOrdersForegroundService.kt`** — Android `Service` declared as `foregroundServiceType=dataSync` (required on Android 14+) that owns the poller's coroutine and survives screen-off / app-backgrounded. `START_STICKY`, so a low-memory kill auto-restarts. Started eagerly from `RestForestApp.onCreate()`.
- **`feature/orders/NewOrderNotifier.kt`** — three-vector alert: heads-up Android notification on `IMPORTANCE_HIGH` channel (`new_orders`), default ringtone via `RingtoneManager.getDefaultUri(TYPE_NOTIFICATION)`, a fallback `ToneGenerator` beep for muted devices, and a 250-150-250 ms vibration pattern (`VibrationEffect.createWaveform`). A second `LOW`-importance channel `orders_polling` carries the silent persistent foreground notification.
- **`feature/orders/NewOrderEventBus.kt`** — singleton `MutableSharedFlow(replay=1, buffer=16)` so the same event lights up both the system notification AND the on-screen pop-up.
- **`feature/orders/NewOrderOverlay.kt` + `NewOrderOverlayViewModel.kt`** — Compose `AlertDialog` mounted at the bottom of `PosScreen`'s composable tree. Shows `🔥 Новый заказ #XXXXXX · 1880₽`, first 5 items, address/phone, with **«Принять»** and **«Открыть детали»** buttons.
- **Backend contract added** — `BackendApi.getNewOrders(@Query("since"))` + DTOs `NewOrdersResponse`, `NewOrderDto`, `NewOrderItemDto` (matches the spec body). Wrapper `BackendRepository.newOrders(since)` returns `Result<NewOrdersResponse>` so the poller never crashes on a 5xx.
- **Android 13+ runtime permission flow** — `MainActivity` requests `POST_NOTIFICATIONS` on first launch; the notifier still gates the `notify()` call behind a `ContextCompat.checkSelfPermission` so denied users get only the in-app dialog (graceful degrade).

### Printer USB / Wi-Fi / Bluetooth selector
- **`feature/printing/PrinterConfig.kt`** — `data class PrinterConfig(interfaceType, address, port=9100, paperWidthMm=80)` + enum `PrinterInterface { USB, WIFI_TCP, BLUETOOTH }`. Default = `WIFI_TCP` with empty address (Pyotr fills it in after buying the printer).
- **`feature/printing/PrinterSettingsDataStore.kt`** — DataStore Preferences (`printer_settings`) so the wiring survives cashier handovers and APK reinstalls.
- **`feature/printing/PrinterRepository.kt` (rewritten)** — single `print(payload)` facade that dispatches to one of three DantSu connections (`TcpConnection`, `UsbConnection`, `BluetoothConnection`). Honors `paperWidthMm` (80 mm → 32 columns, 58 mm → 24). Permission-gated path on Bluetooth.
- **`feature/settings/SettingsScreen.kt` + `SettingsViewModel.kt`** — new route `settings` (added to `Routes` and `RestForestNavHost`). UI: three FilterChips for interface; IP+port fields for Wi-Fi; paired-devices list with refresh button for Bluetooth; an auto-detect note for USB. Two actions: «Тестовая печать» and «Сохранить». Bluetooth runtime permissions (`BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN`) are requested only when the cashier actually picks BT.

### Plumbing
- `AndroidManifest.xml`: added `VIBRATE`, `FOREGROUND_SERVICE_DATA_SYNC`, `BLUETOOTH_ADMIN`, `BLUETOOTH_SCAN`, `ACCESS_FINE/COARSE_LOCATION` (with `maxSdkVersion=30`, since BT scan on pre-Android-12 needed location), `<service>` entry for `NewOrdersForegroundService`, plus `<uses-feature>` flags for USB host and Bluetooth (both `required=false` so the APK still installs on no-BT tablets).
- `RestForestApp.onCreate()` now eagerly calls `notifier.ensureChannel()` and `NewOrdersForegroundService.start(this)`.
- PoS top bar dropdown gained a **«Настройки»** entry that navigates to the new screen.
- `values/` + `values-ru/` strings: 18 new keys (notification channels, dialog buttons, settings labels).

---

## 2. How Pyotr connects the WiFi printer

1. Plug the printer into the same shop router (Ethernet or Wi-Fi). Read its IP from the self-test ticket — most ESC/POS hardware prints it on power-up when the FEED button is held.
2. On the MatePad: PoS → ⚙️ Menu → **Настройки** → choose **Wi-Fi (TCP)** chip.
3. Enter the IP (e.g. `192.168.1.50`) and leave port `9100` unless the printer manual says otherwise.
4. Tap **«Тестовая печать»** — a `REST FOREST TEST` ticket with timestamp and one «Маргарита 1×» line is sent immediately. A snackbar reports success or the exact error.
5. Tap **«Сохранить»**. From now on every kitchen ticket and Z-report goes over the LAN socket.

If Wi-Fi later misbehaves and Pyotr swaps to a BT-only printer, the flow is identical — pick the **Bluetooth** chip, tap a paired device from the list, save. USB stays as the dev-time fallback.

---

## 3. How the new-order alerts work end-to-end

Backend (other agent's responsibility) exposes `GET /api/admin/orders/new?since=<ISO>` returning `{ orders: [...], server_time: "…" }`. The Android side polls every 5 s from `NewOrdersForegroundService`. Each fresh `NewOrderDto` is:

1. emitted onto `NewOrderEventBus`,
2. wrapped into an Android system notification on the `new_orders` HIGH-importance channel (sound + vibration + heads-up banner),
3. picked up by the in-PoS `NewOrderOverlay` Compose dialog if the cashier has the PoS screen open.

The Sprint 5 KDS beep mechanism is **untouched** — that listens to a Room flow of locally-paid orders, which is a different data path. Telegram chat `-5031424054` is parallel and handled server-side.

---

## 4. APK & verification

- Build: `BUILD SUCCESSFUL in 53 s` cold, then 4 s incremental.
- Lint: `BUILD SUCCESSFUL`, 0 errors, 82 warnings (all pre-existing deprecation notices for `Icons.Filled.ArrowBack` and `BluetoothAdapter.getDefaultAdapter()`).
- Size: 19 MB — under the +1-2 MB budget; the BT branch of the DantSu lib was already in the dex from Sprint 5, so the only net adds are ~30 KB of new Kotlin classes + DataStore code.
- All net-new Kotlin sources: `feature/orders/{NewOrdersPoller,NewOrdersForegroundService,NewOrderNotifier,NewOrderEvent,NewOrderEventBus,NewOrderOverlay,NewOrderOverlayViewModel}.kt`; `feature/printing/{PrinterConfig,PrinterSettingsDataStore}.kt`; `feature/settings/{SettingsScreen,SettingsViewModel}.kt`. 14 existing files edited (manifest, app, nav, network, repository, PoS, strings).

Sprint 14 is ready for Pyotr's MatePad sideload; the only blocker before going live is the backend agent landing the `/api/admin/orders/new` endpoint, which the poller will start consuming the moment it returns 200.
