"""Journal d'exécution persistant (C1, plan v3.2 §8.2).

Usage :
    with RunLog("nettoyage", files=[...]) as log:
        log.info("message")
Crée reports/logs/<étape>_<AAAAMMJJ-HHMMSS>.log contenant :
- heure de début et de fin, code de sortie (OK / ÉCHEC + exception) ;
- SHA-256 des scripts, fichiers SQL, configurations et du plan utilisés ;
- toute la sortie console (stdout et stderr dupliqués dans le fichier) ;
- chaque appel psql (libellé, durée, lignes renvoyées) via le point d'accroche pg.LOGGER.
N'enregistre jamais de secret : les variables d'environnement ne sont pas journalisées.
"""
import datetime as dt
import hashlib
import os
import platform
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _Tee:
    def __init__(self, stream, fh):
        self.stream, self.fh = stream, fh

    def write(self, s):
        try:
            self.stream.write(s)
        except UnicodeEncodeError:  # console non UTF-8 (redirection sous Windows) : remplacement, jamais d'arrêt
            enc = getattr(self.stream, "encoding", None) or "ascii"
            self.stream.write(s.encode(enc, "replace").decode(enc))
        self.fh.write(s)  # le journal sur disque reste en UTF-8 intégral
        self.fh.flush()

    def flush(self):
        self.stream.flush()
        self.fh.flush()


class RunLog:
    def __init__(self, step, files=(), log_dir=None):
        self.step = step
        self.files = list(files)
        reports = os.environ.get("CYCLISTIC_REPORTS_DIR", os.path.join(ROOT, "reports"))
        self.log_dir = log_dir or os.path.join(reports, "logs")
        self.started = dt.datetime.now().astimezone()
        self.path = os.path.join(self.log_dir, f"{step}_{self.started:%Y%m%d-%H%M%S}.log")
        self.hashes = {}

    def __enter__(self):
        os.makedirs(self.log_dir, exist_ok=True)
        if os.path.exists(self.path):
            raise RuntimeError(f"journal déjà existant : {self.path}")
        self.fh = open(self.path, "x", encoding="utf-8")
        self._out, self._err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Tee(self._out, self.fh), _Tee(self._err, self.fh)
        print(f"# Étape : {self.step}")
        print(f"# Début : {self.started.isoformat()}")
        print(f"# Python {platform.python_version()} — {platform.platform()}")
        print("# Empreintes SHA-256 des fichiers utilisés :")
        for f in self.files:
            p = f if os.path.isabs(f) else os.path.join(ROOT, f)
            self.hashes[os.path.relpath(p, ROOT).replace("\\", "/")] = sha256(p)
        for name, h in sorted(self.hashes.items()):
            print(f"#   {h}  {name}")
        try:
            import pg
            pg.LOGGER = self._psql_hook
        except ImportError:
            pass
        return self

    def _psql_hook(self, label, seconds, nrows, error):
        status = f"ERREUR {error.splitlines()[0] if error else ''}" if error else f"{nrows} ligne(s)"
        print(f"[psql] {os.path.basename(str(label))[:80]} — {seconds:.1f} s — {status}")

    def info(self, msg):
        print(f"[{dt.datetime.now():%H:%M:%S}] {msg}")

    def __exit__(self, exc_type, exc, tb):
        end = dt.datetime.now().astimezone()
        if exc_type is not None and exc_type is not SystemExit:
            print("# ÉCHEC :", "".join(traceback.format_exception_only(exc_type, exc)).strip())
            status = "ÉCHEC"
        elif exc_type is SystemExit and exc.code not in (0, None):
            status = f"ÉCHEC (code {exc.code})"
        else:
            status = "OK"
        print(f"# Fin : {end.isoformat()} — durée {(end - self.started).total_seconds():.1f} s — statut {status}")
        sys.stdout, sys.stderr = self._out, self._err
        self.fh.close()
        try:
            import pg
            pg.LOGGER = None
        except ImportError:
            pass
        return False
