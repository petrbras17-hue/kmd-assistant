package ru.slicepizza.restforest.core.database.seed

import androidx.compose.ui.graphics.toArgb
import at.favre.lib.crypto.bcrypt.BCrypt
import javax.inject.Inject
import javax.inject.Singleton
import ru.slicepizza.restforest.core.database.dao.CashierDao
import ru.slicepizza.restforest.core.database.dao.CategoryDao
import ru.slicepizza.restforest.core.database.dao.DishDao
import ru.slicepizza.restforest.core.database.entity.CashierEntity
import ru.slicepizza.restforest.core.database.entity.CategoryEntity
import ru.slicepizza.restforest.core.database.entity.DishEntity
import ru.slicepizza.restforest.core.database.entity.DishModifierEntity
import ru.slicepizza.restforest.core.design.SliceColors

/**
 * Idempotent first-run seeder. Source of truth — менюv2 (52 + 1 service)
 * with prices from `ТУТ ПИЦЦА. Документы/menu_v2_parsed.json` and the
 * supplementary drinks/service line from `evening_reports_aggregate.json`
 * (the takeaway +200 ₽ is the second-most-frequent SKU after Margherita).
 *
 * Cashiers (PIN → role):
 *   1111 → Оксана  (cashier)
 *   9999 → Салом   (kitchen → routed to KitchenScreen)
 *   2222 → Шерали  (courier → POS read-only)
 */
