package com.example.kin

import android.accounts.Account
import android.accounts.AccountManager
import android.content.Context
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * MainActivity — extends FlutterActivity and exposes a MethodChannel so Dart
 * can read/write credentials from Android AccountManager.
 *
 * AccountManager data survives app uninstall/reinstall (unless the user
 * explicitly goes to Settings > Apps > Kin > Clear Data or removes the account
 * via Settings > Accounts).  This is the standard Android pattern for
 * persistent credentials.
 */
class MainActivity : FlutterActivity() {

    companion object {
        private const val CHANNEL = "com.example.kin/device_identity"
        private const val ACCOUNT_TYPE = "com.example.kin"
        private const val ACCOUNT_NAME = "kin_device"
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {

                // ── Save credentials into AccountManager ──────────────────
                "saveCredentials" -> {
                    val args = call.arguments as Map<*, *>
                    val am = AccountManager.get(this)
                    var account = getOrCreateAccount(am)
                    args.forEach { (k, v) ->
                        if (k != null && v != null) {
                            am.setUserData(account, k.toString(), v.toString())
                        }
                    }
                    result.success(true)
                }

                // ── Read a single credential from AccountManager ──────────
                "readCredential" -> {
                    val key = call.argument<String>("key")
                    if (key == null) { result.error("NULL_KEY", "Key must not be null", null); return@setMethodCallHandler }
                    val am = AccountManager.get(this)
                    val account = findAccount(am)
                    val value = account?.let { am.getUserData(it, key) }
                    result.success(value)
                }

                // ── Clear all stored credentials ──────────────────────────
                // NOTE: this should ONLY be called from a parent request,
                // never from the child app UI.
                "clearCredentials" -> {
                    val am = AccountManager.get(this)
                    val account = findAccount(am)
                    if (account != null) {
                        @Suppress("DEPRECATION")
                        am.removeAccount(account, null, null)
                    }
                    result.success(true)
                }

                // ── Get the permanent hardware fingerprint ────────────────
                // Uses ANDROID_ID: unique per (device, user, signing key).
                // Stable across reinstalls of the same signed APK.
                "getHardwareId" -> {
                    val androidId = Settings.Secure.getString(
                        contentResolver,
                        Settings.Secure.ANDROID_ID
                    ) ?: "unknown"
                    result.success(androidId)
                }

                // ── Check whether credentials exist ──────────────────────
                "isPaired" -> {
                    val am = AccountManager.get(this)
                    val account = findAccount(am)
                    val token = account?.let { am.getUserData(it, "access_token") }
                    result.success(!token.isNullOrEmpty())
                }

                else -> result.notImplemented()
            }
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private fun getOrCreateAccount(am: AccountManager): Account {
        return findAccount(am) ?: run {
            val account = Account(ACCOUNT_NAME, ACCOUNT_TYPE)
            am.addAccountExplicitly(account, null, null)
            account
        }
    }

    private fun findAccount(am: AccountManager): Account? {
        return try {
            am.getAccountsByType(ACCOUNT_TYPE).firstOrNull()
        } catch (e: Exception) {
            null
        }
    }
}
