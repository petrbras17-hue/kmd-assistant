package ru.slicepizza.restforest.core.database

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import ru.slicepizza.restforest.core.database.dao.AiChatDao
import ru.slicepizza.restforest.core.database.dao.CashierDao
import ru.slicepizza.restforest.core.database.dao.CategoryDao
import ru.slicepizza.restforest.core.database.dao.DishDao
import ru.slicepizza.restforest.core.database.dao.EmployeeDao
import ru.slicepizza.restforest.core.database.dao.IngredientDao
import ru.slicepizza.restforest.core.database.dao.InventoryMovementDao
import ru.slicepizza.restforest.core.database.dao.InventoryRevisionDao
import ru.slicepizza.restforest.core.database.dao.ShiftScheduleDao
import ru.slicepizza.restforest.core.database.dao.SupplierDao
import ru.slicepizza.restforest.core.database.entity.EmployeeEntity
import ru.slicepizza.restforest.core.database.entity.InventoryRevisionEntity
import ru.slicepizza.restforest.core.database.entity.LeaveRequestEntity
import ru.slicepizza.restforest.core.database.entity.ShiftScheduleEntity
import ru.slicepizza.restforest.core.database.entity.ShiftSwapRequestEntity
import ru.slicepizza.restforest.core.database.entity.SupplierEntity
import ru.slicepizza.restforest.core.database.dao.KitchenStatusOverrideDao
import ru.slicepizza.restforest.core.database.dao.OrderDao
import ru.slicepizza.restforest.core.database.dao.PaymentLogDao
import ru.slicepizza.restforest.core.database.dao.PendingWriteoffDao
import ru.slicepizza.restforest.core.database.dao.PrintJobDao
import ru.slicepizza.restforest.core.database.dao.ShiftDao
import ru.slicepizza.restforest.core.database.dao.StockLevelDao
import ru.slicepizza.restforest.core.database.dao.TechCardDao
import ru.slicepizza.restforest.core.database.entity.AiChatMessageEntity
import ru.slicepizza.restforest.core.database.entity.CashierEntity
import ru.slicepizza.restforest.core.database.entity.CategoryEntity
import ru.slicepizza.restforest.core.database.entity.DishEntity
import ru.slicepizza.restforest.core.database.entity.DishModifierEntity
import ru.slicepizza.restforest.core.database.entity.IngredientEntity
import ru.slicepizza.restforest.core.database.entity.InventoryMovementEntity
import ru.slicepizza.restforest.core.database.entity.KitchenStatusOverrideEntity
import ru.slicepizza.restforest.core.database.entity.OrderEntity
import ru.slicepizza.restforest.core.database.entity.OrderItemEntity
import ru.slicepizza.restforest.core.database.entity.PaymentLogEntity
import ru.slicepizza.restforest.core.database.entity.PendingWriteoffEntity
import ru.slicepizza.restforest.core.database.entity.PrintJobEntity
import ru.slicepizza.restforest.core.database.entity.ShiftEntity
import ru.slicepizza.restforest.core.database.entity.StockLevelEntity
import ru.slicepizza.restforest.core.database.entity.TechCardEntity
import ru.slicepizza.restforest.core.database.entity.TechCardLineEntity

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
        PaymentLogEntity::class,
        KitchenStatusOverrideEntity::class,
        // Sprint 16 — Tech Cards + Auto-writeoff (iiko parity), agent: tech-cards-android
        IngredientEntity::class,
        TechCardEntity::class,
        TechCardLineEntity::class,
        InventoryMovementEntity::class,
        StockLevelEntity::class,
        PendingWriteoffEntity::class,
        // Sprint 15 — AI assistant chat history
        AiChatMessageEntity::class,
        // Sprint 17 — Inventory UI (revision cache + supplier CRUD cache)
        SupplierEntity::class,
        InventoryRevisionEntity::class,
        // Sprint HR-2 — Staff scheduling / payroll / leaves
        EmployeeEntity::class,
        ShiftScheduleEntity::class,
        ShiftSwapRequestEntity::class,
        LeaveRequestEntity::class
    ],
    version = 8,
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
    abstract fun kitchenStatusOverrideDao(): KitchenStatusOverrideDao
    // Sprint 16 — Tech Cards + Auto-writeoff
    abstract fun ingredientDao(): IngredientDao
    abstract fun techCardDao(): TechCardDao
    abstract fun inventoryMovementDao(): InventoryMovementDao
    abstract fun stockLevelDao(): StockLevelDao
    abstract fun pendingWriteoffDao(): PendingWriteoffDao
    // Sprint 15 — AI assistant chat history
    abstract fun aiChatDao(): AiChatDao
    // Sprint 17 — Inventory UI (revision history + supplier CRUD)
    abstract fun supplierDao(): SupplierDao
    abstract fun inventoryRevisionDao(): InventoryRevisionDao
    // Sprint HR-2 — Staff scheduling / payroll
    abstract fun employeeDao(): EmployeeDao
    abstract fun shiftScheduleDao(): ShiftScheduleDao
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

    /** Sprint 14.1 — Bug #2 fix: persistent kitchen status overrides survive
     *  tablet reboots. Earlier `_statusOverrides` was memory-only, so повар
     *  would lose the «В работе» list on power cycle. */
    val MIGRATION_3_4: Migration = object : Migration(3, 4) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `kitchen_status_override` (
                  `orderId` TEXT NOT NULL,
                  `itemId` TEXT NOT NULL,
                  `status` TEXT NOT NULL,
                  `startedAt` INTEGER,
                  `updatedAt` INTEGER NOT NULL,
                  PRIMARY KEY(`orderId`, `itemId`)
                )
                """.trimIndent()
            )
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS `index_kitchen_status_override_updatedAt` " +
                    "ON `kitchen_status_override`(`updatedAt`)"
            )
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS `index_kitchen_status_override_status` " +
                    "ON `kitchen_status_override`(`status`)"
            )
        }
    }

    /**
     * Sprint 16 — Tech Cards + Auto-writeoff. Adds 6 new tables atomically:
     *   - ingredient (master list)
     *   - tech_card + tech_card_line (recipes with versioning)
     *   - inventory_movement (signed delta history)
     *   - stock_level (current qty per ingredient)
     *   - pending_writeoff (offline buffer for backend sync)
     *
     * Не трогает существующие dish / tab_order / cashier / kitchen_status_override —
     * old tester installations keep their data verbatim.
     */
    val MIGRATION_4_5: Migration = object : Migration(4, 5) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `ingredient` (
                  `id` TEXT NOT NULL,
                  `name` TEXT NOT NULL,
                  `unit` TEXT NOT NULL,
                  `category` TEXT NOT NULL,
                  `min_stock_qty` REAL NOT NULL,
                  `cost_per_unit_kopecks` INTEGER NOT NULL,
                  `supplier_id` TEXT,
                  `is_active` INTEGER NOT NULL DEFAULT 1,
                  `created_at` INTEGER NOT NULL,
                  `updated_at` INTEGER NOT NULL,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_ingredient_name` ON `ingredient`(`name`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_ingredient_category` ON `ingredient`(`category`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_ingredient_is_active` ON `ingredient`(`is_active`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `tech_card` (
                  `id` TEXT NOT NULL,
                  `dish_id` TEXT NOT NULL,
                  `version` INTEGER NOT NULL,
                  `is_active` INTEGER NOT NULL,
                  `notes` TEXT,
                  `created_at` INTEGER NOT NULL,
                  PRIMARY KEY(`id`),
                  FOREIGN KEY(`dish_id`) REFERENCES `dish`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_tech_card_dish_id` ON `tech_card`(`dish_id`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_tech_card_is_active` ON `tech_card`(`is_active`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `tech_card_line` (
                  `id` TEXT NOT NULL,
                  `tech_card_id` TEXT NOT NULL,
                  `ingredient_id` TEXT NOT NULL,
                  `gross_qty` REAL NOT NULL,
                  `net_qty` REAL NOT NULL,
                  `loss_pct` REAL NOT NULL,
                  `loss_category` TEXT NOT NULL,
                  `notes` TEXT,
                  PRIMARY KEY(`id`),
                  FOREIGN KEY(`tech_card_id`) REFERENCES `tech_card`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE,
                  FOREIGN KEY(`ingredient_id`) REFERENCES `ingredient`(`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_tech_card_line_tech_card_id` ON `tech_card_line`(`tech_card_id`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_tech_card_line_ingredient_id` ON `tech_card_line`(`ingredient_id`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `inventory_movement` (
                  `id` TEXT NOT NULL,
                  `ingredient_id` TEXT NOT NULL,
                  `movement_type` TEXT NOT NULL,
                  `qty` REAL NOT NULL,
                  `order_id` TEXT,
                  `revision_id` TEXT,
                  `occurred_at` INTEGER NOT NULL,
                  `cost_kopecks` INTEGER NOT NULL,
                  `comment` TEXT,
                  `synced_at` INTEGER,
                  PRIMARY KEY(`id`),
                  FOREIGN KEY(`ingredient_id`) REFERENCES `ingredient`(`id`) ON UPDATE NO ACTION ON DELETE RESTRICT
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_inventory_movement_ingredient_id` ON `inventory_movement`(`ingredient_id`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_inventory_movement_movement_type` ON `inventory_movement`(`movement_type`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_inventory_movement_occurred_at` ON `inventory_movement`(`occurred_at`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_inventory_movement_order_id` ON `inventory_movement`(`order_id`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `stock_level` (
                  `ingredient_id` TEXT NOT NULL,
                  `qty` REAL NOT NULL,
                  `reserved_qty` REAL NOT NULL DEFAULT 0,
                  `updated_at` INTEGER NOT NULL,
                  PRIMARY KEY(`ingredient_id`),
                  FOREIGN KEY(`ingredient_id`) REFERENCES `ingredient`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE
                )
                """.trimIndent()
            )

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `pending_writeoff` (
                  `id` TEXT NOT NULL,
                  `order_id` TEXT NOT NULL,
                  `payload_json` TEXT NOT NULL,
                  `created_at` INTEGER NOT NULL,
                  `attempt_count` INTEGER NOT NULL DEFAULT 0,
                  `last_error` TEXT,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_pending_writeoff_created_at` ON `pending_writeoff`(`created_at`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_pending_writeoff_attempt_count` ON `pending_writeoff`(`attempt_count`)")
        }
    }

    /**
     * Sprint 15 — AI assistant chat. Single table `ai_chat_messages` keyed by
     * UUID, ordered by createdAt. Bot persists user/assistant turns so Пётр
     * может пролистать прошлые сессии без сети.
     */
    val MIGRATION_5_6: Migration = object : Migration(5, 6) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `ai_chat_messages` (
                  `id` TEXT NOT NULL,
                  `role` TEXT NOT NULL,
                  `content` TEXT NOT NULL,
                  `createdAt` INTEGER NOT NULL,
                  `metaJson` TEXT,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_ai_chat_messages_createdAt` ON `ai_chat_messages`(`createdAt`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_ai_chat_messages_role` ON `ai_chat_messages`(`role`)")
        }
    }

    /**
     * Sprint 17 — Inventory UI. Adds offline cache для supplier CRUD и
     * списка ревизий. Сами ревизии создаются на бэке (admin_inventory.py),
     * но Пётр хочет видеть последние 100 даже без сети.
     */
    val MIGRATION_6_7: Migration = object : Migration(6, 7) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `supplier` (
                  `id` TEXT NOT NULL,
                  `name` TEXT NOT NULL,
                  `phone` TEXT,
                  `email` TEXT,
                  `address` TEXT,
                  `inn` TEXT,
                  `contactPerson` TEXT,
                  `notes` TEXT,
                  `isActive` INTEGER NOT NULL DEFAULT 1,
                  `updatedAt` INTEGER NOT NULL,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_supplier_name` ON `supplier`(`name`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_supplier_isActive` ON `supplier`(`isActive`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `inventory_revision` (
                  `id` TEXT NOT NULL,
                  `startedAt` TEXT NOT NULL,
                  `completedAt` TEXT,
                  `totalLossAmount` REAL NOT NULL,
                  `linesCount` INTEGER NOT NULL,
                  `notes` TEXT,
                  `status` TEXT NOT NULL,
                  `cachedAt` INTEGER NOT NULL,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS `index_inventory_revision_startedAt` " +
                    "ON `inventory_revision`(`startedAt`)"
            )
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS `index_inventory_revision_status` " +
                    "ON `inventory_revision`(`status`)"
            )
        }
    }

    /**
     * Sprint HR-2 — Staff scheduling, payroll, swaps, leaves.
     * Добавляет 4 новые таблицы для зеркала backend.employees / shift_schedule /
     * shift_swap_requests / leave_requests. Логин на POS по-прежнему через
     * CashierEntity.pinHash — это просто кэш HR-данных для офлайн-UI.
     */
    val MIGRATION_7_8: Migration = object : Migration(7, 8) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `employee` (
                  `id` INTEGER NOT NULL,
                  `fullName` TEXT NOT NULL,
                  `role` TEXT NOT NULL,
                  `pin` TEXT,
                  `phone` TEXT,
                  `telegramId` INTEGER,
                  `hireDate` TEXT,
                  `firedDate` TEXT,
                  `employmentType` TEXT NOT NULL,
                  `ratePerDayKopecks` INTEGER NOT NULL,
                  `hourlyRateKopecks` INTEGER NOT NULL,
                  `pieceRatePct` REAL NOT NULL,
                  `mealAllowanceKopecks` INTEGER NOT NULL,
                  `isActive` INTEGER NOT NULL,
                  `updatedAt` INTEGER NOT NULL,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_employee_role` ON `employee`(`role`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_employee_isActive` ON `employee`(`isActive`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `shift_schedule` (
                  `id` INTEGER NOT NULL,
                  `employeeId` INTEGER NOT NULL,
                  `plannedDate` TEXT NOT NULL,
                  `plannedStart` TEXT NOT NULL,
                  `plannedEnd` TEXT NOT NULL,
                  `status` TEXT NOT NULL,
                  `actualShiftId` INTEGER,
                  `actualStart` TEXT,
                  `actualEnd` TEXT,
                  `notes` TEXT,
                  `cachedAt` INTEGER NOT NULL,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_shift_schedule_employeeId_plannedDate` ON `shift_schedule`(`employeeId`, `plannedDate`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_shift_schedule_plannedDate_status` ON `shift_schedule`(`plannedDate`, `status`)")
            db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS `index_shift_schedule_employeeId_plannedDate_plannedStart` ON `shift_schedule`(`employeeId`, `plannedDate`, `plannedStart`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `shift_swap_request` (
                  `id` INTEGER NOT NULL,
                  `fromEmployeeId` INTEGER NOT NULL,
                  `toEmployeeId` INTEGER,
                  `scheduleId` INTEGER NOT NULL,
                  `status` TEXT NOT NULL,
                  `reason` TEXT,
                  `createdAt` TEXT NOT NULL,
                  `decidedAt` TEXT,
                  `cachedAt` INTEGER NOT NULL,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_shift_swap_request_status` ON `shift_swap_request`(`status`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_shift_swap_request_fromEmployeeId` ON `shift_swap_request`(`fromEmployeeId`)")

            db.execSQL(
                """
                CREATE TABLE IF NOT EXISTS `leave_request` (
                  `id` INTEGER NOT NULL,
                  `employeeId` INTEGER NOT NULL,
                  `leaveType` TEXT NOT NULL,
                  `startDate` TEXT NOT NULL,
                  `endDate` TEXT NOT NULL,
                  `status` TEXT NOT NULL,
                  `reason` TEXT,
                  `createdAt` TEXT NOT NULL,
                  `decidedAt` TEXT,
                  `cachedAt` INTEGER NOT NULL,
                  PRIMARY KEY(`id`)
                )
                """.trimIndent()
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_leave_request_employeeId` ON `leave_request`(`employeeId`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_leave_request_status` ON `leave_request`(`status`)")
        }
    }

    val ALL: Array<Migration> = arrayOf(
        MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5, MIGRATION_5_6,
        MIGRATION_6_7, MIGRATION_7_8
    )
}
