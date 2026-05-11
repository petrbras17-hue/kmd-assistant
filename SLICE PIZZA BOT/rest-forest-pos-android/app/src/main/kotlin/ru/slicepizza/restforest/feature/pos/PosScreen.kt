package ru.slicepizza.restforest.feature.pos

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ElevatedFilterChip
import androidx.compose.material3.FilterChipDefaults
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import ru.slicepizza.restforest.R
import ru.slicepizza.restforest.core.database.entity.CategoryEntity
import ru.slicepizza.restforest.core.database.entity.DishEntity
import ru.slicepizza.restforest.core.database.entity.DishModifierEntity
import ru.slicepizza.restforest.core.design.RestForestTheme
import ru.slicepizza.restforest.core.design.SliceColors
import ru.slicepizza.restforest.core.domain.Money

@Composable
fun PosScreen(
    onLogout: () -> Unit,
    onOpenHistory: (String?) -> Unit,
    onOpenStopList: () -> Unit,
    onOpenCloseShift: () -> Unit,
    onShiftClosed: () -> Unit,
    viewModel: PosViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Row(modifier = Modifier.fillMaxSize()) {
            Column(modifier = Modifier.weight(0.6f).fillMaxHeight().padding(16.dp)) {
                TopBar(
                    cashierName = state.cashierName,
                    onMenu = { /* handled inline */ },
                    onLogout = onLogout,
                    onOpenHistory = { onOpenHistory(state.shiftId) },
                    onOpenStopList = onOpenStopList,
                    onOpenCloseShift = onOpenCloseShift,
                    shiftOpen = state.shiftOpen
                )
                Spacer(Modifier.height(12.dp))
                KpiStrip(state.kpi)
                Spacer(Modifier.height(12.dp))
                SearchBar(state.searchQuery, viewModel::onSearchChange)
                Spacer(Modifier.height(12.dp))
                CategoryStrip(
                    categories = state.categories,
                    selectedId = state.selectedCategoryId,
                    onSelect = viewModel::selectCategory
                )
                Spacer(Modifier.height(12.dp))
                DishGrid(
                    dishes = state.dishes,
                    onTap = viewModel::onDishTap
                )
            }
            HorizontalDivider(
                modifier = Modifier.fillMaxHeight().width(1.dp),
                color = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f)
            )
            CartPanel(
                state = state,
                viewModel = viewModel,
                modifier = Modifier.weight(0.4f).fillMaxHeight().padding(16.dp)
            )
        }
    }

    // Modifier sheet
    state.pendingDish?.let { d ->
        ModifierDialog(
            dish = d,
            modifiers = state.pendingDishModifiers,
            onConfirm = viewModel::confirmPendingDish,
            onDismiss = viewModel::dismissPendingDish
        )
    }

    // Payment sheets
    state.paymentSheet?.let { sheet ->
        PaymentDialog(
            sheet = sheet,
            total = state.cartTotal,
            onConfirm = { cashReceived ->
                val method = when (sheet) {
                    PaymentSheet.Cash -> "cash"
                    PaymentSheet.Card -> "card"
                    PaymentSheet.Sbp -> "sbp"
                }
                viewModel.confirmPayment(method, cashReceived)
            },
            onDismiss = viewModel::dismissPayment
        )
    }

    // Success dialog
    state.lastReceiptId?.let { id ->
        ReceiptSuccessDialog(receiptId = id, onDismiss = viewModel::acknowledgeReceipt)
    }
}

