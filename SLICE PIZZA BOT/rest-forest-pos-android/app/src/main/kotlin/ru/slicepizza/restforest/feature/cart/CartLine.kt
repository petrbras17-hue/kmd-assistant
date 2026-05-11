package ru.slicepizza.restforest.feature.cart

import ru.slicepizza.restforest.core.database.entity.DishEntity
import ru.slicepizza.restforest.core.database.entity.DishModifierEntity
import ru.slicepizza.restforest.core.domain.Money

/**
 * Immutable cart line — the cart itself is a List<CartLine>. Every cart-modifying
 * action returns a new list, never mutates in place.
 */
data class CartLine(
    val key: String,
    val dish: DishEntity,
    val modifiers: List<DishModifierEntity>,
    val qty: Int
) {
    val modifiersTotal: Money get() = modifiers.fold(Money.Zero) { acc, m -> acc + Money(m.priceKopecks) }
    val unitPriceWithMods: Money get() = Money(dish.priceKopecks) + modifiersTotal
    val lineTotal: Money get() = unitPriceWithMods * qty
    val modifierIds: List<String> get() = modifiers.map { it.id }
}

fun cartLineKey(dishId: String, modifierIds: List<String>): String =
    if (modifierIds.isEmpty()) dishId
    else "$dishId|${modifierIds.sorted().joinToString(",")}"
