package ru.slicepizza.restforest.feature.pos

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.unit.dp
import ru.slicepizza.restforest.R
import ru.slicepizza.restforest.core.design.SliceColors
import ru.slicepizza.restforest.feature.cart.CartLine

@Composable
fun CartPanel(
    state: PosUiState,
    viewModel: PosViewModel,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier.fillMaxHeight()) {
        Text(
            text = stringResource(R.string.pos_cart_total),
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
            fontWeight = FontWeight.W700
        )
        Spacer(Modifier.height(4.dp))
        OrderTypeRow(selected = state.orderType, onSelect = viewModel::setOrderType)
        Spacer(Modifier.height(8.dp))
        DiscountRow(
            state = state,
            onDiscount = viewModel::applyDiscountAbsolute,
            onPercent = viewModel::applyDiscountPercent,
            onPromo = viewModel::applyPromoCode
        )
        Spacer(Modifier.height(8.dp))

        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
            if (state.cart.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        text = stringResource(R.string.pos_cart_empty),
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.5f)
                    )
                }
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(state.cart, key = { it.key }) { line ->
                        CartLineRow(
                            line = line,
                            onInc = { viewModel.incrementLine(line.key) },
                            onDec = { viewModel.decrementLine(line.key) },
                            onRm = { viewModel.removeLine(line.key) }
                        )
                    }
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        QuickActionsRow(viewModel = viewModel, cartEmpty = state.cart.isEmpty())
        Spacer(Modifier.height(12.dp))
        TotalsBlock(state)
        Spacer(Modifier.height(12.dp))
        PaymentButtons(state, viewModel)
    }
}

@Composable
private fun OrderTypeRow(selected: String, onSelect: (String) -> Unit) {
    val options = listOf(
        "dine_in" to "В зале",
        "takeaway" to "На вынос",
        "delivery" to "Доставка"
    )
    SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
        options.forEachIndexed { i, (key, label) ->
            SegmentedButton(
                selected = selected == key,
                onClick = { onSelect(key) },
                shape = SegmentedButtonDefaults.itemShape(index = i, count = options.size)
            ) { Text(label) }
        }
    }
}

@Composable
private fun DiscountRow(
    state: PosUiState,
    onDiscount: (Long) -> Unit,
    onPercent: (Int) -> Unit,
    onPromo: (String) -> Boolean
) {
    var promoOpen by remember { mutableStateOf(false) }
    var percentOpen by remember { mutableStateOf(false) }
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedButton(onClick = { percentOpen = true }) { Text("Скидка %") }
        OutlinedButton(onClick = { promoOpen = true }) { Text(stringResource(R.string.pos_promo)) }
        if (state.discountKopecks > 0) {
            OutlinedButton(onClick = { onDiscount(0L); }) { Text("Сброс") }
        }
    }
    if (percentOpen) {
        var percent by remember { mutableStateOf("10") }
        AlertDialog(
            onDismissRequest = { percentOpen = false },
            title = { Text("Скидка %") },
            text = {
                OutlinedTextField(
                    value = percent,
                    onValueChange = { percent = it.filter { c -> c.isDigit() }.take(3) },
                    label = { Text("0–100") }
                )
            },
            confirmButton = {
                Button(onClick = {
                    onPercent(percent.toIntOrNull() ?: 0)
                    percentOpen = false
                }) { Text(stringResource(R.string.confirm)) }
            },
            dismissButton = { TextButton(onClick = { percentOpen = false }) { Text(stringResource(R.string.cancel)) } }
        )
    }
    if (promoOpen) {
        var code by remember { mutableStateOf("") }
        var error by remember { mutableStateOf(false) }
        AlertDialog(
            onDismissRequest = { promoOpen = false },
            title = { Text(stringResource(R.string.pos_promo)) },
            text = {
                Column {
                    OutlinedTextField(
                        value = code,
                        onValueChange = { code = it.uppercase(); error = false },
                        label = { Text("SLICE10 / NEWCUST / KO20") }
                    )
                    if (error) {
                        Text("Не найден", color = SliceColors.Pepperoncino)
                    }
                }
            },
            confirmButton = {
                Button(onClick = {
                    if (onPromo(code)) promoOpen = false else error = true
                }) { Text(stringResource(R.string.confirm)) }
            },
            dismissButton = { TextButton(onClick = { promoOpen = false }) { Text(stringResource(R.string.cancel)) } }
        )
    }
}

