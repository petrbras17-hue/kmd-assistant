package ru.slicepizza.restforest.feature.kitchen

import android.media.AudioManager
import android.media.ToneGenerator
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import ru.slicepizza.restforest.R
import ru.slicepizza.restforest.core.design.SliceColors

private val ts = SimpleDateFormat("HH:mm", Locale("ru"))

@Composable
fun KitchenScreen(
    onLogout: () -> Unit,
    viewModel: KitchenViewModel = hiltViewModel()
) {
    val cards by viewModel.cards.collectAsState()
    val beep by viewModel.newOrderBeep.collectAsState()

    val tone = remember {
        ToneGenerator(AudioManager.STREAM_NOTIFICATION, 80)
    }
    DisposableEffect(Unit) { onDispose { tone.release() } }
    LaunchedEffect(beep) {
        if (beep > 0L) tone.startTone(ToneGenerator.TONE_PROP_BEEP, 250)
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = stringResource(R.string.kds_title),
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.W700
                )
                Spacer(Modifier.weight(1f))
                IconButton(onClick = onLogout) { Icon(Icons.Filled.Logout, null) }
            }
            Spacer(Modifier.height(8.dp))
            if (cards.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(stringResource(R.string.kds_empty))
                }
            } else {
                LazyVerticalGrid(
                    columns = GridCells.Adaptive(minSize = 260.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(cards, key = { it.order.id }) { card ->
                        KitchenCardView(card, onSetStatus = viewModel::setStatus)
                    }
                }
            }
        }
    }
}

@Composable
private fun KitchenCardView(card: KitchenCard, onSetStatus: (String, KitchenStatus) -> Unit) {
    val tint = when {
        card.agedMinutes >= 10 -> SliceColors.Pepperoncino
        card.agedMinutes >= 5 -> SliceColors.Warning
        else -> SliceColors.Basil
    }
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .clip(CircleShape)
                        .background(tint)
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = "#${card.order.id.take(6).uppercase()}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.W700
                )
                Spacer(Modifier.weight(1f))
                Text(
                    text = ts.format(Date(card.order.createdAt)),
                    style = MaterialTheme.typography.labelMedium
                )
            }
            Text(
                text = "${card.agedMinutes} мин",
                style = MaterialTheme.typography.labelLarge,
                color = tint,
                fontWeight = FontWeight.W600
            )
            HorizontalDivider(modifier = Modifier.padding(vertical = 6.dp))
            card.items.forEach { it ->
                Text(text = "${it.qty}× ${it.dishId}")
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Button(
                    onClick = { onSetStatus(card.order.id, KitchenStatus.InProgress) },
                    colors = ButtonDefaults.buttonColors(containerColor = SliceColors.Saffron),
                    modifier = Modifier.weight(1f)
                ) { Text(stringResource(R.string.kds_action_in_progress)) }
                Button(
                    onClick = { onSetStatus(card.order.id, KitchenStatus.Ready) },
                    colors = ButtonDefaults.buttonColors(containerColor = SliceColors.Basil),
                    modifier = Modifier.weight(1f)
                ) { Text(stringResource(R.string.kds_action_ready)) }
            }
        }
    }
}
