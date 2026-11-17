package de.rh.pctools

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/** Kleine Helfer für eine Oberfläche ohne XML-Layouts. */
object Ui {
    const val BLUE = 0xFF1C4FA6.toInt()
    const val TEXT = 0xFF1F2A44.toInt()
    const val MUTED = 0xFF6B7890.toInt()
    const val BG = 0xFFF4F6FA.toInt()

    fun dp(a: Activity, v: Int) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), a.resources.displayMetrics).toInt()

    fun color(state: String) = when (state) {
        "Rot" -> 0xFFDC2626.toInt()
        "Gelb" -> 0xFFF59E0B.toInt()
        "Grün" -> 0xFF22C55E.toInt()
        else -> 0xFF9AA5B8.toInt()
    }

    fun text(a: Activity, s: String, size: Float = 15f, bold: Boolean = false, col: Int = TEXT): TextView =
        TextView(a).apply {
            text = s; textSize = size; setTextColor(col)
            if (bold) setTypeface(typeface, Typeface.BOLD)
        }

    fun card(a: Activity): LinearLayout = LinearLayout(a).apply {
        orientation = LinearLayout.VERTICAL
        val p = dp(a, 14); setPadding(p, p, p, p)
        background = GradientDrawable().apply { setColor(Color.WHITE); cornerRadius = dp(a, 14).toFloat(); setStroke(dp(a, 1), 0xFFE2E7F0.toInt()) }
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { setMargins(0, 0, 0, dp(a, 10)) }
    }

    fun dot(a: Activity, state: String, size: Int = 18): View = View(a).apply {
        background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(color(state)) }
        layoutParams = LinearLayout.LayoutParams(dp(a, size), dp(a, size)).apply { setMargins(0, 0, dp(a, 12), 0); gravity = Gravity.CENTER_VERTICAL }
    }

    fun button(a: Activity, s: String, primary: Boolean = true, icon: Int = 0, onClick: () -> Unit): Button = Button(a).apply {
        text = s; isAllCaps = false; textSize = 15f
        setTextColor(if (primary) Color.WHITE else BLUE)
        stateListAnimator = null; elevation = 0f
        if (icon != 0) {
            val d = a.getDrawable(icon)?.mutate()
            if (d != null) { val sz = dp(a, 20); d.setBounds(0, 0, sz, sz); d.setTint(if (primary) Color.WHITE else BLUE); setCompoundDrawablesRelative(d, null, null, null); compoundDrawablePadding = dp(a, 8) }
            gravity = Gravity.CENTER
        }
        background = GradientDrawable().apply { setColor(if (primary) BLUE else 0xFFE8EEF9.toInt()); cornerRadius = dp(a, 10).toFloat() }
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { setMargins(0, dp(a, 6), 0, dp(a, 6)) }
        setOnClickListener { onClick() }
    }

    fun row(a: Activity, label: String, value: String): LinearLayout = LinearLayout(a).apply {
        orientation = LinearLayout.HORIZONTAL
        setPadding(0, dp(a, 3), 0, dp(a, 3))
        addView(text(a, label, 13f, true, MUTED).apply { layoutParams = LinearLayout.LayoutParams(dp(a, 120), LinearLayout.LayoutParams.WRAP_CONTENT) })
        addView(text(a, value, 14f).apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) })
    }

    /** Scrollbarer Bildschirm (Rand zu Titel-/Statusleiste regelt das Theme: windowOptOutEdgeToEdgeEnforcement). */
    fun screen(a: Activity, content: View): ScrollView = ScrollView(a).apply {
        setBackgroundColor(BG)
        isFillViewport = true
        addView(content)
    }

    fun stat(a: Activity, n: Int, label: String, col: Int): LinearLayout = LinearLayout(a).apply {
        orientation = LinearLayout.VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        val p = dp(a, 8); setPadding(p, p, p, p)
        background = GradientDrawable().apply { setColor(Color.WHITE); cornerRadius = dp(a, 12).toFloat(); setStroke(dp(a, 1), 0xFFE2E7F0.toInt()) }
        layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { setMargins(dp(a, 3), 0, dp(a, 3), dp(a, 10)) }
        addView(text(a, n.toString(), 22f, true, col).apply { gravity = Gravity.CENTER })
        addView(text(a, label, 12f, false, MUTED).apply { gravity = Gravity.CENTER })
    }

    fun open(a: Activity, url: String) {
        try { a.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url))) }
        catch (e: Exception) { android.widget.Toast.makeText(a, "Kein Browser gefunden", android.widget.Toast.LENGTH_SHORT).show() }
    }

    fun copy(a: Activity, label: String, textValue: String) {
        (a.getSystemService(Activity.CLIPBOARD_SERVICE) as android.content.ClipboardManager).setPrimaryClip(android.content.ClipData.newPlainText(label, textValue))
        android.widget.Toast.makeText(a, "Kopiert", android.widget.Toast.LENGTH_SHORT).show()
    }

    // ---------------------------------------------------------------- Design-Bausteine
    const val PURPLE = 0xFF6D4AE8.toInt()
    const val GREEN = 0xFF16A34A.toInt()
    const val RED = 0xFFDC2626.toInt()
    const val AMBER = 0xFFD97706.toInt()

    fun soft(col: Int): Int = (col and 0x00FFFFFF) or 0x1F000000   // 12 % Deckkraft
    fun stateColor(state: String) = when (state) { "Rot" -> RED; "Gelb" -> AMBER; "Grün" -> GREEN; else -> MUTED }
    fun stateWord(state: String) = when (state) { "Grün" -> "Alles gut"; "Gelb" -> "Kleinigkeiten"; "Rot" -> "Bitte kümmern"; else -> state.ifBlank { "unbekannt" } }
    fun stateIcon(state: String) = when (state) { "Grün" -> R.drawable.ic_s_checkcircle; "Gelb" -> R.drawable.ic_s_info; "Rot" -> R.drawable.ic_s_alert; else -> R.drawable.ic_s_pcs }

    fun icon(a: Activity, res: Int, col: Int, size: Int = 20): android.widget.ImageView = android.widget.ImageView(a).apply {
        setImageResource(res); setColorFilter(col)
        layoutParams = LinearLayout.LayoutParams(dp(a, size), dp(a, size))
    }

    /** Farbige Kachel mit Symbol (z.B. vor Überschriften und Listeneinträgen). */
    fun tile(a: Activity, res: Int, col: Int, size: Int = 40, filled: Boolean = false): android.widget.FrameLayout = android.widget.FrameLayout(a).apply {
        background = GradientDrawable().apply { setColor(if (filled) col else soft(col)); cornerRadius = dp(a, size / 3).toFloat() }
        layoutParams = LinearLayout.LayoutParams(dp(a, size), dp(a, size)).apply { setMargins(0, 0, dp(a, 12), 0); gravity = Gravity.CENTER_VERTICAL }
        addView(android.widget.ImageView(a).apply { setImageResource(res); setColorFilter(if (filled) Color.WHITE else col) },
            android.widget.FrameLayout.LayoutParams(dp(a, size * 11 / 20), dp(a, size * 11 / 20), Gravity.CENTER))
    }

    /** Überschrift einer Karte mit Symbol-Kachel. */
    fun heading(a: Activity, res: Int, col: Int, title: String, sub: String? = null): LinearLayout = LinearLayout(a).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
        setPadding(0, 0, 0, dp(a, 8))
        addView(tile(a, res, col, 36))
        addView(LinearLayout(a).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            addView(text(a, title, 17f, true))
            if (!sub.isNullOrBlank()) addView(text(a, sub, 13f, false, MUTED))
        })
    }

    /** Kleines farbiges Abzeichen ("Alles gut", "Demo" …). */
    fun badge(a: Activity, s: String, col: Int): TextView = text(a, s, 12f, true, col).apply {
        val h = dp(a, 9); val v = dp(a, 3); setPadding(h, v, h, v)
        background = GradientDrawable().apply { setColor(soft(col)); cornerRadius = dp(a, 20).toFloat() }
    }

    /** Dünner Fortschrittsbalken (z.B. Score). */
    fun meter(a: Activity, value: Int, col: Int): android.widget.ProgressBar = android.widget.ProgressBar(a, null, android.R.attr.progressBarStyleHorizontal).apply {
        max = 100; progress = value.coerceIn(0, 100)
        progressTintList = android.content.res.ColorStateList.valueOf(col)
        progressBackgroundTintList = android.content.res.ColorStateList.valueOf(0xFFE2E7F0.toInt())
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(a, 6)).apply { setMargins(0, dp(a, 8), 0, 0) }
    }

    /** Großer farbiger Kopfbereich mit Verlauf. */
    fun hero(a: Activity, res: Int, title: String, sub: String): LinearLayout = LinearLayout(a).apply {
        orientation = LinearLayout.VERTICAL
        val p = dp(a, 18); setPadding(p, p, p, p)
        background = GradientDrawable(GradientDrawable.Orientation.TL_BR, intArrayOf(0xFF1C4FA6.toInt(), 0xFF3B5BDB.toInt(), PURPLE)).apply { cornerRadius = dp(a, 18).toFloat() }
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { setMargins(0, 0, 0, dp(a, 12)) }
        val row = LinearLayout(a).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        row.addView(android.widget.FrameLayout(a).apply {
            background = GradientDrawable().apply { setColor(0x33FFFFFF); cornerRadius = dp(a, 14).toFloat() }
            layoutParams = LinearLayout.LayoutParams(dp(a, 48), dp(a, 48)).apply { setMargins(0, 0, dp(a, 14), 0) }
            addView(android.widget.ImageView(a).apply { setImageResource(res); setColorFilter(Color.WHITE) }, android.widget.FrameLayout.LayoutParams(dp(a, 28), dp(a, 28), Gravity.CENTER))
        })
        row.addView(LinearLayout(a).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            addView(text(a, title, 22f, true, Color.WHITE).apply { tag = "title" })
            addView(text(a, sub, 13f, false, 0xDDFFFFFF.toInt()).apply { tag = "sub" })
        })
        addView(row)
    }

    /** Kennzahl im Kopfbereich (weiß auf Verlauf). */
    fun heroStat(a: Activity, n: Int, label: String): LinearLayout = LinearLayout(a).apply {
        orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL
        val p = dp(a, 6); setPadding(p, dp(a, 8), p, dp(a, 8))
        background = GradientDrawable().apply { setColor(0x26FFFFFF); cornerRadius = dp(a, 12).toFloat() }
        layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { setMargins(dp(a, 3), dp(a, 12), dp(a, 3), 0) }
        addView(text(a, n.toString(), 20f, true, Color.WHITE).apply { gravity = Gravity.CENTER })
        addView(text(a, label, 11f, false, 0xDDFFFFFF.toInt()).apply { gravity = Gravity.CENTER })
    }

    /** Zeile mit Symbol, Text und Pfeil – für Menülisten (Links, Einstellungen). */
    fun navRow(a: Activity, res: Int, col: Int, title: String, sub: String? = null, onClick: () -> Unit): LinearLayout = LinearLayout(a).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
        setPadding(0, dp(a, 8), 0, dp(a, 8))
        addView(tile(a, res, col, 34))
        addView(LinearLayout(a).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            addView(text(a, title, 15f, true))
            if (!sub.isNullOrBlank()) addView(text(a, sub, 12f, false, MUTED))
        })
        addView(icon(a, R.drawable.ic_s_chev, MUTED, 18))
        isClickable = true
        val out = TypedValue(); a.theme.resolveAttribute(android.R.attr.selectableItemBackground, out, true); setBackgroundResource(out.resourceId)
        setOnClickListener { onClick() }
    }
}
