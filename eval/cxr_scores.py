"""Calcule les probabilités du lecteur spécialisé sur un jeu de radios étiquetées (une ligne JSON par image).

Usage (Python de cxr-venv) :
  python eval/cxr_scores.py kermany    -> eval/results/cxr_kermany.jsonl
  python eval/cxr_scores.py montgomery -> eval/results/cxr_montgomery.jsonl
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "radiology"))
from cxr_model import CXRReader  # noqa: E402

DATA = Path(os.environ.get("MEDASSIST_ROOT", Path.home() / "open-webui")) / Path("cxr-data")


def kermany():
    for label in ("NORMAL", "PNEUMONIA"):
        for f in sorted((DATA / "kermany" / label).glob("*.jpeg")):
            yield f, int(label == "PNEUMONIA")


def kermanycalib():
    # 200 normales + 200 pneumonies du jeu d'ENTRAÎNEMENT : sert à fixer le seuil pédiatrique, jamais au test
    for label in ("NORMAL", "PNEUMONIA"):
        for f in sorted((DATA / "kermany" / "calib" / label).glob("*.jpeg")):
            yield f, int(label == "PNEUMONIA")


def shenzhen():
    # 80 normales + 80 tuberculoses (Shenzhen, Chine) : calibration adulte, autre hôpital que le test Montgomery
    for f in sorted((DATA / "shenzhen").glob("CHNCXR_*.png")):
        yield f, int(f.stem.endswith("_1"))


def montgomery():
    # Nom de fichier MCUCXR_xxxx_0.png (normal) ou _1.png (tuberculose)
    for f in sorted((DATA / "montgomery" / "MontgomerySet" / "CXR_png").glob("*.png")):
        yield f, int(f.stem.endswith("_1"))


if __name__ == "__main__":
    name = sys.argv[1]
    reader = CXRReader()
    out = ROOT / "eval" / "results" / f"cxr_{name}.jsonl"
    t0 = time.time()
    with out.open("w", encoding="utf-8") as fh:
        for n, (f, y) in enumerate(globals()[name](), 1):
            fh.write(json.dumps({"file": f.name, "label": y, "probs": reader.predict(f.read_bytes())}) + "\n")
            if n % 50 == 0:
                print(f"{n} images, {time.time() - t0:.0f}s", flush=True)
    print(f"terminé : {out}", flush=True)
