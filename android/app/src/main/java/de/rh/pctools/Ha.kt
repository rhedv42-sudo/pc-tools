package de.rh.pctools

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyStore
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Ein PC aus Home Assistant (sensor.pcpflege_<pc>_zustand, gesendet von PC-Tools). */
data class Pc(
    val key: String,
    val name: String,
    val state: String,
    val score: Int,
    val problems: List<String>,
    val lastRun: String,
    val updated: String,
    val windows: String,
    val model: String,
    val version: String,
    val diskFree: String,
    val uptime: String,
    val bitlocker: String,
    val bitlockerLevel: String,
    val bios: String,
    val rebootPending: Boolean,
    val helpOpen: Boolean,
    val helpTime: String,
    val helpMessage: String,
    val helpReport: String,
    val jobsEnabled: Boolean,
    val jobs: List<String>
)

class HaHttpException(val code: Int, msg: String) : Exception(msg)

data class Job(val state: String, val action: String, val message: String, val time: String)

object Ha {
    private const val PREFS = "pctools"
    private const val KEY_ALIAS = "pctools_token_key"

    fun prefs(c: Context) = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun url(c: Context): String = prefs(c).getString("url", "") ?: ""

    fun isSetUp(c: Context) = url(c).isNotBlank() && token(c).isNotBlank()

    fun demo(c: Context) = prefs(c).getBoolean("demo", false)
    fun setDemo(c: Context, on: Boolean) = prefs(c).edit().putBoolean("demo", on).apply()

