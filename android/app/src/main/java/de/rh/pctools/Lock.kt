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

    @Volatile private var busy = false
    @Volatile private var busySince = 0L

    /** true = beim Öffnen muss entsperrt werden. */
    fun locked(c: Context) = enabled(c) && System.currentTimeMillis() - unlockedAt >= 120_000

    /** Beim Öffnen: entsperren, wenn die letzte Entsperrung länger als 2 Minuten her ist.
     *  Läuft schon eine Abfrage (z.B. weil Android beim Anzeigen kurz onPause/onResume auslöst), passiert nichts.
     *  Abbruch schließt die App nicht, sondern zeigt einen Sperrbildschirm mit "Entsperren". */
    fun requireOpen(a: Activity, onFail: (() -> Unit)? = null, onOk: () -> Unit) {
        if (!locked(a)) { onOk(); return }
        if (busy && System.currentTimeMillis() - busySince < 30_000) { Diag.add(a, "Entsperren läuft schon"); return }
        auth(a, "PC-Tools entsperren", "Zum Öffnen der App") { ok -> if (ok) onOk() else if (onFail != null) onFail() else showLocked(a, onOk) }
    }

    private fun showLocked(a: Activity, onOk: () -> Unit) {
        if (a.isFinishing || a.isDestroyed) return
        val box = android.widget.LinearLayout(a).apply {
            orientation = android.widget.LinearLayout.VERTICAL; gravity = android.view.Gravity.CENTER; setBackgroundColor(Ui.BG)
            val p = Ui.dp(a, 32); setPadding(p, p, p, p)
        }
        box.addView(Ui.text(a, "PC-Tools ist gesperrt", 22f, true).apply { gravity = android.view.Gravity.CENTER })
        box.addView(Ui.text(a, "Zum Öffnen mit Fingerabdruck, Gesicht oder Handy-PIN entsperren.", 15f, col = Ui.MUTED).apply { gravity = android.view.Gravity.CENTER; setPadding(0, Ui.dp(a, 8), 0, Ui.dp(a, 20)) })
        box.addView(Ui.button(a, "Entsperren") { requireOpen(a) { a.recreate() } })
        a.setContentView(box)
    }

    /** Vor jedem Auftrag: immer bestätigen. */
    fun confirm(a: Activity, title: String, onOk: () -> Unit) {
        if (!enabled(a)) { onOk(); return }
        if (busy && System.currentTimeMillis() - busySince < 30_000) return
        auth(a, title, "Zum Senden des Auftrags bestätigen") { ok -> if (ok) onOk() }
    }

    private fun auth(a: Activity, title: String, sub: String, done0: (Boolean) -> Unit) {
        busy = true; busySince = System.currentTimeMillis()
        Diag.add(a, "Entsperren gestartet (" + title + ")")
        val done: (Boolean) -> Unit = { r -> busy = false; Diag.add(a, if (r) "Entsperrt" else "Entsperren abgebrochen"); done0(r) }
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
            try {
                val b = BiometricPrompt.Builder(a).setTitle(title).setSubtitle(sub)
                if (Build.VERSION.SDK_INT >= 30) {
                    b.setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK or BiometricManager.Authenticators.DEVICE_CREDENTIAL)
                } else {
                    @Suppress("DEPRECATION")
                    b.setDeviceCredentialAllowed(true)
                }
                b.build().authenticate(CancellationSignal(), a.mainExecutor, object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) { ok() }
                    override fun onAuthenticationError(errorCode: Int, errString: CharSequence) { Diag.add(a, "Entsperr-Fehler $errorCode: $errString"); done(false) }
                })
                return
            } catch (e: Exception) { Diag.add(a, "Fingerabdruck-Abfrage nicht möglich: " + e); /* weiter mit der Android-Bildschirmsperre */ }
        }
        try {
            val km = a.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
            @Suppress("DEPRECATION")
            val i = km.createConfirmDeviceCredentialIntent(title, sub)
            if (i == null) { ok(); return }
            pending = { r -> if (r) ok() else done(false) }
            @Suppress("DEPRECATION")
            a.startActivityForResult(i, REQ)
        } catch (e: Exception) { done(false) }
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
