"""Latéralité calculée par le lecteur spécialisé vs côté noté par le radiologue (Montgomery, atteintes unilatérales).

Usage (Python de cxr-venv) : python eval/cxr_laterality.py
"""
import re
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "radiology"))

SET = Path(os.environ.get("MEDASSIST_ROOT", Path.home() / "open-webui")) / Path("cxr-data", "montgomery", "MontgomerySet")
RIGHT = re.compile(r"\b(rul|rml|rll|right|rt)\b")
LEFT = re.compile(r"\b(lul|lll|lingula|lungula|left|lt)\b")


def reading_side(text):
    t = text.lower()
    if "bilat" in t or "both" in t:
        return None
    r, l = bool(RIGHT.search(t)), bool(LEFT.search(t))
    return "droit" if r and not l else "gauche" if l and not r else None


def ask_side(model, image_bytes):
    """Même question posée à un modèle de vision généraliste (Ollama)."""
    import base64, io, json, urllib.request  # noqa: E401
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    schema = {"type": "object", "properties": {"side": {"type": "string", "enum": ["right", "left", "both", "none"]}},
              "required": ["side"]}
    body = {"model": model, "stream": False, "think": False, "format": schema, "keep_alive": "30m",
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 40},
            "messages": [{"role": "user", "images": [base64.b64encode(buf.getvalue()).decode()],
                          "content": "This frontal chest X-ray of an adult with tuberculosis is displayed in standard "
                                     "radiological convention. On which side of the PATIENT is the main abnormality? "
                                     'Answer in JSON: {"side": "right" | "left" | "both" | "none"}.'}]}
    req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        side = json.loads(json.load(resp)["message"]["content"])["side"]
    return {"right": "droit", "left": "gauche"}.get(side, "bilatéral ou indéterminé")


if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else None  # absent : lecteur spécialisé
    if not model:
        from cxr_model import NO_SIDE, CXRReader  # torch et calibration : lecteur spécialisé seulement
        reader = CXRReader()
    rows = []
    for txt in sorted((SET / "ClinicalReadings").glob("*_1.txt")):
        truth = reading_side(txt.read_text(errors="ignore").split("\n", 2)[-1])
        if not truth:
            continue
        image = (SET / "CXR_png" / f"{txt.stem}.png").read_bytes()
        if model:
            rows.append((txt.stem, truth, ask_side(model, image), model, None))
        else:
            probs = reader.predict(image)
            # Anomalie localisable la plus probable (au-dessus du seuil ou non)
            top = max((p for p in probs if p not in NO_SIDE), key=probs.get)
            loc = reader.localize(image, top)
            rows.append((txt.stem, truth, loc["cote_patient"], top, loc["part_gauche_image"]))
        print(*rows[-1], flush=True)
    decided = [r for r in rows if not r[2].startswith("bilat")]
    good = sum(r[1] == r[2] for r in decided)
    print(f"\nAtteintes unilatérales : {len(rows)} ; côté tranché par le lecteur : {len(decided)} ; "
          f"correct : {good}/{len(decided)} ; inversé : {len(decided) - good}")