@Singleton
class DatabaseSeeder @Inject constructor(
    private val cashierDao: CashierDao,
    private val categoryDao: CategoryDao,
    private val dishDao: DishDao
) {

    suspend fun seedIfEmpty() {
        if (cashierDao.count() == 0) seedCashiers()
        if (categoryDao.count() == 0) seedCategories()
        if (dishDao.count() == 0) seedDishes()
    }

    // ------------------------------------------------------------------
    // Cashiers
    // ------------------------------------------------------------------

    private suspend fun seedCashiers() {
        val now = System.currentTimeMillis()
        cashierDao.upsertAll(
            listOf(
                CashierEntity(
                    id = "cashier-oksana",
                    name = "Оксана",
                    pinHash = hashPin("1111"),
                    role = "cashier",
                    isActive = true,
                    updatedAt = now
                ),
                CashierEntity(
                    id = "cashier-salom",
                    name = "Салом",
                    pinHash = hashPin("9999"),
                    role = "kitchen",
                    isActive = true,
                    updatedAt = now
                ),
                CashierEntity(
                    id = "cashier-sherali",
                    name = "Шерали",
                    pinHash = hashPin("2222"),
                    role = "courier",
                    isActive = true,
                    updatedAt = now
                )
            )
        )
    }

    private fun hashPin(pin: String): String =
        BCrypt.withDefaults().hashToString(10, pin.toCharArray())

    // ------------------------------------------------------------------
    // Categories
    // ------------------------------------------------------------------

    private suspend fun seedCategories() {
        val now = System.currentTimeMillis()
        categoryDao.upsertAll(
            listOf(
                CategoryEntity("cat-classic", "Классическая пицца", 10, SliceColors.Ember.toArgb(), now),
                CategoryEntity("cat-neapolitan", "Неаполитанская пицца", 20, SliceColors.Pepperoncino.toArgb(), now),
                CategoryEntity("cat-kids", "Детская пицца", 30, SliceColors.FuchsiaPhysical.toArgb(), now),
                CategoryEntity("cat-addons", "Добавки", 40, SliceColors.Basil.toArgb(), now),
                CategoryEntity("cat-dough", "Тесто", 50, SliceColors.Saffron.toArgb(), now),
                CategoryEntity("cat-drinks", "Напитки", 60, SliceColors.Saffron.toArgb(), now),
                CategoryEntity("cat-dessert", "Десерты", 70, SliceColors.FuchsiaPhysical.toArgb(), now),
                CategoryEntity("cat-service", "Услуги", 80, SliceColors.Char.toArgb(), now)
            )
        )
    }

    // ------------------------------------------------------------------
    // Dishes
    // ------------------------------------------------------------------

    private suspend fun seedDishes() {
        val now = System.currentTimeMillis()
        val items = mutableListOf<DishEntity>()

        // ------- 15 classical pizzas (cat-classic, kitchen=pizza) -------
        items += dish("dish-pizza-4-syra", "cat-classic", "4 сыра", 690, "pizza")
        items += dish("dish-pizza-veggie", "cat-classic", "Вегетарианская", 690, "pizza")
        items += dish("dish-pizza-ham-pineapple", "cat-classic", "Ветчина Ананас", 690, "pizza")
        items += dish("dish-pizza-ham-mush", "cat-classic", "Ветчина Грибы", 660, "pizza")
        items += dish("dish-pizza-pear-gorgon", "cat-classic", "Груша Горгонзола", 740, "pizza")
        items += dish("dish-pizza-calzone", "cat-classic", "Кальцоне", 750, "pizza")
        items += dish("dish-pizza-goat-beet", "cat-classic", "Козий сыр и Свекла", 660, "pizza")
        items += dish("dish-pizza-margherita", "cat-classic", "Маргарита", 540, "pizza")
        items += dish("dish-pizza-meat", "cat-classic", "Мясная", 850, "pizza")
        items += dish("dish-pizza-parma-arugula", "cat-classic", "Парма Руккола", 850, "pizza")
        items += dish("dish-pizza-pepperoni", "cat-classic", "Пепперони", 690, "pizza")
        items += dish("dish-pizza-chicken", "cat-classic", "С курицей", 630, "pizza")
        items += dish("dish-pizza-salmon", "cat-classic", "С лососем", 2090, "pizza")
        items += dish("dish-pizza-tuna", "cat-classic", "С тунцом", 790, "pizza")
        items += dish("dish-pizza-focaccia", "cat-classic", "Фокачча", 350, "pizza")

        // ------- 6 Neapolitan (Чоризо + Карамельный лук stopped) -------
        items += dish("dish-neap-margherita", "cat-neapolitan", "Маргарита неаполитанская", 590, "pizza")
        items += dish("dish-neap-chicken", "cat-neapolitan", "С курицей неаполитанская", 650, "pizza")
        items += dish("dish-neap-4-syra", "cat-neapolitan", "4 сыра неаполитанская", 690, "pizza")
        items += dish("dish-neap-suprim", "cat-neapolitan", "Суприм неаполитанская", 890, "pizza")
        items += dish("dish-neap-chorizo", "cat-neapolitan", "Чоризо неаполитанская", 720, "pizza", available = false)
        items += dish("dish-neap-onion", "cat-neapolitan", "Карамельный лук неаполитанская", 950, "pizza", available = false)

        // ------- 2 kids -------
        items += dish("dish-kids-fruit", "cat-kids", "Детская Фруктовая", 1200, "kids")
        items += dish("dish-kids-chocolate", "cat-kids", "Детская Шоколадная", 650, "kids")

        // ------- 21 addons (cat-addons, kitchen=addons) -------
        items += dish("dish-addon-pineapple40", "cat-addons", "Ананас 40 гр", 110, "addons")
        items += dish("dish-addon-buffalo20", "cat-addons", "Баффало 20 гр", 110, "addons")
        items += dish("dish-addon-ham40", "cat-addons", "Ветчина 40 гр", 150, "addons")
        items += dish("dish-addon-gorgonzola20", "cat-addons", "Горгонзола 20 гр", 150, "addons")
        items += dish("dish-addon-pear40", "cat-addons", "Груша 40 гр", 95, "addons")
        items += dish("dish-addon-chicken45", "cat-addons", "Курица 45 гр", 110, "addons")
        items += dish("dish-addon-salmon200", "cat-addons", "Лосось 200 гр", 350, "addons")
        items += dish("dish-addon-redonion10", "cat-addons", "Лук красный 10 гр", 90, "addons")
        items += dish("dish-addon-olives10", "cat-addons", "Маслины 10 гр", 130, "addons")
        items += dish("dish-addon-mozzarella120", "cat-addons", "Моцарелла 120 гр", 240, "addons")
        items += dish("dish-addon-parma40", "cat-addons", "Пармская ветчина 40 гр", 280, "addons")
        items += dish("dish-addon-pepper10", "cat-addons", "Перец болгарский 10 гр", 130, "addons")
        items += dish("dish-addon-pizza-heart", "cat-addons", "Пицца сердце", 300, "addons")
        items += dish("dish-addon-tomato40", "cat-addons", "Помидоры 40 гр", 90, "addons")
        items += dish("dish-addon-arugula10", "cat-addons", "Руккола 10 гр", 110, "addons")
        items += dish("dish-addon-tomato-sauce40", "cat-addons", "Соус Томатный 40 гр", 100, "addons")
        items += dish("dish-addon-goat100", "cat-addons", "Сыр Козий 100 гр", 340, "addons")
        items += dish("dish-addon-tuna50", "cat-addons", "Тунец 50 гр", 210, "addons")
        items += dish("dish-addon-jalapeno10", "cat-addons", "Холопеньо 10 гр", 110, "addons")
        items += dish("dish-addon-chorizo45", "cat-addons", "Чоризо 45 гр", 230, "addons", available = false)
        items += dish("dish-addon-mushrooms30", "cat-addons", "Шампиньоны 30 гр", 90, "addons")

        // ------- 2 doughs -------
        items += dish("dish-dough-classic", "cat-dough", "Тесто классическое", 130, "pizza")
        items += dish("dish-dough-neap", "cat-dough", "Тесто неаполитанское", 150, "pizza")

        // ------- 5 drinks (concrete SKUs) -------
        items += dish("dish-drink-cola033", "cat-drinks", "Кока-Кола 0.33", 200, "drinks")
        items += dish("dish-drink-sprite033", "cat-drinks", "Спрайт 0.33", 200, "drinks")
        items += dish("dish-drink-fanta033", "cat-drinks", "Фанта 0.33", 200, "drinks")
        items += dish("dish-drink-water05", "cat-drinks", "Вода 0.5", 100, "drinks")
        items += dish("dish-drink-tea", "cat-drinks", "Чай в ассортименте", 150, "drinks")

        // ------- 1 ice cream -------
        items += dish("dish-dessert-icecream", "cat-dessert", "Мороженое в ассортименте", 150, "drinks")

        // ------- 1 service line: takeaway +200 (38 sales over 24 days) -------
        items += dish("dish-service-takeaway", "cat-service", "На вынос +200", 200, "none")

        dishDao.upsertDishes(items)

        // Modifiers — keep small, optional. POS shows ModifierBottomSheet only
        // for pizzas that have ≥1 modifier. iiko-style tech cards land in
        // Sprint 4 when PowerSync ↔ Supabase is wired.
        dishDao.upsertModifiers(seedModifiers(now))
    }

    private fun dish(
        id: String,
        categoryId: String,
        name: String,
        priceRub: Int,
        kitchenSection: String,
        available: Boolean = true,
        imageUrl: String? = null
    ): DishEntity = DishEntity(
        id = id,
        categoryId = categoryId,
        name = name,
        priceKopecks = priceRub.toLong() * 100L,
        imageUrl = imageUrl,
        isAvailable = available,
        sku = id,
        kitchenSection = kitchenSection,
        updatedAt = System.currentTimeMillis()
    )

    private fun seedModifiers(now: Long): List<DishModifierEntity> = listOf(
        // Маргарита — двойной сыр
        DishModifierEntity(
            id = "mod-margherita-cheese",
            dishId = "dish-pizza-margherita",
            name = "+ Моцарелла 120 г",
            priceKopecks = 240L * 100L,
            isRequired = false,
            sortOrder = 0,
            updatedAt = now
        ),
        DishModifierEntity(
            id = "mod-margherita-arugula",
            dishId = "dish-pizza-margherita",
            name = "+ Руккола 10 г",
            priceKopecks = 110L * 100L,
            isRequired = false,
            sortOrder = 1,
            updatedAt = now
        ),
        // Пепперони — острый перец
        DishModifierEntity(
            id = "mod-pepperoni-jalapeno",
            dishId = "dish-pizza-pepperoni",
            name = "+ Холопеньо 10 г",
            priceKopecks = 110L * 100L,
            isRequired = false,
            sortOrder = 0,
            updatedAt = now
        ),
        // Мясная — двойной сыр
        DishModifierEntity(
            id = "mod-meat-cheese",
            dishId = "dish-pizza-meat",
            name = "+ Моцарелла 120 г",
            priceKopecks = 240L * 100L,
            isRequired = false,
            sortOrder = 0,
            updatedAt = now
        )
    )
}
