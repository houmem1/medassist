"""Contrôle de l'installation MedAssist : Ollama, modèles, index documentaire, lecteur radio, Open WebUI.

Usage (n'importe quel Python 3.11 avec numpy, par exemple celui d'Open WebUI) :
  %USERPROFILE%\\open-webui\\venv\\Scripts\\python.exe doctor.py
Dossier d'installation : variable MEDASSIST_ROOT, sinon %USERPROFILE%\\open-webui.
Code de sortie 0 si tout est bon, 1 sinon. Aucune donnée n'est envoyée hors du PC.
"""
import json
import os
import re
import socket
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("MEDASSIST_ROOT", Path.home() / "open-webui"))  # dossier d'installation
OLLAMA = "http://localhost:11434"
MODELS = {"qwen3.6:35b": "rédaction et relecture", "medgemma:4b": "vision médicale", "bge-m3": "base documentaire"}
PIPE_SOURCE = Path(__file__).resolve().parent / "openwebui" / "medassist_pipe.py"
OK, KO, WARN = "✅", "❌", "⚠️ "
problems = 0


def line(ok, label, detail="", warn=False):
    global problems
    mark = OK if ok else (WARN if warn else KO)
    if not ok and not warn:
        problems += 1
    print(f"{mark} {label}" + (f" — {detail}" if detail else ""))


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.load(resp)


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


# --- Ollama et modèles
try:
    tags = get(f"{OLLAMA}/api/tags")
    installed = {m["name"] for m in tags["models"]}
    line(True, "Ollama répond", OLLAMA)
    for model, role in MODELS.items():
        present = model in installed or f"{model}:latest" in installed
        line(present, f"Modèle {model} ({role})", "" if present else f"ollama pull {model}")
except Exception as e:  # noqa: BLE001
    line(False, "Ollama répond", f"{e} — lancez Ollama")

# --- Base documentaire
index = ROOT / "knowledge" / "index"
try:
    manifest = json.loads((index / "manifest.json").read_text(encoding="utf-8"))
    n_lines = sum(1 for _ in (index / "passages.jsonl").open(encoding="utf-8"))
    import numpy as np
    n_rows = np.load(index / "embeddings.npy", mmap_mode="r").shape[0]
    coherent = n_lines == n_rows == manifest.get("passages")
    line(coherent, "Index documentaire", f"{n_lines} passages, {len(manifest.get('documents', {}))} documents, "
                                         f"construit le {manifest.get('built')}" + ("" if coherent else " — INCOHÉRENT : relancez ingest.py"))
    docs = {p.name for p in (ROOT / "knowledge" / "docs").glob("*.pdf")}
    missing = docs - set(manifest.get("documents", {}))
    line(not missing, "PDF tous indexés", "" if not missing else f"non indexés : {', '.join(sorted(missing))} — relancez ingest.py", warn=True)
except FileNotFoundError:
    line(False, "Index documentaire", f"absent dans {index} — lancez knowledge\\ingest.py", warn=True)
except Exception as e:  # noqa: BLE001
    line(False, "Index documentaire", str(e))

# --- Lecteur radio
try:
    health = get("http://127.0.0.1:8765/health", timeout=3)
    line(bool(health.get("ok")), "Lecteur radio thoracique", health.get("modele", ""))
except Exception:  # noqa: BLE001
    line(False, "Lecteur radio thoracique", "service arrêté sur 127.0.0.1:8765 (start-medassist.ps1 le lance)", warn=True)
cal = ROOT / "radiology" / "calibration.json"
if cal.exists():
    local = json.loads(cal.read_text(encoding="utf-8")).get("local")
    line(bool(local), "Calibration adulte locale", f"{local['n_calibration']} radios normales" if local
         else "absente : pas de verdict du spécialiste chez l'adulte (radiology\\calibrate_local.py)", warn=True)

# --- Open WebUI et fonction installée
line(port_open(8080), "Open WebUI", "http://localhost:8080" if port_open(8080) else "arrêté (start-medassist.ps1)", warn=True)
try:
    db = sqlite3.connect(f"file:{ROOT / 'data' / 'webui.db'}?mode=ro", uri=True)
    content, active = db.execute("SELECT content, is_active FROM function WHERE id='medassist'").fetchone()
    installed_v = re.search(r"^version:\s*(\S+)", content, re.M).group(1)
    source_v = re.search(r"^version:\s*(\S+)", PIPE_SOURCE.read_text(encoding="utf-8"), re.M).group(1) if PIPE_SOURCE.exists() else None
    same = source_v in (None, installed_v)
    line(bool(active) and same, f"Fonction MedAssist {installed_v}" + (" active" if active else " INACTIVE"),
         "" if same else f"source {source_v} non installée : openwebui\\install.py")
    signup = db.execute("SELECT value FROM config WHERE key='ui.enable_signup'").fetchone()
    closed = signup is not None and json.loads(signup[0]) is False
    line(closed, "Inscriptions fermées" if closed else "Inscriptions ouvertes",
         "" if closed else "Admin > Paramètres > Général > Autoriser les inscriptions, à désactiver une fois les comptes créés",
         warn=True)
except Exception as e:  # noqa: BLE001
    line(False, "Fonction MedAssist dans Open WebUI", str(e))

# --- Fichiers de lancement
line((ROOT / ".webui_secret_key").exists(), "Clé de session fixe", "" if (ROOT / ".webui_secret_key").exists()
     else "créée au prochain lancement par start-medassist.ps1", warn=True)
line((ROOT / "ca-bundle.pem").exists(), "Certificats (Avast)", str(ROOT / "ca-bundle.pem"), warn=True)

# --- Habillage (logo, feuille de style, fiches des modèles)
try:
    import open_webui
    pkg = Path(open_webui.__file__).resolve().parent
    src = next(d for d in (pkg / "frontend" / "static", pkg / "static" / "static") if d.is_dir())
    static_ok = (src / "custom.css").stat().st_size > 0 and (src / "medassist_pro.png").exists()
except Exception:  # noqa: BLE001
    static_ok = False
try:
    db = sqlite3.connect(f"file:{ROOT / 'data' / 'webui.db'}?mode=ro", uri=True)
    n_cards = db.execute("SELECT count(*) FROM model WHERE id IN ('medassist.pro', 'medassist.patient')").fetchone()[0]
except Exception:  # noqa: BLE001
    n_cards = 0
line(static_ok and n_cards == 2, "Habillage MedAssist",
     "logo, feuille de style et fiches des deux modèles" if static_ok and n_cards == 2
     else "incomplet : relancez openwebui\\install.py", warn=True)

print("\nTout est en ordre." if not problems else f"\n{problems} problème(s) bloquant(s).")
sys.exit(1 if problems else 0)
