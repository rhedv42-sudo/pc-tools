package de.rh.pctools

import android.app.NotificationManager
import android.content.Context
import android.os.Build
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** Kleines Protokoll (nur auf dem Handy), damit sich Probleme ohne Rätselraten finden lassen. Kein Token, keine Adresse im Klartext. */
object Diag {
    private val fmt = DateTimeFormatter.ofPattern("dd.MM. HH:mm:ss")

    @Synchronized
    fun add(c: Context, msg: String) {
        try {
            val p = Ha.prefs(c)
            val old = p.getString("diag", "") ?: ""
            val lines = (old.split('\n').filter { it.isNotBlank() } + (LocalDateTime.now().format(fmt) + "  " + msg.take(300))).takeLast(80)
            p.edit().putString("diag", lines.joinToString("\n")).apply()
        } catch (_: Exception) { }
    }

    fun log(c: Context): String = Ha.prefs(c).getString("diag", "") ?: ""

    fun clear(c: Context) = Ha.prefs(c).edit().remove("diag").apply()

    fun hostShort(u: String): String = try {
        val h = java.net.URI(u).host ?: "?"
        val s = java.net.URI(u).scheme ?: "?"
        s + "://" + (if (h.length > 16) h.take(4) + "…" + h.takeLast(10) else h)
    } catch (e: Exception) { "?" }

    fun report(c: Context): String = buildString {
        append("PC-Tools-App ").append(BuildConfigLite.version(c)).append('\n')
        append("Android ").append(Build.VERSION.RELEASE).append(" (API ").append(Build.VERSION.SDK_INT).append(") · ").append(Build.MANUFACTURER).append(' ').append(Build.MODEL).append('\n')
        val u = Ha.url(c)
        append("Verbindung: ").append(if (u.isBlank()) "nicht eingerichtet" else hostShort(u)).append(" · Token: ").append(if (Ha.token(c).isBlank()) "fehlt" else "gespeichert").append('\n')
        append("App-Sperre: ").append(if (Lock.enabled(c)) "an" else "aus").append(" · Displaysperre: ").append(if (Lock.deviceSecure(c)) "ja" else "nein").append(" · Demo: ").append(if (Ha.demo(c)) "an" else "aus").append('\n')
        val nm = c.getSystemService(NotificationManager::class.java)
        append("Benachrichtigungen: ").append(if (nm != null && nm.areNotificationsEnabled()) "erlaubt" else "nicht erlaubt").append('\n')
        val ct = Ha.prefs(c).getLong("cache_time", 0L)
        append("Letzter erfolgreicher Abruf: ").append(if (ct > 0) Ha.niceMillis(ct) else "noch keiner").append('\n')
        append("\nProtokoll:\n").append(log(c))
    }
}
