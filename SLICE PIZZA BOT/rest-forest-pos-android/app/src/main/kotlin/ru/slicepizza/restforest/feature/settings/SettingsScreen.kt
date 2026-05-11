package ru.slicepizza.restforest.feature.settings

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.Usb
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import ru.slicepizza.restforest.R
import ru.slicepizza.restforest.feature.printing.PrinterInterface

@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }

    // Ask for BLUETOOTH_CONNECT once when the user picks the BT interface.
    val btPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ ->
        viewModel.refreshBluetoothDevices()
    }

    LaunchedEffect(state.flash) {
        val msg = state.flash ?: return@LaunchedEffect
        val display = when {
            msg == "saved" -> "Сохранено."
            msg == "test_ok" -> "Тестовый чек отправлен на принтер."
            msg.startsWith("test_fail:") -> "Ошибка печати: ${msg.removePrefix("test_fail:")}"
            else -> msg
        }
        snackbar.showSnackbar(display)
        viewModel.consumeFlash()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = null)
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbar) }
    ) { padding ->
        Surface(
            modifier = Modifier.fillMaxSize().padding(padding),
            color = MaterialTheme.colorScheme.background
        ) {
            Column(
                modifier = Modifier.fillMaxSize().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = stringResource(R.string.settings_section_printer),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.W700
                )

                InterfacePicker(state.interfaceType) { iface ->
                    if (iface == PrinterInterface.BLUETOOTH && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                        btPermissionLauncher.launch(
                            arrayOf(
                                Manifest.permission.BLUETOOTH_CONNECT,
                                Manifest.permission.BLUETOOTH_SCAN
                            )
                        )
                    }
                    viewModel.selectInterface(iface)
                }

                HorizontalDivider()

                when (state.interfaceType) {
                    PrinterInterface.WIFI_TCP -> WifiSection(
                        address = state.address,
                        port = state.port,
                        onAddress = viewModel::setAddress,
                        onPort = viewModel::setPort
                    )
                    PrinterInterface.BLUETOOTH -> BluetoothSection(
                        devices = state.bondedDevices,
                        selectedAddress = state.address,
                        onRefresh = viewModel::refreshBluetoothDevices,
                        onSelect = viewModel::selectBondedDevice
                    )
                    PrinterInterface.USB -> Text(
                        stringResource(R.string.settings_printer_usb_hint),
                        style = MaterialTheme.typography.bodyMedium
                    )
                }

                Spacer(Modifier.height(8.dp))

                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedButton(
                        onClick = viewModel::testPrint,
                        enabled = !state.testing,
                        modifier = Modifier.weight(1f)
                    ) { Text(stringResource(R.string.settings_printer_test)) }
                    Button(
                        onClick = viewModel::save,
                        enabled = !state.saving,
                        modifier = Modifier.weight(1f)
                    ) { Text(stringResource(R.string.settings_printer_save)) }
                }
            }
        }
    }
}

@Composable
private fun InterfacePicker(
    selected: PrinterInterface,
    onSelect: (PrinterInterface) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(stringResource(R.string.settings_printer_interface), style = MaterialTheme.typography.labelLarge)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(
                selected = selected == PrinterInterface.WIFI_TCP,
                onClick = { onSelect(PrinterInterface.WIFI_TCP) },
                label = { Text(stringResource(R.string.settings_printer_iface_wifi)) },
                leadingIcon = { Icon(Icons.Filled.Wifi, contentDescription = null) }
            )
            FilterChip(
                selected = selected == PrinterInterface.BLUETOOTH,
                onClick = { onSelect(PrinterInterface.BLUETOOTH) },
                label = { Text(stringResource(R.string.settings_printer_iface_bluetooth)) },
                leadingIcon = { Icon(Icons.Filled.Bluetooth, contentDescription = null) }
            )
            FilterChip(
                selected = selected == PrinterInterface.USB,
                onClick = { onSelect(PrinterInterface.USB) },
                label = { Text(stringResource(R.string.settings_printer_iface_usb)) },
                leadingIcon = { Icon(Icons.Filled.Usb, contentDescription = null) }
            )
        }
    }
}

@Composable
private fun WifiSection(
    address: String,
    port: Int,
    onAddress: (String) -> Unit,
    onPort: (String) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(
            value = address,
            onValueChange = onAddress,
            label = { Text(stringResource(R.string.settings_printer_ip)) },
            placeholder = { Text("192.168.1.50") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        OutlinedTextField(
            value = port.toString(),
            onValueChange = { onPort(it.filter { c -> c.isDigit() }) },
            label = { Text(stringResource(R.string.settings_printer_port)) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
    }
}

@Composable
private fun BluetoothSection(
    devices: List<BondedDevice>,
    selectedAddress: String,
    onRefresh: () -> Unit,
    onSelect: (String) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = stringResource(R.string.settings_printer_bt_devices),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f)
            )
            OutlinedButton(onClick = onRefresh) {
                Text(stringResource(R.string.settings_printer_bt_scan))
            }
        }
        if (devices.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(stringResource(R.string.settings_printer_bt_empty))
            }
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(6.dp),
                contentPadding = PaddingValues(vertical = 4.dp),
                modifier = Modifier.fillMaxWidth().height(220.dp)
            ) {
                items(devices, key = { it.address }) { d ->
                    val selected = d.address == selectedAddress
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer
                            else MaterialTheme.colorScheme.surface
                        ),
                        modifier = Modifier
                            .fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Filled.Bluetooth, contentDescription = null)
                            Spacer(Modifier.width(12.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(d.name, fontWeight = FontWeight.W600)
                                Text(d.address, style = MaterialTheme.typography.labelMedium)
                            }
                            OutlinedButton(onClick = { onSelect(d.address) }) {
                                Text(if (selected) "✓" else "Выбрать")
                            }
                        }
                    }
                }
            }
        }
    }
}
