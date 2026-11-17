package de.rh.pctools

import android.app.Application

/** Merkt sich einen Absturz, damit die App ihn beim nächsten Start anzeigen kann (zum Weitergeben an den Entwickler). */
class App : Application() {
    override fun onCreate() {
        super.onCreate()
        val prev = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            try {
                val sw = java.io.StringWriter(); e.printStackTrace(java.io.PrintWriter(sw))
                Ha.prefs(this).edit().putString("crash", "Version ${BuildConfigLite.version(this)} · Android ${android.os.Build.VERSION.RELEASE} · ${android.os.Build.MODEL}\n\n" + sw.toString().take(6000)).commit()
            } catch (_: Exception) { }
            prev?.uncaughtException(t, e)
        }
    }
}

object BuildConfigLite {
    fun version(c: android.content.Context): String = try { c.packageManager.getPackageInfo(c.packageName, 0).versionName ?: "?" } catch (e: Exception) { "?" }
}
