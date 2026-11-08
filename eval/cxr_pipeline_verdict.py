"""Mesure le verdict de MedGemma avec EXACTEMENT la question et la réduction d'image du pipeline installé.

Les chiffres affichés dans les réponses doivent venir de la question réellement posée : une formulation
différente (« dépistage de la tuberculose » vs « radio anormale ? ») change les résultats.
Usage (Python d'Open WebUI) : python eval/cxr_pipeline_verdict.py  -> eval/results/cxr_<jeu>_pipeline.jsonl
"""
import base64
import importlib.util
import json
import random
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("mp", ROOT / "openwebui" / "medassist_pipe.py")
mp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mp)
DATA = Path(os.environ.get("MEDASSIST_ROOT", Path.home() / "open-webui")) / Path("cxr-data")


def kermany_sample():
    """Les mêmes 100 radios (50/50, graine 0) que eval/cxr_vlm.py."""
    items = [(f, int(lab == "PNEUMONIA")) for lab in ("NORMAL", "PNEUMONIA")
             for f in sorted((DATA / "kermany" / lab).glob("*.jpeg"))]
    rng = random.Random(0)
    pos, neg = [i for i in items if i[1]], [i for i in items if not i[1]]
    return rng.sample(pos, 50) + rng.sample(neg, 50)


def montgomery():
    return [(f, int(f.stem.endswith("_1")))
            for f in sorted((DATA / "montgomery" / "MontgomerySet" / "CXR_png").glob("*.png"))]


if __name__ == "__main__":
    engine = mp.Engine()
    for name, items, pop in (("kermany", kermany_sample(), "enfant"), ("montgomery", montgomery(), "adulte")):
        out = ROOT / "eval" / "results" / f"cxr_{name}_pipeline.jsonl"
        t0 = time.time()
        with out.open("w", encoding="utf-8") as fh:
            for f, y in items:
                img = mp.shrink(base64.b64encode(f.read_bytes()).decode())
                try:
                    v = json.loads(engine._vision(mp.VERDICT_PROMPT.format(who=mp.WHO[pop]), img, mp.VERDICT_SCHEMA))
                    conf = max(0, min(100, int(v["confidence"]))) / 100
                    pred, score = bool(v["abnormal"]), conf if v["abnormal"] else 1 - conf
                except Exception as e:  # noqa: BLE001
                    pred, score = None, None
                    print(f"{f.name}: {e}", flush=True)
                fh.write(json.dumps({"file": f.name, "label": y, "pred": pred, "score": score}) + "\n")
        print(f"{name}: {len(items)} images en {time.time() - t0:.0f}s -> {out.name}", flush=True)
