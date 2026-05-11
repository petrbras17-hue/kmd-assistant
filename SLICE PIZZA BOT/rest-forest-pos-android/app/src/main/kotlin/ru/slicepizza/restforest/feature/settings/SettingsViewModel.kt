package ru.slicepizza.restforest.feature.settings

import android.annotation.SuppressLint
import android.app.Application
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.slicepizza.restforest.feature.printing.PrinterConfig
import ru.slicepizza.restforest.feature.printing.PrinterInterface
import ru.slicepizza.restforest.feature.printing.PrinterRepository
import ru.slicepizza.restforest.feature.printing.PrinterSettingsDataStore

data class BondedDevice(val name: String, val address: String)

data class SettingsUiState(
    val interfaceType: PrinterInterface = PrinterInterface.WIFI_TCP,
    val address: String = "",
    val port: Int = PrinterConfig.DEFAULT_TCP_PORT,
    val paperWidthMm: Int = PrinterConfig.DEFAULT_PAPER_WIDTH_MM,
    val bondedDevices: List<BondedDevice> = emptyList(),
    val saving: Boolean = false,
    val testing: Boolean = false,
    val flash: String? = null
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val app: Application,
    private val settings: PrinterSettingsDataStore,
    private val printer: PrinterRepository
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val cfg = settings.config.first()
            _state.value = _state.value.copy(
                interfaceType = cfg.interfaceType,
                address = cfg.address,
                port = cfg.port,
                paperWidthMm = cfg.paperWidthMm,
                bondedDevices = listBondedBluetoothDevices()
            )
        }
    }

    fun selectInterface(iface: PrinterInterface) {
        _state.value = _state.value.copy(interfaceType = iface, flash = null)
        if (iface == PrinterInterface.BLUETOOTH) refreshBluetoothDevices()
    }

    fun setAddress(v: String) {
        _state.value = _state.value.copy(address = v, flash = null)
    }

    fun setPort(v: String) {
        val port = v.toIntOrNull() ?: return
        _state.value = _state.value.copy(port = port, flash = null)
    }

    fun selectBondedDevice(addr: String) {
        _state.value = _state.value.copy(address = addr, flash = null)
    }

    fun refreshBluetoothDevices() {
        _state.value = _state.value.copy(bondedDevices = listBondedBluetoothDevices())
    }

    fun save() {
        val s = _state.value
        viewModelScope.launch {
            _state.value = s.copy(saving = true)
            settings.save(
                PrinterConfig(
                    interfaceType = s.interfaceType,
                    address = s.address.trim(),
                    port = s.port,
                    paperWidthMm = s.paperWidthMm
                )
            )
            _state.value = _state.value.copy(saving = false, flash = "saved")
        }
    }

    fun testPrint() {
        val s = _state.value
        viewModelScope.launch {
            _state.value = s.copy(testing = true)
            val cfg = PrinterConfig(
                interfaceType = s.interfaceType,
                address = s.address.trim(),
                port = s.port,
                paperWidthMm = s.paperWidthMm
            )
            val ts = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale("ru"))
                .format(java.util.Date())
            val payload = buildString {
                appendLine("[C]<font size='big'><b>REST FOREST TEST</b></font>")
                appendLine("[C]Slice Pizza POS")
                appendLine("[C]--------------------------------")
                appendLine("[L]Время:[R]$ts")
                appendLine("[L]Интерфейс:[R]${cfg.interfaceType.name}")
                appendLine("[L]Адрес:[R]${cfg.address.ifBlank { "—" }}")
                appendLine("[C]--------------------------------")
                appendLine("[L]<font size='big'>Маргарита 1×</font>")
                appendLine("[L]")
                appendLine("[L]")
            }
            val result = withContext(Dispatchers.IO) { printer.printWith(cfg, payload) }
            _state.value = _state.value.copy(
                testing = false,
                flash = result.fold(
                    onSuccess = { "test_ok" },
                    onFailure = { "test_fail:${it.message ?: it::class.simpleName}" }
                )
            )
        }
    }

    fun consumeFlash() {
        _state.value = _state.value.copy(flash = null)
    }

    @SuppressLint("MissingPermission")
    private fun listBondedBluetoothDevices(): List<BondedDevice> {
        if (!hasBluetoothPermission()) return emptyList()
        val adapter: BluetoothAdapter? =
            (app.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter
                ?: BluetoothAdapter.getDefaultAdapter()
        return try {
            adapter?.bondedDevices.orEmpty().map { d ->
                BondedDevice(name = d.name ?: d.address, address = d.address)
            }
        } catch (_: SecurityException) {
            emptyList()
        }
    }

    private fun hasBluetoothPermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            ContextCompat.checkSelfPermission(app, android.Manifest.permission.BLUETOOTH_CONNECT) ==
                PackageManager.PERMISSION_GRANTED
        } else {
            true
        }
    }
}
