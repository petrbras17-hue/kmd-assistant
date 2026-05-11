package ru.slicepizza.restforest.feature.printing

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import ru.slicepizza.restforest.core.domain.Money
import ru.slicepizza.restforest.feature.cart.CartLine

/**
 * Formats kitchen tickets in DantSu/ESCPOS-ThermalPrinter markup.
 *
 * Markup reminder:
 *   [C]  centered      [L]  left aligned    [R]  right aligned
 *   <font size='big'>…</font>   bigger glyphs
 *   <b>…</b>                    bold
 *
 * Tickets are short — kitchen needs glance-readable item list. We split per
 * `kitchenSection` so the cold-drinks fridge doesn't get pizza tickets.
 */
object EscPosFormatter {

    private val ts = SimpleDateFormat("HH:mm dd.MM", Locale("ru"))

    /** One ticket per section. Returns Map<section, content>. */
    fun formatKitchenTickets(
        orderShortId: String,
        cashierName: String,
        lines: List<CartLine>,
        orderType: String,
        now: Long = System.currentTimeMillis()
    ): Map<String, String> {
        val bySection = lines
            .filter { it.dish.kitchenSection != "none" }
            .groupBy { it.dish.kitchenSection }
        return bySection.mapValues { (section, secLines) ->
            buildSectionTicket(orderShortId, cashierName, section, orderType, secLines, now)
        }
    }

    private fun buildSectionTicket(
        orderShortId: String,
        cashierName: String,
        section: String,
        orderType: String,
        lines: List<CartLine>,
        now: Long
    ): String {
        val sb = StringBuilder()
        sb.appendLine("[C]<font size='big'><b>== ${sectionLabel(section)} ==</b></font>")
        sb.appendLine("[L]")
        sb.appendLine("[L]<b>Заказ:</b> #$orderShortId")
        sb.appendLine("[L]<b>Кассир:</b> $cashierName")
        sb.appendLine("[L]<b>Время:</b> ${ts.format(Date(now))}")
        sb.appendLine("[L]<b>Тип:</b> ${orderTypeLabel(orderType)}")
        sb.appendLine("[C]--------------------------------")
        for (l in lines) {
            sb.appendLine("[L]<font size='big'>${l.qty}× ${l.dish.name}</font>")
            l.modifiers.forEach { m ->
                sb.appendLine("[L]  + ${m.name}")
            }
        }
        sb.appendLine("[C]--------------------------------")
        sb.appendLine("[L]")
        sb.appendLine("[L]")
        return sb.toString()
    }

    private fun sectionLabel(section: String): String = when (section) {
        "pizza" -> "ПЕЧЬ — пицца"
        "drinks" -> "БАР — напитки"
        "kids" -> "Детская кухня"
        "addons" -> "Добавки"
        "service" -> "Сервис"
        else -> section.uppercase()
    }

    private fun orderTypeLabel(t: String): String = when (t) {
        "takeaway" -> "На вынос"
        "delivery" -> "Доставка"
        else -> "В зале"
    }

    /** Z-report ticket — printed when shift closes. */
    fun formatZReport(
        cashierName: String,
        openedAt: Long,
        closedAt: Long,
        revenue: Money,
        cash: Money,
        card: Money,
        sbp: Money,
        orderCount: Int,
        avg: Money,
        top: List<Pair<String, Int>>
    ): String {
        val sb = StringBuilder()
        sb.appendLine("[C]<font size='big'><b>Z-ОТЧЁТ</b></font>")
        sb.appendLine("[C]Slice Pizza")
        sb.appendLine("[C]--------------------------------")
        sb.appendLine("[L]<b>Кассир:</b> $cashierName")
        sb.appendLine("[L]<b>Открытие:</b> ${ts.format(Date(openedAt))}")
        sb.appendLine("[L]<b>Закрытие:</b> ${ts.format(Date(closedAt))}")
        sb.appendLine("[C]--------------------------------")
        sb.appendLine("[L]<b>Выручка:</b>[R]${revenue.format()}")
        sb.appendLine("[L]Чеков:[R]$orderCount")
        sb.appendLine("[L]Средний:[R]${avg.format()}")
        sb.appendLine("[C]--------------------------------")
        sb.appendLine("[L]Наличные:[R]${cash.format()}")
        sb.appendLine("[L]Карта:[R]${card.format()}")
        sb.appendLine("[L]СБП:[R]${sbp.format()}")
        if (top.isNotEmpty()) {
            sb.appendLine("[C]--------------------------------")
            sb.appendLine("[L]<b>Топ-5:</b>")
            top.forEach { (name, qty) ->
                sb.appendLine("[L]  $name[R]×$qty")
            }
        }
        sb.appendLine("[L]")
        return sb.toString()
    }
}
