"""Configurations « pipeline » du banc : exactement le code de la fonction Open WebUI."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "medassist_pipe", Path(__file__).resolve().parent.parent / "openwebui" / "medassist_pipe.py")
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)


def _engine(profile="pro", **kw):
    engine = mp.Engine(**kw)

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
    # Même pipeline avec MedGemma 27B (une fois téléchargé)
    "pro_full_mg27": _engine(model="medgemma:27b"),
}
