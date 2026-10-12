"""Test de connexion PostgreSQL (lecture seule : ne crée rien, n'importe rien).

Usage : python -I scripts/check_pg.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pg import psql  # noqa: E402

try:
    (version, user, enc), = psql("postgres", "SELECT version(), current_user, "
                                 "pg_encoding_to_char(encoding) FROM pg_database WHERE datname = 'postgres'")
    (can_create,), = psql("postgres", "SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname = current_user")
    exists = bool(psql("postgres", "SELECT 1 FROM pg_database WHERE datname = 'cyclistic'"))
except RuntimeError as e:
    print("CONNEXION ÉCHOUÉE :", e)
    sys.exit(1)
print("CONNEXION OK")
print("  serveur              :", version)
print("  utilisateur          :", user)
print("  encodage serveur     :", enc)
print("  droit CREATE DATABASE:", "oui" if can_create == "t" else "NON")
print("  base cyclistic       :", "existe déjà" if exists else "absente (sera créée à l'import)")
