package de.rh.pctools

import android.app.Activity
import android.os.Bundle
import android.text.InputType
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView

class SetupActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Verbindung zu Home Assistant"
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Ui.BG); val p = Ui.dp(this@SetupActivity, 18); setPadding(p, p, p, p) }
        root.addView(Ui.text(this, "PC-Tools-App", 22f, true))
        root.addView(Ui.text(this, "Die App zeigt die Ampel, Hilferufe und Hinweise aller PCs, die PC-Tools an Home Assistant meldet, und schickt Aufträge (Pflege, Updates …).\n\nDazu braucht sie die Adresse deines Home Assistant und ein langlebiges Zugangstoken (Home Assistant > Profil > Sicherheit > Langlebige Zugangstoken > Token erstellen). Das Token wird verschlüsselt nur auf diesem Handy gespeichert.", 14f, col = Ui.MUTED).apply { setPadding(0, Ui.dp(this@SetupActivity, 8), 0, Ui.dp(this@SetupActivity, 14)) })
        root.addView(Ui.text(this, "Adresse", 14f, true))
        val url = EditText(this).apply { hint = "https://xyz.ui.nabu.casa oder http://192.168.1.10:8123"; inputType = InputType.TYPE_TEXT_VARIATION_URI; setText(Ha.url(this@SetupActivity)) }
        root.addView(url)
        root.addView(Ui.text(this, "Zugangstoken", 14f, true).apply { setPadding(0, Ui.dp(this@SetupActivity, 10), 0, 0) })
        val tok = EditText(this).apply { hint = if (Ha.token(this@SetupActivity).isNotBlank()) "(gespeichert – leer lassen = unverändert)" else "eyJ0eXAiOiJKV1Qi…"; inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD }
        root.addView(tok)
        val state = Ui.text(this, "", 14f)
        root.addView(Ui.button(this, "Verbinden und speichern") {
            val u = url.text.toString().trim(); val t = tok.text.toString().trim().ifBlank { Ha.token(this) }
            if (!u.startsWith("http")) { state.text = "Bitte die Adresse mit http:// oder https:// eingeben."; return@button }
            if (t.isBlank()) { state.text = "Bitte das Zugangstoken eingeben."; return@button }
            state.text = "Prüfe …"
            Thread {
                val msg = Lock.checkUrl(u) ?: try { Ha.test(this, u, t); Ha.save(this, u, t); Ha.setDemo(this, false); Diag.add(this, "Verbindung gespeichert: " + Diag.hostShort(u)); null } catch (e: Exception) { e.message ?: e.toString() }
                runOnUiThread { if (msg == null) finish() else state.text = "Verbindung fehlgeschlagen: $msg" }
            }.start()
        })
        root.addView(state)
        root.addView(Ui.text(this, "Sicherheit", 14f, true).apply { setPadding(0, Ui.dp(this@SetupActivity, 16), 0, 0) })
        root.addView(CheckBox(this).apply {
            text = "App-Sperre: beim Öffnen und vor jedem Auftrag mit Fingerabdruck oder Handy-PIN entsperren (empfohlen)"
            isChecked = Lock.enabled(this@SetupActivity)
            setOnClickListener {
                val box = this
                if (box.isChecked) { Lock.setEnabled(this@SetupActivity, true); return@setOnClickListener }
                box.isChecked = true // erst nach Bestätigung ausschalten
                Lock.confirm(this@SetupActivity, "App-Sperre ausschalten") { Lock.setEnabled(this@SetupActivity, false); box.isChecked = false }
            }
        })
        root.addView(Ui.text(this, "Verbindung: http:// nur im Heimnetz (z.B. http://192.168.1.10:8123), von unterwegs nur https://. Für Aufträge reicht ein Home-Assistant-Benutzer ohne Administratorrechte (z.B. „pctools-app“), wenn der Helfer input_text.pctools_auftrag angelegt ist.", 13f, col = Ui.MUTED))
        root.addView(Ui.text(this, "\nBenachrichtigungen: Die App prüft etwa alle 15 Minuten und meldet sich, wenn ein PC rot wird oder um Hilfe ruft.", 13f, col = Ui.MUTED))
        root.addView(Ui.button(this, "Anleitung & FAQ", false) { startActivity(android.content.Intent(this, HelpActivity::class.java)) })
        setContentView(Ui.screen(this, root))
    }
}
