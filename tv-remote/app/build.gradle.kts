plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// versionCode = CI run number so every published APK installs over the previous one.
val buildNumber = (System.getenv("BUILD_NUMBER") ?: "1").toInt()
val baseVersion = rootProject.file("VERSION").readText().trim()

android {
    namespace = "com.bm85.tvremote"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.bm85.tvremote"
        minSdk = 26
        targetSdk = 35
        versionCode = buildNumber
        versionName = "$baseVersion.$buildNumber"
    }

    signingConfigs {
        create("release") {
            storeFile = file("tvremote.keystore")
            storePassword = "tvremote"
            keyAlias = "tvremote"
            keyPassword = "tvremote"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    packaging {
        resources {
            excludes += setOf("META-INF/versions/9/OSGI-INF/MANIFEST.MF", "META-INF/{AL2.0,LGPL2.1}")
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    // Self-signed client certificate for the Android TV Remote protocol
    implementation("org.bouncycastle:bcpkix-jdk18on:1.79")
}
