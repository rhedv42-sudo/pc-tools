"""Hintergrund-Aufträge mit Protokollzeilen, die die Oberfläche abfragt."""
import itertools
import threading
import time
import traceback

from .i18n import t

MAX_LINES = 5000
_jobs = {}
_lock = threading.Lock()
_ids = itertools.count(1)


class Job:
    def __init__(self, kind, title):
        self.id = str(next(_ids))
        self.kind = kind
        self.title = title
        self.lines = []
        self.state = "running"     # running | done | error
        self.result = None
        self.progress = None       # 0..100 oder None
        self.started = time.time()
        self.finished = None
        self._lock = threading.Lock()

    def log(self, line):
        with self._lock:
            self.lines.append(str(line))
            if len(self.lines) > MAX_LINES:
                del self.lines[: len(self.lines) - MAX_LINES]

    def to_dict(self, since=0):
        with self._lock:
            since = max(0, min(since, len(self.lines)))
            return {"id": self.id, "kind": self.kind, "title": self.title, "state": self.state,
                    "lines": self.lines[since:], "next": len(self.lines), "result": self.result,
                    "progress": self.progress, "started": self.started, "finished": self.finished}


def start(kind, title, func, *args):
    """Startet func(job, *args) in einem Thread. Der Rückgabewert wird job.result."""
    job = Job(kind, title)
    with _lock:
        # Alte, fertige Aufträge aufräumen
        for jid in [j for j, o in _jobs.items() if o.finished and time.time() - o.finished > 3600]:
            del _jobs[jid]
        _jobs[job.id] = job

    def runner():
        try:
            job.result = func(job, *args)
            job.state = "done"
            if isinstance(job.result, dict) and job.result.get("error"):
                job.state = "error"
        except Exception as e:  # Fehler sichtbar machen statt den Server zu stören
            job.log(t("Fehler: {0}", e))
            job.log(traceback.format_exc().splitlines()[-1])
            job.state = "error"
        job.finished = time.time()
        job.progress = 100 if job.state == "done" else job.progress

    threading.Thread(target=runner, name="job-" + job.id, daemon=True).start()
    return job


def get(job_id):
    with _lock:
        return _jobs.get(str(job_id))


def running():
    with _lock:
        return [j.to_dict(len(j.lines)) for j in _jobs.values() if j.state == "running"]
