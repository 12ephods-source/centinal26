plugins {
    id("com.android.application")
}

android {
    namespace = "com.frost.bluetoothguard"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.frost.bluetoothguard"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
