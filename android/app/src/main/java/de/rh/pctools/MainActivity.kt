package de.rh.pctools

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.widget.LinearLayout
import android.widget.ScrollView

class MainActivity : Activity() {
    private lateinit var list: LinearLayout
    private lateinit var info: android.widget.TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "PC-Tools – Meine PCs"
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Ui.BG); val p = Ui.dp(this@MainActivity, 14); setPadding(p, p, p, p) }
        info = Ui.text(this, "Lade …", 13f, col = Ui.MUTED)
        list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(info)
        root.addView(list)
        setContentView(ScrollView(this).apply { setBackgroundColor(Ui.BG); addView(root) })
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        CheckJob.schedule(this)
    }

    override fun onResume() {
        super.onResume()
        if (!Ha.isSetUp(this)) { startActivity(Intent(this, SetupActivity::class.java)); return }
        Lock.requireOpen(this) { load() }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (!Lock.onResult(requestCode, resultCode)) super.onActivityResult(requestCode, resultCode, data)
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, "Aktualisieren").setShowAsAction(MenuItem.SHOW_AS_ACTION_ALWAYS)
        menu.add(0, 2, 1, "Einstellungen")
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        when (item.itemId) {
            1 -> load()
            2 -> Lock.confirm(this, "Einstellungen öffnen") { startActivity(Intent(this, SetupActivity::class.java)) }
        }
        return true
    }

    private fun load() {
        info.text = "Lade …"
        Thread {
            try {
                val pcs = Ha.loadPcs(this)
                runOnUiThread { show(pcs) }
            } catch (e: Exception) {
                runOnUiThread { info.text = "Fehler: " + (e.message ?: e.toString()); list.removeAllViews() }
            }
        }.start()
    }

    private fun show(pcs: List<Pc>) {
        list.removeAllViews()
        val red = pcs.count { it.state == "Rot" }; val help = pcs.count { it.helpOpen }
        info.text = if (pcs.isEmpty()) "Noch keine PCs gefunden. In PC-Tools auf jedem PC: Meine PCs > Anbindung > „Home Assistant direkt“ einschalten." else
            "${pcs.size} PC(s)" + (if (help > 0) " · $help Hilferuf(e)!" else "") + (if (red > 0) " · $red rot" else "") + " · Stand " + java.time.LocalTime.now().withNano(0).withSecond(0)
        for (pc in pcs) {
            val card = Ui.card(this)
            val head = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            head.addView(Ui.dot(this, pc.state, 22))
            val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) }
            col.addView(Ui.text(this, pc.name, 18f, true))
            val sub = buildString {
                append(pc.state)
                if (pc.score >= 0) append(" · Score ${pc.score}")
                if (pc.problems.isNotEmpty()) append(" · ${pc.problems.size} Hinweis(e)")
                if (pc.updated.isNotBlank()) append(" · ${Ha.nice(pc.updated)}")
            }
            col.addView(Ui.text(this, sub, 13f, col = Ui.MUTED))
            head.addView(col)
            card.addView(head)
            if (pc.helpOpen) card.addView(Ui.text(this, "🆘 Hilferuf " + Ha.nice(pc.helpTime) + (if (pc.helpMessage.isNotBlank()) ": „${pc.helpMessage}“" else ""), 14f, true, 0xFFDC2626.toInt()).apply { setPadding(0, Ui.dp(this@MainActivity, 8), 0, 0) })
            if (pc.bitlockerLevel == "Error" || pc.bitlocker.contains("nicht gesichert")) card.addView(Ui.text(this, "BitLocker: " + pc.bitlocker, 13f, col = 0xFFB45309.toInt()).apply { setPadding(0, Ui.dp(this@MainActivity, 6), 0, 0) })
            card.setOnClickListener { startActivity(Intent(this, PcActivity::class.java).putExtra("key", pc.key)) }
            list.addView(card)
        }
    }
}
