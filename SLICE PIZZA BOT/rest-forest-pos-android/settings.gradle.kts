pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // Sprint 5: DantSu/ESCPOS-ThermalPrinter-Android is only published to JitPack.
        // Narrowed to the `com.github.DantSu` group so we don't shadow Maven Central
        // packages with stale JitPack mirrors.
        maven {
            url = uri("https://jitpack.io")
            content {
                includeGroup("com.github.DantSu")
            }
        }
    }
}

rootProject.name = "RestForestPos"
include(":app")
