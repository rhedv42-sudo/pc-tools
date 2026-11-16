package de.rh.pctools

import android.app.Activity
import android.app.AlertDialog
import android.app.KeyguardManager
import android.content.Context
import android.hardware.biometrics.BiometricManager
import android.hardware.biometrics.BiometricPrompt
import android.os.Build
import android.os.CancellationSignal
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress
import java.net.URI

/** App-Sperre (Fingerabdruck/Gesicht oder Handy-PIN) und Prüfung der Verbindung. */
object Lock {
    private const val REQ = 4712
    private var unlockedAt = 0L
    private var pending: ((Boolean) -> Unit)? = null

    fun enabled(c: Context) = Ha.prefs(c).getBoolean("lock", true)
    fun setEnabled(c: Context, on: Boolean) = Ha.prefs(c).edit().putBoolean("lock", on).apply()

    fun deviceSecure(c: Context) = (c.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager).isDeviceSecure

    /** Beim Öffnen: entsperren, wenn die letzte Entsperrung länger als 2 Minuten her ist. */
    fun requireOpen(a: Activity, onOk: () -> Unit) {
        if (!enabled(a) || System.currentTimeMillis() - unlockedAt < 120_000) { onOk(); return }
        auth(a, "PC-Tools entsperren", "Zum Öffnen der App") { ok -> if (ok) onOk() else a.finishAffinity() }
    }

    /** Vor jedem Auftrag: immer bestätigen. */
    fun confirm(a: Activity, title: String, onOk: () -> Unit) {
        if (!enabled(a)) { onOk(); return }
        auth(a, title, "Zum Senden des Auftrags bestätigen") { ok -> if (ok) onOk() }
    }

    private fun auth(a: Activity, title: String, sub: String, done: (Boolean) -> Unit) {
        if (!deviceSecure(a)) {
            AlertDialog.Builder(a).setTitle("Keine Displaysperre")
                .setMessage("Für die App-Sperre braucht das Handy eine Displaysperre (PIN, Muster oder Passwort, gern mit Fingerabdruck). Bitte in den Android-Einstellungen unter Sicherheit einrichten.\n\nSo lange ist die App ungeschützt.")
                .setPositiveButton("Trotzdem weiter") { _, _ -> unlockedAt = System.currentTimeMillis(); done(true) }
                .setNegativeButton("Abbrechen") { _, _ -> done(false) }
                .setCancelable(false).show()
            return
        }
        val ok: () -> Unit = { unlockedAt = System.currentTimeMillis(); done(true) }
        if (Build.VERSION.SDK_INT >= 28) {
            val b = BiometricPrompt.Builder(a).setTitle(title).setSubtitle(sub)
            if (Build.VERSION.SDK_INT >= 30) {
                b.setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK or BiometricManager.Authenticators.DEVICE_CREDENTIAL)
            } else {
                @Suppress("DEPRECATION")
                b.setDeviceCredentialAllowed(true)
            }
            b.build().authenticate(CancellationSignal(), a.mainExecutor, object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) { ok() }
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) { done(false) }
            })
        } else {
            val km = a.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
            @Suppress("DEPRECATION")
            val i = km.createConfirmDeviceCredentialIntent(title, sub)
            if (i == null) { ok(); return }
            pending = { r -> if (r) ok() else done(false) }
            @Suppress("DEPRECATION")
            a.startActivityForResult(i, REQ)
        }
    }

    /** Aus onActivityResult der Activities aufrufen (nur Android 8/8.1). */
    fun onResult(requestCode: Int, resultCode: Int): Boolean {
        if (requestCode != REQ) return false
        val p = pending; pending = null
        p?.invoke(resultCode == Activity.RESULT_OK)
        return true
    }

    // ---- Verbindung: http nur im Heimnetz, sonst https
    fun isPrivate(addr: InetAddress): Boolean {
        if (addr.isLoopbackAddress || addr.isSiteLocalAddress || addr.isLinkLocalAddress) return true
        if (addr is Inet4Address) { val b = addr.address; val x = b[0].toInt() and 255; val y = b[1].toInt() and 255; return x == 100 && y in 64..127 }
        if (addr is Inet6Address) { val x = addr.address[0].toInt() and 0xFE; return x == 0xFC }
        return false
    }

    /** Liefert null, wenn die Adresse in Ordnung ist, sonst eine Fehlermeldung. Netzwerkzugriff - nicht im UI-Thread aufrufen. */
    fun checkUrl(url: String): String? {
        val u = try { URI(url) } catch (e: Exception) { return "Die Adresse ist ungültig." }
        val host = u.host ?: return "Die Adresse ist ungültig."
        if (u.scheme.equals("https", true)) return null
        if (!u.scheme.equals("http", true)) return "Die Adresse muss mit http:// oder https:// beginnen."
        val local = host.endsWith(".local", true) || host.endsWith(".lan", true) || host.endsWith(".home.arpa", true) || host.endsWith(".internal", true) || host.endsWith(".fritz.box", true) || !host.contains('.')
        val addrs = try { InetAddress.getAllByName(host).toList() } catch (e: Exception) { return if (local) null else "Die Adresse $host ist nicht erreichbar." }
        if (addrs.isNotEmpty() && addrs.all { isPrivate(it) }) return null
        return "Unverschlüsseltes http:// ist nur im Heimnetz erlaubt (z.B. http://192.168.1.10:8123). Von unterwegs bitte die https://-Adresse nutzen (z.B. Nabu Casa: https://….ui.nabu.casa) – sonst würde das Zugangstoken unverschlüsselt durchs Internet gehen."
    }
}
