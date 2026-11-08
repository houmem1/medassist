"""Contrôle des doses citées (v1.5.8) rejoué sur les réponses déjà enregistrées : combien d'alertes, et lesquelles ?
Chaque alerte est imprimée avec sa phrase pour être jugée à la main (vraie mauvaise attribution ou fausse alerte).
Les extraits sont reconstitués à partir du bloc « Sources » (document + page) de chaque réponse."""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipelines import mp  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
INDEX = Path(mp.KB_DIR)
pages = collections.defaultdict(list)
for line in (INDEX / "passages.jsonl").open(encoding="utf-8"):
    p = json.loads(line)
    pages[(p["doc"], p["page"])].append(p["text"])
by_title = {mp.doc_title(doc): doc for doc, _ in pages}
SOURCE = re.compile(r"^- \[(\d{1,2})\] (.+), page (\d+)$", re.M)

# Réponse observée dans l'interface (BPCO, v1.5.7) : « 500 mg » attribué à la HAS [3], qui ne donne aucune dose
UI_BPCO = ("Posologie : Amoxicilline 500 mg, 3 fois par jour (toutes les 8 heures) [2], [3].\n\n"
           "**📚 Sources (base documentaire locale)**\n- [1] OMS 2022 AWaRe antibiotic book, page 180\n"
           "- [2] OMS 2022 AWaRe antibiotic book, page 184\n- [3] HAS 2024 choix durees antibiotherapie synthese, page 3")


def page_text(hit):
    return "\n".join(pages[(hit["doc"], hit["page"])])


def check(answer):
    srcs = {int(n): (by_title.get(t), int(pg)) for n, t, pg in SOURCE.findall(answer)}
    if not srcs:
        return None, []
    hits = [{"doc": srcs[n][0], "page": srcs[n][1]} if n in srcs and srcs[n][0] else {"doc": "?", "page": 0}
            for n in range(1, max(srcs) + 1)]
    return hits, mp.dose_misattributions(answer, hits, page_text)


seen, n_answers, n_flagged = set(), 0, 0
files = sorted(RESULTS.rglob("*.jsonl"))
records = [("ui", "bpco", UI_BPCO)]
for f in files:
    for line in f.open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and isinstance(r.get("answer"), str):
            records.append((str(f.relative_to(RESULTS)), r.get("id", "?"), r["answer"]))
for src, rid, answer in records:
    if answer in seen or "📚 Sources" not in answer:
        continue
    seen.add(answer)
    hits, flags = check(answer)
    if hits is None:
        continue
    n_answers += 1
    if flags:
        n_flagged += 1
        print(f"=== {src} {rid}")
        for dose, missing in flags:
            seg = next((s for s in answer.split("\n") if dose in s), "")[:300]
            where = ", ".join("%s p%s" % (hits[n - 1]["doc"][:20], hits[n - 1]["page"]) for n in missing)
            print(f"  {dose} absent de {missing} ({where})")
            print(f"     « {seg} »")
print(f"\nRéponses avec sources : {n_answers} ; avec au moins une alerte : {n_flagged}")
