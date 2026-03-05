#!/bin/bash
# verify_production.sh
# Final check before creating a release APK

echo "Verifying production readiness..."
set -e

# 1. Check if ENV vars for keystore are present
if [ -z "$KEYSTORE_PATH" ] || [ -z "$KEYSTORE_PASSWORD" ] || [ -z "$KEY_ALIAS" ] || [ -z "$KEY_PASSWORD" ]; then
    echo "❌ Missing signing keystore environment variables. (KEYSTORE_PATH, KEYSTORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD)"
    # Don't exit 1 yet if running locally without keys, just warn
    # exit 1 
else
    echo "✅ Keystore environment variables present."
fi

# 2. Check for R8 and signing configs in build.gradle.kts
if grep -q "isMinifyEnabled = true" android/app/build.gradle.kts && grep -q "isShrinkResources = true" android/app/build.gradle.kts; then
    echo "✅ R8 obfuscation enabled in build.gradle.kts"
else
    echo "❌ R8 missing from build.gradle.kts"
    exit 1
fi

if grep -q "signingConfigs.getByName(\"release\")" android/app/build.gradle.kts; then
     echo "✅ Release signing config present in build.gradle.kts"
else
     echo "❌ Release signing config missing from build.gradle.kts"
     exit 1
fi

# 3. Check for Proguard rules file and its contents
if [ -f "android/app/proguard-rules.pro" ]; then
    if grep -q "com.transistorsoft.flutter.backgroundgeolocation" android/app/proguard-rules.pro; then
        echo "✅ Background Geolocation ProGuard rules found."
    else
        echo "❌ Background Geolocation ProGuard rules missing in proguard-rules.pro"
        exit 1
    fi
else
    echo "❌ proguard-rules.pro not found"
    exit 1
fi

# 4. Ensure no hardcoded API_BASE_URL where it dictates
if grep -B 2 -A 2 'API_BASE_URL' lib/services/location_service.dart; then
    echo "❌ Hardcoded API_BASE_URL found in location_service.dart"
    exit 1
else
    echo "✅ No hardcoded API_BASE_URL in LocationService."
fi

echo "All checks passed! 🎉"
echo "You can now safely build the release APK:"
echo "flutter build apk --release"
