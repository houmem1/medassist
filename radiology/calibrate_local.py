"""Calibre le lecteur spécialisé sur les radiographies NORMALES de votre propre service (adultes, face).

Les seuils dépendent de l'appareil et du traitement d'image : calibrés dans un hôpital, ils ne tiennent pas
dans un autre. Avec 50 à 100 radiographies thoraciques de face d'adultes, jugées normales par un radiologue
et anonymisées (PNG ou JPEG), le lecteur donne ensuite un verdict calibré pour votre site.

Usage (Python de cxr-venv, service arrêté) :
  python radiology/calibrate_local.py C:\\chemin\\vers\\radios_normales
Règles : seuil de chaque anomalie = 95e centile des normales (≈ 5 % de fausses alertes par anomalie) ;
seuil global = 95e centile du maximum des anomalies retenues. Sans cas pathologiques, la sensibilité reste
à mesurer : faites-la vérifier sur quelques cas connus avant usage.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cxr_model import CXRReader  # noqa: E402

MIN_IMAGES, MIN_THRESHOLD = 50, 0.10
CAL_FILE = Path(__file__).resolve().parent / "calibration.json"

if __name__ == "__main__":
    folder = Path(sys.argv[1])
    files = sorted(f for f in folder.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if len(files) < MIN_IMAGES:
        sys.exit(f"{len(files)} images trouvées : il en faut au moins {MIN_IMAGES}.")
    reader = CXRReader()
    probs = []
    for n, f in enumerate(files, 1):
        probs.append(reader.predict(f.read_bytes()))
        if n % 10 == 0:
            print(f"{n}/{len(files)}", flush=True)
    thresholds = {k: t for k in probs[0] if (t := float(np.percentile([p[k] for p in probs], 95))) >= MIN_THRESHOLD}
    glob = float(np.percentile([max(p[k] for k in thresholds) for p in probs], 95))
    cal = json.loads(CAL_FILE.read_text(encoding="utf-8"))
    cal["local"] = {"score_global": sorted(thresholds), "seuil_global": glob, "seuils_anomalies": thresholds,
                    "n_calibration": len(files), "source": str(folder)}
    CAL_FILE.write_text(json.dumps(cal, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Calibration locale enregistrée ({len(files)} radios normales). Redémarrez MedAssist.")
