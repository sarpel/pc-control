// Top-level build file where you can add configuration options common to all sub-projects/modules.
buildscript {
    extra.apply {
        set("compose_version", "1.5.4")
        set("compose_bom_version", "2023.10.01")
        set("kotlin_version", "1.9.20")  // Updated for Compose compatibility
        set("hilt_version", "2.47")
        set("room_version", "2.5.0")
        set("okhttp_version", "4.12.0")
    }
}
plugins {
    id("com.android.application") version "8.1.2" apply false
    id("com.android.library") version "8.1.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.20" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "1.9.20" apply false
    id("com.google.devtools.ksp") version "1.9.20-1.0.14" apply false
    id("com.google.dagger.hilt.android") version "2.47" apply false
    id("io.gitlab.arturbosch.detekt") version "1.23.0" apply false
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}