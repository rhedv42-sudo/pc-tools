plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val appVersionName = (System.getenv("PCT_VERSION") ?: "1.0.0")
val appVersionCode = (System.getenv("PCT_VERSION_CODE") ?: "1").toInt()
val ksFile = System.getenv("PCT_KEYSTORE")

android {
    namespace = "de.rh.pctools"
    compileSdk = 35
    defaultConfig {
        applicationId = "de.rh.pctools"
        minSdk = 26
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersionName
    }
    signingConfigs {
        if (ksFile != null && file(ksFile).exists()) {
            create("release") {
                storeFile = file(ksFile)
                storeType = System.getenv("PCT_STORE_TYPE") ?: "PKCS12"
                storePassword = System.getenv("PCT_KEYSTORE_PASS")
                keyAlias = System.getenv("PCT_KEY_ALIAS") ?: "pctools"
                keyPassword = System.getenv("PCT_KEY_PASS") ?: System.getenv("PCT_KEYSTORE_PASS")
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (ksFile != null && file(ksFile).exists()) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
