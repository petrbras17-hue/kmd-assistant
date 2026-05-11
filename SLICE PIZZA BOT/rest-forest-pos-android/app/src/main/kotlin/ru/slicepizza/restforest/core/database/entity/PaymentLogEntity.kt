package ru.slicepizza.restforest.core.database.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "payment_log",
    indices = [Index("orderId"), Index("status"), Index("createdAt")]
)
data class PaymentLogEntity(
    @PrimaryKey val id: String,
    val orderId: String,
    /** "lifepay_cash" | "lifepay_card" | "lifepay_sbp" | "vtb_pinpad" */
    val provider: String,
    val paymentId: String?,
    /** "pending" | "succeeded" | "failed" | "refunded" */
    val status: String,
    val amountKopecks: Long,
    val payloadJson: String?,
    val errorMessage: String?,
    val retryCount: Int,
    val createdAt: Long
)
