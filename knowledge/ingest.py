"""Indexe les PDF de la base documentaire de MedAssist (100 % local : pypdf + bge-m3 via Ollama).

Déposez vos PDF dans <dossier d'installation>\\knowledge\\docs, puis lancez (Python d'Open WebUI) :
  %USERPROFILE%\\open-webui\\venv\\Scripts\\python.exe %USERPROFILE%\\open-webui\\knowledge\\ingest.py
L'index (passages + embeddings) est écrit dans knowledge\\index ; MedAssist le relit à la question suivante.
Un nom de fichier lisible sert de titre de source : « HAS_2024_choix_durees_antibiotherapie_synthese.pdf ».
"""
import hashlib
import json
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
DOCS, INDEX = BASE / "docs", BASE / "index"
OLLAMA, MODEL = "http://localhost:11434", "bge-m3"
CHUNK, OVERLAP, MIN_CHARS = 1000, 200, 120


def embed(texts):
    req = urllib.request.Request(f"{OLLAMA}/api/embed", json.dumps({"model": MODEL, "input": texts}).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp)["embeddings"]


def page_text(page):
    """Extraction \u00ab mise en page \u00bb : les colonnes d'un tableau restent sur la m\u00eame ligne, s\u00e9par\u00e9es par \u00ab | \u00bb.
    En extraction simple, la cellule fusionn\u00e9e \u00ab 7 jours maximum \u00bb de la fiche HAS tombait sous la ligne suivante
    (PAC avec comorbidit\u00e9s) et le mod\u00e8le l'y rattachait, au lieu de \u00ab Suspicion de pneumocoque \u00bb.
    Les pages tourn\u00e9es perdent du texte en mise en page (60 pages sur 850) : on garde alors l'extraction simple."""
    plain = page.extract_text() or ""
    try:
        text = page.extract_text(extraction_mode="layout") or ""
    except Exception:  # noqa: BLE001 - mise en page indisponible pour cette page : extraction simple
        return plain
    lines = [re.sub(r"\S\s{3,}(?=\S)", lambda m: m.group(0)[0] + " | ", ln.strip()) for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    size = lambda t: len(re.sub(r"\W", "", t))  # noqa: E731
    return text if size(text) >= 0.9 * size(plain) else plain


def clean(text):
    text = text.replace("\u00ad", "").replace("\ufb01", "fi").replace("\ufb02", "fl")
    # Ligatures mal d\u00e9cod\u00e9es dans le livre AWaRe (polices CFF) : \u00ab De/g246nition \u00bb, \u00ab In/g248uenza \u00bb
    text = text.replace("/g246", "fi").replace("/g248", "fl")
    text = re.sub(r"-\n(?=[a-zà-ÿ])", "", text)          # mots coupés en fin de ligne
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def chunks(text):
    """Passages de ~1000 caractères avec recouvrement, coupés de préférence en fin de phrase ou de ligne."""
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK)
        if end < len(text):
            cut = max(text.rfind(". ", start + CHUNK // 2, end), text.rfind("\n", start + CHUNK // 2, end))
            end = cut + 1 if cut > 0 else end
        yield text[start:end].strip()
        if end >= len(text):
            break
        start = max(end - OVERLAP, start + 1)


REFERENCES = re.compile(r"doi\.org|https?://|\bet al\b|\b(19|20)\d{2};\s?\d")


def is_noise(passage):
    """Tables des matières, pages vides et bibliographies. Les références (revues, années, DOI) ne contiennent
    aucune recommandation et faisaient passer pour réel un essai fictif (« publié dans le NEJM en 2019 »)."""
    dots = passage.count(".") / max(1, len(passage))
    return len(passage) < MIN_CHARS or dots > 0.25 or len(REFERENCES.findall(passage)) >= 3


if __name__ == "__main__":
    pdfs = sorted(DOCS.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"Aucun PDF dans {DOCS}")
    try:
        embed(["test"])
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Ollama ou le modèle {MODEL} indisponible ({e}) : lancez Ollama, puis « ollama pull {MODEL} ».")
    records, skipped = [], []
    for pdf in pdfs:
        try:
            reader = PdfReader(pdf)
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("PDF protégé par mot de passe")
            len(reader.pages)
        except Exception as e:  # noqa: BLE001 - un PDF illisible n'empêche pas d'indexer les autres
            print(f"{pdf.name} : ignoré ({e})", flush=True)
            skipped.append(pdf.name)
            continue
        n_before = len(records)
        for page_no, page in enumerate(reader.pages, 1):
            try:
                text = clean(page_text(page))
            except Exception as e:  # noqa: BLE001 - une page illisible ne doit pas bloquer tout le document
                print(f"  {pdf.name} p.{page_no} illisible : {e}")
                continue
            for passage in chunks(text):
                if not is_noise(passage):
                    records.append({"doc": pdf.stem, "page": page_no, "text": passage})
        print(f"{pdf.name} : {len(reader.pages)} pages, {len(records) - n_before} passages", flush=True)

    t0, vectors = time.time(), []
    for i in range(0, len(records), 32):
        vectors += embed([r["text"] for r in records[i:i + 32]])
        if (i // 32) % 20 == 0:
            print(f"  embeddings {min(i + 32, len(records))}/{len(records)} ({time.time() - t0:.0f} s)", flush=True)
    if not records:
        sys.exit("Aucun passage extrait : PDF scannés (images sans texte) ou illisibles.")
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-12  # cosinus = produit scalaire

    # Écriture dans un dossier temporaire, puis bascule : MedAssist (qui relit l'index dès que manifest.json change)
    # ne voit jamais un index à moitié écrit, et une indexation interrompue laisse l'ancien index intact.
    tmp = INDEX.with_name(INDEX.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    np.save(tmp / "embeddings.npy", matrix.astype(np.float16))
    with (tmp / "passages.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    manifest = {"model": MODEL, "built": time.strftime("%Y-%m-%d %H:%M"), "passages": len(records),
                "documents": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in pdfs if p.name not in skipped},
                "ignores": skipped}
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    old = INDEX.with_name(INDEX.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if INDEX.exists():
        INDEX.rename(old)
    tmp.rename(INDEX)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
    print(f"Index : {len(records)} passages, {matrix.shape[1]} dimensions, {time.time() - t0:.0f} s -> {INDEX}"
          + (f" ; ignorés : {', '.join(skipped)}" if skipped else ""))
