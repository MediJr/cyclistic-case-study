"""Accès PostgreSQL via psql (aucun mot de passe dans le code ni sur disque).

Ordre de recherche du mot de passe :
1. variable PGPASSWORD déjà définie dans le terminal (temporaire, propre à la session) ;
2. fichier pgpass (PGPASSFILE ou %APPDATA%\\postgresql\\pgpass.conf) s'il existe ;
3. sinon, saisie masquée dans le terminal (getpass), gardée en mémoire pour ce seul processus.
"""
import getpass
import os
import subprocess
import sys

_PSQL_WINDOWS_DEFAULT = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"
# Variable PSQL si définie ; sinon installation Windows par défaut si elle existe ; sinon psql du PATH.
PSQL = os.environ.get("PSQL") or (_PSQL_WINDOWS_DEFAULT if os.path.isfile(_PSQL_WINDOWS_DEFAULT) else "psql")


def _interactive():
    """Vrai seulement pour une vraie console (sous Windows, NUL passe isatty())."""
    if not sys.stdin.isatty():
        return False
    if os.name != "nt":
        return True
    import ctypes
    import msvcrt
    mode = ctypes.c_ulong()
    handle = msvcrt.get_osfhandle(sys.stdin.fileno())
    return ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)) != 0


def _ensure_password():
    if os.environ.get("PGPASSWORD"):
        return
    pgpass = os.environ.get("PGPASSFILE") or os.path.join(
        os.environ.get("APPDATA", ""), "postgresql", "pgpass.conf")
    if os.path.isfile(pgpass):
        return
    if not _interactive():
        raise RuntimeError("Aucun mot de passe PostgreSQL disponible : lancez le script dans un "
                           "terminal interactif ou définissez PGPASSWORD pour la session.")
    user = os.environ.get("PGUSER", "postgres")
    os.environ["PGPASSWORD"] = getpass.getpass(f"Mot de passe PostgreSQL ({user}@localhost) : ")


def _env():
    _ensure_password()
    env = dict(os.environ)
    env.setdefault("PGHOST", "localhost")
    env.setdefault("PGUSER", "postgres")
    env["PGCLIENTENCODING"] = "UTF8"
    return env


# Point d'accroche facultatif pour journaliser chaque appel (cf. scripts/runlog.py) :
# fonction(description, durée_s, nb_lignes). Ne reçoit jamais de secret.
LOGGER = None


def _set_lines(variables):
    """Variables psql transmises par l'entrée standard (UTF-8), jamais en ligne de commande."""
    lines = []
    for name, value in (variables or {}).items():
        value = str(value)
        if not name.isidentifier() or any(c in value for c in "\\\n\r"):
            raise ValueError(f"variable psql refusée : {name}")
        lines.append(f"\\set {name} '" + value.replace("'", "''") + "'")
    return "\n".join(lines) + ("\n" if lines else "")


def psql(db, sql=None, file=None, stdin=None, read_only=False, single_transaction=False,
         variables=None, label=None):
    """Exécute du SQL (ou un fichier) ; renvoie les lignes (champs séparés par tabulation).

    read_only          : session forcée en lecture seule (default_transaction_read_only=on).
    single_transaction : tout le script dans une seule transaction (psql -1).
    variables          : dict de variables psql (\\set), utilisables en :'nom' dans le SQL.
    """
    import time
    cmd = [PSQL, "-X", "-w", "-q", "-v", "ON_ERROR_STOP=1", "-At", "-F", "\t", "-d", db]
    if single_transaction:
        cmd.append("-1")
    # Le SQL passe par l'entrée standard en UTF-8 : un argument -c serait converti
    # dans la page de code Windows et corromprait les caractères accentués.
    if file and not variables:
        cmd += ["-f", file]
    else:
        cmd += ["-f", "-"]
        if file:
            sql = open(file, encoding="utf-8").read()
        if sql is not None:
            stdin = sql if sql.rstrip().endswith(";") or file else sql + ";"
        if variables:
            stdin = _set_lines(variables) + (stdin or "")
    env = _env()
    if read_only:
        env["PGOPTIONS"] = (env.get("PGOPTIONS", "") + " -c default_transaction_read_only=on").strip()
    t0 = time.time()
    res = subprocess.run(cmd, input=stdin.encode("utf-8") if stdin else None,
                         capture_output=True, env=env)
    if res.returncode != 0:
        # messages du serveur : UTF-8 (PGCLIENTENCODING) ; messages propres à psql : page de code Windows
        try:
            err = res.stderr.decode("utf-8").strip()
        except UnicodeDecodeError:
            err = res.stderr.decode("cp1252", errors="replace").strip()
        if LOGGER:
            LOGGER(label or (file or "sql"), time.time() - t0, None, err)
        raise RuntimeError(f"psql a échoué ({res.returncode}) : {err}")
    out = res.stdout.decode("utf-8")  # données : UTF-8 strict (PGCLIENTENCODING)
    rows = [line.split("\t") for line in out.splitlines() if line != ""]
    if LOGGER:
        LOGGER(label or (file or "sql"), time.time() - t0, len(rows), None)
    return rows
