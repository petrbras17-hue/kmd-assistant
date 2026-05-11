package ru.slicepizza.restforest.feature.history

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import ru.slicepizza.restforest.R
import androidx.compose.ui.res.stringResource
import ru.slicepizza.restforest.core.database.entity.OrderEntity
import ru.slicepizza.restforest.core.domain.Money

private val ts = SimpleDateFormat("HH:mm dd.MM", Locale("ru"))

@Composable
fun OrdersHistoryScreen(
    onBack: () -> Unit,
    viewModel: OrdersHistoryViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) }
                Text(
                    text = stringResource(R.string.history_title),
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.W700
                )
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(
                    onClick = { viewModel.setFilter(HistoryFilter.Shift) },
                    label = { Text(stringResource(R.string.history_filter_shift)) }
                )
                AssistChip(
                    onClick = { viewModel.setFilter(HistoryFilter.Today) },
                    label = { Text(stringResource(R.string.history_filter_today)) }
                )
            }
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = state.query,
                onValueChange = viewModel::setQuery,
                label = { Text("Поиск по сумме / id") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))

            if (state.orders.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(stringResource(R.string.history_empty))
                }
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(state.orders, key = { it.id }) { o ->
                        OrderRow(o, onClick = { viewModel.openDetails(o) })
                    }
                }
            }
        }
    }

    state.detailsFor?.let { o ->
        AlertDialog(
            onDismissRequest = viewModel::closeDetails,
            title = { Text("Заказ #${o.id.take(6).uppercase()}") },
            text = {
                Column {
                    Text("Время: ${ts.format(Date(o.createdAt))}")
                    Text("Способ: ${o.paymentMethod ?: "—"}")
                    Text("Тип: ${o.orderType}")
                    if (o.discountKopecks > 0)
                        Text("Скидка: -${Money(o.discountKopecks).format()}")
                    if (o.paymentId != null) Text("Чек: ${o.paymentId}")
                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                    state.detailItems.forEach { it ->
                        Row(modifier = Modifier.fillMaxWidth()) {
                            Text("${it.qty}× ${it.dishId}", modifier = Modifier.weight(1f))
                            Text(Money(it.priceAtSaleKopecks * it.qty).format())
                        }
                    }
                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                    Row(modifier = Modifier.fillMaxWidth()) {
                        Text("Итого", fontWeight = FontWeight.W700, modifier = Modifier.weight(1f))
                        Text(Money(o.totalKopecks).format(), fontWeight = FontWeight.W700)
                    }
                }
            },
            confirmButton = {
                Button(onClick = viewModel::closeDetails) { Text(stringResource(R.string.close)) }
            },
            dismissButton = {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { /* refund mock */ }) {
                        Text(stringResource(R.string.history_action_refund))
                    }
                    OutlinedButton(onClick = { /* reprint mock */ }) {
                        Text(stringResource(R.string.history_action_reprint))
                    }
                }
            }
        )
    }
}

@Composable
private fun OrderRow(o: OrderEntity, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable { onClick() },
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text("#${o.id.take(6).uppercase()}", style = MaterialTheme.typography.titleMedium)
                Text(
                    text = "${ts.format(Date(o.createdAt))}  · ${o.paymentMethod ?: "—"}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                )
            }
            Text(
                text = Money(o.totalKopecks).format(),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.W700
            )
        }
    }
}
