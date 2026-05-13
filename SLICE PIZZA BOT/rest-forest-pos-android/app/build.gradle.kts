plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

android {
    namespace = "ru.slicepizza.restforest"
    compileSdk = libs.versions.compileSdk.get().toInt()

    defaultConfig {
        applicationId = "ru.slicepizza.restforest"
        minSdk = libs.versions.minSdk.get().toInt()
        targetSdk = libs.versions.targetSdk.get().toInt()
        versionCode = 4
        versionName = "0.3.2-iiko-vtb"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables { useSupportLibrary = true }

        // Restaurant tablets are always landscape — locked at activity level too.
        resourceConfigurations += setOf("en", "ru")

        // Backend that exposes LIFE PAY Cloud fiscal endpoints + admin reports.
        val fiscalReceiptBaseUrl: String = (project.findProperty("fiscalReceiptBaseUrl") as String?)
            ?: System.getenv("FISCAL_RECEIPT_BASE_URL")
            ?: "https://slicepizza.ru"
        buildConfigField("String", "FISCAL_RECEIPT_BASE_URL", "\"$fiscalReceiptBaseUrl\"")

        // Sentry DSN — Sprint 38: hardcoded production DSN for slice-pizza-android.
        // Можно override через -PsentryDsn=... или env SENTRY_DSN_ANDROID для CI.
        val sentryDsnDefault =
            "https://8ae8a772026474e1090f2e5b56e386ba@o4511379500433408.ingest.de.sentry.io/4511379556270160"
        val sentryDsn: String = (project.findProperty("sentryDsn") as String?)
            ?: System.getenv("SENTRY_DSN_ANDROID")
            ?: sentryDsnDefault
        buildConfigField("String", "SENTRY_DSN", "\"$sentryDsn\"")
    }

    // Production-Hardening — release signing.
    // Keystore + пароли НЕ коммитятся (см. keystore/.gitignore).
    // Build падает с ясной ошибкой если keystore отсутствует, вместо silent fallback на debug.
    signingConfigs {
        create("release") {
            val keystoreFile = rootProject.file("keystore/slice-pizza-release.jks")
            if (keystoreFile.exists()) {
                storeFile = keystoreFile
                storePassword = System.getenv("KEYSTORE_PASSWORD") ?: ""
                keyAlias = "slice-pizza"
                keyPassword = System.getenv("KEY_PASSWORD") ?: ""
                enableV1Signing = true
                enableV2Signing = true
                enableV3Signing = true
                enableV4Signing = true
            }
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
            // Sprint 3.2 — production backend over HTTPS, local dev can swap
            // to http://10.0.2.2:8000 via overriding strings.xml.
            buildConfigField("String", "BACKEND_BASE_URL", "\"https://slicepizza.ru/api/admin/\"")
            buildConfigField("String", "BACKEND_ADMIN_TOKEN", "\"f4jXd968ohSVSZpUtOq4WA0ZisDVHLD024jTPFExOjg\"")
            // ВТБ acquiring — реальный pinpad (INPAS) appears in Sprint 7 after NDA.
            buildConfigField("boolean", "CARD_PINPAD_ENABLED", "false")
            // Sprint 7: pinpad adapter mode. "mock" → MockPinpadAdapter (DEV/tests);
            // "real" → InpasPinpadAdapter (after INPAS NDA + SDK is dropped in).
            buildConfigField("String", "PINPAD_MODE", "\"mock\"")
            buildConfigField("boolean", "DEBUG_MODE", "true")
            buildConfigField("String", "SENTRY_ENVIRONMENT", "\"debug\"")
        }
        release {
            // Production-Hardening — R8 minify + resource shrinking
            isMinifyEnabled = true
            isShrinkResources = true
            buildConfigField("String", "BACKEND_BASE_URL", "\"https://slicepizza.ru/api/admin/\"")
            buildConfigField("String", "BACKEND_ADMIN_TOKEN", "\"\"")
            buildConfigField("boolean", "CARD_PINPAD_ENABLED", "false")
            buildConfigField("String", "PINPAD_MODE", "\"mock\"")
            buildConfigField("boolean", "DEBUG_MODE", "false")
            buildConfigField("String", "SENTRY_ENVIRONMENT", "\"production\"")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // Apply release signing only when keystore present.
            val keystoreFile = rootProject.file("keystore/slice-pizza-release.jks")
            if (keystoreFile.exists()) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
        freeCompilerArgs += listOf(
            "-Xjvm-default=all",
            "-opt-in=kotlinx.coroutines.ExperimentalCoroutinesApi",
            "-opt-in=androidx.compose.material3.ExperimentalMaterial3Api",
            "-opt-in=androidx.compose.foundation.ExperimentalFoundationApi"
        )
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
        unitTests.isReturnDefaultValues = true
    }

    ksp {
        arg("room.schemaLocation", "$projectDir/schemas")
        arg("room.incremental", "true")
    }
}

dependencies {
    // Core AndroidX
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.core.splashscreen)

    // Compose
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material3.window.size)
    implementation(libs.androidx.material.icons.extended)
    implementation(libs.androidx.navigation.compose)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)

    // Hilt
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.androidx.hilt.navigation.compose)

    // Room
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    // DataStore
    implementation(libs.androidx.datastore.preferences)

    // Retrofit + OkHttp (Sprint 3.2: backend wiring to slicepizza.ru/api/admin)
    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp.logging)
    implementation(libs.kotlinx.serialization.json)

    // Coil for menu images (Supabase storage URLs)
    implementation(libs.coil.compose)

    // Coroutines
    implementation(libs.kotlinx.coroutines.android)

    // BCrypt — PIN hashing
    implementation(libs.bcrypt)

    // Sprint 5: KDS + ESC/POS printing -----------------------------------
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.androidx.hilt.work)
    ksp(libs.androidx.hilt.compiler)
    implementation(libs.escpos.thermal.printer.android)

    // Production-Hardening — Sentry crash + ANR + native crash reporting.
    // sentry-android-okhttp инструментирует Retrofit, добавляет breadcrumb
    // на каждый HTTP request. Timber tree → logs as breadcrumbs.
    implementation(libs.sentry.android)
    implementation(libs.sentry.android.okhttp)
    implementation(libs.sentry.android.timber)

    // Timber for structured logging + file persistence (FileLoggingTree in prod).
    implementation(libs.timber)

    // Sprint 7: unit tests for pinpad adapter, cash drawer, print queue,
    // receipt customization. Robolectric so Context-bound code (DataStore,
    // CashDrawerService) can run on the JVM without an emulator.
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.core)
    testImplementation(libs.androidx.test.ext.junit)
    testImplementation(libs.androidx.room.testing)
}
