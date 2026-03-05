# Release Readiness Checklist

This checklist must be completed before the Kin Flutter App is considered production-ready.

### 1. Signing Key Management

- [ ] A production Android Keystore (`.jks` or `.keystore`) has been generated using `keytool`.
- [ ] The keystore file is stored securely (e.g., in a secure cloud vault or CI secret manager) and is **never** committed to version control.
- [ ] `android/app/build.gradle.kts` is configured to read the signing credentials (`KEYSTORE_PATH`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`) from environment variables, rather than hardcoded strings. If environment variables are missing during local development, the build should safely fall back to the debug key.

### 2. ProGuard/R8 Obfuscation Rules

- [ ] The Flutter app relies on R8 for code shrinking and obfuscation (`minifyEnabled true` and `shrinkResources true` in the `release` build type).
- [ ] Explicit ProGuard rules are configured in `android/app/proguard-rules.pro` to preserve the `flutter_background_geolocation` classes. This prevents the plugin's background services and event buses from being erroneously stripped or renamed by R8.
  - Required rules ensure classes under `com.transistorsoft.**` and `org.greenrobot.eventbus.**` are preserved.

### 3. App Icon and Splash Screen Assets

- [ ] All required app icon resolutions are generated and placed in the appropriate `android/app/src/main/res/mipmap-*` directories.
- [ ] A production-grade splash screen is configured natively (e.g., using `flutter_native_splash` or standard Android drawable configurations) so it appears immediately upon app launch while the Flutter engine initializes.

### 4. Version Naming Convention

- [ ] The app adheres to Semantic Versioning (SemVer) format (e.g., `1.0.0`).
- [ ] `pubspec.yaml` defines the version as `MAJOR.MINOR.PATCH+BUILD` (e.g., `1.0.0+1`).
- [ ] CI/CD processes automatically increment the `build` number for every release candidate to ensure uniqueness in the Google Play Console or direct APK distribution.

### 5. QR Pairing Flow End-to-End

- [ ] **Parent Dashboard (React)**: An "Add Device" button triggers a `POST /auth/generate-pairing-token` request. The returned token (valid for 10 minutes) is displayed as a QR code using a library like `qrcode.react`.
- [ ] **Child Device (Flutter)**: The onboarding screen features a QR code scanner (using a reliable package like `mobile_scanner`).
- [ ] **Device Registration**: Upon scanning, the Flutter app calls `POST /auth/pair-device` with the token. The server responds with a device-scoped JWT, the server URL, and the MQTT broker address.
- [ ] **Secure Storage**: The Flutter app stores the JWT, server URL, and MQTT broker address securely using `EncryptedSharedPreferences` (e.g., via `flutter_secure_storage`).
- [ ] **Zero Hardcoded URLs**: The Flutter codebase no longer contains any hardcoded staging or production server URLs. All network traffic dynamically uses the configuration retrieved during pairing.
