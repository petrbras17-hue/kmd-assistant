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
import ru.slicepizza.restforest.core.database.dao.CashierDao
import ru.slicepizza.restforest.core.database.dao.CategoryDao
import ru.slicepizza.restforest.core.database.dao.DishDao
import ru.slicepizza.restforest.core.database.dao.OrderDao
import ru.slicepizza.restforest.core.database.dao.PaymentLogDao
import ru.slicepizza.restforest.core.database.dao.PrintJobDao
import ru.slicepizza.restforest.core.database.dao.ShiftDao

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
}
