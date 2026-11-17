package de.rh.pctools

import android.app.Activity
import android.os.Bundle
import android.text.InputType
import android.view.MenuItem
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout

class SetupActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Einstellungen"
        actionBar?.setDisplayHomeAsUpEnabled(true)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Ui.BG); val p = Ui.dp(this@SetupActivity, 14); setPadding(p, p, p, p) }
        root.addView(Ui.hero(this, R.drawable.ic_s_server, "Verbindung", "Zu deinem Home Assistant – zu Hause oder über Nabu Casa"))

        val c = Ui.card(this)
        c.addView(Ui.heading(this, R.drawable.ic_s_link, Ui.BLUE, "Home Assistant", "Adresse und langlebiges Zugangstoken"))
        c.addView(Ui.text(this, "Das Token erstellst du in Home Assistant: unten links auf deinen Namen > Sicherheit > Langlebige Zugangstoken > Token erstellen. Es wird verschlüsselt nur auf diesem Handy gespeichert – bitte nirgends sonst einfügen.", 13f, col = Ui.MUTED).apply { setPadding(0, 0, 0, Ui.dp(this@SetupActivity, 10)) })
        c.addView(Ui.text(this, "Adresse", 13f, true, Ui.MUTED))
        val url = EditText(this).apply { hint = "https://xyz.ui.nabu.casa oder http://192.168.1.10:8123"; inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI; setText(Ha.url(this@SetupActivity)); setSingleLine() }
        c.addView(url)
        c.addView(Ui.text(this, "Zugangstoken", 13f, true, Ui.MUTED).apply { setPadding(0, Ui.dp(this@SetupActivity, 8), 0, 0) })
        val tok = EditText(this).apply { hint = if (Ha.token(this@SetupActivity).isNotBlank()) "gespeichert – leer lassen = unverändert" else "eyJhbGciOi…"; inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD; setSingleLine() }
        c.addView(tok)
        val state = Ui.text(this, "", 14f)
        c.addView(Ui.button(this, "Verbinden und speichern", true, R.drawable.ic_s_checkcircle) {
            val u = url.text.toString().trim().trimEnd('/'); val t = tok.text.toString().trim().ifBlank { Ha.token(this) }
            if (!u.startsWith("http")) { state.setTextColor(Ui.RED); state.text = "Bitte die Adresse mit http:// oder https:// eingeben."; return@button }
            if (t.isBlank()) { state.setTextColor(Ui.RED); state.text = "Bitte das Zugangstoken eingeben."; return@button }
            state.setTextColor(Ui.MUTED); state.text = "Prüfe Verbindung …"
            Thread {
                val msg = Lock.checkUrl(u) ?: try { Ha.test(this, u, t); Ha.save(this, u, t); Ha.setDemo(this, false); Diag.add(this, "Verbindung gespeichert: " + Diag.hostShort(u)); null } catch (e: Exception) { e.message ?: e.toString() }
                runOnUiThread { if (msg == null) finish() else { state.setTextColor(Ui.RED); state.text = "Verbindung fehlgeschlagen: $msg" } }
            }.start()
        })
        c.addView(state)
        root.addView(c)

        val s = Ui.card(this)
        s.addView(Ui.heading(this, R.drawable.ic_s_shield, Ui.GREEN, "Sicherheit"))
        s.addView(CheckBox(this).apply {
            text = "App-Sperre: beim Öffnen und vor jedem Auftrag mit Fingerabdruck oder Handy-PIN entsperren (empfohlen)"
            textSize = 14f; setTextColor(Ui.TEXT)
            isChecked = Lock.enabled(this@SetupActivity)
            setOnClickListener {
                val box = this
                if (box.isChecked) { Lock.setEnabled(this@SetupActivity, true); return@setOnClickListener }
                box.isChecked = true // erst nach Bestätigung ausschalten
                Lock.confirm(this@SetupActivity, "App-Sperre ausschalten") { Lock.setEnabled(this@SetupActivity, false); box.isChecked = false }
            }
        })
        for ((ic, t) in listOf(
            R.drawable.ic_s_wifi to "http:// nur im Heimnetz (z.B. http://192.168.1.10:8123), unterwegs nur https://.",
            R.drawable.ic_s_key to "Für Aufträge reicht ein Home-Assistant-Benutzer ohne Administratorrechte (z.B. „pctools-app“), wenn der Helfer input_text.pctools_auftrag angelegt ist.",
            R.drawable.ic_s_bell to "Die App prüft etwa alle 15 Minuten und meldet sich, wenn ein PC rot wird oder um Hilfe ruft.")) {
            s.addView(LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL; setPadding(0, Ui.dp(this@SetupActivity, 6), 0, Ui.dp(this@SetupActivity, 2))
                addView(Ui.icon(this@SetupActivity, ic, Ui.MUTED, 18).apply { (layoutParams as LinearLayout.LayoutParams).rightMargin = Ui.dp(this@SetupActivity, 10) })
                addView(Ui.text(this@SetupActivity, t, 13f, col = Ui.MUTED).apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) })
            })
        }
        root.addView(s)
        root.addView(Ui.button(this, "Anleitung & FAQ", false, R.drawable.ic_s_book) { startActivity(android.content.Intent(this, HelpActivity::class.java)) })
        setContentView(Ui.screen(this, root))
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) { finish(); return true }
        return super.onOptionsItemSelected(item)
    }
}
