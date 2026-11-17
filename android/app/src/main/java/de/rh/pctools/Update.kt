package de.rh.pctools

import android.content.Context
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL

/** Sucht auf GitHub nach einer neueren App-Version (Releases mit Tag "android-v…"). Es werden keine Daten über dich gesendet. */
object Update {
    data class Info(val version: String, val url: String)

    private fun num(v: String): List<Int> = v.removePrefix("android-v").removePrefix("v").split('.').map { it.filter(Char::isDigit).toIntOrNull() ?: 0 }

    fun newer(a: String, b: String): Boolean {
        val x = num(a); val y = num(b)
        for (i in 0 until maxOf(x.size, y.size)) {
            val p = x.getOrElse(i) { 0 }; val q = y.getOrElse(i) { 0 }
            if (p != q) return p > q
        }
        return false
    }

    /** Netzwerkzugriff – nicht im UI-Thread aufrufen. null = keine neuere Version. */
    fun check(c: Context): Info? {
        val con = URL("https://api.github.com/repos/rhedv42-sudo/pc-tools/releases?per_page=30").openConnection() as HttpURLConnection
        con.connectTimeout = 10000; con.readTimeout = 15000
        con.setRequestProperty("Accept", "application/vnd.github+json")
        con.setRequestProperty("User-Agent", "PC-Tools-App")
        val text = con.inputStream.bufferedReader().use { it.readText() }
        con.disconnect()
        val arr = JSONArray(text)
        var best: Info? = null
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val tag = o.optString("tag_name")
            if (!tag.startsWith("android-v") || o.optBoolean("draft") || o.optBoolean("prerelease")) continue
            val v = tag.removePrefix("android-v")
            if (best == null || newer(v, best.version)) best = Info(v, o.optString("html_url"))
        }
        val cur = BuildConfigLite.version(c)
        val p = Ha.prefs(c).edit().putLong("upd_checked", System.currentTimeMillis())
        return if (best != null && newer(best.version, cur)) { p.putString("upd_ver", best.version).putString("upd_url", best.url).apply(); best }
        else { p.remove("upd_ver").remove("upd_url").apply(); null }
    }

    /** Höchstens einmal am Tag im Hintergrund prüfen. */
    fun due(c: Context) = System.currentTimeMillis() - Ha.prefs(c).getLong("upd_checked", 0L) > 24L * 3600_000

    fun known(c: Context): Info? {
        val v = Ha.prefs(c).getString("upd_ver", null) ?: return null
        if (!newer(v, BuildConfigLite.version(c))) return null
        return Info(v, Ha.prefs(c).getString("upd_url", "") ?: "")
    }
}
