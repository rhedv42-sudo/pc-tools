package de.rh.pctools

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import javax.net.ssl.SSLException

/** Startseite: zeigt sofort etwas an – gespeicherten Stand, Willkommen, Demo oder eine verständliche Fehlermeldung. */
class MainActivity : Activity() {
    private lateinit var top: LinearLayout      // Hinweise oben (Demo, Update, Fehler, Sperre)
    private lateinit var status: TextView
    private lateinit var progress: ProgressBar
    private lateinit var list: LinearLayout
    @Volatile private var loading = false
    private lateinit var heroTitle: TextView
    private lateinit var heroStats: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "PC-Tools"
        if (intent?.getBooleanExtra("demo_test", false) == true) Ha.setDemo(this, true)
        Diag.add(this, "App gestartet (" + BuildConfigLite.version(this) + ", Android " + Build.VERSION.RELEASE + ")")
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Ui.BG); val p = Ui.dp(this@MainActivity, 14); setPadding(p, p, p, p) }
        val bar = Ui.hero(this, R.drawable.ic_s_pcs, "Meine PCs", "Wird vorbereitet …")
        status = bar.findViewWithTag("sub")
        heroTitle = bar.findViewWithTag("title")
        progress = ProgressBar(this).apply { isIndeterminate = true; visibility = View.GONE; indeterminateTintList = android.content.res.ColorStateList.valueOf(android.graphics.Color.WHITE); layoutParams = LinearLayout.LayoutParams(Ui.dp(this@MainActivity, 22), Ui.dp(this@MainActivity, 22)) }
        (bar.getChildAt(0) as LinearLayout).addView(progress)
        heroStats = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; visibility = View.GONE }
        bar.addView(heroStats)
        top = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, Ui.dp(this@MainActivity, 8), 0, 0) }
        list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(bar); root.addView(top); root.addView(list)
        setContentView(Ui.screen(this, root))

        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        try { CheckJob.schedule(this) } catch (e: Exception) { Diag.add(this, "Hintergrund-Prüfung nicht möglich: $e") }
        Ha.prefs(this).getString("crash", null)?.let { c ->
            Ha.prefs(this).edit().remove("crash").apply()
            AlertDialog.Builder(this).setTitle("Die App ist zuletzt abgestürzt")
                .setMessage("Das tut mir leid. Bitte diesen Text kopieren und als Fehler melden (Menü ⋮ > Über die App > Fehler melden):\n\n" + c)
                .setPositiveButton("Kopieren") { _, _ -> Ui.copy(this, "PC-Tools-App Absturz", c) }
                .setNegativeButton("Schließen", null).show()
        }
        // Sofort etwas zeigen: gespeicherter Stand
        Ha.cached(this)?.let { (pcs, t) -> show(pcs, "Gespeicherter Stand vom " + Ha.niceMillis(t)) }
    }

    override fun onResume() {
        super.onResume()
        invalidateOptionsMenu()
        if (!Ha.demo(this) && !Ha.isSetUp(this)) { showWelcome(); return }
        if (!Ha.demo(this) && Lock.locked(this)) {
            showLockedHint()
            Lock.requireOpen(this, onFail = { showLockedHint() }) { top.removeAllViews(); load() }
            return
        }
        load()
        if (Update.due(this)) Thread { try { Update.check(this); runOnUiThread { showTopHints() } } catch (_: Exception) { } }.start()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (!Lock.onResult(requestCode, resultCode)) super.onActivityResult(requestCode, resultCode, data)
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, "Aktualisieren").setShowAsAction(MenuItem.SHOW_AS_ACTION_ALWAYS)
        menu.add(0, 2, 1, "Einstellungen")
        menu.add(0, 3, 2, "Hilfe & FAQ")
        menu.add(0, 4, 3, if (Ha.demo(this)) "Demo beenden" else "Demo ansehen")
        menu.add(0, 5, 4, "Über die App")
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        when (item.itemId) {
            1 -> if (!Ha.demo(this) && !Ha.isSetUp(this)) showWelcome() else if (!Ha.demo(this) && Lock.locked(this)) Lock.requireOpen(this, onFail = { showLockedHint() }) { load() } else load()
            2 -> openSettings()
            3 -> startActivity(Intent(this, HelpActivity::class.java))
            4 -> { Ha.setDemo(this, !Ha.demo(this)); Diag.add(this, if (Ha.demo(this)) "Demo an" else "Demo aus"); invalidateOptionsMenu(); list.removeAllViews(); onResume() }
            5 -> startActivity(Intent(this, AboutActivity::class.java))
        }
        return true
    }

    private fun openSettings() {
        val go = { startActivity(Intent(this, SetupActivity::class.java)) }
        if (Ha.isSetUp(this)) Lock.confirm(this, "Einstellungen öffnen") { go() } else go()
    }

    // ---------------------------------------------------------------- Zustände
    private fun showWelcome() {
        status.text = "Noch nicht eingerichtet"; heroTitle.text = "Willkommen"; heroStats.visibility = View.GONE
        top.removeAllViews(); list.removeAllViews()
        val c = Ui.card(this)
        c.addView(Ui.heading(this, R.drawable.ic_s_pcs, Ui.BLUE, "Willkommen bei der PC-Tools-App"))
        c.addView(Ui.text(this, "Die App zeigt dir alle PCs, die PC-Tools pflegt – mit Ampel, Hilferufen und Hinweisen – und schickt Aufträge wie Pflege oder Updates. Die Daten kommen über deinen eigenen Home Assistant, nicht über eine fremde Cloud.", 15f, col = Ui.MUTED).apply { setPadding(0, Ui.dp(this@MainActivity, 6), 0, Ui.dp(this@MainActivity, 10)) })
        c.addView(Ui.button(this, "Verbindung einrichten", true, R.drawable.ic_s_link) { startActivity(Intent(this, SetupActivity::class.java)) })
        c.addView(Ui.button(this, "Erst mal Demo ansehen", false, R.drawable.ic_s_play) { Ha.setDemo(this, true); invalidateOptionsMenu(); load() })
        c.addView(Ui.button(this, "Anleitung & FAQ", false, R.drawable.ic_s_book) { startActivity(Intent(this, HelpActivity::class.java)) })
        list.addView(c)
        val n = Ui.card(this)
        n.addView(Ui.heading(this, R.drawable.ic_s_checkcircle, Ui.GREEN, "Was du brauchst"))
        for ((ic, t) in listOf(R.drawable.ic_s_windows to "PC-Tools 14.6 oder neuer auf den PCs, mit „Home Assistant direkt“ (Meine PCs > Anbindung)", R.drawable.ic_s_server to "Home Assistant – zu Hause oder über Nabu Casa", R.drawable.ic_s_key to "Ein langlebiges Zugangstoken aus Home Assistant"))
            n.addView(LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, Ui.dp(this@MainActivity, 5), 0, Ui.dp(this@MainActivity, 5))
                addView(Ui.tile(this@MainActivity, ic, Ui.PURPLE, 30)); addView(Ui.text(this@MainActivity, t, 14f).apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) }) })
        list.addView(n)
    }

    private fun showLockedHint() {
        status.text = "Gesperrt"; heroStats.visibility = View.GONE
        top.removeAllViews()
        val c = Ui.card(this)
        c.addView(Ui.heading(this, R.drawable.ic_s_lock, Ui.BLUE, "PC-Tools ist gesperrt"))
        c.addView(Ui.text(this, "Zum Öffnen mit Fingerabdruck, Gesicht oder Handy-PIN entsperren.", 14f, col = Ui.MUTED).apply { setPadding(0, Ui.dp(this@MainActivity, 4), 0, Ui.dp(this@MainActivity, 6)) })
        c.addView(Ui.button(this, "Entsperren", true, R.drawable.ic_s_finger) { Lock.requireOpen(this, onFail = { showLockedHint() }) { top.removeAllViews(); load() } })
        top.addView(c)
        list.removeAllViews()
    }

    private fun load() {
        if (loading) return
        loading = true
        progress.visibility = View.VISIBLE
        heroTitle.text = if (Ha.demo(this)) "Demo" else heroTitle.text
        status.text = if (Ha.demo(this)) "Demo wird geladen …" else "Lade von " + Diag.hostShort(Ha.url(this)) + " …"
        Diag.add(this, "Laden gestartet")
        Thread {
            try {
                val pcs = Ha.loadPcs(this)
                Diag.add(this, "Geladen: ${pcs.size} PC(s)")
                runOnUiThread { loading = false; progress.visibility = View.GONE; show(pcs, null) }
            } catch (e: Throwable) {
                Diag.add(this, "Laden fehlgeschlagen: $e")
                runOnUiThread { loading = false; progress.visibility = View.GONE; showError(e) }
            }
        }.start()
    }

    private fun showTopHints() {
        top.removeAllViews()
        if (Ha.demo(this)) {
            val c = Ui.card(this).apply { background = (background as android.graphics.drawable.GradientDrawable).apply { setColor(0xFFFFF7ED.toInt()); setStroke(Ui.dp(this@MainActivity, 1), 0xFFFED7AA.toInt()) } }
            c.addView(Ui.heading(this, R.drawable.ic_s_play, 0xFFEA580C.toInt(), "Demo – Beispieldaten"))
            c.addView(Ui.text(this, "So sieht die App mit vier PCs aus. Aufträge werden in der Demo nicht gesendet.", 14f, col = 0xFF9A3412.toInt()))
            c.addView(Ui.button(this, "Demo beenden", false) { Ha.setDemo(this, false); invalidateOptionsMenu(); list.removeAllViews(); onResume() })
            top.addView(c)
        }
        Update.known(this)?.let { u ->
            val c = Ui.card(this)
            c.addView(Ui.heading(this, R.drawable.ic_s_download, Ui.BLUE, "Neue App-Version ${u.version}", "Updates lassen sich jetzt einfach drüber installieren."))
            c.addView(Ui.button(this, "Ansehen und herunterladen", true, R.drawable.ic_s_download) { Ui.open(this, u.url) })
            top.addView(c)
        }
    }

    private fun show(pcs: List<Pc>, note: String?) {
        showTopHints()
        list.removeAllViews()
        status.text = note ?: ((if (Ha.demo(this)) "Demo · " else "") + "Stand " + java.time.LocalTime.now().withNano(0).withSecond(0))
        heroTitle.text = if (pcs.isEmpty()) "Meine PCs" else if (pcs.size == 1) "1 PC im Blick" else "${pcs.size} PCs im Blick"
        heroStats.removeAllViews()
        if (pcs.isEmpty()) {
            heroStats.visibility = View.GONE
            val c = Ui.card(this)
            c.addView(Ui.heading(this, R.drawable.ic_s_wifi, Ui.GREEN, "Verbunden – noch keine PCs", "Home Assistant antwortet, meldet aber noch keinen PC."))
            val steps = listOf(
                Triple(R.drawable.ic_s_download, "PC-Tools 14.6 oder neuer", "Auf jedem PC installieren bzw. aktualisieren."),
                Triple(R.drawable.ic_s_link, "Home Assistant direkt", "Meine PCs > Anbindung: einschalten, Adresse und Token eintragen, Speichern."),
                Triple(R.drawable.ic_s_send, "Jetzt senden", "Danach hier auf Aktualisieren tippen."))
            steps.forEachIndexed { i, (ic, t, d) ->
                c.addView(LinearLayout(this).apply {
                    orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, Ui.dp(this@MainActivity, 6), 0, Ui.dp(this@MainActivity, 6))
                    addView(Ui.tile(this@MainActivity, ic, Ui.BLUE, 34))
                    addView(LinearLayout(this@MainActivity).apply { orientation = LinearLayout.VERTICAL; layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                        addView(Ui.text(this@MainActivity, "${i + 1}. $t", 15f, true)); addView(Ui.text(this@MainActivity, d, 13f, col = Ui.MUTED)) })
                })
            }
            c.addView(Ui.button(this, "Aktualisieren", true, R.drawable.ic_s_refresh) { load() })
            c.addView(Ui.button(this, "Anleitung & FAQ", false, R.drawable.ic_s_book) { startActivity(Intent(this, HelpActivity::class.java)) })
            c.addView(Ui.button(this, "Demo ansehen", false, R.drawable.ic_s_play) { Ha.setDemo(this, true); invalidateOptionsMenu(); load() })
            list.addView(c)
            return
        }
        // Zusammenfassung im Kopfbereich
        val help = pcs.count { it.helpOpen }
        heroStats.visibility = View.VISIBLE
        heroStats.addView(Ui.heroStat(this, help, "Hilferufe"))
        heroStats.addView(Ui.heroStat(this, pcs.count { it.state == "Rot" }, "rot"))
        heroStats.addView(Ui.heroStat(this, pcs.count { it.state == "Gelb" }, "gelb"))
        heroStats.addView(Ui.heroStat(this, pcs.count { it.state == "Grün" }, "grün"))
        for (pc in pcs) {
            val sc = Ui.stateColor(pc.state)
            val card = Ui.card(this)
            val head = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
            head.addView(Ui.tile(this, if (pc.helpOpen) R.drawable.ic_s_help else Ui.stateIcon(pc.state), if (pc.helpOpen) Ui.RED else sc, 46, pc.helpOpen || pc.state == "Rot"))
            val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) }
            col.addView(Ui.text(this, pc.name, 18f, true))
            val chips = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, Ui.dp(this@MainActivity, 4), 0, 0) }
            chips.addView(Ui.badge(this, Ui.stateWord(pc.state), sc))
            if (pc.score >= 0) chips.addView(Ui.badge(this, "Score ${pc.score}", Ui.BLUE), LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { leftMargin = Ui.dp(this@MainActivity, 6) })
            if (pc.problems.isNotEmpty()) chips.addView(Ui.badge(this, "${pc.problems.size} Hinweis" + (if (pc.problems.size > 1) "e" else ""), Ui.AMBER), LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { leftMargin = Ui.dp(this@MainActivity, 6) })
            col.addView(chips)
            head.addView(col)
            head.addView(Ui.icon(this, R.drawable.ic_s_chev, Ui.MUTED, 22))
            card.addView(head)
            if (pc.score >= 0) card.addView(Ui.meter(this, pc.score, sc))
            if (pc.helpOpen) {
                card.addView(LinearLayout(this).apply {
                    orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(Ui.dp(this@MainActivity, 10), Ui.dp(this@MainActivity, 8), Ui.dp(this@MainActivity, 10), Ui.dp(this@MainActivity, 8))
                    background = android.graphics.drawable.GradientDrawable().apply { setColor(Ui.soft(Ui.RED)); cornerRadius = Ui.dp(this@MainActivity, 10).toFloat() }
                    layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = Ui.dp(this@MainActivity, 10) }
                    addView(Ui.icon(this@MainActivity, R.drawable.ic_s_chat, Ui.RED, 18).apply { (layoutParams as LinearLayout.LayoutParams).rightMargin = Ui.dp(this@MainActivity, 8) })
                    addView(Ui.text(this@MainActivity, "Hilferuf " + Ha.nice(pc.helpTime) + (if (pc.helpMessage.isNotBlank()) ": „${pc.helpMessage}“" else ""), 14f, true, 0xFF991B1B.toInt()).apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) })
                })
            }
            val foot = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, Ui.dp(this@MainActivity, 8), 0, 0) }
            foot.addView(Ui.icon(this, R.drawable.ic_s_clock, Ui.MUTED, 14).apply { (layoutParams as LinearLayout.LayoutParams).rightMargin = Ui.dp(this@MainActivity, 5) })
            foot.addView(Ui.text(this, if (pc.updated.isNotBlank()) "gemeldet " + Ha.nice(pc.updated) else "noch nicht gemeldet", 12f, col = Ui.MUTED).apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) })
            if (pc.bitlocker.isNotBlank()) {
                val warn = pc.bitlockerLevel == "Error" || pc.bitlockerLevel == "Warn" || pc.bitlocker.contains("nicht")
                foot.addView(Ui.icon(this, R.drawable.ic_s_lock, if (warn) Ui.AMBER else Ui.GREEN, 14).apply { (layoutParams as LinearLayout.LayoutParams).rightMargin = Ui.dp(this@MainActivity, 4) })
                foot.addView(Ui.text(this, if (warn) "BitLocker prüfen" else "BitLocker", 12f, col = if (warn) Ui.AMBER else Ui.MUTED))
            }
            card.addView(foot)
            val out = android.util.TypedValue(); theme.resolveAttribute(android.R.attr.selectableItemBackground, out, true); card.foreground = getDrawable(out.resourceId)
            card.setOnClickListener { startActivity(Intent(this, PcActivity::class.java).putExtra("key", pc.key)) }
            list.addView(card)
        }
        list.addView(Ui.text(this, "Tippe auf einen PC für Details und Aufträge.", 13f, col = Ui.MUTED).apply { gravity = Gravity.CENTER; setPadding(0, Ui.dp(this@MainActivity, 4), 0, Ui.dp(this@MainActivity, 16)) })
    }

    private fun explain(e: Throwable): Pair<String, String> = when {
        e is HaHttpException && (e.code == 401 || e.code == 403) -> Pair("Zugangstoken ungültig", "Home Assistant lehnt das Token ab (Fehler ${e.code}). Meist wurde es gelöscht oder falsch kopiert. Erstelle in Home Assistant unter Profil > Sicherheit ein neues langlebiges Zugangstoken und trage es unter Einstellungen ein.")
        e is HaHttpException && e.code == 404 -> Pair("Adresse stimmt nicht ganz", "Home Assistant ist erreichbar, kennt die Seite aber nicht (404). Bitte nur die Grundadresse eintragen, z.B. https://xyz.ui.nabu.casa – ohne /lovelace oder Ähnliches.")
        e is HaHttpException -> Pair("Home Assistant meldet einen Fehler", e.message ?: "HTTP ${e.code}")
        e is UnknownHostException -> Pair("Adresse nicht gefunden", "Das Handy findet die Adresse nicht. Ist Internet bzw. WLAN an? Adressen wie homeassistant.local oder 192.168.x.x gehen nur im Heimnetz – für unterwegs die Nabu-Casa-Adresse (https://….ui.nabu.casa) eintragen.")
        e is SocketTimeoutException || e is ConnectException -> Pair("Home Assistant antwortet nicht", "Die Adresse ist bekannt, aber Home Assistant antwortet nicht. Läuft er? Bist du im richtigen Netz? Unterwegs geht nur die https-Adresse.")
        e is SSLException -> Pair("Sichere Verbindung fehlgeschlagen", "Das Zertifikat wurde nicht akzeptiert. Mit Nabu Casa sollte das nicht passieren – bei eigenem Zertifikat dieses auf dem Handy installieren.")
        else -> Pair("Keine Verbindung", e.message ?: e.toString())
    }

    private fun showError(e: Throwable) {
        val (t, m) = explain(e)
        val cached = Ha.cached(this)
        if (cached != null && list.childCount == 0) show(cached.first, "") else showTopHints()
        status.text = "Nicht aktualisiert" + (if (cached != null) " · gespeicherter Stand vom " + Ha.niceMillis(cached.second) else "")
        val c = Ui.card(this).apply { background = (background as android.graphics.drawable.GradientDrawable).apply { setColor(0xFFFEF2F2.toInt()); setStroke(Ui.dp(this@MainActivity, 1), 0xFFFECACA.toInt()) } }
        c.addView(Ui.heading(this, R.drawable.ic_s_alert, Ui.RED, t))
        c.addView(Ui.text(this, m, 14f, col = 0xFF7F1D1D.toInt()).apply { setPadding(0, Ui.dp(this@MainActivity, 4), 0, Ui.dp(this@MainActivity, 6)) })
        c.addView(Ui.button(this, "Erneut versuchen", true, R.drawable.ic_s_refresh) { load() })
        c.addView(Ui.button(this, "Einstellungen", false, R.drawable.ic_s_cog) { openSettings() })
        c.addView(Ui.button(this, "Hilfe & FAQ", false, R.drawable.ic_s_book) { startActivity(Intent(this, HelpActivity::class.java)) })
        top.addView(c, 0)
    }
}