@Composable
private fun TopBar(
    cashierName: String,
    onMenu: () -> Unit,
    onLogout: () -> Unit,
    onOpenHistory: () -> Unit,
    onOpenStopList: () -> Unit,
    onOpenCloseShift: () -> Unit,
    shiftOpen: Boolean
) {
    var expanded by remember { mutableStateOf(false) }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            text = "Slice POS",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
            fontWeight = FontWeight.W700
        )
        Spacer(Modifier.width(12.dp))
        Text(
            text = "· $cashierName",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
        )
        Spacer(Modifier.weight(1f))
        Box {
            IconButton(onClick = { expanded = true }) {
                Icon(Icons.Filled.Menu, contentDescription = null)
            }
            DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.pos_menu_history)) },
                    onClick = { expanded = false; onOpenHistory() }
                )
                if (shiftOpen) {
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.pos_menu_close_shift)) },
                        onClick = { expanded = false; onOpenCloseShift() }
                    )
                }
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.pos_menu_stoplist)) },
                    onClick = { expanded = false; onOpenStopList() }
                )
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.pos_menu_logout)) },
                    onClick = { expanded = false; onLogout() }
                )
            }
        }
    }
}

@Composable
private fun KpiStrip(kpi: KpiSnapshot) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        KpiCard(stringResource(R.string.pos_kpi_revenue), kpi.revenue.format(), Modifier.weight(1f))
        KpiCard(stringResource(R.string.pos_kpi_checks), kpi.ordersCount.toString(), Modifier.weight(1f))
        KpiCard(stringResource(R.string.pos_kpi_avg), kpi.avgCheck.format(), Modifier.weight(1f))
    }
}

@Composable
private fun KpiCard(label: String, value: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.W700
            )
        }
    }
}

@Composable
private fun SearchBar(value: String, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        placeholder = { Text(stringResource(R.string.pos_search_hint)) },
        leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
        trailingIcon = {
            if (value.isNotEmpty()) {
                IconButton(onClick = { onChange("") }) {
                    Icon(Icons.Filled.Close, contentDescription = null)
                }
            }
        },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
}

@Composable
private fun CategoryStrip(
    categories: List<CategoryEntity>,
    selectedId: String?,
    onSelect: (String) -> Unit
) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        items(categories, key = { it.id }) { c ->
            val selected = c.id == selectedId
            ElevatedFilterChip(
                selected = selected,
                onClick = { onSelect(c.id) },
                label = { Text(c.name) },
                colors = FilterChipDefaults.elevatedFilterChipColors(
                    selectedContainerColor = Color(c.colorArgb),
                    selectedLabelColor = SliceColors.Mozzarella
                )
            )
        }
    }
}

@Composable
private fun DishGrid(dishes: List<DishEntity>, onTap: (DishEntity) -> Unit) {
    LazyVerticalGrid(
        columns = GridCells.Adaptive(minSize = 160.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(bottom = 32.dp)
    ) {
        items(dishes, key = { it.id }) { d ->
            DishCell(d, onTap)
        }
    }
}

@Composable
private fun DishCell(dish: DishEntity, onTap: (DishEntity) -> Unit) {
    val available = dish.isAvailable
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .aspectRatio(1.2f)
            .clickable(enabled = available) { onTap(dish) },
        colors = CardDefaults.cardColors(
            containerColor = if (available) MaterialTheme.colorScheme.surface
                             else MaterialTheme.colorScheme.surface.copy(alpha = 0.5f)
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(12.dp),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = dish.name,
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 3
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = Money(dish.priceKopecks).format(),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.W700,
                    color = if (available) SliceColors.Ember else SliceColors.Pepperoncino
                )
                if (!available) {
                    Spacer(Modifier.weight(1f))
                    Text(
                        text = "СТОП",
                        style = MaterialTheme.typography.labelMedium,
                        color = SliceColors.Pepperoncino
                    )
                }
            }
        }
    }
}

