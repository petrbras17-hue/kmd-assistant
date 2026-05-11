package ru.slicepizza.restforest.feature.auth

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Backspace
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import ru.slicepizza.restforest.R
import ru.slicepizza.restforest.core.design.RestForestTheme
import ru.slicepizza.restforest.core.design.SliceColors

@Composable
fun AuthScreen(
    onSignedIn: (cashierId: String, role: String) -> Unit,
    viewModel: AuthViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.events.collect { ev ->
            if (ev is AuthEvent.SignedIn) onSignedIn(ev.cashierId, ev.role)
        }
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        AuthLayout(
            pin = state.pin,
            error = state.error,
            onDigit = viewModel::onDigit,
            onBackspace = viewModel::onBackspace,
            onClearError = viewModel::onClearError
        )
    }
}

@Composable
private fun AuthLayout(
    pin: String,
    error: Boolean,
    onDigit: (Char) -> Unit,
    onBackspace: () -> Unit,
    onClearError: () -> Unit
) {
    val shake by animateFloatAsState(
        targetValue = if (error) 1f else 0f,
        animationSpec = tween(durationMillis = 320),
        label = "shake"
    )
    val isWide = LocalConfiguration.current.screenWidthDp >= 700

    LaunchedEffect(error) {
        if (error) {
            kotlinx.coroutines.delay(500)
            onClearError()
        }
    }

    Row(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        horizontalArrangement = Arrangement.spacedBy(48.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(
            modifier = Modifier.weight(1f),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = stringResource(R.string.auth_title),
                style = MaterialTheme.typography.displayLarge,
                color = MaterialTheme.colorScheme.onBackground
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = stringResource(R.string.auth_subtitle),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
            )
            Spacer(Modifier.height(32.dp))
            PinDots(
                pin = pin,
                error = error,
                modifier = Modifier.graphicsLayer { translationX = if (error) (8f - 16f * shake) else 0f }
            )
        }
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            val rows = listOf(
                listOf('1', '2', '3'),
                listOf('4', '5', '6'),
                listOf('7', '8', '9'),
                listOf(' ', '0', '<')
            )
            rows.forEach { row ->
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    row.forEach { ch ->
                        when (ch) {
                            ' ' -> Box(modifier = Modifier.size(if (isWide) 88.dp else 72.dp))
                            '<' -> KeyBackspace(onBackspace, big = isWide)
                            else -> KeyDigit(ch, onDigit, big = isWide)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PinDots(pin: String, error: Boolean, modifier: Modifier = Modifier) {
    val color = if (error) SliceColors.Pepperoncino else SliceColors.Ember
    Row(modifier = modifier, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
        repeat(AuthViewModel.PIN_LENGTH) { i ->
            Box(
                modifier = Modifier
                    .size(24.dp)
                    .clip(CircleShape)
                    .background(if (i < pin.length) color else color.copy(alpha = 0.18f))
            )
        }
    }
}

@Composable
private fun KeyDigit(ch: Char, onDigit: (Char) -> Unit, big: Boolean) {
    val size = if (big) 88.dp else 72.dp
    Surface(
        modifier = Modifier
            .size(size)
            .clip(CircleShape)
            .clickable { onDigit(ch) },
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 2.dp,
        shape = CircleShape
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                text = ch.toString(),
                style = MaterialTheme.typography.displayMedium,
                fontWeight = FontWeight.W600,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

@Composable
private fun KeyBackspace(onClick: () -> Unit, big: Boolean) {
    val size = if (big) 88.dp else 72.dp
    Surface(
        modifier = Modifier
            .size(size)
            .clip(CircleShape)
            .clickable { onClick() },
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = CircleShape
    ) {
        Box(contentAlignment = Alignment.Center) {
            Icon(
                imageVector = Icons.Filled.Backspace,
                contentDescription = stringResource(R.string.auth_delete),
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Preview(widthDp = 1280, heightDp = 800, showBackground = true)
@Composable
private fun AuthPreview() {
    RestForestTheme {
        Surface(color = SliceColors.Dough) {
            AuthLayout(pin = "12", error = false, onDigit = {}, onBackspace = {}, onClearError = {})
        }
    }
}
