package ru.slicepizza.restforest.core.database.di

import android.content.Context
import androidx.room.Room
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton
import ru.slicepizza.restforest.core.database.RestForestDatabase
import ru.slicepizza.restforest.core.database.RestForestMigrations
import ru.slicepizza.restforest.core.database.dao.AiChatDao
import ru.slicepizza.restforest.core.database.dao.CashierDao
import ru.slicepizza.restforest.core.database.dao.CategoryDao
import ru.slicepizza.restforest.core.database.dao.DishDao
import ru.slicepizza.restforest.core.database.dao.IngredientDao
import ru.slicepizza.restforest.core.database.dao.InventoryMovementDao
import ru.slicepizza.restforest.core.database.dao.InventoryRevisionDao
import ru.slicepizza.restforest.core.database.dao.KitchenStatusOverrideDao
import ru.slicepizza.restforest.core.database.dao.OrderDao
import ru.slicepizza.restforest.core.database.dao.PaymentLogDao
import ru.slicepizza.restforest.core.database.dao.PendingWriteoffDao
import ru.slicepizza.restforest.core.database.dao.PrintJobDao
import ru.slicepizza.restforest.core.database.dao.ShiftDao
import ru.slicepizza.restforest.core.database.dao.StockLevelDao
import ru.slicepizza.restforest.core.database.dao.SupplierDao
import ru.slicepizza.restforest.core.database.dao.TechCardDao

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides @Singleton
    fun provideDatabase(@ApplicationContext ctx: Context): RestForestDatabase =
        Room.databaseBuilder(ctx, RestForestDatabase::class.java, "rest_forest.db")
            .addMigrations(*RestForestMigrations.ALL)
            // First-run installs land directly at v3; we still allow a clean
            // wipe if a tester sideloads a wildly old build.
            .fallbackToDestructiveMigrationOnDowngrade()
            .build()

    @Provides fun provideCashierDao(db: RestForestDatabase): CashierDao = db.cashierDao()
    @Provides fun provideCategoryDao(db: RestForestDatabase): CategoryDao = db.categoryDao()
    @Provides fun provideDishDao(db: RestForestDatabase): DishDao = db.dishDao()
    @Provides fun provideOrderDao(db: RestForestDatabase): OrderDao = db.orderDao()
    @Provides fun provideShiftDao(db: RestForestDatabase): ShiftDao = db.shiftDao()
    @Provides fun providePrintJobDao(db: RestForestDatabase): PrintJobDao = db.printJobDao()
    @Provides fun providePaymentLogDao(db: RestForestDatabase): PaymentLogDao = db.paymentLogDao()
    @Provides fun provideKitchenStatusOverrideDao(db: RestForestDatabase): KitchenStatusOverrideDao =
        db.kitchenStatusOverrideDao()

    // Sprint 16 — Tech Cards + Auto-writeoff DAOs (agent: tech-cards-android)
    @Provides fun provideIngredientDao(db: RestForestDatabase): IngredientDao = db.ingredientDao()
    @Provides fun provideTechCardDao(db: RestForestDatabase): TechCardDao = db.techCardDao()
    @Provides fun provideInventoryMovementDao(db: RestForestDatabase): InventoryMovementDao =
        db.inventoryMovementDao()
    @Provides fun provideStockLevelDao(db: RestForestDatabase): StockLevelDao = db.stockLevelDao()
    @Provides fun providePendingWriteoffDao(db: RestForestDatabase): PendingWriteoffDao =
        db.pendingWriteoffDao()

    // Sprint 15 — AI assistant chat history
    @Provides fun provideAiChatDao(db: RestForestDatabase): AiChatDao = db.aiChatDao()

    // Sprint 17 — Inventory UI (revision history + supplier CRUD)
    @Provides fun provideSupplierDao(db: RestForestDatabase): SupplierDao = db.supplierDao()
    @Provides fun provideInventoryRevisionDao(db: RestForestDatabase): InventoryRevisionDao =
        db.inventoryRevisionDao()
}
