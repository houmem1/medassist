"""Test de bout en bout du pipeline installé (même code que la fonction Open WebUI) sur de vraies radiographies.

Usage (Python d'Open WebUI, service radio lancé) :
  python eval/cxr_e2e.py image.png "question" [pro|patient]   -> eval/results/e2e_<image>.md
"""
import base64
import importlib.util
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("mp", ROOT / "openwebui" / "medassist_pipe.py")
mp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mp)

if __name__ == "__main__":
    image, question = Path(sys.argv[1]), sys.argv[2]
    profile = sys.argv[3] if len(sys.argv) > 3 else "pro"
    msgs = [{"role": "user", "content": question, "images": [base64.b64encode(image.read_bytes()).decode()]}]
    t0 = time.time()
    steps = []
    text, trace = mp.Engine().run(msgs, profile, status=lambda s: steps.append(f"{time.time() - t0:5.0f}s  {s}"))
    text = re.sub(r"\(data:image/jpeg;base64,[^)]+\)", "(image annotée)", text)
    out = ROOT / "eval" / "results" / f"e2e_{image.stem}_{profile}.md"
    out.write_text(f"# {image.name} ({profile}) — {time.time() - t0:.0f} s\n\nQuestion : {question}\n\n"
                   f"```\n" + "\n".join(steps) + f"\n```\n\nTrace : {trace}\n\n---\n\n{text}\n", encoding="utf-8")
    print(f"{out.name} : {time.time() - t0:.0f} s ; cxr={trace['cxr']} ; corrections={len(trace['issues'])}")
