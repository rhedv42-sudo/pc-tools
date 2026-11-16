package de.rh.pctools

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class PcActivity : Activity() {
    private lateinit var root: LinearLayout
    private var key = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        key = intent.getStringExtra("key") ?: ""
        title = key.uppercase()
        actionBar?.setDisplayHomeAsUpEnabled(true)
        root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Ui.BG); val p = Ui.dp(this@PcActivity, 14); setPadding(p, p, p, p) }
        setContentView(ScrollView(this).apply { setBackgroundColor(Ui.BG); addView(root) })
    }

    override fun onResume() { super.onResume(); load() }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, "Aktualisieren").setShowAsAction(MenuItem.SHOW_AS_ACTION_ALWAYS)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) { finish(); return true }
        if (item.itemId == 1) load()
        return true
    }

    private fun load() {
        root.removeAllViews()
        root.addView(Ui.text(this, "Lade …", 13f, col = Ui.MUTED))
        Thread {
            try {
                val pc = Ha.loadPcs(this).firstOrNull { it.key == key }
                val job = Ha.job(this, key)
                runOnUiThread { show(pc, job) }
            } catch (e: Exception) {
                runOnUiThread { root.removeAllViews(); root.addView(Ui.text(this, "Fehler: " + (e.message ?: e.toString()))) }
            }
        }.start()
    }

    private fun show(pc: Pc?, job: Job?) {
        root.removeAllViews()
        if (pc == null) { root.addView(Ui.text(this, "PC nicht gefunden.")); return }
        title = pc.name
        // Ampel
        val head = Ui.card(this)
        val hr = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        hr.addView(Ui.dot(this, pc.state, 40))
        val hc = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        hc.addView(Ui.text(this, when (pc.state) { "Grün" -> "Alles in Ordnung"; "Gelb" -> "Ein paar Kleinigkeiten"; "Rot" -> "Bitte kümmern"; else -> pc.state }, 20f, true))
        hc.addView(Ui.text(this, (if (pc.score >= 0) "Zustands-Score ${pc.score} von 100 · " else "") + "gemeldet " + Ha.nice(pc.updated), 13f, col = Ui.MUTED))
        hr.addView(hc); head.addView(hr)
        root.addView(head)

        // Hilferuf
        if (pc.helpOpen) {
            val c = Ui.card(this)
            c.addView(Ui.text(this, "🆘 Hilferuf vom " + Ha.nice(pc.helpTime), 17f, true, 0xFFDC2626.toInt()))
            if (pc.helpMessage.isNotBlank()) c.addView(Ui.text(this, "„${pc.helpMessage}“", 16f).apply { setPadding(0, Ui.dp(this@PcActivity, 6), 0, Ui.dp(this@PcActivity, 6)) })
            if (pc.helpReport.isNotBlank()) c.addView(Ui.button(this, "Bericht anzeigen", false) {
                AlertDialog.Builder(this).setTitle("Hilferuf ${pc.name}").setMessage(pc.helpReport).setPositiveButton("OK", null).show()
            })
            root.addView(c)
        }

        // Probleme
        if (pc.problems.isNotEmpty()) {
            val c = Ui.card(this)
            c.addView(Ui.text(this, "Hinweise", 16f, true))
            for (p in pc.problems) c.addView(Ui.text(this, "• $p", 14f).apply { setPadding(0, Ui.dp(this@PcActivity, 4), 0, 0) })
            root.addView(c)
        }

        // Aufträge
        val jc = Ui.card(this)
        jc.addView(Ui.text(this, "Aufträge an diesen PC", 16f, true))
        if (job != null && job.state.isNotBlank() && job.state != "unknown") {
            jc.addView(Ui.text(this, "Letzter Auftrag: ${Ha.jobLabel(job.action)} – ${job.state}" + (if (job.message.isNotBlank()) " (${job.message})" else "") + " · " + Ha.nice(job.time), 13f, col = Ui.MUTED).apply { setPadding(0, Ui.dp(this@PcActivity, 4), 0, Ui.dp(this@PcActivity, 6)) })
        }
        if (!pc.jobsEnabled) {
            jc.addView(Ui.text(this, "Auf dem PC in PC-Tools einschalten: Meine PCs > Anbindung > „Aufträge aus Home Assistant bzw. der Android-App annehmen“.", 13f, col = Ui.MUTED))
        } else {
            jc.addView(Ui.text(this, "Der PC prüft alle 10 Minuten, ob ein Auftrag da ist.", 13f, col = Ui.MUTED))
            for (a in pc.jobs.ifEmpty { listOf("Status", "Pflege", "Updates", "Aufraeumen", "Virenscan", "Sicherung", "Selbstupdate") }) {
                jc.addView(Ui.button(this, Ha.jobLabel(a), a == "Pflege") { confirm(pc, a) })
            }
        }
        root.addView(jc)

        // Details
        val dc = Ui.card(this)
        dc.addView(Ui.text(this, "Details", 16f, true))
        fun r(l: String, v: String) { if (v.isNotBlank()) dc.addView(Ui.row(this, l, v)) }
        r("Modell", pc.model); r("Windows", pc.windows); r("Speicher C:", pc.diskFree); r("Läuft seit", pc.uptime)
        r("Letzte Pflege", pc.lastRun); r("Neustart", if (pc.rebootPending) "ausstehend" else ""); r("BitLocker", pc.bitlocker); r("BIOS", pc.bios); r("PC-Tools", pc.version)
        root.addView(dc)
    }

    private fun confirm(pc: Pc, action: String) {
        AlertDialog.Builder(this)
            .setTitle(Ha.jobLabel(action))
            .setMessage("Auftrag „${Ha.jobLabel(action)}“ an ${pc.name} senden?")
            .setPositiveButton("Senden") { _, _ ->
                Thread {
                    val msg = try { Ha.sendJob(this, pc.key, pc.name, action); "Auftrag gesendet – der PC holt ihn in spätestens 10 Minuten ab." } catch (e: Exception) { "Fehler: " + (e.message ?: e.toString()) }
                    runOnUiThread { AlertDialog.Builder(this).setMessage(msg).setPositiveButton("OK") { _, _ -> load() }.show() }
                }.start()
            }
            .setNegativeButton("Abbrechen", null)
            .show()
    }
}
