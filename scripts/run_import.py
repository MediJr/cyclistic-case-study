"""Mission 4 : import brut puis contrôles d'import, en un seul processus.

Usage : python -I scripts/run_import.py
Le mot de passe est demandé une seule fois (getpass) et reste en mémoire de ce processus.
S'arrête sans lancer les contrôles si l'import échoue.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import load_raw  # noqa: E402
import qa_import  # noqa: E402

t0 = time.time()
print("=== IMPORT BRUT ===")
try:
    load_raw.main()
except Exception as e:  # arrêt immédiat : aucun contournement
    print("IMPORT ÉCHOUÉ :", e)
    sys.exit(2)
print(f"Durée import : {time.time() - t0:.0f} s")

print("\n=== CONTRÔLES D'IMPORT ===")
qa_import.main()
