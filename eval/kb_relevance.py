"""Tri des extraits par le modèle : combien en garde-t-il, sur le banc documentaire (à garder) et le banc général
(majoritairement hors du thème de la base) ? Sortie : results/kb_relevance.jsonl."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docbench import ITEMS as DOC  # noqa: E402
from medbench import ITEMS as MED  # noqa: E402
from pipelines import mp  # noqa: E402

engine = mp.Engine()
out = Path(__file__).resolve().parent / "results" / "kb_relevance.jsonl"
with out.open("w", encoding="utf-8") as f:
    for bench, items in (("doc", DOC), ("med", MED)):
        for it in items:
            t0 = time.time()
            hits = engine.kb.search(it["q"], engine.kb_topk, engine.kb_min_score)
            kept = engine.relevant(it["q"], hits) if hits else []
            row = {"bench": bench, "id": it["id"], "found": len(hits), "kept": len(kept),
                   "kept_pages": [f"{h['doc'][:12]} p{h['page']}" for h in kept], "secs": round(time.time() - t0, 1)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(bench, it["id"], f"{len(kept)}/{len(hits)}", row["kept_pages"], f"{row['secs']}s", flush=True)
