package de.rh.pctools

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent

/** Prüft im Hintergrund (ca. alle 15 Minuten): neuer Hilferuf oder PC wird rot -> Benachrichtigung. */
class CheckJob : JobService() {
    override fun onStartJob(params: JobParameters): Boolean {
        Thread {
            try { check(this) } catch (_: Exception) { }
            jobFinished(params, false)
        }.start()
        return true
    }

    override fun onStopJob(params: JobParameters) = true

    companion object {
        private const val JOB_ID = 4711
        private const val CHANNEL = "pctools"

        fun schedule(c: Context) {
            val js = c.getSystemService(JobScheduler::class.java) ?: return
            if (js.getPendingJob(JOB_ID) != null) return
            js.schedule(
                JobInfo.Builder(JOB_ID, ComponentName(c, CheckJob::class.java))
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                    .setPeriodic(15 * 60 * 1000L)
                    .setPersisted(true)
                    .build()
            )
        }

        fun check(c: Context) {
            if (!Ha.isSetUp(c) || Ha.demo(c)) return
            val pcs = Ha.loadPcs(c)
            val p = Ha.prefs(c)
            val nm = c.getSystemService(NotificationManager::class.java) ?: return
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "PC-Tools Meldungen", NotificationManager.IMPORTANCE_HIGH))
            val ed = p.edit()
            for (pc in pcs) {
                val helpKey = "help_" + pc.key
                if (pc.helpOpen && pc.helpTime.isNotBlank() && p.getString(helpKey, "") != pc.helpTime) {
                    notify(c, nm, pc, "Hilferuf von ${pc.name}", if (pc.helpMessage.isNotBlank()) pc.helpMessage else "Bericht in der App ansehen", pc.key.hashCode())
                    ed.putString(helpKey, pc.helpTime)
                }
                val stKey = "state_" + pc.key
                val old = p.getString(stKey, "")
                if (pc.state == "Rot" && old != "Rot") {
                    notify(c, nm, pc, "${pc.name} ist rot", pc.problems.firstOrNull() ?: "Bitte in der App nachsehen", pc.key.hashCode() + 1)
                }
                ed.putString(stKey, pc.state)
            }
            ed.apply()
        }

        private fun notify(c: Context, nm: NotificationManager, pc: Pc, title: String, text: String, id: Int) {
            val pi = PendingIntent.getActivity(c, id, Intent(c, PcActivity::class.java).putExtra("key", pc.key).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            val n = Notification.Builder(c, CHANNEL)
                .setSmallIcon(R.drawable.ic_notify)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(Notification.BigTextStyle().bigText(text))
                .setContentIntent(pi)
                .setAutoCancel(true)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setPublicVersion(Notification.Builder(c, CHANNEL).setSmallIcon(R.drawable.ic_notify).setContentTitle(title).setContentText("Details in der App ansehen").setContentIntent(pi).setAutoCancel(true).build())
                .build()
            try { nm.notify(id, n) } catch (_: SecurityException) { }
        }
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) { try { CheckJob.schedule(context) } catch (_: Exception) { } }
}
