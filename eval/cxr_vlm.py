"""Même question binaire posée à un modèle de vision généraliste via Ollama (une ligne JSON par image).

Usage (Python de cxr-venv) :
  python eval/cxr_vlm.py medgemma:4b kermany 100     -> échantillon équilibré de 100 images
  python eval/cxr_vlm.py qwen3.6:35b montgomery 0    -> toutes les images
"""
import base64
import io
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cxr_scores import kermany, montgomery  # noqa: E402

QUESTIONS = {
    "kermany": ("This is a frontal chest X-ray of a child aged 1 to 5 years. "
                "Is there radiographic evidence of pneumonia?", "pneumonia"),
    "montgomery": ("This is a frontal chest X-ray of an adult screened for tuberculosis. "
                   "Is this radiograph abnormal (any pathological finding, such as signs of tuberculosis)?", "abnormal"),
}


def ask(model, question, key, image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    schema = {"type": "object", "properties": {key: {"type": "boolean"},
                                               "confidence": {"type": "integer", "minimum": 0, "maximum": 100}},
              "required": [key, "confidence"]}
    body = {"model": model, "stream": False, "think": False, "format": schema, "keep_alive": "30m",
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 100},
            "messages": [{"role": "user", "images": [base64.b64encode(buf.getvalue()).decode()],
                          "content": question + f' Answer in JSON: {{"{key}": true or false, '
                                                '"confidence": 0-100 (how sure you are of that answer)}.'}]}
    req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        ans = json.loads(json.load(resp)["message"]["content"])
    conf = max(0, min(100, int(ans["confidence"]))) / 100
    # Score continu pour l'AUC : probabilité « positif »
    return bool(ans[key]), conf if ans[key] else 1 - conf


if __name__ == "__main__":
    model, name, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    items = list(globals()[name]())
    if n:
        rng = random.Random(0)
        pos = [i for i in items if i[1]]
        neg = [i for i in items if not i[1]]
        items = rng.sample(pos, n // 2) + rng.sample(neg, n // 2)
    question, key = QUESTIONS[name]
    out = Path(__file__).resolve().parent / "results" / f"cxr_{name}_{model.replace(':', '_')}.jsonl"
    t0 = time.time()
    with out.open("w", encoding="utf-8") as fh:
        for k, (f, y) in enumerate(items, 1):
            try:
                pred, score = ask(model, question, key, f.read_bytes())
            except Exception as e:  # noqa: BLE001 - une image en échec ne doit pas arrêter la mesure
                pred, score = None, None
                print(f"{f.name}: {e}", flush=True)
            fh.write(json.dumps({"file": f.name, "label": y, "pred": pred, "score": score}) + "\n")
            if k % 20 == 0:
                print(f"{k}/{len(items)} images, {time.time() - t0:.0f}s", flush=True)
    print(f"terminé : {out}", flush=True)
