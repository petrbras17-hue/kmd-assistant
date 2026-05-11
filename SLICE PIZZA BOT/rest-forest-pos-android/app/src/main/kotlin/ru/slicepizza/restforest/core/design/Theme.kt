package ru.slicepizza.restforest.core.design

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp

private val LightScheme = lightColorScheme(
    primary = SliceColors.Ember,
    onPrimary = SliceColors.Mozzarella,
    primaryContainer = SliceColors.Saffron,
    onPrimaryContainer = SliceColors.Char,
    secondary = SliceColors.Basil,
    onSecondary = SliceColors.Mozzarella,
    secondaryContainer = SliceColors.MutedSurface,
    onSecondaryContainer = SliceColors.Char,
    tertiary = SliceColors.FuchsiaPhysical,
    onTertiary = SliceColors.Mozzarella,
    background = SliceColors.Dough,
    onBackground = SliceColors.Char,
    surface = SliceColors.Mozzarella,
    onSurface = SliceColors.Char,
    surfaceVariant = SliceColors.MutedSurface,
    onSurfaceVariant = SliceColors.Char,
    outline = SliceColors.Outline,
    error = SliceColors.Error,
    onError = SliceColors.Mozzarella
)

private val DarkScheme = darkColorScheme(
    primary = SliceColors.Ember,
    onPrimary = SliceColors.Mozzarella,
    background = SliceColors.Char,
    onBackground = SliceColors.Dough,
    surface = SliceColors.Char,
    onSurface = SliceColors.Dough,
    secondary = SliceColors.Basil,
    tertiary = SliceColors.FuchsiaPhysical
)

private val SliceShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(28.dp)
)

@Composable
fun RestForestTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkScheme else LightScheme,
        typography = SliceTypography,
        shapes = SliceShapes,
        content = content
    )
}
