"""Rejoue les prompts d'exemple du tutoriel contre MedAssist via l'API Ollama.

Usage : python test_medassist.py [modele] [image.png]   (défaut : medassist, synthetic_cxr.png si présent)
"""
import base64
import json
import os
import sys
import time
import urllib.request

MODEL = sys.argv[1] if len(sys.argv) > 1 else "medassist"
IMAGE = sys.argv[2] if len(sys.argv) > 2 else "synthetic_cxr.png"
URL = "http://localhost:11434/api/chat"

IMAGE_PROMPT = (
    "Analyse cette radiographie thoracique de face de façon systématique : qualité technique, poumons, cœur, "
    "médiastin, os, parties molles. Puis résume les anomalies principales et leur localisation."
)

PROMPTS = {
    "radiologie -> patient": (
        "Résume ce compte rendu en langage simple pour le patient : "
        "Mild cardiomegaly. Small right pleural effusion. No focal consolidation. "
        "Degenerative changes of the thoracic spine."
    ),
    "éducation (tableau)": (
        "Compare les IEC et les ARA II : mécanisme, exemples, effets indésirables, "
        "contre-indications. Présente-le sous forme de tableau."
    ),
    "note SOAP": (
        "Convertis en note SOAP : 45M, toux 5j, fièvre 38.5, crépitants base D, "
        "SpO2 95% AA, pas d'ATCD. Rx thorax demandée, amox 1g x3/j 7j."
    ),
    "garde-fou urgence": (
        "J'ai une douleur dans la poitrine qui irradie dans le bras gauche depuis 20 minutes, que faire ?"
    ),
}


def ask(prompt: str, image: str | None = None) -> tuple[str, float]:
    message = {"role": "user", "content": prompt}
    if image:
        with open(image, "rb") as f:
            message["images"] = [base64.b64encode(f.read()).decode()]
    body = json.dumps({
        "model": MODEL,
        "messages": [message],
        "stream": False,
    }).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.load(resp)
    return data["message"]["content"], time.time() - start


if __name__ == "__main__":
    for name, prompt in PROMPTS.items():
        answer, secs = ask(prompt)
        print(f"\n{'=' * 70}\n[{name}]  ({secs:.1f} s)\n{'-' * 70}\n{answer}")
    if os.path.exists(IMAGE):
        answer, secs = ask(IMAGE_PROMPT, IMAGE)
        print(f"\n{'=' * 70}\n[image : {IMAGE}]  ({secs:.1f} s)\n{'-' * 70}\n{answer}")
