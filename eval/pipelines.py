"""Configurations « pipeline » du banc : exactement le code de la fonction Open WebUI."""
import importlib.util
import json
import os
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "medassist_pipe", Path(__file__).resolve().parent.parent / "openwebui" / "medassist_pipe.py")
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)


# Options Ollama supplémentaires pour un banc, en JSON : MEDASSIST_OLLAMA_OPTS='{"num_gpu": 24}' (couches sur la
# carte graphique, pour garder une marge de mémoire vidéo quand d'autres applications l'occupent : au-delà, le modèle
# déborde en mémoire partagée et une réponse peut prendre 30 min au lieu de 30 s) ou '{"num_gpu": 0, "num_thread": 6}'.
EXTRA_OPTS = json.loads(os.environ.get("MEDASSIST_OLLAMA_OPTS", "{}"))


def _engine(profile="pro", **kw):
    engine = mp.Engine(**kw)
    engine.opts.update(EXTRA_OPTS)
    engine.strict.update(EXTRA_OPTS)

    def fn(q):
        answer, trace = engine.run([{"role": "user", "content": q}], profile)
        fn.last_trace = trace  # relu par run_eval pour diagnostiquer un échec (extraits, relecture, refus)
        return answer

    return fn


PIPELINES = {
    # Effet du seul prompt Pro
    "pro_prompt": _engine(verify=False, entity_check=False),
    # + contrôle des noms inconnus
    "pro_entities": _engine(verify=False, entity_check=True),
    # Relecture sans contrôle des noms
    "pro_verify": _engine(entity_check=False),
    # Pipeline complet (ce qui tourne dans Open WebUI, avec la base documentaire)
    "pro_full": _engine(),
    "patient_full": _engine("patient"),
    # Même pipeline sans base documentaire, pour mesurer son apport
    "pro_nokb": _engine(kb_dir=None),
    "patient_nokb": _engine("patient", kb_dir=None),
    # Profil bureautique : même pipeline avec le modèle de 9 milliards (16 Go de RAM, sans carte graphique)
    "pro_full_q9": _engine(model="qwen3.5:9b", num_ctx=8192),
    "patient_full_q9": _engine("patient", model="qwen3.5:9b", num_ctx=8192),
    "pro_nokb_q9": _engine(model="qwen3.5:9b", num_ctx=8192, kb_dir=None),
    # Génération précédente, déjà présente : plancher de comparaison pour le profil bureautique
    "pro_full_q7": _engine(model="qwen2.5:7b", num_ctx=8192),
    "patient_full_q7": _engine("patient", model="qwen2.5:7b", num_ctx=8192),
    # Même pipeline avec MedGemma 27B (une fois téléchargé)
    "pro_full_mg27": _engine(model="medgemma:27b"),
}
