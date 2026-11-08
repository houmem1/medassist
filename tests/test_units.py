"""Tests unitaires hors ligne du pipeline MedAssist : aucun appel à Ollama (le modèle est simulé).

Lancer (Python d'Open WebUI, pour pydantic) :
  %USERPROFILE%\\open-webui\\venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""
import importlib.util
import json
import unittest
import urllib.error
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "medassist_pipe", Path(__file__).resolve().parent.parent / "openwebui" / "medassist_pipe.py")
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)


class Triage(unittest.TestCase):
    def test_suicide_both_profiles(self):
        for profile in ("pro", "patient"):
            self.assertIn(mp.BANNER_SUICIDE, mp.triage("J'ai envie de mourir", profile))

    def test_emergency_patient_only(self):
        q = "Mon père a une douleur thoracique depuis 20 minutes"
        self.assertIn(mp.BANNER_EMERGENCY, mp.triage(q, "patient"))
        self.assertNotIn(mp.BANNER_EMERGENCY, mp.triage(q, "pro"))

    def test_image_banner(self):
        self.assertEqual(mp.triage("Lis cette radio", "pro", has_image=True)[0], mp.BANNER_IMAGE["pro"])
        self.assertEqual(mp.triage("Lis cette radio", "pro"), [])

    def test_accents_ignored(self):
        self.assertIn(mp.BANNER_EMERGENCY, mp.triage("Il N'ARRIVE PAS À RESPIRER", "patient"))


class Population(unittest.TestCase):
    def test_age_in_years(self):
        self.assertEqual(mp.population_from_text("Enfant de 5 ans, toux"), "enfant")
        self.assertEqual(mp.population_from_text("Homme de 45 ans"), "adulte")
        self.assertEqual(mp.population_from_text("Patient âgé de 16 ans"), "adulte")

    def test_durations_are_not_ages(self):
        self.assertIsNone(mp.population_from_text("Toux depuis 2 ans"))
        self.assertIsNone(mp.population_from_text("Opéré il y a 3 ans"))
        self.assertEqual(mp.population_from_text("Fumeur depuis 20 ans, homme de 60 ans"), "adulte")
        self.assertEqual(mp.population_from_text("Femme, 10 ans de tabagisme"), "adulte")

    def test_months_and_words(self):
        self.assertEqual(mp.population_from_text("Nourrisson de 3 mois"), "enfant")
        self.assertEqual(mp.population_from_text("radio d'un bébé"), "enfant")
        self.assertIsNone(mp.population_from_text("Radiographie thoracique"))


class Names(unittest.TestCase):
    def test_bare_name(self):
        self.assertEqual(mp.bare_name("score de Hammond-Lefèvre"), "Hammond-Lefèvre")
        self.assertEqual(mp.bare_name("Essai COMPASS"), "COMPASS")
        self.assertEqual(mp.bare_name("amoxicilline"), "amoxicilline")

    def test_deny_patterns(self):
        for text in ("INCONNU", "Ce score n'existe pas.", "Je ne connais pas ce nom", "Il s'agit d'un essai fictif"):
            self.assertTrue(mp.DENY.search(mp._norm(text)), text)
        self.assertFalse(mp.DENY.search(mp._norm("Le score CURB-65 comporte cinq critères.")))

    def test_refusal_fallback_patterns(self):
        answer = "Les extraits fournis ne contiennent pas d'information sur le lithium. Je ne connais pas ce point."
        n = mp._norm(answer)
        self.assertTrue(mp.KB_REFUSAL.search(n) and mp.ABSTAINED.search(n))
        self.assertFalse(mp.KB_REFUSAL.search(mp._norm("Selon les extraits, la durée est de 5 jours [1].")))


class Sources(unittest.TestCase):
    hits = [{"doc": "HAS_2024_x", "page": 3}, {"doc": "OMS_2022_y", "page": 180}]

    def test_sources_block_lists_cited_only(self):
        block = mp.kb_sources("Amoxicilline [2]. Durée 5 jours [2].", self.hits)
        self.assertIn("[2] OMS 2022 y, page 180", block)
        self.assertNotIn("[1]", block)

    def test_invented_number_flagged(self):
        block = mp.kb_sources("Dose [3].", self.hits)
        self.assertIn("[3]", block)
        self.assertIn("absent des extraits", block)

    def test_no_citation_no_block(self):
        self.assertIsNone(mp.kb_sources("Pas de citation.", self.hits))


class Doses(unittest.TestCase):
    def test_parsing_and_equivalences(self):
        self.assertIn((1000.0, "mg"), mp._doses("1 g toutes les 8 heures"))
        self.assertIn((4000.0, "mg"), mp._doses("4 000 mg par jour"))
        self.assertIn((800000.0, "ui"), mp._doses("800 000 UI"))
        self.assertIn((800000.0, "ui"), mp._doses("800,000 IU"))
        self.assertIn((1.5, "g"), mp._doses("1,5 g"))
        self.assertEqual(mp._doses("2 gélules et 5 gouttes"), set())

    def test_misattribution(self):
        hits = [{"doc": "OMS", "page": 184}, {"doc": "HAS", "page": 3}]
        pages = {("OMS", 184): "Amoxicillin (oral): 500 mg given every 8 hours", ("HAS", 3): "amoxicilline | 5 jours"}
        page_text = lambda h: pages[(h["doc"], h["page"])]  # noqa: E731
        answer = "Posologie : amoxicilline 500 mg toutes les 8 heures [1], [2].\nDurée : 5 jours [2]."
        self.assertEqual(mp.dose_misattributions(answer, hits, page_text), [("500 mg", [2])])
        self.assertEqual(mp.dose_misattributions("Amoxicilline 500 mg [1].", hits, page_text), [])

    def test_sources_block_ignored(self):
        hits = [{"doc": "HAS", "page": 3}]
        answer = "Durée 5 jours [1].\n\n**📚 Sources (base documentaire locale)**\n- [1] HAS 500 mg, page 3"
        self.assertEqual(mp.dose_misattributions(answer, hits, lambda h: "5 jours"), [])


class History(unittest.TestCase):
    previous = ("> 🚨 **Si une personne est en danger maintenant, appelez immédiatement les secours** : 190\n\n"
                "#### 🩻 Radiographie thoracique de face : double lecture automatique (adulte)\n| a | b |\n\n"
                "Réponse utile [1].\n\n"
                "**📚 Sources (base documentaire locale)**\n- [1] HAS, page 3\n\n"
                "> 🔎 **Contrôle des citations** : « 500 mg » ne figure pas dans [1].\n\n"
                "---\n*Contrôles : relecture : 0 correction(s). Aide à la décision.*")

    def test_clean_history_removes_appended_blocks(self):
        cleaned = mp.clean_history(self.previous)
        self.assertEqual(cleaned, "#### 🩻 Radiographie thoracique de face : double lecture automatique (adulte)\n| a | b |\n\n"
                                  "Réponse utile [1].")

    def test_to_ollama_cleans_assistant_and_extracts_images(self):
        body = [{"role": "system", "content": "x"},
                {"role": "user", "content": [{"type": "text", "text": "Lis"},
                                             {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}}]},
                {"role": "assistant", "content": self.previous},
                {"role": "user", "content": "Et chez l'enfant ?"}]
        out = mp._to_ollama(body)
        self.assertEqual([m["role"] for m in out], ["user", "assistant", "user"])
        self.assertEqual(out[0]["images"], ["QUJD"])
        self.assertNotIn("📚", out[1]["content"])
        self.assertIn("🩻", out[1]["content"])


class Radiology(unittest.TestCase):
    def test_verdict(self):
        self.assertEqual(mp.verdict({"anormale": True}, {"abnormal": True}), "anormale")
        self.assertEqual(mp.verdict({"anormale": False}, {"abnormal": False}), "normale")
        self.assertEqual(mp.verdict({"anormale": True}, {"abnormal": False}), "discordance")
        self.assertEqual(mp.verdict({"anormale": None}, {"abnormal": True}), "anormale")
        self.assertIsNone(mp.verdict({"anormale": None}, None))
        self.assertEqual(mp.verdict({"anormale": True}, None), "anormale")

    def test_laterality(self):
        res = {"anomalies": [{"cote_patient": "bilatéral ou indéterminé"}, {"cote_patient": "droit"}], "cote_visuel": "droit"}
        self.assertIn("concordants", mp.laterality(res))
        res["cote_visuel"] = "gauche"
        self.assertIn("discordant", mp.laterality(res))
        self.assertIsNone(mp.laterality({"anomalies": []}))


class Errors(unittest.TestCase):
    def test_explain(self):
        msg = mp.explain_error(urllib.error.URLError("refused"), "m", "v", "http://localhost:11434")
        self.assertIn("Ollama ne répond pas", msg)
        http = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        self.assertIn("ollama pull m", mp.explain_error(http, "m", "v", "u"))
        self.assertIn("Erreur interne", mp.explain_error(KeyError("x"), "m", "v", "u"))


class FakeEngine(mp.Engine):
    """Moteur sans Ollama : réponses fixes, recherche documentaire simulée."""

    def __init__(self, hits=(), **kw):
        super().__init__(kb_dir=None, entity_check=False, verify=False, cxr_url=None, **kw)
        self.calls, self.queries, self._hits = [], [], list(hits)
        if self._hits:
            self.kb = self

    def search(self, query, k, min_score):
        self.queries.append(query)
        return self._hits

    def page_text(self, hit):
        return "amoxicilline 5 jours"

    def relevant(self, question, hits):
        return hits

    def _call(self, messages, opts=None, fmt=None):
        self.calls.append(messages)
        self.truncated = False
        return "Réponse [1]." if self._hits else "Réponse."


class Pipeline(unittest.TestCase):
    def test_no_citation_rule_on_followup_without_hits(self):
        e = FakeEngine()
        history = [{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "R1 [1]."},
                   {"role": "user", "content": "Et chez l'enfant ?"}]
        e.kb = None
        text, trace = e.run(history, "pro")
        self.assertIn("n'écris aucun numéro", e.calls[0][0]["content"])
        text, trace = e.run([{"role": "user", "content": "Q1"}], "pro")
        self.assertNotIn("n'écris aucun numéro", e.calls[1][0]["content"])

    def test_followup_query_includes_previous_question(self):
        e = FakeEngine(hits=[{"doc": "HAS_2024", "page": 3, "text": "amoxicilline 5 jours", "score": 0.7}])
        history = [{"role": "user", "content": "Exacerbation de BPCO : quel antibiotique ?"},
                   {"role": "assistant", "content": "Amoxicilline."}, {"role": "user", "content": "Et chez l'enfant ?"}]
        text, trace = e.run(history, "pro")
        self.assertTrue(e.queries[0].startswith("Exacerbation de BPCO"))
        self.assertTrue(trace.get("kb_followup"))
        self.assertIn("[1] HAS 2024, page 3", text)

    def test_child_dose_banner(self):
        e = FakeEngine()
        text, _ = e.run([{"role": "user", "content": "Quelle dose de paracétamol pour un enfant de 15 kg ?"}], "patient")
        self.assertIn(mp.BANNER_CHILD_DOSE, text)

    def test_truncation_banner(self):
        e = FakeEngine()
        e._call = lambda messages, opts=None, fmt=None: (setattr(e, "truncated", True), "Début…")[1]
        text, trace = e.run([{"role": "user", "content": "Explique."}], "pro")
        self.assertTrue(trace["truncated"])
        self.assertIn(mp.BANNER_TRUNCATED, text)


class ReviewFindings(unittest.TestCase):
    """Cas relevés par la relecture indépendante de la v1.6."""

    def test_deny_ignores_real_descriptions(self):
        n = mp._norm
        self.assertFalse(mp.DENY.search(n("Vascularite de l'enfant d'étiologie inconnue, avec fièvre prolongée.")))
        self.assertFalse(mp.DENY.search(n("Maladie héréditaire ; il n'existe pas de traitement curatif.")))
        for text in ("INCONNU", "Ce score n'existe pas.", "Je ne connais pas ce nom.", "Le terme est inconnu dans la littérature.",
                     "Il s'agit d'un essai fictif.", "Aucune étude de ce nom."):
            self.assertTrue(mp.DENY.search(n(text)), text)

    def test_suicide_not_migraines(self):
        self.assertEqual(mp.triage("Comment en finir avec mes migraines ?", "patient"), [])
        self.assertIn(mp.BANNER_SUICIDE, mp.triage("Je veux en finir", "patient"))
        self.assertIn(mp.BANNER_SUICIDE, mp.triage("Je veux en finir avec la vie", "pro"))

    def test_months_duration_is_not_an_age(self):
        self.assertIsNone(mp.population_from_text("Toux depuis 3 mois"))
        self.assertEqual(mp.population_from_text("Femme, 3 mois de grossesse, dyspnée"), "adulte")
        self.assertIsNone(mp.population_from_text("3 mois de grossesse, dyspnée"))
        self.assertEqual(mp.population_from_text("Nourrisson de 3 mois"), "enfant")

    def test_abstention_is_about_the_name(self):
        n = mp._norm
        self.assertFalse(mp.ABSTAINED.search(n("Fièvre d'origine inconnue : bilan.")))
        self.assertTrue(mp.ABSTAINED.search(n("Je ne connais pas le score de Pellegrin.")))
        answer = "Le score de Pellegrin comporte 4 items. Fièvre d'origine inconnue à explorer."
        self.assertFalse(mp.abstains_about(answer, "score de Pellegrin"))
        self.assertTrue(mp.abstains_about("Je ne connais pas le score de Pellegrin.", "score de Pellegrin"))

    def test_kb_refusal_not_on_negative_recommendation(self):
        self.assertFalse(mp.KB_REFUSAL.search(mp._norm("Les extraits [1] indiquent qu'aucun antibiotique n'est recommandé.")))
        self.assertTrue(mp.KB_REFUSAL.search(mp._norm("Les extraits fournis ne contiennent aucune information sur le lithium.")))

    def test_history_strips_data_uri_images(self):
        text = "#### 🩻 Lecture\n\n![Zones (Pneumonia)](data:image/jpeg;base64,/9j/AAAA)\n\nTexte."
        cleaned = mp.clean_history(text)
        self.assertNotIn("base64", cleaned)
        self.assertIn("(image annotée : Zones (Pneumonia))", cleaned)

    def test_history_images_dropped_and_rule_added(self):
        e = FakeEngine()
        history = [{"role": "user", "content": "Lis cette radio", "images": ["QUJD"]},
                   {"role": "assistant", "content": "#### 🩻 Lecture : normale"},
                   {"role": "user", "content": "Et le côté gauche ?"}]
        text, trace = e.run(history, "pro")
        sent = e.calls[0]
        self.assertFalse(any(m.get("images") for m in sent))
        self.assertIn("ne te sont plus montrées", sent[0]["content"])
        self.assertNotIn(mp.BANNER_IMAGE["pro"], text)

    def test_stray_citations_removed_without_hits(self):
        e = FakeEngine()
        e._call = lambda messages, opts=None, fmt=None: "Amoxicilline 5 jours [1], [2]. Fin."
        text, trace = e.run([{"role": "user", "content": "BPCO ?"}], "pro")
        self.assertNotIn("[1]", text)
        self.assertNotIn("📚", text)
        self.assertTrue(trace["stray_citations"])

    def test_described_firm_name_is_flagged_despite_unknown_elsewhere(self):
        e = FakeEngine()
        e.entity_check = True
        e.unknown_entities = lambda q: [("score de Pellegrin", "score")]
        e._call = lambda messages, opts=None, fmt=None: "Le score de Pellegrin comporte 4 items. Cause inconnue."
        text, _ = e.run([{"role": "user", "content": "Critères du score de Pellegrin ?"}], "pro")
        self.assertIn("Contrôle automatique", text)
        e._call = lambda messages, opts=None, fmt=None: "Je ne connais pas le score de Pellegrin."
        text, _ = e.run([{"role": "user", "content": "Critères du score de Pellegrin ?"}], "pro")
        self.assertNotIn("Contrôle automatique", text)

    def test_16bit_image_is_rescaled_not_clipped(self):
        import base64
        import io
        import numpy as np
        from PIL import Image
        arr = (np.linspace(0, 4000, 64 * 64).reshape(64, 64)).astype("uint16")
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, "PNG")
        out = mp.shrink(base64.b64encode(buf.getvalue()).decode())
        img = Image.open(io.BytesIO(base64.b64decode(out)))
        self.assertEqual(img.mode, "L")
        values = np.asarray(img)
        self.assertLess(values.min(), 10)
        self.assertGreater(values.max(), 245)
        self.assertGreater(len(np.unique(values)), 100)


class PipeWrapper(unittest.TestCase):
    def test_empty_question(self):
        import asyncio
        pipe = mp.Pipe()
        out = asyncio.run(pipe.pipe({"model": "medassist.pro", "messages": [{"role": "user", "content": "   "}]}))
        self.assertIn("Aucune question", out)


if __name__ == "__main__":
    unittest.main()
