package de.rh.pctools

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.view.MenuItem
import android.widget.LinearLayout
import android.widget.TextView

/** Version, Update-Prüfung, Links, Datenschutz, Diagnose und Zurücksetzen. */
class AboutActivity : Activity() {
    private lateinit var upd: TextView
    private lateinit var diag: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Über die App"
        actionBar?.setDisplayHomeAsUpEnabled(true)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Ui.BG); val p = Ui.dp(this@AboutActivity, 14); setPadding(p, p, p, p) }

        root.addView(Ui.hero(this, R.drawable.ic_s_pcs, "PC-Tools-App", "Version " + BuildConfigLite.version(this) + " · Open Source"))
        val a = Ui.card(this)
        a.addView(Ui.heading(this, R.drawable.ic_s_info, Ui.BLUE, "Über die App"))
        a.addView(Ui.text(this, "Begleiter zu PC-Tools für Windows: Ampel aller PCs, Hilferufe, Hinweise und Aufträge – über deinen eigenen Home Assistant. Kostenlos und Open Source (Apache 2.0), ohne Werbung und ohne Tracking.", 14f).apply { setPadding(0, Ui.dp(this@AboutActivity, 8), 0, Ui.dp(this@AboutActivity, 4)) })
        upd = Ui.text(this, Update.known(this)?.let { "Neue Version ${it.version} verfügbar." } ?: "", 14f, true, Ui.BLUE)
        a.addView(upd)
        a.addView(Ui.button(this, "Nach Updates suchen", true, R.drawable.ic_s_refresh) { checkUpdate() })
        root.addView(a)

        val l = Ui.card(this)
        l.addView(Ui.heading(this, R.drawable.ic_s_link, Ui.PURPLE, "Links"))
        l.addView(Ui.navRow(this, R.drawable.ic_s_globe, Ui.GREEN, "Webseite von PC-Tools") { Ui.open(this, "https://rhedv42-sudo.github.io/pc-tools/") })
        l.addView(Ui.navRow(this, R.drawable.ic_s_code, 0xFF475569.toInt(), "Quelltext auf GitHub") { Ui.open(this, "https://github.com/rhedv42-sudo/pc-tools") })
        l.addView(Ui.navRow(this, R.drawable.ic_s_bug, Ui.RED, "Fehler melden") { Ui.open(this, "https://github.com/rhedv42-sudo/pc-tools/issues/new/choose") })
        l.addView(Ui.navRow(this, R.drawable.ic_s_chat, Ui.BLUE, "Frage stellen oder Idee teilen") { Ui.open(this, "https://github.com/rhedv42-sudo/pc-tools/discussions") })
        l.addView(Ui.navRow(this, R.drawable.ic_s_star, Ui.AMBER, "Gefällt dir PC-Tools?", "Stern auf GitHub geben") { Ui.open(this, "https://github.com/rhedv42-sudo/pc-tools") })
        l.addView(Ui.navRow(this, R.drawable.ic_s_book, Ui.BLUE, "Hilfe & FAQ") { startActivity(Intent(this, HelpActivity::class.java)) })
        root.addView(l)

        val d = Ui.card(this)
        d.addView(Ui.heading(this, R.drawable.ic_s_shield, Ui.GREEN, "Datenschutz"))
        d.addView(Ui.text(this, "• Die App spricht nur mit deinem Home Assistant.\n• Das Zugangstoken liegt verschlüsselt im Android-Schlüsselspeicher dieses Handys.\n• Einmal am Tag fragt die App bei GitHub nach einer neuen Version – ohne Daten über dich.\n• Kein Tracking, keine Werbung, keine Analyse-Dienste.", 14f).apply { setPadding(0, Ui.dp(this@AboutActivity, 6), 0, 0) })
        d.addView(Ui.button(this, "Datenschutz-Erklärung", false, R.drawable.ic_s_report) { Ui.open(this, "https://github.com/rhedv42-sudo/pc-tools/blob/main/DATENSCHUTZ.md") })
        root.addView(d)

        val g = Ui.card(this)
        g.addView(Ui.heading(this, R.drawable.ic_s_report, 0xFF475569.toInt(), "Diagnose"))
        g.addView(Ui.text(this, "Hilft bei Fehlermeldungen. Enthält kein Token und keine vollständige Adresse.", 13f, col = Ui.MUTED))
        diag = Ui.text(this, Diag.report(this), 12f).apply { typeface = Typeface.MONOSPACE; setTextIsSelectable(true); setPadding(0, Ui.dp(this@AboutActivity, 8), 0, Ui.dp(this@AboutActivity, 4)) }
        g.addView(diag)
        g.addView(Ui.button(this, "Diagnose kopieren", false, R.drawable.ic_s_report) { Ui.copy(this, "PC-Tools-App Diagnose", Diag.report(this)) })
        g.addView(Ui.button(this, "Protokoll leeren", false, R.drawable.ic_s_trash) { Diag.clear(this); diag.text = Diag.report(this) })
        root.addView(g)

        val r = Ui.card(this)
        r.addView(Ui.heading(this, R.drawable.ic_s_trash, Ui.RED, "Zurücksetzen"))
        r.addView(Ui.text(this, "Löscht Adresse, Token, gespeicherten Stand und Einstellungen aus der App. Auf den PCs und in Home Assistant ändert sich nichts.", 13f, col = Ui.MUTED))
        r.addView(Ui.button(this, "Alle Daten in der App löschen", false, R.drawable.ic_s_trash) { reset() })
        root.addView(r)

        root.addView(Ui.text(this, "PC-Tools by RH – Open Source unter Apache 2.0. Windows ist eine Marke von Microsoft, Home Assistant eine Marke der Open Home Foundation.", 12f, col = Ui.MUTED).apply { setPadding(Ui.dp(this@AboutActivity, 4), Ui.dp(this@AboutActivity, 4), Ui.dp(this@AboutActivity, 4), Ui.dp(this@AboutActivity, 16)) })
        setContentView(Ui.screen(this, root))
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) { finish(); return true }
        return super.onOptionsItemSelected(item)
    }

    private fun checkUpdate() {
        upd.text = "Suche …"
        Thread {
            val msg = try { Update.check(this)?.let { "Neue Version ${it.version} verfügbar." } ?: "Du hast die neueste Version." } catch (e: Exception) { "Prüfung nicht möglich: " + (e.message ?: e.toString()) }
            runOnUiThread {
                upd.text = msg
                Update.known(this)?.let { u ->
                    AlertDialog.Builder(this).setTitle("Neue Version ${u.version}")
                        .setMessage("Auf der GitHub-Seite unten bei „Assets“ die Datei PC-Tools-App-${u.version}.apk antippen, öffnen und installieren.")
                        .setPositiveButton("Zur Download-Seite") { _, _ -> Ui.open(this, u.url) }
                        .setNegativeButton("Später", null).show()
                }
            }
        }.start()
    }

    private fun reset() {
        Lock.confirm(this, "App zurücksetzen") {
            AlertDialog.Builder(this).setTitle("Alle Daten in der App löschen?")
                .setMessage("Adresse, Token, gespeicherter Stand und Einstellungen werden gelöscht. Danach musst du die Verbindung neu einrichten.")
                .setPositiveButton("Löschen") { _, _ ->
                    Ha.prefs(this).edit().clear().commit()
                    startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK or Intent.FLAG_ACTIVITY_NEW_TASK))
                    finish()
                }
                .setNegativeButton("Abbrechen", null).show()
        }
    }
}
