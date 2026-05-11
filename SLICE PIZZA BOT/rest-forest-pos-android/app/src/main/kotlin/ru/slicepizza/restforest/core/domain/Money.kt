package ru.slicepizza.restforest.core.domain

import java.util.Locale

/**
 * Single source of truth for monetary values.
 *
 * Stored as Long kopecks (1 ₽ = 100 копеек) so we never round-trip through
 * Double. Arithmetic operators are overloaded so cart math stays expressive
 * without leaking the Long under the hood.
 */
@JvmInline
value class Money(val kopecks: Long) : Comparable<Money> {

    operator fun plus(other: Money): Money = Money(kopecks + other.kopecks)
    operator fun minus(other: Money): Money = Money(kopecks - other.kopecks)
    operator fun times(qty: Int): Money = Money(kopecks * qty)
    operator fun times(qty: Long): Money = Money(kopecks * qty)
    override operator fun compareTo(other: Money): Int = kopecks.compareTo(other.kopecks)

    val rubles: Long get() = kopecks / 100
    val pennyPart: Long get() = (kopecks % 100).let { if (it < 0) -it else it }

    /** Format as "1 234 ₽" (suppress kopecks if .00) or "1 234,50 ₽". */
    fun format(locale: Locale = Locale("ru", "RU")): String {
        val sign = if (kopecks < 0) "-" else ""
        val abs = if (kopecks < 0) -kopecks else kopecks
        val rub = abs / 100
        val pen = abs % 100
        val rubFmt = "%,d".format(locale, rub).replace(',', ' ')
        return if (pen == 0L) {
            "$sign$rubFmt ₽"
        } else {
            "$sign$rubFmt,%02d ₽".format(locale, pen)
        }
    }

    companion object {
        val Zero: Money = Money(0L)
        fun rubles(rub: Int): Money = Money(rub.toLong() * 100L)
        fun rubles(rub: Long): Money = Money(rub * 100L)
        fun fromRubles(rub: Double): Money = Money((rub * 100.0).toLong())
    }
}