@Composable
private fun ModifierDialog(
    dish: DishEntity,
    modifiers: List<DishModifierEntity>,
    onConfirm: (Set<String>) -> Unit,
    onDismiss: () -> Unit
) {
    var selected by remember { mutableStateOf(setOf<String>()) }
    val extraKopecks = modifiers.filter { it.id in selected }.sumOf { it.priceKopecks }
    val total = Money(dish.priceKopecks + extraKopecks)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(dish.name) },
        text = {
            LazyColumn {
                items(modifiers, key = { it.id }) { m ->
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Checkbox(
                            checked = m.id in selected,
                            onCheckedChange = { checked ->
                                selected = if (checked) selected + m.id else selected - m.id
                            }
                        )
                        Text(m.name, modifier = Modifier.weight(1f))
                        Text(Money(m.priceKopecks).format())
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = { onConfirm(selected) }) {
                Text("Добавить · ${total.format()}")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) }
        }
    )
}

@Composable
private fun PaymentDialog(
    sheet: PaymentSheet,
    total: Money,
    onConfirm: (Money?) -> Unit,
    onDismiss: () -> Unit
) {
    when (sheet) {
        PaymentSheet.Cash -> {
            var received by remember { mutableStateOf("") }
            val receivedMoney = received.toLongOrNull()?.let { Money.rubles(it) }
            val change = receivedMoney?.minus(total)?.takeIf { it.kopecks >= 0L }
            AlertDialog(
                onDismissRequest = onDismiss,
                title = { Text(stringResource(R.string.pay_cash)) },
                text = {
                    Column {
                        Text("${stringResource(R.string.pos_cart_total)}: ${total.format()}")
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(
                            value = received,
                            onValueChange = { received = it.filter { c -> c.isDigit() } },
                            label = { Text(stringResource(R.string.pay_received)) },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true
                        )
                        Spacer(Modifier.height(8.dp))
                        Text("${stringResource(R.string.pay_change)}: ${change?.format() ?: "—"}")
                    }
                },
                confirmButton = {
                    Button(
                        enabled = receivedMoney != null && receivedMoney >= total,
                        onClick = { onConfirm(receivedMoney) }
                    ) { Text(stringResource(R.string.confirm)) }
                },
                dismissButton = {
                    TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) }
                }
            )
        }
        PaymentSheet.Card -> AlertDialog(
            onDismissRequest = onDismiss,
            title = { Text(stringResource(R.string.pay_card)) },
            text = {
                Column {
                    Text("${stringResource(R.string.pos_cart_total)}: ${total.format()}")
                    Spacer(Modifier.height(8.dp))
                    Text(stringResource(R.string.pay_card_wait))
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Real ВТБ pinpad lands in Sprint 7 (INPAS NDA).",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )
                }
            },
            confirmButton = {
                Button(onClick = { onConfirm(null) }) { Text(stringResource(R.string.confirm)) }
            },
            dismissButton = {
                TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) }
            }
        )
        PaymentSheet.Sbp -> AlertDialog(
            onDismissRequest = onDismiss,
            title = { Text(stringResource(R.string.pay_sbp)) },
            text = {
                Column {
                    Text("${stringResource(R.string.pos_cart_total)}: ${total.format()}")
                    Spacer(Modifier.height(8.dp))
                    Text(stringResource(R.string.pay_sbp_qr))
                    Spacer(Modifier.height(8.dp))
                    Box(
                        modifier = Modifier
                            .size(180.dp)
                            .background(MaterialTheme.colorScheme.surfaceVariant),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("QR mock", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            },
            confirmButton = {
                Button(onClick = { onConfirm(null) }) { Text(stringResource(R.string.confirm)) }
            },
            dismissButton = {
                TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) }
            }
        )
    }
}

@Composable
private fun ReceiptSuccessDialog(receiptId: String, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.pay_success, receiptId)) },
        confirmButton = {
            Button(onClick = onDismiss) { Text(stringResource(R.string.pay_done)) }
        }
    )
}

@Preview(widthDp = 1280, heightDp = 800)
@Composable
private fun PosPreview() {
    RestForestTheme {
        Surface(color = SliceColors.Dough) {
            Box(modifier = Modifier.padding(16.dp)) {
                Text("POS preview — real screen requires Hilt", color = SliceColors.Char)
            }
        }
    }
}
