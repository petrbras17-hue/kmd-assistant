package ru.slicepizza.restforest.core.database

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import ru.slicepizza.restforest.core.database.dao.CashierDao
import ru.slicepizza.restforest.core.database.dao.CategoryDao
import ru.slicepizza.restforest.core.database.dao.DishDao
import ru.slicepizza.restforest.core.database.dao.OrderDao
import ru.slicepizza.restforest.core.database.dao.PaymentLogDao
import ru.slicepizza.restforest.core.database.dao.PrintJobDao
import ru.slicepizza.restforest.core.database.dao.ShiftDao
import ru.slicepizza.restforest.core.database.entity.CashierEntity
import ru.slicepizza.restforest.core.database.entity.CategoryEntity
import ru.slicepizza.restforest.core.database.entity.DishEntity
import ru.slicepizza.restforest.core.database.entity.DishModifierEntity
import ru.slicepizza.restforest.core.database.entity.OrderEntity
import ru.slicepizza.restforest.core.database.entity.OrderItemEntity
import ru.slicepizza.restforest.core.database.entity.PaymentLogEntity
import ru.slicepizza.restforest.core.database.entity.PrintJobEntity
import ru.slicepizza.restforest.core.database.entity.ShiftEntity

@Database(
    entities = [
        CashierEntity::class,
        CategoryEntity::class,
        DishEntity::class,
        DishModifierEntity::class,
        OrderEntity::class,
        OrderItemEntity::class,
        ShiftEntity::class,
        PrintJobEntity::class,
        PaymentLogEntity::class
    ],
    version = 3,
    exportSchema = true
)
abstract class RestForestDatabase : RoomDatabase() {
    abstract fun cashierDao(): CashierDao
    abstract fun categoryDao(): CategoryDao
    abstract fun dishDao(): DishDao
    abstract fun orderDao(): OrderDao
    abstract fun shiftDao(): ShiftDao
    abstract fun printJobDao(): PrintJobDao
    abstract fun paymentLogDao(): PaymentLogDao
}

/**
 * Sprint 3 → Sprint 5 → Sprint 3.2 migrations. The schema we ship today is
 * v3; migrations exist so a tester who previously installed the Sprint 3
 * APK keeps their cashier PINs across upgrades.
 */
object RestForestMigrations {

    /** Adds `cashier_shift`, `print_job`, `payment_log`, plus the iiko-style
     *  order columns (shiftId, discount, cash received, promo, order type). */
    val MIGRATION_1_2: Migration = object : Migration(1, 2) {
        override fun migrate(db: SupportSQLiteDatabase) {
            // Order extras
            db.execSQL("ALTER TABLE `tab_order` ADD COLUMN `shiftId` TEXT")
            db.execSQL("ALTER TABLE `tab_order` ADD COLUMN `discountKopecks` INTEGER NOT NULL DEFAULT 0")
            db.execSQL("ALTER TABLE `tab_order` ADD COLUMN `cashReceivedKopecks` INTEGER")
            db.execSQL("ALTER TABLE `tab_order` ADD COLUMN `promoCode` TEXT")
            db.execSQL("ALTER TABLE `tab_order` ADD COLUMN `orderType` TEXT NOT NULL DEFAULT 'dine_in'")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_tab_order_shiftId` ON `tab_order`(`shiftId`)")

            // Dishes get kitchen routing.
            db.execSQL("ALTER TABLE `dish` ADD COLUMN `kitchen_section` TEXT NOT NULL DEFAULT 'pizza'")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_dish_kitchen_section` ON `dish`(`kitchen_section`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `cashier_shift` (
                  `id` TEXT NOT NULL,
                  `cashierId` TEXT NOT NULL,
                  `openedAt` INTEGER NOT NULL,
                  `closedAt` INTEGER,
                  `openingAmountKopecks` INTEGER NOT NULL,
                  `closingAmountKopecks` INTEGER,
                  `totalRevenueKopecks` INTEGER NOT NULL,
                  `totalCashKopecks` INTEGER NOT NULL,
                  `totalCardKopecks` INTEGER NOT NULL,
                  `totalSbpKopecks` INTEGER NOT NULL,
                  `orderCount` INTEGER NOT NULL,
                  PRIMARY KEY(`id`),
                  FOREIGN KEY(`cashierId`) REFERENCES `cashier`(`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_cashier_shift_cashierId` ON `cashier_shift`(`cashierId`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_cashier_shift_openedAt` ON `cashier_shift`(`openedAt`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_cashier_shift_closedAt` ON `cashier_shift`(`closedAt`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `print_job` (
                  `id` TEXT NOT NULL,
                  `orderId` TEXT NOT NULL,
                  `status` TEXT NOT NULL,
                  `contentBlob` TEXT NOT NULL,
                  `retries` INTEGER NOT NULL,
                  `error` TEXT,
                  `createdAt` INTEGER NOT NULL,
                  `updatedAt` INTEGER NOT NULL,
                  `printedAt` INTEGER,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_print_job_status` ON `print_job`(`status`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_print_job_createdAt` ON `print_job`(`createdAt`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_print_job_orderId` ON `print_job`(`orderId`)")
        }
    }

    /** Adds payment_log + paymentId/paymentStatus on orders for LIFE PAY. */
    val MIGRATION_2_3: Migration = object : Migration(2, 3) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE `tab_order` ADD COLUMN `paymentId` TEXT")
            db.execSQL("ALTER TABLE `tab_order` ADD COLUMN `paymentStatus` TEXT")
            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `payment_log` (
                  `id` TEXT NOT NULL,
                  `orderId` TEXT NOT NULL,
                  `provider` TEXT NOT NULL,
                  `paymentId` TEXT,
                  `status` TEXT NOT NULL,
                  `amountKopecks` INTEGER NOT NULL,
                  `payloadJson` TEXT,
                  `errorMessage` TEXT,
                  `retryCount` INTEGER NOT NULL,
                  `createdAt` INTEGER NOT NULL,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_payment_log_orderId` ON `payment_log`(`orderId`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_payment_log_status` ON `payment_log`(`status`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_payment_log_createdAt` ON `payment_log`(`createdAt`)")
        }
    }

    val ALL: Array<Migration> = arrayOf(MIGRATION_1_2, MIGRATION_2_3)
}
