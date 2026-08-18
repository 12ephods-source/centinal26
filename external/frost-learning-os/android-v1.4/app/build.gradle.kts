plugins { id("com.android.application") }

android {
    namespace = "com.robertfrost.learningos"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.robertfrost.learningos"
        minSdk = 26
        targetSdk = 35
        versionCode = 14
        versionName = "1.4"
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }
}
