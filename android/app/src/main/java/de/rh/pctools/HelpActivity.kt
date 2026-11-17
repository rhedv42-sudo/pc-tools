package de.rh.pctools

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.MenuItem
import android.view.View
import android.widget.LinearLayout

/** Anleitung und häufige Fragen – ohne Internet lesbar. */
class HelpActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Hilfe & FAQ"
        actionBar?.setDisplayHomeAsUpEnabled(true)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Ui.BG); val p = Ui.dp(this@HelpActivity, 14); setPadding(p, p, p, p) }

        val g = Ui.card(this)
        g.addView(Ui.text(this, "So richtest du alles ein", 18f, true))
        g.addView(Ui.text(this,
            "1. Auf jedem PC PC-Tools 14.6 oder neuer installieren (kostenlos, rhedv42-sudo.github.io/pc-tools).\n\n" +
            "2. In PC-Tools: Meine PCs > Anbindung > „Home Assistant direkt“ einschalten. Adresse deines Home Assistant und ein Zugangstoken eintragen, Speichern. Für Aufträge zusätzlich „Aufträge aus Home Assistant bzw. der Android-App annehmen“ anhaken.\n\n" +
            "3. Für die App in Home Assistant ein eigenes Zugangstoken erstellen: unten links auf deinen Namen > Sicherheit > Langlebige Zugangstoken > Token erstellen. Am sichersten mit einem eigenen Benutzer ohne Administratorrechte (z.B. „pctools-app“) – dann zusätzlich unter Einstellungen > Geräte & Dienste > Helfer einen Text-Helfer „pctools_auftrag“ (max. Länge 255) anlegen.\n\n" +
            "4. In der App unter Einstellungen die Adresse (zu Hause z.B. http://192.168.1.10:8123, unterwegs https://….ui.nabu.casa) und das Token eintragen – fertig.",
            14f).apply { setPadding(0, Ui.dp(this@HelpActivity, 8), 0, 0) })
        root.addView(g)

        root.addView(Ui.text(this, "Häufige Fragen", 18f, true).apply { setPadding(Ui.dp(this@HelpActivity, 2), Ui.dp(this@HelpActivity, 6), 0, Ui.dp(this@HelpActivity, 8)) })
        for ((q, a) in FAQ) root.addView(faq(q, a))

        val l = Ui.card(this)
        l.addView(Ui.text(this, "Noch Fragen?", 16f, true))
        l.addView(Ui.button(this, "Frage stellen oder Idee teilen") { Ui.open(this, "https://github.com/rhedv42-sudo/pc-tools/discussions") })
        l.addView(Ui.button(this, "Fehler melden", false) { Ui.open(this, "https://github.com/rhedv42-sudo/pc-tools/issues/new/choose") })
        l.addView(Ui.button(this, "Diagnose kopieren (für Fehlermeldungen)", false) { Ui.copy(this, "PC-Tools-App Diagnose", Diag.report(this)) })
        l.addView(Ui.button(this, "Webseite von PC-Tools", false) { Ui.open(this, "https://rhedv42-sudo.github.io/pc-tools/") })
        root.addView(l)
        setContentView(Ui.screen(this, root))
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) { finish(); return true }
        return super.onOptionsItemSelected(item)
    }

    private fun faq(q: String, a: String): LinearLayout {
        val c = Ui.card(this)
        val head = Ui.text(this, "＋  $q", 15f, true)
        val body = Ui.text(this, a, 14f, col = Ui.MUTED).apply { visibility = View.GONE; setPadding(0, Ui.dp(this@HelpActivity, 8), 0, 0) }
        c.addView(head); c.addView(body)
        c.setOnClickListener {
            val open = body.visibility != View.VISIBLE
            body.visibility = if (open) View.VISIBLE else View.GONE
            head.text = (if (open) "－  " else "＋  ") + q
        }
        return c
    }

    companion object {
        val FAQ = listOf(
            "Warum sehe ich keine PCs?" to "Die PCs melden sich nur, wenn in PC-Tools unter Meine PCs > Anbindung „Home Assistant direkt“ eingeschaltet ist (PC-Tools 14.6 oder neuer). In Home Assistant heißen sie sensor.pcpflege_<pc-name>_zustand. Nach dem Einschalten am PC auf „Jetzt senden“ klicken und hier auf Aktualisieren tippen.",
            "Was bedeuten Grün, Gelb, Rot und der Score?" to "Grün: alles in Ordnung. Gelb: Kleinigkeiten, z.B. ein offenes Update. Rot: bitte kümmern, z.B. Virenschutz aus, Sicherung sehr alt oder kaum Speicher frei. Der Score (0–100) fasst alles in einer Zahl zusammen – je höher, desto besser.",
            "Was ist ein Hilferuf?" to "Auf dem PC gibt es den Knopf „Hilfe holen“. Er schickt einen verständlichen Bericht (Zustand, Probleme, Fehler) – hier erscheint er rot ganz oben, und du bekommst eine Benachrichtigung.",
            "Wie schnell kommt ein Auftrag beim PC an?" to "Der PC schaut alle 10 Minuten nach, ob ein Auftrag da ist. Er muss eingeschaltet sein, und in PC-Tools muss „Aufträge … annehmen“ angehakt sein. Erlaubt sind nur: Zustand melden, Pflege, Updates, Aufräumen, Virenscan, Sicherung, PC-Tools aktualisieren. Aufträge älter als 24 Stunden lehnt der PC ab.",
            "Warum kommen keine Benachrichtigungen?" to "Die App prüft etwa alle 15 Minuten. Bitte prüfen: Android-Einstellungen > Apps > PC-Tools > Benachrichtigungen erlauben, und unter Akku „Nicht eingeschränkt“ wählen – sonst stoppt Android die Prüfung im Hintergrund.",
            "Was zeigt der Sperrbildschirm?" to "Nur „Hilferuf von PC X“ bzw. „PC X ist rot“. Details siehst du erst in der App. Dafür in den Android-Einstellungen unter Benachrichtigungen > Sperrbildschirm „Vertrauliche Inhalte ausblenden“ wählen.",
            "Was ist die App-Sperre?" to "Beim Öffnen und vor jedem Auftrag fragt die App nach Fingerabdruck, Gesicht oder Handy-PIN. So kann niemand mit deinem entsperrten Handy Aufträge an die PCs schicken. Abschalten unter Einstellungen (nur nach Bestätigung).",
            "Warum geht http:// nur zu Hause?" to "Ohne https würde das Zugangstoken unverschlüsselt durchs Internet gehen. Darum erlaubt die App http:// nur für Adressen im Heimnetz (192.168.x.x, 10.x.x.x, homeassistant.local …). Unterwegs bitte die https-Adresse nehmen, z.B. von Nabu Casa.",
            "Wo ist mein Token gespeichert?" to "Nur auf diesem Handy, verschlüsselt mit dem Android-Schlüsselspeicher. Es wird an niemanden außer deinen Home Assistant geschickt. Bitte das Token nie in Chats oder E-Mails kopieren – wenn doch passiert: in Home Assistant löschen und neu erstellen.",
            "Reicht ein Benutzer ohne Administratorrechte?" to "Für die App ja – dann laufen Aufträge über den Helfer input_text.pctools_auftrag (Text, max. Länge 255). Die PCs selbst brauchen ein Token eines Administrators, weil sie ihren Zustand in Home Assistant eintragen.",
            "Fehler „Zugangstoken ungültig“ (401)" to "Das Token wurde gelöscht, ist abgelaufen oder unvollständig kopiert. In Home Assistant ein neues langlebiges Zugangstoken erstellen und unter Einstellungen eintragen.",
            "Fehler „Adresse nicht gefunden“" to "Adressen wie homeassistant.local oder 192.168.x.x funktionieren nur im eigenen WLAN. Für unterwegs die Nabu-Casa-Adresse eintragen.",
            "Sendet die App Daten an den Entwickler?" to "Nein. Die App spricht nur mit deinem Home Assistant. Einzige Ausnahme: einmal am Tag eine Anfrage an GitHub, ob es eine neue App-Version gibt – ohne Daten über dich.",
            "Was kostet die App?" to "Nichts. PC-Tools und die App sind Open Source (Apache 2.0), ohne Werbung und ohne Abo.",
            "Wie bekomme ich Updates?" to "Die App meldet neue Versionen oben auf der Startseite und unter „Über die App“. Herunterladen über GitHub, APK öffnen, installieren. Lässt sich die neue Version nicht drüber installieren, die alte vorher deinstallieren (danach Adresse und Token neu eintragen).",
            "Die App macht etwas Komisches – was tun?" to "Menü ⋮ > Über die App > Diagnose kopieren und zusammen mit einer kurzen Beschreibung als Fehler melden. Die Diagnose enthält kein Token und keine vollständige Adresse."
        )
    }
}
