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

    fun button(a: Activity, s: String, primary: Boolean = true, onClick: () -> Unit): Button = Button(a).apply {
        text = s; isAllCaps = false; textSize = 15f
        setTextColor(if (primary) Color.WHITE else BLUE)
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
}
