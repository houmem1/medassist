"""Latence du pipeline complet sur processeur seul, comme sur un PC bureautique sans carte graphique.

Force Ollama à ne rien mettre sur la carte graphique (num_gpu=0) et limite les fils de calcul, pour approcher
un portable de bureau. Les réponses passent par le vrai pipeline (noms, base documentaire, rédaction, relecture).

  python eval/cpu_latency.py qwen3.5:9b --threads 6 --ids ph01,cl05,pg01
Résultat : eval/results/cpu_latency_<modele>.jsonl (une ligne par question : durées, tokens, réponse).
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipelines  # noqa: E402
from medbench import ITEMS  # noqa: E402

DEFAULT_IDS = "ph01,cl05,pg01"  # pharmacologie simple, clinique avec extraits documentaires, piège (médicament fictif)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--threads", type=int, default=6, help="fils de calcul (cœurs d'un PC bureautique)")
    ap.add_argument("--ids", default=DEFAULT_IDS)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--profile", default="pro")
    args = ap.parse_args()

    engine = pipelines.mp.Engine(model=args.model, num_ctx=args.num_ctx, keep_alive="10m")
    cpu = {"num_gpu": 0, "num_thread": args.threads}
    engine.opts.update(cpu)
    engine.strict.update(cpu)
    # Le modèle précédent peut occuper la carte : on le décharge pour mesurer la vraie montée en charge
    urllib.request.urlopen(urllib.request.Request("http://localhost:11434/api/generate",
                                                  json.dumps({"model": args.model, "keep_alive": 0}).encode(),
                                                  {"Content-Type": "application/json"}), timeout=120).read()
    items = [i for i in ITEMS if i["id"] in set(args.ids.split(","))]
    out = HERE / "results" / f"cpu_latency_{args.model.replace(':', '_').replace('/', '_')}.jsonl"
    print(f"{args.model} sur processeur seul, {args.threads} fils, contexte {args.num_ctx}")
    with out.open("w", encoding="utf-8") as f:
        for n, item in enumerate(items):
            t0 = time.time()
            answer, trace = engine.run([{"role": "user", "content": item["q"]}], args.profile)
            dt = time.time() - t0
            row = {"id": item["id"], "q": item["q"], "seconds": round(dt, 1), "first_call": n == 0,
                   "answer_chars": len(answer), "trace": {k: v for k, v in trace.items() if k != "banners"},
                   "answer": answer}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"  {item['id']}: {dt / 60:.1f} min, {len(answer)} caractères, relecture "
                  f"{len(trace.get('issues', []))} correction(s), extraits {len(trace.get('sources', []))}"
                  + ("  (1er appel : chargement du modèle et des prompts)" if n == 0 else ""))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
