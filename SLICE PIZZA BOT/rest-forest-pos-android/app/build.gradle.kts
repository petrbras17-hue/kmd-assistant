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
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
            // Sprint 3.2 — production backend over HTTPS, local dev can swap
            // to http://10.0.2.2:8000 via overriding strings.xml.
            buildConfigField("String", "BACKEND_BASE_URL", "\"https://slicepizza.ru/api/admin/\"")
            buildConfigField("String", "BACKEND_ADMIN_TOKEN", "\"9a143e16d5b324923192843b0c741c410523ff650322b4428709a08fe428df54\"")
            // ВТБ acquiring — реальный pinpad (INPAS) appears in Sprint 7 after NDA.
            buildConfigField("boolean", "CARD_PINPAD_ENABLED", "false")
        }
        release {
            isMinifyEnabled = false
            // Release signing intentionally deferred to Sprint 10 (beta release).
            buildConfigField("String", "BACKEND_BASE_URL", "\"https://slicepizza.ru/api/admin/\"")
            buildConfigField("String", "BACKEND_ADMIN_TOKEN", "\"\"")
            buildConfigField("boolean", "CARD_PINPAD_ENABLED", "false")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
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
}
