"""Métriques des lectures de radiographies : AUC, sensibilité, spécificité (IC 95 % par bootstrap).

Usage : python eval/cxr_metrics.py   (lit tous les eval/results/cxr_*.jsonl)

Scores principaux, fixés AVANT de voir les résultats (choisir après coup le meilleur score
gonflerait la performance) :
- kermany (pneumonie de l'enfant) : max(Pneumonia, Consolidation, Lung Opacity, Infiltration)
- montgomery (radio anormale, tuberculose) : max des 18 anomalies
Les autres scores du spécialiste sont exploratoires.
"""
import json
from pathlib import Path

import numpy as np

RESULTS = Path(__file__).resolve().parent / "results"
OPACITY = ["Pneumonia", "Consolidation", "Lung Opacity", "Infiltration"]
PRIMARY = {"kermany": lambda p: max(p[k] for k in OPACITY), "montgomery": lambda p: max(p.values())}
EXPLORATORY = ["Pneumonia", "Lung Opacity", "Consolidation", "Infiltration", "Fibrosis", "Effusion"]


def auc(y, s):
    """Probabilité qu'un positif ait un score plus élevé qu'un négatif (ex aequo = 1/2)."""
    y, s = np.asarray(y), np.asarray(s)
    pos, neg = s[y == 1], s[y == 0]
    return ((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg))


def metrics(y, s, threshold=0.5, boot=1000):
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    pred = s >= threshold
    sens, spec = pred[y == 1].mean(), (~pred[y == 0]).mean()
    rng = np.random.default_rng(0)
    aucs = []
    for _ in range(boot):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            aucs.append(auc(y[i], s[i]))
    lo, hi = np.percentile(aucs, [2.5, 97.5])
    return f"AUC {auc(y, s):.3f} [{lo:.3f}-{hi:.3f}]  sens {sens:.0%}  spec {spec:.0%}  acc {(pred == y).mean():.0%}  n={len(y)}"


def pediatric_threshold(target_sens=0.90):
    """Seuil fixé sur l'ensemble de calibration (jeu d'ENTRAÎNEMENT Kermany) : le plus haut seuil qui détecte
    au moins 90 % des pneumonies. Règle choisie avant de voir son effet sur le test."""
    f = RESULTS / "cxr_kermanycalib.jsonl"
    if not f.exists():
        return None
    pos = sorted(PRIMARY["kermany"](r["probs"]) for r in map(json.loads, f.open(encoding="utf-8")) if r["label"])
    return pos[int(np.floor((1 - target_sens) * len(pos)))]


if __name__ == "__main__":
    ped = pediatric_threshold()
    for f in sorted(RESULTS.glob("cxr_*.jsonl")):
        rows = [json.loads(line) for line in f.open(encoding="utf-8")]
        dataset = f.stem.split("_")[1]
        if dataset not in PRIMARY:
            continue
        print(f"== {f.stem}")
        if "probs" in rows[0]:  # lecteur spécialisé
            y = [r["label"] for r in rows]
            print(f"   PRINCIPAL         {metrics(y, [PRIMARY[dataset](r['probs']) for r in rows])}")
            if dataset == "kermany" and ped is not None:
                print(f"   seuil pédiatrique {ped:.3f} (calibration) : "
                      f"{metrics(y, [PRIMARY[dataset](r['probs']) for r in rows], threshold=ped)}")
            for k in EXPLORATORY:
                print(f"   {k:17s} {metrics(y, [r['probs'][k] for r in rows])}")
        else:  # modèle de vision généraliste
            ok = [r for r in rows if r["score"] is not None]
            print(f"   réponses valides {len(ok)}/{len(rows)}")
            print(f"   PRINCIPAL         {metrics([r['label'] for r in ok], [r['score'] for r in ok])}")
            # Le spécialiste sur exactement les mêmes images, pour une comparaison équitable
            spec_file = RESULTS / f"cxr_{dataset}.jsonl"
            if spec_file.exists():
                spec = {r["file"]: r for r in map(json.loads, spec_file.open(encoding="utf-8"))}
                same = [spec[r["file"]] for r in ok if r["file"] in spec]
                if len(same) == len(ok):
                    thr = ped if dataset == "kermany" and ped is not None else 0.5
                    print(f"   spécialiste, mêmes images (seuil {thr:.3f}) : "
                          f"{metrics([r['label'] for r in same], [PRIMARY[dataset](r['probs']) for r in same], thr)}")
