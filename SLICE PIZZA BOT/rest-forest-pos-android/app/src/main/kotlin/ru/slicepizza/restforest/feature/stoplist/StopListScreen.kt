package ru.slicepizza.restforest.feature.stoplist

import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import ru.slicepizza.restforest.R
import ru.slicepizza.restforest.core.domain.Money

@Composable
fun StopListScreen(
    onBack: () -> Unit,
    viewModel: StopListViewModel = hiltViewModel()
) {
    val list by viewModel.dishesFlow.collectAsState()
    val saving by viewModel.saving.collectAsState()

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) }
                Text(
                    text = stringResource(R.string.stoplist_title),
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.W700
                )
            }
            Spacer(Modifier.height(8.dp))
            LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(list, key = { it.id }) { dish ->
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = dish.name,
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.W600
                                )
                                Text(Money(dish.priceKopecks).format(),
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                            }
                            Text(
                                if (dish.isAvailable) stringResource(R.string.stoplist_available)
                                else stringResource(R.string.stoplist_stopped)
                            )
                            Spacer(Modifier.height(4.dp))
                            Switch(
                                checked = dish.isAvailable,
                                onCheckedChange = { viewModel.toggle(dish, it) },
                                enabled = saving != dish.id
                            )
                        }
                    }
                }
            }
        }
    }
}