@Composable
private fun CartLineRow(line: CartLine, onInc: () -> Unit, onDec: () -> Unit, onRm: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = line.dish.name,
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    if (line.modifiers.isNotEmpty()) {
                        Text(
                            text = line.modifiers.joinToString { it.name },
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                        )
                    }
                    Text(
                        text = line.lineTotal.format(),
                        style = MaterialTheme.typography.titleSmall,
                        color = SliceColors.Ember,
                        fontWeight = FontWeight.W600
                    )
                }
                IconButton(onClick = onDec) { Icon(Icons.Filled.Remove, null) }
                Text("${line.qty}", style = MaterialTheme.typography.titleMedium)
                IconButton(onClick = onInc) { Icon(Icons.Filled.Add, null) }
                IconButton(onClick = onRm) {
                    Icon(Icons.Filled.Delete, null, tint = SliceColors.Pepperoncino)
                }
            }
        }
    }
}

@Composable
private fun QuickActionsRow(viewModel: PosViewModel, cartEmpty: Boolean) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        item {
            AssistChip(
                onClick = { viewModel.addQuickService("dish-service-takeaway") },
                label = { Text(stringResource(R.string.qa_takeaway)) }
            )
        }
        item {
            AssistChip(
                onClick = {
                    viewModel.setOrderType("delivery")
                    viewModel.addQuickService("dish-service-takeaway") // 200₽ placeholder; +100 manually
                },
                label = { Text(stringResource(R.string.qa_delivery)) }
            )
        }
        item {
            AssistChip(
                onClick = { viewModel.doubleLastLine() },
                enabled = !cartEmpty,
                label = { Text(stringResource(R.string.qa_double_portion)) }
            )
        }
        item {
            AssistChip(
                onClick = { viewModel.applyDiscountAbsolute(30L * 100L) },
                label = { Text(stringResource(R.string.qa_no_box)) }
            )
        }
        item {
            AssistChip(
                onClick = { viewModel.addQuickService("dish-addon-mozzarella120") },
                label = { Text(stringResource(R.string.qa_extra_cheese)) }
            )
        }
    }
}

@Composable
private fun TotalsBlock(state: PosUiState) {
    Column {
        if (state.discountKopecks > 0) {
            Row {
                Text(stringResource(R.string.pos_discount), modifier = Modifier.weight(1f))
                Text("-${ru.slicepizza.restforest.core.domain.Money(state.discountKopecks).format()}",
                    color = SliceColors.Pepperoncino)
            }
        }
        Row {
            Text(
                text = stringResource(R.string.pos_cart_total),
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.weight(1f),
                fontWeight = FontWeight.W700
            )
            Text(
                text = state.cartTotal.format(),
                style = MaterialTheme.typography.headlineMedium,
                color = SliceColors.Ember,
                fontWeight = FontWeight.W700
            )
        }
    }
}

@Composable
private fun PaymentButtons(state: PosUiState, viewModel: PosViewModel) {
    val enabled = state.cart.isNotEmpty()
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
        Button(
            onClick = { viewModel.openPayment(PaymentSheet.Cash) },
            enabled = enabled,
            modifier = Modifier.weight(1f).height(56.dp),
            colors = ButtonDefaults.buttonColors(containerColor = SliceColors.Basil)
        ) { Text(stringResource(R.string.pay_cash)) }
        Button(
            onClick = { viewModel.openPayment(PaymentSheet.Card) },
            enabled = enabled,
            modifier = Modifier.weight(1f).height(56.dp),
            colors = ButtonDefaults.buttonColors(containerColor = SliceColors.Ember)
        ) { Text(stringResource(R.string.pay_card)) }
        Button(
            onClick = { viewModel.openPayment(PaymentSheet.Sbp) },
            enabled = enabled,
            modifier = Modifier.weight(1f).height(56.dp),
            colors = ButtonDefaults.buttonColors(containerColor = SliceColors.FuchsiaPhysical)
        ) { Text(stringResource(R.string.pay_sbp)) }
    }
}
