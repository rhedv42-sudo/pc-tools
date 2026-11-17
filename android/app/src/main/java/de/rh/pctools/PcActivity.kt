package de.rh.pctools

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.View
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
        setContentView(Ui.screen(this, root))
    }

    override fun onResume() { super.onResume(); if (Ha.demo(this)) load() else Lock.requireOpen(this) { load() } }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (!Lock.onResult(requestCode, resultCode)) super.onActivityResult(requestCode, resultCode, data)
    }

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
                Diag.add(this, "PC laden fehlgeschlagen: $e")
                runOnUiThread { root.removeAllViews(); root.addView(Ui.text(this, "Konnte nicht laden: " + (e.message ?: e.toString()))); root.addView(Ui.button(this, "Erneut versuchen") { load() }) }
            }
        }.start()
    }

    private fun jobIcon(a: String) = when (a) {
        "Status" -> R.drawable.ic_s_report; "Pflege" -> R.drawable.ic_s_wrench; "Updates" -> R.drawable.ic_s_refresh
        "Aufraeumen" -> R.drawable.ic_s_clean; "Virenscan" -> R.drawable.ic_s_virus; "Sicherung" -> R.drawable.ic_s_save
        "Selbstupdate" -> R.drawable.ic_s_download; else -> R.drawable.ic_s_bolt
    }
    private fun jobColor(a: String) = when (a) {
        "Pflege" -> Ui.BLUE; "Updates" -> Ui.GREEN; "Aufraeumen" -> 0xFF0891B2.toInt(); "Virenscan" -> 0xFF0F766E.toInt()
        "Sicherung" -> 0xFFDB2777.toInt(); "Selbstupdate" -> Ui.PURPLE; else -> 0xFF475569.toInt()
    }

    private fun show(pc: Pc?, job: Job?) {
        root.removeAllViews()
        if (pc == null) {
            val c = Ui.card(this); c.addView(Ui.heading(this, R.drawable.ic_s_alert, Ui.AMBER, "PC nicht gefunden", "Er meldet sich gerade nicht in Home Assistant.")); root.addView(c); return
        }
        title = pc.name
        val sc = Ui.stateColor(pc.state)
        // Kopfbereich
        val hero = Ui.hero(this, Ui.stateIcon(pc.state), Ui.stateWord(pc.state), (if (pc.score >= 0) "Zustands-Score ${pc.score} von 100 · " else "") + "gemeldet " + Ha.nice(pc.updated))
        hero.background = android.graphics.drawable.GradientDrawable(android.graphics.drawable.GradientDrawable.Orientation.TL_BR,
            when (pc.state) { "Rot" -> intArrayOf(0xFFB91C1C.toInt(), 0xFFDC2626.toInt(), 0xFFEA580C.toInt()); "Gelb" -> intArrayOf(0xFFB45309.toInt(), 0xFFD97706.toInt(), 0xFFF59E0B.toInt()); "Grün" -> intArrayOf(0xFF15803D.toInt(), 0xFF16A34A.toInt(), 0xFF0D9488.toInt()); else -> intArrayOf(Ui.BLUE, Ui.PURPLE) }
        ).apply { cornerRadius = Ui.dp(this@PcActivity, 18).toFloat() }
        if (pc.score >= 0) hero.addView(android.widget.ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100; progress = pc.score; progressTintList = android.content.res.ColorStateList.valueOf(android.graphics.Color.WHITE)
            progressBackgroundTintList = android.content.res.ColorStateList.valueOf(0x55FFFFFF)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this@PcActivity, 8)).apply { topMargin = Ui.dp(this@PcActivity, 14) }
        })
        root.addView(hero)

        // Hilferuf
        if (pc.helpOpen) {
            val c = Ui.card(this).apply { background = (background as android.graphics.drawable.GradientDrawable).apply { setColor(0xFFFEF2F2.toInt()); setStroke(Ui.dp(this@PcActivity, 1), 0xFFFECACA.toInt()) } }
            c.addView(Ui.heading(this, R.drawable.ic_s_help, Ui.RED, "Hilferuf", "vom " + Ha.nice(pc.helpTime)))
            if (pc.helpMessage.isNotBlank()) c.addView(Ui.text(this, "„${pc.helpMessage}“", 16f, false, 0xFF7F1D1D.toInt()).apply { setPadding(0, 0, 0, Ui.dp(this@PcActivity, 6)) })
            if (pc.helpReport.isNotBlank()) c.addView(Ui.button(this, "Bericht anzeigen", true, R.drawable.ic_s_report) {
                AlertDialog.Builder(this).setTitle("Hilferuf ${pc.name}").setMessage(pc.helpReport).setPositiveButton("OK", null).show()
            })
            root.addView(c)
        }

        // Hinweise
        if (pc.problems.isNotEmpty()) {
            val c = Ui.card(this)
            c.addView(Ui.heading(this, R.drawable.ic_s_alert, Ui.AMBER, "Hinweise", "${pc.problems.size} offene Punkte"))
            for (p in pc.problems) c.addView(LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, Ui.dp(this@PcActivity, 4), 0, Ui.dp(this@PcActivity, 4))
                addView(View(this@PcActivity).apply { background = android.graphics.drawable.GradientDrawable().apply { shape = android.graphics.drawable.GradientDrawable.OVAL; setColor(sc) }; layoutParams = LinearLayout.LayoutParams(Ui.dp(this@PcActivity, 8), Ui.dp(this@PcActivity, 8)).apply { rightMargin = Ui.dp(this@PcActivity, 10) } })
                addView(Ui.text(this@PcActivity, p, 14f).apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) })
            })
            root.addView(c)
        }

        // Aufträge
        val jc = Ui.card(this)
        jc.addView(Ui.heading(this, R.drawable.ic_s_send, Ui.BLUE, "Aufträge an diesen PC", if (pc.jobsEnabled) "Der PC schaut alle 10 Minuten nach." else null))
        if (job != null && job.state.isNotBlank() && job.state != "unknown") {
            val jcCol = when (job.state) { "erledigt" -> Ui.GREEN; "Fehler", "abgelehnt" -> Ui.RED; else -> Ui.AMBER }
            jc.addView(LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, 0, 0, Ui.dp(this@PcActivity, 8))
                addView(Ui.badge(this@PcActivity, job.state, jcCol))
                addView(Ui.text(this@PcActivity, "  ${Ha.jobLabel(job.action)}" + (if (job.message.isNotBlank()) " – ${job.message}" else "") + " · " + Ha.nice(job.time), 13f, col = Ui.MUTED).apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) })
            })
        }
        if (!pc.jobsEnabled) {
            jc.addView(Ui.text(this, "Auf dem PC in PC-Tools einschalten: Meine PCs > Anbindung > „Aufträge aus Home Assistant bzw. der Android-App annehmen“.", 13f, col = Ui.MUTED))
        } else {
            val acts = pc.jobs.ifEmpty { listOf("Status", "Pflege", "Updates", "Aufraeumen", "Virenscan", "Sicherung", "Selbstupdate") }
            if ("Pflege" in acts) jc.addView(Ui.button(this, Ha.jobLabel("Pflege"), true, R.drawable.ic_s_wrench) { confirm(pc, "Pflege") })
            // übrige Aufträge als zweispaltiges Raster aus Kacheln
            val rest = acts.filter { it != "Pflege" }
            var row: LinearLayout? = null
            rest.forEachIndexed { i, a ->
                if (i % 2 == 0) { row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }; jc.addView(row) }
                row!!.addView(LinearLayout(this).apply {
                    orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL
                    val p = Ui.dp(this@PcActivity, 10); setPadding(p, Ui.dp(this@PcActivity, 12), p, Ui.dp(this@PcActivity, 12))
                    background = android.graphics.drawable.GradientDrawable().apply { setColor(Ui.soft(jobColor(a))); cornerRadius = Ui.dp(this@PcActivity, 14).toFloat() }
                    layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { setMargins(Ui.dp(this@PcActivity, 4), Ui.dp(this@PcActivity, 4), Ui.dp(this@PcActivity, 4), Ui.dp(this@PcActivity, 4)) }
                    addView(Ui.icon(this@PcActivity, jobIcon(a), jobColor(a), 26))
                    addView(Ui.text(this@PcActivity, Ha.jobLabel(a), 13f, true, jobColor(a)).apply { gravity = Gravity.CENTER; setPadding(0, Ui.dp(this@PcActivity, 6), 0, 0) })
                    isClickable = true; setOnClickListener { confirm(pc, a) }
                })
                if (i == rest.size - 1 && i % 2 == 0) row!!.addView(View(this).apply { layoutParams = LinearLayout.LayoutParams(0, 1, 1f).apply { setMargins(Ui.dp(this@PcActivity, 4), 0, Ui.dp(this@PcActivity, 4), 0) } })
            }
        }
        root.addView(jc)

        // Details
        val dc = Ui.card(this)
        dc.addView(Ui.heading(this, R.drawable.ic_s_info, 0xFF475569.toInt(), "Details"))
        fun r(ic: Int, l: String, v: String) {
            if (v.isBlank()) return
            dc.addView(LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, Ui.dp(this@PcActivity, 5), 0, Ui.dp(this@PcActivity, 5))
                addView(Ui.icon(this@PcActivity, ic, Ui.MUTED, 18).apply { (layoutParams as LinearLayout.LayoutParams).rightMargin = Ui.dp(this@PcActivity, 10) })
                addView(Ui.text(this@PcActivity, l, 13f, true, Ui.MUTED).apply { layoutParams = LinearLayout.LayoutParams(Ui.dp(this@PcActivity, 108), LinearLayout.LayoutParams.WRAP_CONTENT) })
                addView(Ui.text(this@PcActivity, v, 14f).apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) })
            })
        }
        r(R.drawable.ic_s_pcs, "Modell", pc.model); r(R.drawable.ic_s_windows, "Windows", pc.windows); r(R.drawable.ic_s_disk, "Speicher C:", pc.diskFree); r(R.drawable.ic_s_clock, "Läuft seit", pc.uptime)
        r(R.drawable.ic_s_wrench, "Letzte Pflege", pc.lastRun); r(R.drawable.ic_s_refresh, "Neustart", if (pc.rebootPending) "ausstehend" else ""); r(R.drawable.ic_s_lock, "BitLocker", pc.bitlocker); r(R.drawable.ic_s_chip, "BIOS", pc.bios); r(R.drawable.ic_s_bolt, "PC-Tools", pc.version)
        root.addView(dc)
    }

    private fun confirm(pc: Pc, action: String) {
        AlertDialog.Builder(this)
            .setTitle(Ha.jobLabel(action))
            .setMessage("Auftrag „${Ha.jobLabel(action)}“ an ${pc.name} senden?")
            .setPositiveButton("Senden") { _, _ -> if (Ha.demo(this)) { AlertDialog.Builder(this).setTitle("Demo").setMessage("In der Demo wird nichts gesendet. Echt würde der PC den Auftrag „${Ha.jobLabel(action)}“ in spätestens 10 Minuten abholen und hier „läuft“ und danach „erledigt“ melden.").setPositiveButton("OK", null).show(); return@setPositiveButton }
                Lock.confirm(this, Ha.jobLabel(action) + " an " + pc.name) {
                Thread {
                    val msg = try { Ha.sendJob(this, pc.key, pc.name, action); "Auftrag gesendet – der PC holt ihn in spätestens 10 Minuten ab." } catch (e: Exception) { "Fehler: " + (e.message ?: e.toString()) }
                    runOnUiThread { AlertDialog.Builder(this).setMessage(msg).setPositiveButton("OK") { _, _ -> load() }.show() }
                }.start()
            } }
            .setNegativeButton("Abbrechen", null)
            .show()
    }
}
