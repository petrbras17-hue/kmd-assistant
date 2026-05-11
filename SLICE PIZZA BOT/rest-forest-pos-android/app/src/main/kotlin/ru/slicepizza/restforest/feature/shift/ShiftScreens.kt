package ru.slicepizza.restforest.feature.shift

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import ru.slicepizza.restforest.R
import ru.slicepizza.restforest.core.domain.Money

@Composable
fun ShiftOpenScreen(
    onOpened: () -> Unit,
    onCancel: () -> Unit,
    viewModel: ShiftViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    var amount by remember { mutableStateOf("0") }
    LaunchedEffect(Unit) {
        viewModel.events.collect { ev ->
            if (ev is ShiftEvent.Opened) onOpened()
        }
    }
    if (state.openShift != null) {
        // already opened — bounce out
        LaunchedEffect(Unit) { onOpened() }
    }
    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
            Card {
                Column(modifier = Modifier.padding(24.dp).fillMaxWidth(0.8f)) {
                    Text(
                        text = stringResource(R.string.shift_open_title),
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.W700
                    )
                    Spacer(Modifier.height(16.dp))
                    OutlinedTextField(
                        value = amount,
                        onValueChange = { amount = it.filter { c -> c.isDigit() }.ifEmpty { "0" } },
                        label = { Text(stringResource(R.string.shift_opening_amount)) },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(16.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = onCancel) { Text(stringResource(R.string.cancel)) }
                        Spacer(Modifier.weight(1f))
                        Button(
                            enabled = !state.saving,
                            onClick = { viewModel.openShift(amount.toLongOrNull() ?: 0L) }
                        ) { Text(stringResource(R.string.shift_open_button)) }
                    }
                }
            }
        }
    }
}

@Composable
fun ShiftCloseScreen(
    onClosed: () -> Unit,
    onCancel: () -> Unit,
    viewModel: ShiftViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) {
        viewModel.events.collect { ev -> if (ev is ShiftEvent.Closed) onClosed() }
    }
    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
            Text(
                text = stringResource(R.string.shift_close_title),
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.W700
            )
            Spacer(Modifier.height(16.dp))
            val z = state.z
            if (z == null) {
                Text("Загрузка…")
            } else {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        ZRow(stringResource(R.string.shift_z_revenue), z.revenue.format())
                        ZRow(stringResource(R.string.shift_z_checks), z.orders.toString())
                        ZRow(stringResource(R.string.shift_z_avg), z.avg.format())
                        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                        ZRow(stringResource(R.string.shift_z_cash), z.cash.format())
                        ZRow(stringResource(R.string.shift_z_card), z.card.format())
                        ZRow(stringResource(R.string.shift_z_sbp), z.sbp.format())
                        if (z.top.isNotEmpty()) {
                            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                            Text(stringResource(R.string.shift_z_top), fontWeight = FontWeight.W600)
                            z.top.forEach { row ->
                                ZRow(row.dishName, "×${row.qty}  ${Money(row.totalKopecks).format()}")
                            }
                        }
                    }
                }
            }
            Spacer(Modifier.weight(1f))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onCancel) { Text(stringResource(R.string.cancel)) }
                Spacer(Modifier.weight(1f))
                Button(
                    enabled = !state.saving && state.z != null,
                    onClick = { viewModel.closeShift() }
                ) { Text(stringResource(R.string.shift_z_confirm)) }
            }
        }
    }
}

@Composable
private fun ZRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Text(label, modifier = Modifier.weight(1f))
        Text(value, fontWeight = FontWeight.W600)
    }
}
