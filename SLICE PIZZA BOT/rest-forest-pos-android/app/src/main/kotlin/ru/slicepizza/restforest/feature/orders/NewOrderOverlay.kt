package ru.slicepizza.restforest.feature.orders

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import ru.slicepizza.restforest.R

/**
 * Renders a heads-up dialog inside the PoS screen whenever a new order
 * lands. Subscribes to [NewOrderEventBus] via [NewOrderOverlayViewModel] so
 * the same singleton SharedFlow feeds both system notification and on-screen
 * pop-up — that way the cashier never misses an order, regardless of whether
 * the tablet was active, idle or backgrounded.
 */
@Composable
fun NewOrderOverlay(
    onOpenDetails: ((NewOrderEvent) -> Unit)? = null,
    viewModel: NewOrderOverlayViewModel = hiltViewModel()
) {
    var current by remember { mutableStateOf<NewOrderEvent?>(null) }

    LaunchedEffect(Unit) {
        viewModel.events.collect { event ->
            current = event
        }
    }

    val event = current ?: return
    AlertDialog(
        onDismissRequest = { current = null },
        title = {
            Text(
                text = stringResource(R.string.new_order_dialog_title, event.shortId()),
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.W700
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    text = stringResource(R.string.new_order_dialog_total, event.totalRubles()),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.W700,
                    color = MaterialTheme.colorScheme.primary
                )
                Spacer(Modifier.height(4.dp))
                event.order.items.take(5).forEach { item ->
                    Text("• ${item.qty}× ${item.name}")
                }
                if (event.order.items.size > 5) {
                    Text("… +${event.order.items.size - 5} ещё")
                }
                event.order.address?.takeIf { it.isNotBlank() }?.let {
                    Spacer(Modifier.height(4.dp))
                    Text("📍 $it", style = MaterialTheme.typography.bodySmall)
                }
                event.order.phone?.takeIf { it.isNotBlank() }?.let {
                    Text("📞 $it", style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            Button(onClick = { current = null }) {
                Text(stringResource(R.string.new_order_dialog_accept))
            }
        },
        dismissButton = {
            if (onOpenDetails != null) {
                TextButton(onClick = {
                    val e = current
                    current = null
                    if (e != null) onOpenDetails(e)
                }) {
                    Text(stringResource(R.string.new_order_dialog_details))
                }
            } else {
                TextButton(onClick = { current = null }) {
                    Text(stringResource(R.string.new_order_dialog_dismiss))
                }
            }
        }
    )
}
