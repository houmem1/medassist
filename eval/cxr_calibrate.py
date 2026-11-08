"""Seuils du lecteur spécialisé par population, fixés sur des données de CALIBRATION uniquement.

Règles (choisies avant d'en voir l'effet sur les jeux de test) :
- « radio anormale » : score global = max des 4 scores d'opacité (enfant : pneumonie) ou des 18 anomalies
  (adulte), comme fixé dans cxr_metrics.PRIMARY ; seuil = le plus haut qui détecte au moins
  90 % des radios pathologiques de calibration ;
- affichage d'une anomalie : son score doit dépasser le 95e centile des radios NORMALES de calibration
  (au plus ~5 % de fausses alertes par anomalie) ;
- anomalie écartée de l'affichage si ce seuil est < 0,10 : sortie quasi nulle, le moindre bruit la déclencherait.
Calibration enfant : 400 radios d'entraînement Kermany. Calibration adulte : 160 radios de Shenzhen.
Tests indépendants : Kermany test (enfant), Montgomery (adulte).

Usage : python eval/cxr_calibrate.py   -> radiology/calibration.json, puis les métriques sur les tests
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
CALIB = {"enfant": "kermanycalib", "adulte": "shenzhen"}
TEST = {"enfant": "kermany", "adulte": "montgomery"}
OPACITY = ["Pneumonia", "Consolidation", "Lung Opacity", "Infiltration"]
GLOBAL = {"enfant": OPACITY, "adulte": None}  # None : les 18 anomalies
MIN_THRESHOLD = 0.10


def global_score(probs, pop):
    keys = GLOBAL[pop] or probs.keys()
    return max(probs[k] for k in keys)


def load(name):
    return [json.loads(line) for line in (RESULTS / f"cxr_{name}.jsonl").open(encoding="utf-8")]


def calibrate(rows, pop, target_sens=0.90, normal_quantile=95):
    pos = sorted(global_score(r["probs"], pop) for r in rows if r["label"])
    labels = rows[0]["probs"].keys()
    normals = [r["probs"] for r in rows if not r["label"]]
    return {"score_global": GLOBAL[pop] or "toutes", "seuil_global": pos[int(np.floor((1 - target_sens) * len(pos)))],
            "seuils_anomalies": {k: t for k in labels
                                 if (t := float(np.percentile([p[k] for p in normals], normal_quantile))) >= MIN_THRESHOLD},
            "n_calibration": len(rows)}


def evaluate(rows, cal, pop):
    """Sensibilité / spécificité du score global, et part de radios normales avec au moins une anomalie affichée."""
    y = np.array([r["label"] for r in rows])
    glob = np.array([global_score(r["probs"], pop) >= cal["seuil_global"] for r in rows])
    shown = np.array([any(r["probs"][k] >= t for k, t in cal["seuils_anomalies"].items()) for r in rows])
    return (f"global : sens {glob[y == 1].mean():.0%} spec {(~glob[y == 0]).mean():.0%} | "
            f"au moins une anomalie affichée : malades {shown[y == 1].mean():.0%}, normales {shown[y == 0].mean():.0%}")


if __name__ == "__main__":
    out = {}
    for pop in ("enfant", "adulte"):
        out[pop] = calibrate(load(CALIB[pop]), pop)
        print(f"{pop} : seuil global {out[pop]['seuil_global']:.3f} (calibration {CALIB[pop]}, n={out[pop]['n_calibration']})")
        print(f"   test {TEST[pop]} -> {evaluate(load(TEST[pop]), out[pop], pop)}")
    (ROOT / "radiology" / "calibration.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("écrit : radiology/calibration.json")