    fun niceMillis(ms: Long): String = try {
        Instant.ofEpochMilli(ms).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("dd.MM. HH:mm"))
    } catch (e: Exception) { "" }

    /** Zuletzt erfolgreich geladener Stand (zum sofortigen Anzeigen beim Öffnen). */
    fun cached(c: Context): Pair<List<Pc>, Long>? {
        if (demo(c)) return null
        val s = prefs(c).getString("cache", null) ?: return null
        return try { Pair(parseList(JSONArray(s)), prefs(c).getLong("cache_time", 0L)) } catch (e: Exception) { null }
    }

    fun save(c: Context, url: String, token: String) {
        val u = url.trim().trimEnd('/')
        prefs(c).edit().putString("url", u).putString("token", encrypt(token.trim())).apply()
    }

    fun token(c: Context): String {
        val enc = prefs(c).getString("token", "") ?: ""
        if (enc.isBlank()) return ""
        return try { decrypt(enc) } catch (e: Exception) { "" }
    }

    // ---- Token im Android-Keystore verschlüsseln (AES-GCM, Schlüssel verlässt das Gerät nie)
    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(KEY_ALIAS, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        kg.init(
            KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build()
        )
        return kg.generateKey()
    }

    private fun encrypt(plain: String): String {
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.ENCRYPT_MODE, key())
        val out = c.doFinal(plain.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(c.iv, Base64.NO_WRAP) + ":" + Base64.encodeToString(out, Base64.NO_WRAP)
    }

    private fun decrypt(s: String): String {
        val p = s.split(":")
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(p[0], Base64.NO_WRAP)))
        return String(c.doFinal(Base64.decode(p[1], Base64.NO_WRAP)), Charsets.UTF_8)
    }

    // ---- HTTP
    @Volatile private var checkedBase = ""

    private fun request(c: Context, method: String, path: String, body: String? = null, base: String? = null, tok: String? = null): String {
        val b = base ?: url(c)
        if (b.isBlank()) throw Exception("Noch keine Verbindung eingerichtet (Einstellungen).")
        if (b != checkedBase) { Lock.checkUrl(b)?.let { throw Exception(it) }; checkedBase = b }
        val u = URL(b + path)
        val con = u.openConnection() as HttpURLConnection
        con.requestMethod = method
        con.connectTimeout = 10000
        con.readTimeout = 20000
        con.setRequestProperty("Authorization", "Bearer " + (tok ?: token(c)))
        con.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        if (body != null) {
            con.doOutput = true
            con.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
        }
        val code = con.responseCode
        val stream = if (code in 200..299) con.inputStream else con.errorStream
        val text = stream?.bufferedReader()?.use(BufferedReader::readText) ?: ""
        con.disconnect()
        if (code == 401) throw HaHttpException(code, "Home Assistant: Zugangstoken ungültig oder ohne Rechte (401)")
        if (code !in 200..299) throw HaHttpException(code, "Home Assistant: HTTP $code ${text.take(200)}")
        return text
    }

    fun test(c: Context, url: String, token: String): String {
        val t = request(c, "GET", "/api/", base = url.trim().trimEnd('/'), tok = token.trim())
        return JSONObject(t).optString("message", "OK")
    }

    fun loadPcs(c: Context): List<Pc> {
        if (demo(c)) return parseList(demoStates())
        val arr = JSONArray(request(c, "GET", "/api/states"))
        val mine = JSONArray()
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val id = o.optString("entity_id")
            if (id.startsWith("sensor.pcpflege_") && id.endsWith("_zustand")) mine.put(o)
        }
        try { prefs(c).edit().putString("cache", mine.toString()).putLong("cache_time", System.currentTimeMillis()).apply() } catch (_: Exception) { }
        return parseList(mine)
    }

    fun parseList(arr: JSONArray): List<Pc> {
        val list = ArrayList<Pc>()
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val id = o.optString("entity_id")
            if (!id.startsWith("sensor.pcpflege_") || !id.endsWith("_zustand")) continue
            val key = id.removePrefix("sensor.pcpflege_").removeSuffix("_zustand")
            list.add(parse(key, o))
        }
        return list.sortedWith(compareBy<Pc>({ !it.helpOpen }, { rank(it.state) }, { it.name.lowercase() }))
    }

    /** Beispieldaten für die Demo (nichts wird gesendet). */
    private fun demoStates(): JSONArray {
        val now = OffsetDateTime.now()
        fun pc(key: String, name: String, state: String, score: Int, problems: List<String>, model: String, win: String, free: Int, pct: Int, up: Int, bl: String, blLevel: String, minutesAgo: Long, help: JSONObject?): JSONObject {
            val a = JSONObject()
                .put("computer", name).put("score", score).put("problems", JSONArray(problems))
                .put("last_run", now.minusDays(if (state == "Rot") 23 else 1).toLocalDate().toString())
                .put("windows", win).put("model", model).put("version", "14.6.2")
                .put("disk_free_gb", free).put("disk_free_pct", pct).put("uptime_days", up)
                .put("bitlocker", bl).put("bitlocker_level", blLevel).put("bios", "aktuell")
                .put("reboot_pending", state == "Rot").put("jobs_enabled", true)
                .put("jobs", JSONArray(listOf("Status", "Pflege", "Updates", "Aufraeumen", "Virenscan", "Sicherung", "Selbstupdate")))
            if (help != null) a.put("help", help)
            return JSONObject().put("entity_id", "sensor.pcpflege_${key}_zustand").put("state", state)
                .put("last_updated", now.minusMinutes(minutesAgo).toString()).put("attributes", a)
        }
        val help = JSONObject().put("open", true).put("time", now.minusMinutes(11).toString())
            .put("message", "Der Drucker druckt nicht mehr und der PC ist so langsam.")
            .put("report", "Beispiel-Bericht (Demo)\n\nZustand: Rot, Score 48\n• 3 Windows-Updates offen\n• Datensicherung 23 Tage alt\n• Nur noch 18 GB frei auf C:\n\nFehler der letzten 24 Stunden: 2 (Druckwarteschlange)")
        return JSONArray()
            .put(pc("laptop_oma", "LAPTOP-OMA", "Rot", 48, listOf("3 Windows-Updates offen", "Datensicherung 23 Tage alt", "Nur noch 18 GB frei auf C:"), "HP 250 G9", "Windows 11 Home 24H2", 18, 8, 12, "Ein · TPM · Schlüssel: USB, Ausdruck", "OK", 2, help))
            .put(pc("buero_pc", "BUERO-PC", "Gelb", 74, listOf("1 Programm-Update offen"), "Dell OptiPlex 7010", "Windows 11 Pro 25H2", 64, 27, 3, "Ein · Start-Passwort · Schlüssel: PDF", "OK", 6, null))
            .put(pc("wohnzimmer_pc", "WOHNZIMMER-PC", "Grün", 92, emptyList(), "Lenovo ThinkPad T14", "Windows 11 Pro 25H2", 212, 44, 1, "Ein · TPM · Schlüssel: USB, Google Drive", "OK", 1, null))
            .put(pc("kinderzimmer", "KINDERZIMMER", "Grün", 88, emptyList(), "Acer Aspire 5", "Windows 11 Home 25H2", 140, 58, 2, "Aus · nicht verschlüsselt", "Warn", 180, null))
    }

    fun rank(state: String) = when (state) { "Rot" -> 0; "Gelb" -> 1; "Grün" -> 2; else -> 3 }

    private fun strList(a: JSONArray?): List<String> {
        if (a == null) return emptyList()
        return (0 until a.length()).map { a.optString(it) }.filter { it.isNotBlank() }
    }

    private fun parse(key: String, o: JSONObject): Pc {
        val a = o.optJSONObject("attributes") ?: JSONObject()
        val help = a.optJSONObject("help")
        return Pc(
            key = key,
            name = a.optString("computer", key.uppercase()),
            state = o.optString("state", "?"),
            score = a.optInt("score", -1),
            problems = strList(a.optJSONArray("problems")),
            lastRun = a.optString("last_run", ""),
            updated = o.optString("last_updated", a.optString("time", "")),
            windows = a.optString("windows", ""),
            model = a.optString("model", ""),
            version = a.optString("version", ""),
            diskFree = if (a.has("disk_free_gb")) "${a.optString("disk_free_gb")} GB frei (${a.optString("disk_free_pct")} %)" else "",
            uptime = if (a.has("uptime_days")) "${a.optString("uptime_days")} Tage" else "",
            bitlocker = a.optString("bitlocker", ""),
            bitlockerLevel = a.optString("bitlocker_level", ""),
            bios = a.optString("bios", ""),
            rebootPending = a.optBoolean("reboot_pending", false),
            helpOpen = help != null && help.optBoolean("open", false),
            helpTime = help?.optString("time", "") ?: "",
            helpMessage = help?.optString("message", "") ?: "",
            helpReport = help?.optString("report", "") ?: "",
            jobsEnabled = a.optBoolean("jobs_enabled", false),
            jobs = strList(a.optJSONArray("jobs"))
        )
    }

    fun job(c: Context, key: String): Job? {
        if (demo(c)) return null
        return try {
            val o = JSONObject(request(c, "GET", "/api/states/sensor.pcpflege_${key}_auftrag"))
            val a = o.optJSONObject("attributes") ?: JSONObject()
            Job(o.optString("state"), a.optString("action", o.optString("state")), a.optString("message", ""), a.optString("time", o.optString("last_updated")))
        } catch (e: Exception) { null }
    }

    fun sendJob(c: Context, key: String, name: String, action: String) {
        if (demo(c)) throw Exception("Demo: Es wurde nichts gesendet. Richte unter Einstellungen die Verbindung zu Home Assistant ein, um echte Aufträge zu schicken.")
        val now = OffsetDateTime.now().toString()
        val body = JSONObject()
            .put("state", action)
            .put("attributes", JSONObject()
                .put("id", UUID.randomUUID().toString())
                .put("time", now)
                .put("by", "Android " + android.os.Build.MODEL)
                .put("friendly_name", "$name Auftrag")
                .put("icon", "mdi:clipboard-play"))
        try {
            request(c, "POST", "/api/states/sensor.pcpflege_${key}_auftrag", body.toString())
        } catch (e: HaHttpException) {
            if (e.code != 401 && e.code != 403) throw e
            // Token ohne Administratorrechte: Auftrag über den Helfer input_text.pctools_auftrag
            val id = UUID.randomUUID().toString().replace("-", "").take(12)
            val v = "$key|$action|$id|${System.currentTimeMillis() / 1000}"
            try {
                request(c, "POST", "/api/services/input_text/set_value", JSONObject().put("entity_id", "input_text.pctools_auftrag").put("value", v).toString())
            } catch (e2: HaHttpException) {
                throw Exception("Auftrag nicht möglich: Das Token hat keine Administratorrechte und der Helfer „input_text.pctools_auftrag“ fehlt in Home Assistant (Einstellungen > Geräte & Dienste > Helfer > Text, max. Länge 255).")
            }
        }
    }

    fun nice(iso: String): String {
        if (iso.isBlank()) return ""
        return try {
            val t = OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault())
            t.format(DateTimeFormatter.ofPattern("dd.MM. HH:mm"))
        } catch (e: Exception) {
            try { Instant.parse(iso).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("dd.MM. HH:mm")) } catch (e2: Exception) { iso }
        }
    }

    fun jobLabel(a: String) = when (a) {
        "Status" -> "Zustand melden"
        "Pflege" -> "Pflege (Updates + Aufräumen)"
        "Updates" -> "Updates installieren"
        "Aufraeumen" -> "Aufräumen"
        "Virenscan" -> "Virenscan"
        "Sicherung" -> "Datensicherung"
        "Selbstupdate" -> "PC-Tools aktualisieren"
        else -> a
    }
}
