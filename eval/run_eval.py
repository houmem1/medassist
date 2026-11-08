"""Évalue une ou plusieurs configurations sur le banc MedAssist.

Usage :
  python eval/run_eval.py medassist qwen36            # configs nommées (voir CONFIGS)
  python eval/run_eval.py medassist --ids ph01,pg01   # sous-ensemble de questions
  python eval/run_eval.py pro_full pro_nokb --bench doc   # banc de la base documentaire (docbench.py)
Résultats : eval/results/<config>.jsonl (banc doc : <config>__doc.jsonl) + tableau récapitulatif.
"""
import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from docbench import ITEMS as DOC_ITEMS  # noqa: E402
from medbench import ITEMS  # noqa: E402

BENCHES = {"med": (ITEMS, ""), "doc": (DOC_ITEMS, "__doc")}

OLLAMA = "http://localhost:11434/api/chat"
RESULTS = HERE / "results"


def modelfile_system(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return re.search(r'SYSTEM """(.*?)"""', text, re.S).group(1).strip()


def chat(model, messages, think=False, options=None, timeout=900):
    body = {"model": model, "messages": messages, "stream": False, "think": think,
            "options": {"num_predict": 1500, **(options or {})}}
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["message"]["content"]


def single(model, system=None, think=False, options=None):
    def run(question):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": question}]
        return chat(model, msgs, think, options)
    return run


def configs():
    root = HERE.parent
    pro = modelfile_system(root / "Modelfile")
    cfg = {
        "medgemma4b": single("medgemma:4b"),
        "medassist": single("medassist"),
        "qwen36": single("qwen3.6:35b", pro),
        "qwen36_think": single("qwen3.6:35b", pro, think=True, options={"num_predict": 6000}),
        "glm47": single("glm-4.7-flash:q4_K_M", pro),
        "medgemma27b": single("medgemma:27b", pro),
    }
    try:  # configurations avancées (pipeline de vérification), si présentes
        from pipelines import PIPELINES
        cfg.update(PIPELINES)
    except ImportError:
        pass
    return cfg


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    return "".join(c for c in text if not unicodedata.combining(c))


def grade(item, answer):
    a = norm(answer).strip()
    missing = [p for p in item.get("all", []) if not re.search(p, a)]
    forbidden = [p for p in item.get("none", []) if re.search(p, a)]
    return not missing and not forbidden, missing, forbidden


def evaluate(name, fn, ids=None, bench="med"):
    RESULTS.mkdir(exist_ok=True)
    pool, suffix = BENCHES[bench]
    items = [it for it in pool if not ids or it["id"] in ids]
    out = RESULTS / f"{name}{suffix}.jsonl"
    if out.exists():
        # Un passage partiel (--ids) écrasait le fichier complet précédent : il est archivé d'abord
        archive = RESULTS / "archive"
        archive.mkdir(exist_ok=True)
        out.replace(archive / f"{out.stem}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
    rows = []
    with out.open("w", encoding="utf-8") as f:
        for it in items:
            t = time.time()
            try:
                ans = fn(it["q"])
            except Exception as e:  # une erreur réseau ne doit pas tuer tout le run
                ans = f"[ERREUR] {e}"
            secs = time.time() - t
            ok, missing, forbidden = grade(it, ans)
            row = dict(id=it["id"], cat=it["cat"], ok=ok, secs=round(secs, 1),
                       missing=missing, forbidden=forbidden, q=it["q"], answer=ans)
            trace = getattr(fn, "last_trace", None)  # pipelines complets seulement
            if isinstance(trace, dict):
                row["trace"] = {k: v for k, v in trace.items() if k != "banners"}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            print(f"  {name:14s} {it['id']} {'OK ' if ok else 'XX '} {secs:5.1f}s", flush=True)
    return rows


def summary(name, rows):
    by = defaultdict(list)
    for r in rows:
        by[r["cat"]].append(r["ok"])
    cats = " ".join(f"{c}={sum(v)}/{len(v)}" for c, v in sorted(by.items()))
    total = sum(r["ok"] for r in rows)
    secs = sum(r["secs"] for r in rows) / max(len(rows), 1)
    fails = ",".join(r["id"] for r in rows if not r["ok"])
    return f"{name:14s} {total:2d}/{len(rows)}  ({100*total/max(len(rows),1):4.1f}%)  moy {secs:5.1f}s  {cats}  échecs: {fails}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("configs", nargs="+")
    ap.add_argument("--ids", default="")
    ap.add_argument("--bench", choices=sorted(BENCHES), default="med")
    args = ap.parse_args()
    ids = set(filter(None, args.ids.split(",")))
    available = configs()
    lines = []
    for name in args.configs:
        rows = evaluate(name, available[name], ids, args.bench)
        lines.append(summary(name, rows))
    print("\n=== RÉSUMÉ ===")
    print("\n".join(lines))
