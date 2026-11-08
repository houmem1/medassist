"""La sonde avec ou sans préfixe générique (« score de », « étude », « syndrome de »…) : faux négatifs et faux positifs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipelines import mp  # noqa: E402

FICTIFS = [("score de Hammond-Lefèvre", "score"), ("score de Varnier-Halbrook", "score"), ("étude CARDIO-ZEN", "etude"),
           ("essai CLEARANCE", "etude"), ("critères de Russell", "score"), ("syndrome de Brovatrexil", "syndrome"),
           ("syndrome de Kessler-Moreau", "syndrome"), ("recommandations de Dunmore", "recommandation"),
           ("score de Pellegrin", "score"), ("étude HELIOS-7", "etude")]
REELS = [("syndrome de Kounis", "syndrome"), ("syndrome de Lemierre", "syndrome"), ("règle PERC", "score"),
         ("score de Wells", "score"), ("score de Glasgow", "score"), ("score CHA2DS2-VASc", "score"),
         ("étude ISIS-2", "etude"), ("essai COMPASS", "etude"), ("score de Centor", "score"),
         ("score de Mac Isaac", "score"), ("critères de Ranson", "score"), ("score de Child-Pugh", "score"),
         ("triade de Cushing", "syndrome"), ("syndrome de Guillain-Barré", "syndrome"), ("score de Genève", "score"),
         ("étude ARRIVE", "etude"), ("syndrome de Brugada", "syndrome"), ("critères de Duke", "score"),
         # Descriptions réelles contenant « inconnue » ou « n'existe pas de traitement » (relecture v1.6)
         ("syndrome de Kawasaki", "syndrome"), ("maladie de Huntington", "syndrome"), ("syndrome de Marfan", "syndrome"),
         ("score APGAR", "score")]

engine = mp.Engine()
for label, names in (("FICTIFS", FICTIFS), ("RÉELS", REELS)):
    full_hits = bare_hits = either = 0
    for name, kind in names:
        bare = mp.bare_name(name)
        f = engine.probe_denies(name, kind)
        b = engine.probe_denies(bare, kind) if bare != name else f
        full_hits += f
        bare_hits += b
        either += f or b
        print(f"{label:8} {name:32} complet={'INCONNU' if f else '-':8} nu({bare})={'INCONNU' if b else '-'}", flush=True)
    print(f"== {label} : signalés {full_hits}/{len(names)} avec préfixe, {bare_hits}/{len(names)} sans, "
          f"{either}/{len(names)} l'un ou l'autre\n", flush=True)
