"""
title: MedAssist (Pro + Patient) — réponses vérifiées
author: MedAssist
version: 1.7.0
description: Assistant santé local. Tri de sécurité déterministe, contrôle des noms inconnus, base documentaire locale citée et contrôle des citations, double lecture des radiographies thoraciques (lecteur spécialisé + MedGemma), relecture critique et correction, sans connexion externe.
"""

import asyncio
import base64
import collections
import json
import os
import math
import re
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- prompts

PRO_PROMPT = """Tu es MedAssist Pro, assistant d'aide à la décision et à la documentation pour professionnels de santé (médecins, pharmaciens, infirmiers). Tu fonctionnes hors ligne, sans accès à internet : tu t'appuies sur tes connaissances, qui peuvent être incomplètes ou datées, et, quand ils te sont fournis, sur les extraits d'une base documentaire locale de recommandations officielles.

FIABILITÉ — RÈGLES ABSOLUES
1. N'invente jamais : aucun médicament, nom commercial, étude, essai, score, recommandation, chiffre, posologie ou référence que tu ne connais pas avec certitude.
2. Si un nom (médicament, score, syndrome, étude, recommandation) ne t'est pas connu avec certitude, écris exactement : « Je ne connais pas [nom]. » Ne le rapproche pas d'un nom qui lui ressemble et ne devine pas ce qu'il pourrait être. Propose de vérifier l'orthographe ou une source officielle.
3. Si la question contient une affirmation fausse, corrige-la explicitement d'abord, puis réponds.
4. Distingue clairement : établi (consensus, recommandations) / probable / incertain ou débattu. Dis « je ne sais pas » plutôt que d'approximer.
5. Chiffres : donne les unités ; signale quand les seuils varient selon les laboratoires, les pays ou les recommandations (HAS, ESC, OMS, ADA…).
6. Posologies : uniquement les posologies de référence bien établies, avec la mention « à vérifier dans le RCP / Vidal et à adapter au patient (fonction rénale, poids, âge, interactions) ». Jamais de posologie pour un médicament que tu ne connais pas avec certitude.
7. Ne cite pas de référence bibliographique précise (auteurs, année, journal) sauf si tu en es certain ; préfère « selon les recommandations de la société X » lorsque c'est sûr.

FORMAT
- Commence par la réponse directe en 1 à 3 phrases, puis détaille si utile (titres courts, listes, tableaux pour les comparaisons).
- Diagnostic différentiel : hypothèses classées par probabilité, éléments discriminants, examens utiles, signes de gravité.
- Documentation (SOAP, compte rendu, courrier) : uniquement le document demandé, sans ajouter de données absentes ; signale entre crochets les informations manquantes importantes [à compléter].
- Langue : celle de l'utilisateur (français, anglais ou arabe). Terminologie médicale précise.
- Scores et classifications : n'en cite les critères que si tu les connais exactement (ex. CURB-65 = confusion, urée > 7 mmol/L, FR ≥ 30/min, PAS < 90 ou PAD ≤ 60 mmHg, âge ≥ 65 ans) ; n'y mélange jamais d'autres signes de gravité.

IMAGES (radiographies, photos, ECG, documents)
- Décris uniquement ce qui est réellement visible, en signalant les limites (qualité, incidence, une seule vue). Ta lecture est une aide et ne remplace pas l'interprétation d'un radiologue ou d'un spécialiste.
- Latéralité : sur une radiographie ou un scanner en convention radiologique, la DROITE du patient est à GAUCHE de l'image. Vérifie le côté avant de l'écrire (repères : bouton aortique et pointe du cœur du côté gauche du patient) et précise que l'orientation doit être confirmée par les marqueurs de l'image.
- Ne présente jamais une hypothèse visuelle comme un diagnostic établi.

SÉCURITÉ
- Signes d'urgence vitale décrits pour un patient réel : commence par recommander l'appel immédiat des secours (Tunisie : SAMU 190 ; France : 15 ou 112 ; Europe : 112).
- Données identifiantes d'un patient (nom, date de naissance, numéro de dossier) : rappelle de les anonymiser.
- Tes réponses sont une aide et ne remplacent ni le jugement clinique ni les sources officielles."""

PATIENT_PROMPT = """Tu es MedAssist, un assistant d'information santé pour le grand public. Tu fonctionnes hors ligne et tu ne remplaces jamais un médecin ou un pharmacien.

URGENCES — TOUJOURS EN PREMIER
- Si la personne décrit des signes pouvant être graves (douleur thoracique, difficulté à respirer, signes d'AVC comme bouche déviée ou bras qui ne se lève plus, perte de connaissance, saignement important, intoxication ou ingestion de médicaments, surtout chez un enfant, réaction allergique avec gonflement, fièvre chez un nourrisson de moins de 3 mois), ta première phrase est : appeler immédiatement les secours (Tunisie : SAMU 190 ; France : 15 ou 112 ; Europe : 112). Puis seulement les gestes simples à faire en attendant.
- Si la personne exprime des idées suicidaires ou une grande détresse : réponds avec chaleur et sans jugement, encourage-la à parler tout de suite à quelqu'un, donne les numéros (Tunisie : SAMU 190 ; France : 3114, numéro national de prévention du suicide, ou 15 ; Europe : 112) et propose-lui de continuer à échanger.

FIABILITÉ — RÈGLES ABSOLUES
1. N'invente jamais : si tu ne connais pas un médicament, une maladie ou un nom, écris « Je ne connais pas [nom] » et conseille de demander au pharmacien. Ne devine pas à partir d'un nom qui ressemble.
2. Si la question repose sur une idée fausse (par exemple « les antibiotiques soignent le rhume »), corrige-la gentiment et clairement.
3. Ne pose pas de diagnostic : explique les causes possibles en termes simples et dis qui consulter et dans quel délai (urgence, aujourd'hui, dans la semaine).
4. Médicaments : pas de dose personnalisée. Renvoie vers la notice, le pharmacien ou le médecin. Pour un enfant, rappelle que la dose dépend du poids et doit être vérifiée avec le pharmacien. Grossesse ou allaitement : toujours demander l'avis d'un professionnel avant de prendre un médicament.
5. Images (radio, photo de peau, résultat d'analyse) : explique simplement ce que tu vois et ce que cela peut vouloir dire, sans conclure à un diagnostic ; rappelle que seul le médecin qui a prescrit l'examen (ou le radiologue) peut l'interpréter avec le dossier complet.

STYLE
- Phrases courtes, mots simples ; si un terme médical est nécessaire, explique-le entre parenthèses.
- Réponse directe d'abord, puis quelques points pratiques. Pas de longs exposés.
- Ton rassurant mais honnête. Réponds dans la langue de la personne (français, arabe ou anglais).
- Termine par une phrase courte rappelant de consulter un professionnel de santé si les symptômes persistent ou s'aggravent."""

ENTITY_PROMPT = """Tu es un contrôleur de vérité. Voici une question posée à un assistant médical.
Liste uniquement les NOMS PROPRES qu'elle contient, de ces types : medicament (DCI ou nom commercial), score (score, échelle, classification nommée), etude (essai clinique, cohorte), syndrome (syndrome, signe ou maladie portant un nom de personne), recommandation (recommandation datée d'un organisme, vitamine ou molécule désignée par un code).
Ne liste JAMAIS : les termes généraux (symptômes, organes, périodes comme trimestre ou âge, états comme grossesse ou allaitement, classes de médicaments comme IEC ou statines, examens, maladies courantes), ni les revues (NEJM, Lancet, JAMA), organismes (HAS, OMS, ESC, ANSM) et lieux.
Pour chaque nom listé, "certain" vaut true UNIQUEMENT si tu connais ce nom exact et peux en décrire le contenu précis (pour une étude : sa question et son résultat ; pour un score : ses items). Un nom qui ressemble à un nom connu n'est pas certain. Au moindre doute : false.

Question :
\"\"\"{question}\"\"\""""

ENTITY_SCHEMA = {
    "type": "object",
    "properties": {"entites": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "nom": {"type": "string"},
            "type": {"type": "string", "enum": ["medicament", "score", "etude", "syndrome", "recommandation", "autre"]},
            "certain": {"type": "boolean"}},
        "required": ["nom", "type", "certain"]}}},
    "required": ["entites"],
}

# Sonde : sur 12 noms fictifs et 28 réels (dont des raretés), 12 fictifs et 1 réel signalés (tests internes)
PROBE_PROMPT = ("Décris en 2 phrases au maximum « {nom} » ({type}) avec ses éléments précis "
                "(critères ou items, ou question et résultat principal d'une étude, ou signes, ou classe et indication "
                "d'un médicament). Si tu ne connais pas ce nom exact, ou s'il n'existe pas, réponds uniquement : INCONNU.")
MAX_PROBES = 4
FIRM_TYPES = {"score", "etude", "syndrome", "recommandation"}
CHILD_DOSE = re.compile(r"\b(dose|doses|posologie|combien (de|donner)|quantite)\b|\bmg\b|\bml\b")
REFERRAL = re.compile(r"pharmacien|medecin|pediatre")
BANNER_CHILD_DOSE = ("> 💊 **Dose pour un enfant** : à vérifier avec le médecin ou le pharmacien avant de la donner "
                     "(poids exact, forme et concentration du médicament, autres traitements).")
# « inconnu » seul vaut abstention ; « fièvre d'origine inconnue », « étiologie inconnue », « il n'existe pas de
# traitement » sont du texte médical ordinaire et ne doivent pas passer pour une abstention
ABSTAINED = re.compile(r"ne connais pas|n'existe pas(?! de )|(?<!origine )(?<!etiologie )(?<!cause )(?<!mecanisme )"
                       r"\binconnue?s?\b|pas reconnu|fictif|fictive|aucune (information|donnee|trace)")
ABSTAIN_WORDS = r"(ne connais pas|inconnue?|n'existe pas|pas reconnu|fictif|fictive|non reconnu)"


def abstains_about(answer, name):
    """La réponse dit-elle qu'elle ne connaît pas CE nom (consigne : « Je ne connais pas [nom]. ») ? Le test global
    ABSTAINED laissait passer un nom fictif décrit, dès que la réponse parlait ailleurs d'une « cause inconnue »."""
    a, n = _norm(answer), re.escape(_norm(name).strip())
    return bool(re.search(ABSTAIN_WORDS + r"[^.]{0,80}" + n, a) or re.search(n + r"[^.]{0,80}" + ABSTAIN_WORDS, a))

VERIFY_PROMPT = """Tu es un relecteur médical expert, rigoureux et sceptique. Vérifie la RÉPONSE d'un assistant à la QUESTION.
Signale uniquement les vrais problèmes :
- erreur_factuelle : fait médical faux (classe, mécanisme, antidote, seuil, contre-indication, interaction…)
- invention : médicament, étude, score ou chiffre présenté comme réel alors qu'il est inconnu ou douteux
- premisse_fausse : affirmation fausse de la question non corrigée
- danger : conseil pouvant nuire (dose, délai, urgence non signalée, contre-indication omise)
Vérifie en particulier les critères des scores cités (aucun critère ajouté ni manquant), les antidotes, les contre-indications et les numéros d'urgence.
{image_rule}
Ne signale pas le style, la longueur ni les détails secondaires exacts. Ne signale rien de correct : si tout est correct, renvoie une liste vide.
Ne demande jamais de retirer ou d'affaiblir une précaution de sécurité correcte : numéros d'urgence (Tunisie 190, France 15 ou 112, 3114), appel des secours, isolement respiratoire en cas de suspicion de tuberculose, consultation rapide, relecture par un radiologue.

QUESTION :
\"\"\"{question}\"\"\"
{context}
RÉPONSE :
\"\"\"{answer}\"\"\""""

IMAGE_RULE_WITH = ("Une image est jointe : compare la description de la réponse à l'image elle-même "
                   "(anomalies réellement visibles, côté atteint selon la convention radiologique où la droite "
                   "du patient est à gauche de l'image, absence d'anomalie inventée).")
IMAGE_RULE_WITHOUT = "Aucune image n'est jointe : ne juge pas une éventuelle description d'image."

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {"problemes": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["erreur_factuelle", "invention", "premisse_fausse", "danger"]},
            "extrait": {"type": "string"},
            "correction": {"type": "string"}},
        "required": ["type", "extrait", "correction"]}}},
    "required": ["problemes"],
}

REVISE_PROMPT = """Un relecteur expert a relevé des problèmes dans ta réponse précédente. Réécris la réponse complète en corrigeant chacun d'eux, en gardant le même format et le même public. N'ajoute aucune mention de la relecture.

Problèmes relevés :
{issues}

Ta réponse précédente :
\"\"\"{answer}\"\"\""""

# ----------------------------------------------------------------- triage déterministe

def _norm(text):
    text = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    return "".join(c for c in text if not unicodedata.combining(c))


EMERGENCY = re.compile(
    r"douleur (thoracique|dans la poitrine|a la poitrine)|serre(ment)? (dans|a) la poitrine|chest pain"
    r"|(bouche|visage) (devie|de travers|paralyse)|ne (peut|arrive) plus (a )?(lever|bouger|parler)|paralysi|avc\b|stroke"
    r"|(ne|n'arrive pas a|du mal a|difficult\w* a) respir|etouff|suffoqu|can'?t breathe"
    r"|(perte de|perdu) connaissance|inconscient|evanoui|convulsi"
    r"|(a|ont|il a|elle a) avale|ingere|ingestion|intoxi|empoisonn|overdose|surdos"
    r"|saigne(ment)? (abondant|important|beaucoup)|hemorragie"
    r"|(gonfle|gonflement)[^.]{0,30}(gorge|langue|levres|visage)|choc anaphyl")
# « en finir avec mes migraines » n'est pas une idée suicidaire : « en finir » seul, ou avec la vie / tout
SUICIDE = re.compile(
    r"suicid|mettre fin a (mes|ses) jours|en finir(?! avec)|en finir avec (la|ma|sa) vie|en finir avec tout\b"
    r"|me tuer|plus envie de vivre|envie de mourir|kill myself|end my life|want to die")

GENERIC = re.compile(
    r"\b(trimestres?|grossesse|enceinte|allaitement|nourrissons?|enfants?|adultes?|ages?|semaines?|mois|annees?"
    r"|douleurs?|fievre|toux|symptomes?|patients?"
    r"|nejm|lancet|jama|bmj|has|oms|who|esc|aha|acc|ada|ansm|ema|fda|nice|cdc|easl|kdigo|gold|gina)\b")

# Réponses de la sonde qui reviennent à « je ne connais pas ce nom » (texte normalisé, sans accents)
# Un « inconnu » ou un « n'existe pas » au milieu d'une vraie description ne vaut pas refus : « vascularite d'étiologie
# inconnue » (Kawasaki) et « il n'existe pas de traitement curatif » (Huntington) faisaient rejeter des noms réels
DENY = re.compile(
    r"^\W*inconnu\b"
    r"|\b(nom|terme|score|echelle|etude|essai|syndrome|medicament|molecule|entite|appellation|criteres?)s?\b[^.]{0,50}"
    r"\b(?:(?<!origine )(?<!etiologie )(?<!cause )(?<!mecanisme )inconnue?|n'existe pas(?! de )|non reconnue?|non repertoriee?)\b"
    r"|\bn'existe pas (dans la litterature|en tant que|comme|sous ce nom)"
    r"|ne connais pas|aucun(e)? (score|etude|essai|syndrome|medicament|trace|information)"
    r"|pas (de|d'un|un) (score|etude|essai|syndrome|medicament)[^.]{0,40}(reconnu|connu|repertorie|existant)"
    r"|n'est pas (un|une)[^.]{0,60}(reconnue?|repertoriee?) dans la (litterature|pratique)"
    r"|\b(fictif|fictive|invente)\b")

BANNER_EMERGENCY =("> 🚨 **Si une personne est en danger maintenant, appelez immédiatement les secours** : "
                    "Tunisie **190** (SAMU) · France **15** ou **112** · Europe **112**.")
BANNER_SUICIDE = ("> 💬 **Vous n'êtes pas seul·e. Parlez-en tout de suite à quelqu'un** : "
                  "Tunisie **190** (SAMU) · France **3114** (prévention du suicide, 24h/24) ou **15** · Europe **112**.")
# Seules les radiographies thoraciques de face ont été mesurées (voir CXR_PERF) ; le reste n'est pas validé
BANNER_IMAGE = {
    "pro": ("> ⚠️ **Lecture d'image automatique : second avis seulement.** Mesurée uniquement sur des "
            "radiographies thoraciques de face (performances sous le tableau de lecture) ; aucune validation pour "
            "les autres images. Confrontez chaque élément à l'image et au compte rendu d'un radiologue."),
    "patient": ("> ⚠️ **L'analyse d'images par cet assistant n'est pas fiable** : elle peut se tromper "
                "de côté ou voir des choses qui n'existent pas. Seul votre médecin ou le radiologue "
                "peut interpréter votre examen."),
}


def triage(question, profile, has_image=False):
    """Bandeaux ajoutés sans passer par le modèle. En mode Pro, les questions sur les
    intoxications ou les urgences sont souvent théoriques : seul le bandeau suicide y est gardé."""
    q = _norm(question)
    banners = [BANNER_IMAGE[profile]] if has_image else []
    if SUICIDE.search(q):
        banners.append(BANNER_SUICIDE)
    if profile == "patient" and EMERGENCY.search(q):
        banners.append(BANNER_EMERGENCY)
    return banners


# --------------------------------------------------------------------------- Ollama

def ollama_chat(url, model, messages, options, keep_alive, fmt=None, timeout=900, full=False):
    """Appel /api/chat sans flux. full=True renvoie la réponse entière (dont done_reason), sinon le texte."""
    body = {"model": model, "messages": messages, "stream": False, "think": False,
            "keep_alive": keep_alive, "options": options}
    if fmt:
        body["format"] = fmt
    req = urllib.request.Request(url.rstrip("/") + "/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return data if full else data["message"]["content"]


NETWORK = (urllib.error.URLError, TimeoutError, OSError)
TRANSIENT = NETWORK + (json.JSONDecodeError, KeyError)  # réponse d'Ollama tronquée ou mal formée : un nouvel essai


def explain_error(e, model, vision_model, url):
    """Message d'erreur lisible pour l'utilisateur, selon la cause (modèle absent, Ollama arrêté, bogue)."""
    if isinstance(e, urllib.error.HTTPError):
        detail = ""
        try:
            detail = json.loads(e.read()).get("error", "")
        except Exception:  # noqa: BLE001 - corps absent ou non JSON
            pass
        if e.code == 404 or "not found" in detail:
            return (f"Modèle introuvable dans Ollama ({detail or e.reason}). Installez-le : "
                    f"`ollama pull {model}` (ainsi que `{vision_model}` et `bge-m3`).")
        return f"Ollama a renvoyé une erreur {e.code} ({detail or e.reason}). Réessayez ; si cela persiste, redémarrez Ollama."
    if isinstance(e, NETWORK):
        return (f"Ollama ne répond pas sur {url} ({getattr(e, 'reason', None) or e}). "
                "Vérifiez qu'il est lancé (`ollama ps`), puis réessayez.")
    return f"Erreur interne de MedAssist ({type(e).__name__} : {e}). Si elle se répète, signalez-la avec la question posée."


BANNER_TRUNCATED = ("> ✂️ **Réponse coupée** : la longueur maximale a été atteinte. Demandez « continue » ou posez une "
                    "question plus ciblée ; la fin peut manquer.")


# ------------------------------------------------------------- imagerie spécialisée

# En anglais : en français, MedGemma classait toutes les radios de face en « profil » (16/16 justes en anglais).
# Son estimation de l'âge est peu fiable (adulte pour 4 radios d'enfant sur 6) : l'âge de la question prime.
MODALITY_PROMPT = ("Classify this medical image. If it is a chest radiograph, give the projection: frontal (PA or AP, "
                   "both lungs side by side) or lateral (side view, spine at the back), and whether the patient is a "
                   "child or an adult.")
MODALITY_SCHEMA = {
    "type": "object",
    "properties": {
        "modality": {"type": "string", "enum": ["chest_xray", "other_xray", "ct", "mri", "ultrasound", "ecg",
                                                "skin_photo", "fundus", "text_document", "other"]},
        "projection": {"type": "string", "enum": ["frontal", "lateral", "not_applicable"]},
        "age": {"type": "string", "enum": ["child", "adult", "unknown"]}},
    "required": ["modality", "projection", "age"],
}
# « depuis 2 ans », « il y a 3 ans » sont des durées, pas un âge : « toux depuis 2 ans » classait l'adulte en enfant
AGE_YEARS = re.compile(r"(?<!depuis )(?<!il y a )(?<!pendant )(?<!durant )(?<!apres )(?<!after )(?<!for )"
                       r"\b(\d{1,3}) ?(ans?|years?|yo)\b(?! de (tabac|tabagisme|paquets?|traitement|recul|suivi|evolution))")
# « toux depuis 3 mois », « 3 mois de grossesse » : durées, pas l'âge d'un nourrisson
AGE_MONTHS = re.compile(r"(?<!depuis )(?<!il y a )(?<!pendant )(?<!durant )(?<!for )\b\d{1,2} ?(mois|months?)\b"
                        r"(?! (de|d')\s?(toux|fievre|grossesse|amenorrhee|traitement|evolution|symptomes?|douleurs?|suivi|recul))")
ADULT_WORDS = re.compile(r"\b(adulte|adult|homme|femme|man|woman)\b")


def population_from_text(question):
    """« enfant » / « adulte » d'après la question, ou None si elle ne dit rien de l'âge."""
    q = _norm(question)
    years = AGE_YEARS.search(q)
    if years:
        return "enfant" if int(years.group(1)) < 16 else "adulte"
    if AGE_MONTHS.search(q) or CHILD_WORDS.search(q):
        return "enfant"
    if ADULT_WORDS.search(q):
        return "adulte"
    return None
WHO = {"enfant": "a child", "adulte": "an adult"}
VERDICT_PROMPT = ("This is a frontal chest X-ray of {who}. Is this radiograph abnormal (any pathological finding)? "
                  'Answer in JSON: {{"abnormal": true or false, "confidence": 0-100 (how sure you are of that answer)}}.')
VERDICT_SCHEMA = {"type": "object", "properties": {"abnormal": {"type": "boolean"},
                                                   "confidence": {"type": "integer", "minimum": 0, "maximum": 100}},
                  "required": ["abnormal", "confidence"]}
SIDE_PROMPT = ("This frontal chest X-ray is displayed in standard radiological convention. On which side of the "
               'PATIENT is the main abnormality? Answer in JSON: {"side": "right" | "left" | "both" | "none"}.')
SIDE_SCHEMA = {"type": "object", "properties": {"side": {"type": "string", "enum": ["right", "left", "both", "none"]}},
               "required": ["side"]}
SIDE_FR = {"right": "droit", "left": "gauche"}
CHILD_WORDS = re.compile(r"\b(enfant|nourrisson|bebe|pediatri\w*|fillette|garcon de \d|child|infant)\b")


DEEP_MODES = ("I;16", "I;16B", "I;16L", "I;16N", "I", "F")  # 12/16 bits : exports DICOM en PNG


def to_gray8(img):
    """Niveaux de gris 8 bits. Pillow écrête à blanc les radios 12/16 bits avec convert("L") (valeurs > 255 -> 255) :
    elles sont ramenées à 0-255 sur leurs centiles 0,5-99,5. Les autres modes gardent leur conversion habituelle."""
    from PIL import Image
    if img.mode in DEEP_MODES:
        import numpy as np
        arr = np.asarray(img, dtype=np.float32)
        lo, hi = np.percentile(arr, (0.5, 99.5))
        arr = np.clip((arr - lo) / max(hi - lo, 1e-6), 0, 1) * 255
        return Image.fromarray(arr.astype("uint8"), "L")
    return img.convert("L" if img.mode in ("L", "LA", "1") else "RGB")


def shrink(image_b64, max_side=1024):
    """Réduit une image base64 à max_side pixels (PNG, 8 bits) ; renvoie l'original si Pillow échoue."""
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(base64.b64decode(image_b64)))
        if max(img.size) <= max_side and img.mode not in DEEP_MODES:
            return image_b64
        img = to_gray8(img)
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:  # noqa: BLE001
        return image_b64


def cxr_analyze(url, image_b64, population, timeout=180):
    req = urllib.request.Request(url.rstrip("/") + "/analyze",
                                 json.dumps({"image": image_b64, "population": population}).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def verdict(result, vlm):
    """Verdict retenu : « anormale », « normale », « discordance » ou None (aucun lecteur fiable)."""
    spec = result.get("anormale")  # None : seuils du spécialiste non validés pour ce contexte
    if spec is None:
        return None if not vlm else ("anormale" if vlm["abnormal"] else "normale")
    if not vlm:
        return "anormale" if spec else "normale"
    return "anormale" if spec and vlm["abnormal"] else "normale" if not spec and not vlm["abnormal"] else "discordance"


def _where(f):
    side = f.get("cote_patient")
    if not side:
        return "—"
    if side.startswith("bilat"):
        return f"bilatéral ou indéterminé, étage {f['etage']}"
    return f"côté {side} du patient, étage {f['etage']}"


def laterality(result):
    """Côté de l'anomalie principale. Tests sur 35 tuberculoses unilatérales (Montgomery) : quand le calcul du
    spécialiste et la lecture visuelle de Qwen concordent, 17/17 justes ; Qwen seul : 13/15 ; désaccord : 3 cas."""
    # Première anomalie au côté net : une anomalie « indéterminée » mieux classée ne masque pas le calcul
    sided = [f["cote_patient"] for f in result.get("anomalies", []) if f.get("cote_patient") in ("droit", "gauche")]
    calc = sided[0] if sided else None
    visual = result.get("cote_visuel")
    if calc and visual:
        return (f"**{calc}** (calcul et lecture visuelle concordants)" if calc == visual else
                f"⚠️ **discordant** : calcul {calc}, lecture visuelle {visual} — à vérifier sur l'image")
    if visual:
        return f"{visual} selon la lecture visuelle seule (non confirmé par le calcul)"
    if calc:
        return f"{calc} selon le calcul seul (non confirmé par la lecture visuelle)"
    return None


def cxr_block(result, vlm, profile):
    """Double lecture automatique, mise en forme sans passer par le modèle de langage."""
    found = result.get("anomalies", [])
    final = verdict(result, vlm)
    pop = result.get("population", "adulte")
    validated = result.get("verdict_valide")
    if profile == "patient":
        lines = ["#### 🩻 Lecture automatique de la radiographie du thorax"]
        if final == "discordance":
            lines.append("Les deux lecteurs automatiques **ne sont pas d'accord** sur cette image : "
                         "seul un radiologue peut trancher.")
        elif final == "anormale":
            lines.append("La lecture automatique trouve des **signes possiblement anormaux** sur cette radio. "
                         "Montrez-la rapidement au médecin qui l'a prescrite.")
        elif final == "normale":
            lines.append("La lecture automatique ne trouve pas d'anomalie évidente.")
        lines.append("Ce n'est pas un diagnostic : une radio peut paraître normale malgré une maladie, et l'inverse. "
                     "Seul le radiologue ou votre médecin peut interpréter l'examen.")
        return "\n".join(lines)

    lines = [f"#### 🩻 Radiographie thoracique de face : double lecture automatique ({pop})"]
    if result.get("age_source") == "estimation visuelle":
        lines.append(f"*Âge non précisé : « {pop} » estimé sur l'image, ce qui est peu fiable. Indiquez l'âge dans votre "
                     "question (les seuils diffèrent chez l'enfant).*\n")
    lines += ["| Lecteur | Verdict |", "|---|---|"]
    if validated:
        lines.append(f"| Spécialiste (TorchXRayVision) | {'**anormale**' if result['anormale'] else 'normale'} "
                     f"(score {result['score_global']:.2f}, seuil {result['seuil_global']:.2f}) |")
    else:
        lines.append("| Spécialiste (TorchXRayVision) | pas de verdict : seuils non calibrés pour ce site "
                     "(localisation et classement seulement) |")
    if vlm:
        lines.append(f"| Modèle de vision médical ({vlm['model']}) | "
                     f"{'**anormale**' if vlm['abnormal'] else 'normale'} (confiance {vlm['confidence']} %) |")
    if final == "discordance":
        lines.append("\n> ⚠️ **Discordance entre les deux lecteurs** : relecture par un radiologue indispensable.")
    elif final and validated and vlm:
        lines.append(f"\nLes deux lecteurs concordent : radiographie {final}. Une concordance ne vaut pas diagnostic.")
    elif final:
        lines.append(f"\nVerdict retenu (un seul lecteur) : radiographie **{final}**.")
    show = final in ("anormale", "discordance") or (validated and found)
    side = laterality(result)
    if side and show:
        lines.append(f"\n**Côté de l'anomalie principale (patient)** : {side}")
    if found and show:
        title = ("Anomalies au-dessus de leur seuil (spécialiste)" if validated else
                 "Anomalies les plus suspectes selon le spécialiste (classement relatif, non calibré)")
        lines += [f"\n**{title}**", "| Anomalie | Score / seuil | Zone principale |", "|---|---|---|"]
        lines += [f"| {f['nom_fr']} | {f['probabilite']:.2f} / {f['seuil']:.2f} | {_where(f)} |" for f in found]
        if result.get("image_annotee"):
            lines.append(f"\n![Zones qui ont le plus influencé le lecteur ({result['image_annotee_pour']})]"
                         f"(data:image/jpeg;base64,{result['image_annotee']})")
    lines.append(f"\n*{CXR_PERF[result.get('calibration', pop)]}*")  # Open WebUI n'interprète pas <sub>
    return "\n".join(lines)


def cxr_prompt(result, vlm, profile="pro"):
    """Résultats MESURÉS des deux lecteurs transmis au rédacteur (pas de description libre : elle inventait)."""
    found = result.get("anomalies", [])
    final = verdict(result, vlm)
    style = ("\nPrésente ta réponse comme la synthèse de ces lectures automatiques ; n'écris pas que tu n'as pas accès "
             "à l'image.")
    if profile == "patient":
        # Pour le grand public : le verdict et ce qu'il faut faire, sans liste d'anomalies techniques
        text = {"anormale": "la lecture automatique trouve des signes possiblement anormaux",
                "normale": "la lecture automatique ne trouve pas d'anomalie évidente",
                "discordance": "les deux lectures automatiques ne sont pas d'accord"}.get(final, "pas de conclusion")
        return (f"\n\nRADIOGRAPHIE DU THORAX JOINTE : {text}. Ne cite aucune anomalie précise, aucun côté, aucun "
                "matériel : seul le médecin peut interpréter l'image. Explique simplement ce que cela veut dire et qui "
                "consulter, dans quel délai, en tenant compte des symptômes décrits." + style)
    listing = "; ".join(f"{f['nom_fr']} (score {f['probabilite']:.2f} pour un seuil de {f['seuil']:.2f}, {_where(f)})"
                        for f in found) or "aucune"
    text = ("\n\nDOUBLE LECTURE AUTOMATIQUE DE CETTE RADIOGRAPHIE THORACIQUE DE FACE "
            f"(patient {result.get('population', 'adulte')}) :\n")
    if result.get("verdict_valide"):
        text += (f"- Lecteur spécialisé : radiographie {'anormale' if result['anormale'] else 'normale'} ; "
                 f"anomalies au-dessus de leur seuil : {listing}.\n")
    else:
        text += ("- Lecteur spécialisé : pas de verdict (seuils non calibrés pour ce site) ; anomalies les plus "
                 f"suspectes dans son classement relatif : {listing}. Ne les présente pas comme des anomalies "
                 "établies.\n")
    if vlm:
        text += (f"- Modèle de vision médical ({vlm['model']}) : radiographie "
                 f"{'anormale' if vlm['abnormal'] else 'normale'} (confiance {vlm['confidence']} %).\n")
    if final == "discordance":
        text += "LES DEUX LECTEURS SONT EN DÉSACCORD : dis-le clairement et ne tranche pas à leur place.\n"
    elif final:
        text += f"Verdict retenu : radiographie {final}.\n"
    side = laterality(result)
    if side and final in ("anormale", "discordance"):
        text += f"Côté de l'anomalie principale (synthèse calculée) : {side.replace('**', '')}.\n"
    return text + ("Règles : ta conclusion reprend le verdict retenu ci-dessus (jamais l'inverse). Pour le côté atteint, "
                   "reprends exactement la synthèse ci-dessus, y compris son niveau de certitude. N'attribue à chaque "
                   "lecteur que ce qui est écrit ci-dessus. Structure : Technique et limites ; Résultats ; Conclusion "
                   "(hypothèses classées par probabilité, à confronter à la clinique) ; Conduite à tenir (dont la "
                   "relecture par un radiologue)." + style)


# Mesures sur des radiographies jamais vues, avec les questions exactes de ce pipeline
# (eval/cxr_metrics.py, eval/cxr_calibrate.py, eval/cxr_laterality.py, eval/cxr_pipeline_verdict.py)
CXR_PERF = {
    "enfant": ("Mesures (enfant, pneumonie, Kermany) : spécialiste sensibilité 95 % / spécificité 66 % sur 624 radios "
               "(seuil calibré dans le même hôpital : probablement optimiste ailleurs) ; MedGemma 4B 92 % / 80 % sur "
               "100 radios. Ce n'est pas un niveau de radiologue."),
    "adulte": ("Mesures (adulte, dépistage de la tuberculose, 138 radios Montgomery) : MedGemma 4B sensibilité 88 % / "
               "spécificité 92 % (présence de ces radios dans son entraînement non vérifiable) ; côté atteint juste "
               "17/17 quand calcul et lecture visuelle concordent. Spécialiste sans verdict faute de calibration locale "
               "(radiology/calibrate_local.py). Ce n'est pas un niveau de radiologue."),
    "local": ("Spécialiste calibré sur les radios normales de votre site : en simulation, sensibilité 67 % / "
              "spécificité 92 %, à vérifier chez vous. MedGemma 4B (Montgomery) : 88 % / 92 %. "
              "Ce n'est pas un niveau de radiologue."),
}


# ------------------------------------------------------------- base documentaire

# Index de la base documentaire : <dossier d'installation>\knowledge\index (MEDASSIST_ROOT, sinon ~\open-webui)
KB_DIR = os.path.join(os.environ.get("MEDASSIST_ROOT", os.path.join(os.path.expanduser("~"), "open-webui")),
                      "knowledge", "index")
# Similarité bge-m3 : questions couvertes par la base 0,61-0,79 ; questions hors base 0,36-0,73 (médiane 0,55).
# Un seuil seul ne les sépare pas : il écarte le bruit le plus faible, la consigne fait ignorer le reste.
# 0,55 écartait la bonne ligne HAS sur la BPCO (0,548, page de tableau mêlant plusieurs infections) : 0,50.
KB_MIN_SCORE = 0.50
LEXICAL_WEIGHT = 0.15
KB_MAX_KEPT = 5  # extraits gardés après le tri, au plus
CONTEXT_CHARS = 600  # fin du passage précédent jointe à chaque extrait (titres de tableau)


def _words(text):
    return re.findall(r"[a-z0-9]{4,}", text)


def doc_title(stem):
    return stem.replace("_", " ")


class Knowledge:
    """Recherche sémantique dans l'index de knowledge/ingest.py (passages + embeddings bge-m3 normalisés)."""
    _cache = {}  # chargé une fois par processus, rechargé si l'index est reconstruit

    def __init__(self, index_dir, ollama_url, model="bge-m3"):
        self.dir, self.url, self.model = Path(index_dir), ollama_url, model

    def _load(self):
        manifest = self.dir / "manifest.json"
        if not manifest.exists():
            return None
        stamp = manifest.stat().st_mtime
        cached = Knowledge._cache.get(str(self.dir))
        if not cached or cached["stamp"] != stamp:
            import numpy as np
            passages = [json.loads(line) for line in (self.dir / "passages.jsonl").open(encoding="utf-8")]
            norm = [_norm(p["text"]) for p in passages]
            words = [set(_words(t)) for t in norm]
            df = collections.Counter(w for ws in words for w in ws)
            cached = {"stamp": stamp, "matrix": np.load(self.dir / "embeddings.npy").astype("float32"),
                      "passages": passages, "norm": norm, "words": words,
                      "idf": {w: math.log(len(words) / (1 + c)) for w, c in df.items()}}
            Knowledge._cache[str(self.dir)] = cached
        return cached

    def page_text(self, hit):
        """Texte complet de la page d'où vient un extrait (tous ses passages)."""
        data = self._load() or {"passages": []}
        return "\n".join(p["text"] for p in data["passages"] if p["doc"] == hit["doc"] and p["page"] == hit["page"])

    def search(self, query, k=5, min_score=KB_MIN_SCORE):
        """Recherche hybride : similarité bge-m3 + 0,15 × part (pondérée idf) des mots de la question présents.
        Sur eval/docbench.py, la réponse figure dans les 5 extraits pour 19/21 questions en dense seul, 21/21 en
        hybride (les termes exacts français, ex. « abcès », remontent la fiche HAS face aux chapitres OMS anglais).
        Le seuil porte sur la similarité sémantique ; un seul extrait par page (le recouvrement crée des doublons)."""
        import numpy as np
        data = self._load()
        if not data:
            return []
        req = urllib.request.Request(self.url.rstrip("/") + "/api/embed",
                                     json.dumps({"model": self.model, "input": [query]}).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            q = np.asarray(json.load(resp)["embeddings"][0], dtype="float32")
        dense = data["matrix"] @ (q / (np.linalg.norm(q) + 1e-12))
        terms = set(_words(_norm(query)))
        total = sum(data["idf"].get(t, 0) for t in terms) or 1
        lexical = np.array([sum(data["idf"].get(t, 0) for t in terms if t in ws) / total for ws in data["words"]])
        scores = dense + LEXICAL_WEIGHT * lexical
        hits = []
        for i in np.argsort(-scores)[:k * 6]:
            if len(hits) == k:
                break
            p = data["passages"][i]
            # Plusieurs passages d'une même page sont permis : la page 3 de la fiche HAS en a trois (lignes de tableau
            # différentes) et la limite d'un par page écartait la ligne « DHBNN : amoxicilline 7 jours ». Le tri suit.
            if dense[i] >= min_score:
                # Contexte pour le TRI seulement : la fin du passage précédent (même page). Dans les tableaux HAS, le
                # titre de ligne (« Exacerbation de BPCO ») restait dans le passage d'avant, et le tri écartait la bonne
                # ligne. Donné aussi à la rédaction, ce contexte a fait attribuer à l'adulte la ligne enfant d'avant
                # (pneumonie « 5 jours ») : docbench 21/21 -> 19/21. La rédaction ne reçoit donc que le passage.
                prev = data["passages"][i - 1] if i > 0 else None
                before = ""
                if prev and (prev["doc"], prev["page"]) == (p["doc"], p["page"]):
                    before = "…" + prev["text"][-CONTEXT_CHARS:] + "\n"
                hits.append({**p, "before": before, "score": round(float(dense[i]), 3)})
        return hits

    def contains(self, name):
        """Le nom figure-t-il, en mot entier, dans un document de la base ? (il existe donc, même si le modèle
        l'ignore). Sans frontières de mots, « ARRIVE » était trouvé dans « arrivée »."""
        data = self._load()
        n = _norm(name).strip()
        if not data or len(n) < 4:
            return False
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])")
        return any(pattern.search(t) for t in data["norm"])


def kb_prompt(hits):
    lines = ["\n\nEXTRAITS DE LA BASE DOCUMENTAIRE LOCALE (documents officiels choisis par l'utilisateur ; sur un "
             "point qu'ils traitent, ils priment sur tes connaissances) :"]
    lines += [f"[{i}] {doc_title(h['doc'])}, page {h['page']} :\n\"\"\"{h['text']}\"\"\"" for i, h in enumerate(hits, 1)]
    lines.append("RÈGLES : si ces extraits répondent à la question, appuie ta réponse dessus (molécules, doses, durées, "
                 "conduites à tenir) et cite chaque affirmation qui en vient avec son numéro entre crochets, ex. [1]. "
                 "N'utilise que ces numéros, et seulement pour des extraits qui traitent exactement le sujet de la "
                 "question ; ignore les autres. Les extraits COMPLÈTENT tes connaissances sans les remplacer : pour une "
                 "notion de base (classe d'un médicament, définition) ou un point qu'ils ne couvrent pas, réponds "
                 "normalement à partir de tes connaissances, avec tes règles de fiabilité, en écrivant « (hors base "
                 "documentaire) » ; ne refuse jamais de répondre au seul motif que les extraits n'en parlent pas. Un "
                 "extrait ne prouve pas l'existence d'un nom qui n'y figure pas. Tes règles de sécurité restent "
                 "prioritaires sur les extraits : toute posologie est à vérifier et à adapter au patient, et une dose "
                 "pour un enfant renvoie toujours au médecin ou au pharmacien. Si des extraits de sources différentes "
                 "(ex. HAS et OMS) donnent des valeurs différentes pour le même point (durée, dose, molécule), donne "
                 "CHAQUE valeur avec sa source et ses nuances exactes (durée maximale, conditions d'arrêt plus "
                 "précoce, population concernée), sans en retenir une seule. Si un extrait concerne un autre contexte "
                 "(enfant / adulte, autre pays), signale-le. N'écris pas de liste de sources : elle est ajoutée "
                 "automatiquement. Les numéros [n] d'une réponse précédente ne valent plus : seuls ceux ci-dessus comptent.")
    return "\n".join(lines)


FOLLOWUP_CHARS = 60  # en dessous, une question qui suit un échange est complétée par la question précédente
HISTORY_IMAGES_RULE = ("\n\nLes images jointes plus tôt dans la conversation ne te sont plus montrées. Appuie-toi sur ta "
                       "réponse précédente et sur les résultats de lecture automatique qu'elle contient ; n'ajoute aucune "
                       "observation visuelle nouvelle. Pour une nouvelle lecture, demande de joindre à nouveau l'image.")
NO_CITATION_RULE = ("\n\nAucun extrait de la base documentaire n'est fourni pour cette question : n'écris aucun numéro "
                    "entre crochets, même si une réponse précédente en contenait.")


RELEVANCE_PROMPT = """Question d'un utilisateur :
« {question} »

Extraits trouvés par une recherche automatique dans une base de recommandations officielles :
{extracts}

Quels extraits traitent DIRECTEMENT du sujet de la question (même maladie, même médicament ou même situation clinique) et
apportent une information utile pour y répondre ? Un extrait qui partage seulement des mots généraux (dose, surveillance,
enfant, diagnostic, examen) sans parler du sujet précis n'est PAS pertinent. Réponds en JSON : {{"pertinents": [numéros]}},
liste vide si aucun."""
RELEVANCE_SCHEMA = {"type": "object", "properties": {"pertinents": {"type": "array", "items": {"type": "integer"}}},
                    "required": ["pertinents"]}

# « score de Hammond-Lefèvre » : avec son préfixe, la sonde a décrit le score fictif comme une échelle de spasticité ;
# seul (« Hammond-Lefèvre »), elle répond INCONNU. Le type reste donné à la sonde entre parenthèses.
PREFIX = re.compile(r"^(le |la |les |l')?(score|scores|etude|essai|syndrome|maladie|triade|criteres?|regle|echelle"
                    r"|classification|indice|index|signe|test|recommandations?|protocole|schema|methode)"
                    r"( de | du | des | d'| )", re.I)


def bare_name(name):
    """Nom sans son préfixe générique, sur le texte d'origine (accents conservés)."""
    m = PREFIX.match(_norm(name))
    return name[m.end():].strip() if m and name[m.end():].strip() else name


# Refus motivé par les extraits (« les extraits concernent exclusivement des antibiotiques… je ne connais pas ») :
# sur une question hors du thème de la base (lithium), des extraits voisins ont fait refuser une notion de base
# « aucun » seul fait aussi réagir sur « les extraits indiquent qu'aucun antibiotique n'est recommandé » : retiré
KB_REFUSAL = re.compile(r"(extraits?|base documentaire|documents? (locaux|fournis))[^.]{0,120}"
                        r"(ne (contien|concern|trait|couvr|mentionn|precis|parl|fourniss|abord|permet)"
                        r"|aucune? (information|donnee|element|mention)|exclusivement|pas d.information)")


def kb_sources(answer, hits):
    """Bloc « Sources » déterministe : seuls les numéros réellement cités, et alerte sur un numéro inventé."""
    cited = sorted({int(n) for n in re.findall(r"\[(\d{1,2})\]", answer)})
    valid = [n for n in cited if 1 <= n <= len(hits)]
    invalid = [n for n in cited if n not in valid]
    if not cited:
        return None
    lines = ["**📚 Sources (base documentaire locale)**"]
    lines += [f"- [{n}] {doc_title(hits[n - 1]['doc'])}, page {hits[n - 1]['page']}" for n in valid]
    if invalid:
        lines.append(f"- ⚠️ {', '.join(f'[{n}]' for n in invalid)} : numéro cité mais absent des extraits fournis, "
                     "à ignorer.")
    return "\n".join(lines)


# Milliers : « 4 000 mg », « 800 000 UI » (espace) ou « 800,000 IU » (virgule anglaise)
DOSE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[ ,]\d{3})+(?![\d])|\d+(?:[.,]\d+)?)\s?(mg|g|µg|μg|mcg|ui|iu|ml|mmol)(?![^\W\d_]{2})",
                  re.I)  # « 2 gélules » n'est pas une dose ; « 800 000 IUa » (renvoi de note a) en est une
CITES = re.compile(r"\[(\d{1,2})\]")


def _dose_forms(num, unit):
    """Formes équivalentes d'une dose : « 1 g » = « 1000 mg », « 1,5 g » = « 1.5 g » ; µg = mcg ; ui = iu.
    « 1,500 » est ambigu (1,5 en français, 1500 en anglais) et « 4 500 mg » peut être « 4 × 500 mg » : les deux
    lectures sont gardées."""
    unit = {"μg": "µg", "mcg": "µg", "iu": "ui"}.get(unit.lower(), unit.lower())
    if re.fullmatch(r"\d{1,3}(?:[ ,]\d{3})+", num):
        values = {float(re.sub(r"[ ,]", "", num)), float(re.split(r"[ ,]", num)[-1])}
        if re.fullmatch(r"\d{1,3},\d{3}", num):
            values.add(float(num.replace(",", ".")))
    else:
        values = {float(num.replace(",", "."))}
    forms = set()
    for value in values:
        forms.add((value, unit))
        if unit == "g":
            forms.add((value * 1000, "mg"))
        if unit == "mg":
            forms.add((value / 1000, "g"))
    return forms


def _doses(text):
    out = set()
    for num, unit in DOSE.findall(text.replace(" ", " ").replace("\xa0", " ")):
        try:
            out |= {f for f in _dose_forms(num, unit) if f[0] > 0}
        except ValueError:
            continue
    return out


def dose_misattributions(answer, hits, page_text):
    """Filet déterministe sur les citations : une dose (nombre + unité) d'une phrase qui cite [k] doit figurer dans la
    page source de [k]. Observé : « amoxicilline 500 mg, 3 fois par jour [2], [3] », alors que la fiche HAS [3] ne
    donne aucune dose (elle venait de l'OMS [2]). Comparaison sur la page entière du document cité, pas seulement sur
    l'extrait, pour éviter les fausses alertes. Renvoie [(dose affichée, [numéros cités qui ne la contiennent pas])]."""
    body = answer.split("**📚 Sources")[0]
    cache, found = {}, []
    for segment in re.split(r"\n+|(?<=[.!?])\s+(?=[A-ZÀ-Ý*])", body):
        cited = sorted({int(n) for n in CITES.findall(segment) if 1 <= int(n) <= len(hits)})
        if not cited:
            continue
        for m in DOSE.finditer(segment.replace(" ", " ").replace("\xa0", " ")):
            want = _dose_forms(m.group(1), m.group(2))
            missing = []
            for n in cited:
                if n not in cache:
                    cache[n] = _doses(page_text(hits[n - 1]))
                if not (want & cache[n]):
                    missing.append(n)
            if missing and (m.group(0), missing) not in found:
                found.append((m.group(0), missing))
    return found


class Engine:
    """Pipeline : triage -> [lecteur radio] -> entités -> premier jet -> relecture -> correction."""

    def __init__(self, url="http://localhost:11434", model="qwen3.6:35b", num_ctx=16384,
                 keep_alive="30m", verify=True, entity_check=True, cxr_url="http://127.0.0.1:8765",
                 vision_model="medgemma:4b", kb_dir=KB_DIR, kb_topk=8, kb_min_score=KB_MIN_SCORE):
        self.url, self.model, self.keep_alive = url, model, keep_alive
        self.verify, self.entity_check, self.cxr_url = verify, entity_check, cxr_url
        self.vision_model = vision_model or model
        self.kb = Knowledge(kb_dir, url) if kb_dir else None
        self.kb_topk, self.kb_min_score = kb_topk, kb_min_score
        self.opts = {"num_ctx": num_ctx, "temperature": 0.3, "top_p": 0.9, "num_predict": 2048}
        self.strict = {**self.opts, "temperature": 0}
        self.truncated = False  # dernière réponse coupée par num_predict

    def _call(self, messages, opts=None, fmt=None):
        """Un second essai sur une erreur passagère (Ollama renvoie parfois 500 en sortie JSON contrainte, ou coupe
        la connexion) ; un modèle absent (404) remonte tout de suite."""
        last = None
        for _ in range(2):
            try:
                data = ollama_chat(self.url, self.model, messages, opts or self.opts, self.keep_alive, fmt, full=True)
                self.truncated = data.get("done_reason") == "length"
                return data["message"]["content"]
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise
                last = e
            except TRANSIENT as e:
                last = e
        raise last

    def _vision(self, prompt, image, fmt=None, num_predict=60):
        """Appel au modèle de vision médical (MedGemma 4B par défaut : AUC 0,94 sur des radios adultes de test)."""
        opts = {"num_ctx": 4096, "temperature": 0, "num_predict": num_predict}
        return ollama_chat(self.url, self.vision_model, [{"role": "user", "content": prompt, "images": [image]}],
                           opts, self.keep_alive, fmt)

    def probe_denies(self, name, kind):
        """Le modèle sait-il décrire ce nom ? Un « INCONNU » ou un « n'existe pas » le désigne comme douteux."""
        out = self._call([{"role": "user", "content": PROBE_PROMPT.format(nom=name, type=kind)}],
                         {**self.strict, "num_predict": 160})
        return bool(DENY.search(_norm(out)))

    def relevant(self, question, hits):
        """Garde les extraits qui traitent du sujet. La similarité ne sépare pas le hors-sujet (scores 0,50-0,73) du
        pertinent (0,55-0,79) : une page AWaRe sur les examens de laboratoire a fait refuser le seuil d'HbA1c."""
        extracts = "\n".join(f"[{i}] {h.get('before', '')}{h['text']}" for i, h in enumerate(hits, 1))
        raw = self._call([{"role": "user", "content": RELEVANCE_PROMPT.format(question=question, extracts=extracts)}],
                         self.strict, RELEVANCE_SCHEMA)
        try:
            keep = {int(n) for n in json.loads(raw)["pertinents"]}
        except (ValueError, KeyError, TypeError):
            return hits  # tri indisponible : extraits gardés (filet KB_REFUSAL ensuite)
        return [h for i, h in enumerate(hits, 1) if i in keep][:KB_MAX_KEPT]

    def unknown_entities(self, question):
        """Noms de la question que le modèle ne sait pas décrire : [(nom, type)]."""
        raw = self._call([{"role": "user", "content": ENTITY_PROMPT.format(question=question)}],
                         self.strict, ENTITY_SCHEMA)
        try:
            entities = json.loads(raw)["entites"]
        except (ValueError, KeyError, TypeError):
            return []
        q = _norm(question)
        unknown = []
        for e in entities[:MAX_PROBES]:
            name = e.get("nom", "")
            # Garde-fou : un nom signalé doit figurer tel quel dans la question et ne pas être un terme général
            if e.get("type") == "autre" or _norm(name) not in q or GENERIC.search(_norm(name)):
                continue
            # La sonde décide seule : « certain » se trompe dans les deux sens (sûr de CARDIO-ZEN,
            # fictif ; pas sûr de Staphylococcus lugdunensis, réel)
            # Un nom présent tel quel dans un document de la base existe, même si le modèle l'ignore
            # Nom complet ET nom nu : sur 10 noms fictifs, 7 signalés avec préfixe, 8 sans, 9 par l'un ou l'autre
            # (eval/probe_prefix.py) ; prix : 5 noms réels sur 18 signalés à tort, soit une abstention prudente
            bare = bare_name(name)
            denied = self.probe_denies(name, e["type"]) or (bare != name and self.probe_denies(bare, e["type"]))
            if denied and not (self.kb and (self.kb.contains(name) or self.kb.contains(bare))):
                unknown.append((name, e["type"]))
        return unknown

    def review(self, question, answer, images=None, context=""):
        # Le relecteur reçoit les mêmes images : sans elles, il « corrigerait » la description à l'aveugle
        rule = (IMAGE_RULE_WITH if images else IMAGE_RULE_WITHOUT)
        if context:
            rule += ("\nLa réponse doit être FIDÈLE aux informations fournies ci-dessous (résultats d'examen, extraits de "
                     "documents) : toute contradiction avec elles, toute observation d'image qui n'y figure pas, ou toute "
                     "citation [n] attribuant à un extrait ce qu'il ne dit pas, est une erreur_factuelle.")
            context = f"\nINFORMATIONS FOURNIES À L'ASSISTANT :\n\"\"\"{context.strip()}\"\"\"\n"
        msg = {"role": "user", "content": VERIFY_PROMPT.format(question=question, answer=answer, image_rule=rule,
                                                               context=context)}
        if images:
            msg["images"] = images
        # Ollama peut renvoyer une erreur 500 en cours de sortie JSON contrainte : un second essai, puis None
        # (« relecture indisponible ») plutôt que de faire échouer toute la réponse
        for _ in range(2):
            try:
                return json.loads(self._call([msg], self.strict, VERIFY_SCHEMA))["problemes"]
            except Exception:  # noqa: BLE001
                continue
        return None

    def read_images(self, images, question, status):
        """Radiographies thoraciques de face -> double lecture (spécialiste + modèle de vision médical).
        Renvoie [(résultat du spécialiste ou {"erreur"}, avis du modèle de vision ou None)]."""
        out = []
        for original in images[:3]:
            img = shrink(original)  # modèles de vision : 1024 px suffisent ; le spécialiste reçoit l'original
            status("Identification du type d'image…")
            try:
                kind = json.loads(self._vision(MODALITY_PROMPT, img, MODALITY_SCHEMA))
            except Exception as e:  # noqa: BLE001 - modèle de vision absent ou Ollama en erreur : on le dit, sans échouer
                out.append(({"erreur": f"identification du type d'image indisponible ({explain_error(e, self.model, self.vision_model, self.url).split('.')[0]})"}, None))
                continue
            if kind.get("modality") != "chest_xray" or kind.get("projection") != "frontal":
                continue
            # L'âge précisé dans la question l'emporte sur l'estimation visuelle, peu fiable
            pop = population_from_text(question)
            age_source = "question"
            if not pop:
                pop, age_source = ("enfant" if kind.get("age") == "child" else "adulte"), "estimation visuelle"
            status("Lecteur spécialisé de radiographie thoracique…")
            try:
                result = cxr_analyze(self.cxr_url, original, pop)
                result["age_source"] = age_source
            except Exception as e:  # noqa: BLE001 - le service peut être arrêté : on le dit au lieu d'échouer
                out.append(({"erreur": f"lecteur spécialisé indisponible ({e})"}, None))
                continue
            status("Latéralité : lecture visuelle…")
            try:
                side = json.loads(self._call([{"role": "user", "content": SIDE_PROMPT, "images": [img]}],
                                             {**self.strict, "num_ctx": 4096, "num_predict": 40}, SIDE_SCHEMA))["side"]
                result["cote_visuel"] = SIDE_FR.get(side)
            except Exception:  # noqa: BLE001 - sans lecture visuelle, seul le côté calculé reste
                pass
            status("Seconde lecture par le modèle de vision médical…")
            vlm = None
            try:
                vlm = json.loads(self._vision(VERDICT_PROMPT.format(who=WHO[pop]), img, VERDICT_SCHEMA))
                vlm["confidence"] = max(0, min(100, int(vlm["confidence"])))
                vlm["model"] = self.vision_model
            except Exception:  # noqa: BLE001 - sans seconde lecture, le spécialiste reste affiché seul
                vlm = None
            out.append((result, vlm))
        return out

    def run(self, messages, profile="pro", status=lambda msg: None):
        """messages : historique au format Ollama (le dernier est la question). Renvoie (texte, trace)."""
        question = messages[-1].get("content", "")
        system = PRO_PROMPT if profile == "pro" else PATIENT_PROMPT
        originals = messages[-1].get("images")
        trace = {"banners": triage(question, profile, bool(originals)), "unknown": [], "issues": [], "cxr": [],
                 "sources": []}

        blocks = []
        # Les images des messages précédents ne sont pas renvoyées au modèle : il les relirait librement (lecture non
        # mesurée, fausse dans chaque test), et leur poids en base64 saturait le contexte. Les résultats de lecture
        # automatique restent dans sa réponse précédente, conservée dans l'historique.
        had_history_images = any(m.get("images") for m in messages[:-1])
        messages = [{k: v for k, v in m.items() if k != "images"} for m in messages[:-1]] + [messages[-1]]
        if originals:
            # Rédaction et relecture voient l'image réduite (une radio peut dépasser 4000 px de côté)
            messages[-1] = {**messages[-1], "images": [shrink(i) for i in originals]}
        elif had_history_images:
            system += HISTORY_IMAGES_RULE
        context = ""
        if originals and self.cxr_url:
            for res, vlm in self.read_images(originals, question, status):
                if "erreur" in res:
                    blocks.append(f"> ⚠️ {res['erreur']} : lecture faite par le modèle généraliste seul.")
                    trace["cxr"].append(res["erreur"])
                else:
                    blocks.append(cxr_block(res, vlm, profile))
                    context += cxr_prompt(res, vlm, profile)
                    trace["cxr"].append(f"{res['population']}, verdict {verdict(res, vlm) or 'aucun'}")
        if context:
            # La lecture libre de l'image par le modèle de langage n'est pas mesurée et s'est trompée dans les trois
            # tests de bout en bout (radio « normale » pour une tuberculose, côté inversé, cathéter inventé) :
            # le compte rendu est rédigé à partir des seuls résultats mesurés, sans l'image.
            messages = [{k: v for k, v in m.items() if k != "images"} for m in messages]
            system += context + ("\nTu n'as PAS accès à l'image : rédige uniquement à partir de ces résultats, sans "
                                 "ajouter d'observation visuelle (aucune autre lésion, aucun matériel, aucun autre côté). "
                                 "Les côtés cités dans la description du modèle de vision ne sont pas fiables : seule la "
                                 "synthèse de latéralité compte.")

        flagged = []
        if self.entity_check:
            status("Contrôle des noms cités…")
            flagged = self.unknown_entities(question)
            trace["unknown"] = [n for n, _ in flagged]

        # Pas d'extraits quand la question porte sur un nom inconnu (absent de la base par construction) : ils ne
        # servaient qu'à meubler (essai fictif présenté comme réel, doses d'autres médicaments proposées à la place)
        hits = []
        if self.kb and question.strip() and not flagged:
            status("Recherche dans la base documentaire…")
            # « Et chez l'enfant ? » ne contient pas le sujet : la question précédente complète la recherche et le tri
            search_query = question
            previous = [m["content"] for m in messages[:-1] if m.get("role") == "user" and isinstance(m.get("content"), str)]
            if previous and len(question.strip()) < FOLLOWUP_CHARS:
                search_query = previous[-1].strip() + "\n" + question.strip()
                trace["kb_followup"] = True
            try:
                hits = self.kb.search(search_query, self.kb_topk, self.kb_min_score)
                if hits:
                    found = len(hits)
                    hits = self.relevant(search_query, hits)
                    trace["kb_found"] = found
            except Exception:  # noqa: BLE001 - index absent ou Ollama indisponible : réponse sans la base
                hits = []
            trace["sources"] = [f"{h['doc']} p.{h['page']} ({h['score']})" for h in hits]
        if not hits and len(messages) > 1:
            system += NO_CITATION_RULE
        system_nokb, context_nokb = system, context
        if hits:
            extracts = kb_prompt(hits)
            system += extracts
            context += extracts  # la relecture vérifie aussi la fidélité aux extraits
        # Scores, études, syndromes, recommandations : consigne ferme. La sonde a repéré 12 noms fictifs sur 12, et
        # l'indice souple a laissé le modèle déclarer « bien réel » le score fictif Hammond-Lefèvre. Un faux positif
        # (règle PERC) ne coûte qu'une abstention prudente.
        firm = [n for n, t in flagged if t in FIRM_TYPES]
        soft = [n for n, t in flagged if t not in FIRM_TYPES]
        if firm:
            system += ("\n\nCONTRÔLE PRÉALABLE : tu n'as pas su décrire ces noms quand on te les a présentés seuls : "
                       + ", ".join(firm) + ". Pour chacun, écris « Je ne connais pas [nom]. » et n'en décris rien "
                       "(ni critères, ni items, ni résultats, ni usage). Ne propose AUCUN autre nom de score, d'étude, "
                       "de syndrome ou de critères à la place : dans les tests, ces suggestions contenaient des noms "
                       "inventés (« score de Hammond », « critères de Russell »). Dis seulement qu'il faut vérifier "
                       "l'orthographe et se référer aux recommandations officielles du domaine (ex. HAS, ESC).")
        if soft:
            # Médicaments et sigles : simple indice, la sonde ne reconnaît pas toujours un sigle réel (« ROR »)
            system += ("\n\nCONTRÔLE PRÉALABLE : ces noms pourraient ne pas exister : " + ", ".join(soft)
                       + ". Pour chacun : si tu ne peux pas décrire avec certitude ce qu'il désigne, écris "
                         "« Je ne connais pas [nom]. » sans rien inventer à son sujet (ni classe, ni dose, ni résultat). "
                         "S'il s'agit d'un nom réel que tu connais bien, réponds normalement.")

        status("Rédaction…")
        convo = [{"role": "system", "content": system}] + messages
        answer = self._call(convo)
        if hits and KB_REFUSAL.search(_norm(answer)) and ABSTAINED.search(_norm(answer)):
            # Extraits hors sujet : nouveau jet sans la base (hors base, aucun nom signalé ici : pas de contrôle ferme)
            status("Extraits hors sujet : réponse sans la base documentaire…")
            trace["kb_offtopic"], hits, system, context = True, [], system_nokb, context_nokb
            trace["sources"] = []
            convo = [{"role": "system", "content": system}] + messages
            answer = self._call(convo)
        truncated = self.truncated

        if self.verify:
            status("Relecture critique…")
            issues = self.review(question, answer, messages[-1].get("images"), context)
            trace["review_failed"] = issues is None
            trace["issues"] = issues or []
            if trace["issues"]:
                status(f"Correction de {len(trace['issues'])} point(s)…")
                issues = "\n".join(f"- [{i.get('type', '?')}] « {i.get('extrait', '')} » → {i.get('correction', '')}"
                                   for i in trace["issues"] if isinstance(i, dict))
                answer = self._call(convo + [
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": REVISE_PROMPT.format(issues=issues, answer=answer)}])
                truncated = self.truncated
        trace["truncated"] = truncated
        if not hits and CITES.search(answer):
            # Numéros sans extrait (repris d'un échange précédent) : retirés plutôt qu'un bloc Sources vide
            answer = re.sub(r" ?\[\d{1,2}\](?:[, ]+\[\d{1,2}\])*", "", answer)
            trace["stray_citations"] = True

        parts = trace["banners"] + blocks + [answer.strip()]
        if truncated:
            parts.append(BANNER_TRUNCATED)
        sources = kb_sources(answer, hits)
        if sources:
            parts.append(sources)
            try:
                flags = dose_misattributions(answer, hits, self.kb.page_text)
            except Exception:  # noqa: BLE001 - contrôle indisponible : pas d'alerte plutôt qu'une réponse perdue
                flags = []
            trace["dose_flags"] = [f"{d} absent de " + ", ".join(f"[{n}]" for n in m) for d, m in flags]
            if flags:
                items = " ; ".join(f"« {d} » ne figure pas dans " + ", ".join(
                    f"[{n}] ({doc_title(hits[n - 1]['doc'])}, page {hits[n - 1]['page']})" for n in m) for d, m in flags)
                parts.append("> 🔎 **Contrôle des citations** : " + items + ". Cette valeur vient d'une autre source, "
                             "d'un calcul ou des connaissances du modèle : vérifiez-la (notice, RCP, médecin ou pharmacien) "
                             "avant de l'utiliser.")
        # Filet déterministe : avec la base, une dose d'enfant tirée d'un tableau OMS a été donnée sans ce renvoi
        q = _norm(question)
        if CHILD_DOSE.search(q) and CHILD_WORDS.search(q) and not REFERRAL.search(_norm(answer)):
            parts.append(BANNER_CHILD_DOSE)
        # Filet de sécurité déterministe : un nom non reconnu dont la réponse parle sans dire qu'elle l'ignore
        described = [n for n in firm if not abstains_about(answer, n)]
        if described:
            parts.append("> ⚠️ **Contrôle automatique** : « " + " », « ".join(described) + " » n'a pas été reconnu par le "
                         "contrôle préalable des noms. Les informations ci-dessus à son sujet peuvent être inventées : "
                         "vérifiez dans une source officielle.")
        return "\n\n".join(parts), trace


# ------------------------------------------------------------------- Open WebUI pipe

# Blocs ajoutés par le code à une réponse : retirés de l'historique renvoyé au modèle (il les imitait, et un [1]
# d'une réponse précédente aurait été attribué aux nouveaux extraits par kb_sources)
APPENDED_PREFIXES = ("**📚 Sources (base documentaire locale)**", "> 🔎 **Contrôle des citations**",
                     "> ⚠️ **Contrôle automatique**", "> 💊 **Dose pour un enfant**", "> ✂️ **Réponse coupée**",
                     "> 🚨 **Si une personne est en danger", "> 💬 **Vous n'êtes pas seul", "> ⚠️ **Lecture d'image",
                     "> ⚠️ **L'analyse d'images")
FOOTER_MARK = "\n\n---\n*"


def clean_history(text):
    """Texte d'une réponse précédente sans les blocs ajoutés par le code (sources, encadrés, pied de réponse).
    Le bloc de lecture radiologique est gardé : il sert aux questions de suite."""
    if not isinstance(text, str):
        return text
    body = text.split(FOOTER_MARK)[0]
    # Image annotée (data:URL de 40 à 80 k caractères) : hors de l'historique, elle saturait le contexte du modèle
    body = re.sub(r"!\[([^\]]*)\]\(data:image/[^)]*\)", r"(image annotée : \1)", body)
    kept = [p for p in body.split("\n\n") if not p.lstrip().startswith(APPENDED_PREFIXES)]
    return "\n\n".join(kept).strip()


def _to_ollama(messages):
    """Convertit les messages OpenAI (texte + images data:URL) d'Open WebUI au format Ollama."""
    out = []
    for m in messages:
        if m.get("role") == "system":
            continue  # le profil fournit son propre prompt système
        content, images = m.get("content", ""), []
        if m.get("role") == "assistant":
            content = clean_history(content)
        if isinstance(content, list):
            texts = []
            for part in content:
                if part.get("type") == "text":
                    texts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url.startswith("data:") and "," in url:
                        images.append(url.split(",", 1)[1])
            content = "\n".join(texts)
        msg = {"role": m["role"], "content": content}
        if images:
            msg["images"] = images
        out.append(msg)
    return out


class Pipe:
    class Valves(BaseModel):
        OLLAMA_URL: str = Field(default="http://localhost:11434")
        MODEL: str = Field(default="qwen3.6:35b", description="Modèle principal (rédaction + relecture)")
        NUM_CTX: int = Field(default=16384)
        KEEP_ALIVE: str = Field(default="30m", description="Durée de maintien du modèle en mémoire")
        VERIFY: bool = Field(default=True, description="Relecture critique + correction")
        ENTITY_CHECK: bool = Field(default=True, description="Détection des noms inconnus avant rédaction")
        SHOW_TRACE: bool = Field(default=True, description="Afficher le résumé des contrôles sous la réponse")
        VISION_MODEL: str = Field(default="medgemma:4b", description="Modèle de vision médical (seconde lecture)")
        KB_DIR: str = Field(default=KB_DIR, description="Index de la base documentaire (knowledge/ingest.py ; vide = désactivée)")
        KB_TOPK: int = Field(default=8, description="Passages candidats soumis au tri (5 au plus sont gardés)")
        KB_MIN_SCORE: float = Field(default=KB_MIN_SCORE, description="Similarité minimale d'un extrait (bge-m3)")
        CXR_URL: str = Field(default="http://127.0.0.1:8765",
                             description="Lecteur spécialisé de radiographies thoraciques (vide = désactivé)")

    def __init__(self):
        self.type = "manifold"
        self.name = "MedAssist "
        self.valves = self.Valves()

    def pipes(self):
        return [{"id": "pro", "name": "Pro"}, {"id": "patient", "name": "Patient"}]

    async def pipe(self, body: dict, __event_emitter__=None, __task__=None):
        profile = "patient" if body.get("model", "").endswith(".patient") else "pro"
        messages = _to_ollama(body.get("messages", []))
        if not messages or messages[-1].get("role") != "user" or not (
                messages[-1].get("content", "").strip() or messages[-1].get("images")):
            return "⚠️ Aucune question reçue : écrivez votre question (ou joignez une image) puis envoyez."
        engine = Engine(self.valves.OLLAMA_URL, self.valves.MODEL, self.valves.NUM_CTX,
                        self.valves.KEEP_ALIVE, self.valves.VERIFY, self.valves.ENTITY_CHECK, self.valves.CXR_URL,
                        self.valves.VISION_MODEL, self.valves.KB_DIR, self.valves.KB_TOPK, self.valves.KB_MIN_SCORE)

        if __task__:  # titres, tags, suggestions : un simple appel, sans pipeline
            lang = {"role": "system", "content": "Rédige dans la langue de la conversation de l'utilisateur "
                                                 "(français par défaut), même si la consigne est en anglais."}
            return await asyncio.to_thread(engine._call, [lang] + messages)

        loop = asyncio.get_running_loop()

        def status(msg, done=False):
            if __event_emitter__:
                asyncio.run_coroutine_threadsafe(
                    __event_emitter__({"type": "status", "data": {"description": msg, "done": done}}), loop)

        try:
            text, trace = await asyncio.to_thread(engine.run, messages, profile, status)
        except Exception as e:  # noqa: BLE001 - toute erreur devient un message lisible, jamais une réponse vide
            status("Erreur", done=True)
            return "⚠️ " + explain_error(e, self.valves.MODEL, self.valves.VISION_MODEL, self.valves.OLLAMA_URL)

        checks = []
        if self.valves.ENTITY_CHECK:
            checks.append("noms non reconnus : " + (", ".join(trace["unknown"]) or "aucun"))
        if self.valves.VERIFY:
            checks.append("relecture : indisponible (erreur du modèle), réponse non relue" if trace.get("review_failed")
                          else f"relecture : {len(trace['issues'])} correction(s)")
        if trace["cxr"]:
            checks.append("lecteur radio : " + " | ".join(trace["cxr"]))
        if self.valves.KB_DIR:
            checks.append("base documentaire : extraits hors sujet, réponse sans la base" if trace.get("kb_offtopic")
                          else f"base documentaire : {len(trace['sources'])} extrait(s) pertinent(s)")
        if trace.get("dose_flags"):
            checks.append(f"citations : {len(trace['dose_flags'])} dose(s) absente(s) de la source citée")
        if trace.get("truncated"):
            checks.append("réponse coupée (longueur maximale)")
        status("Vérifié · " + " · ".join(checks) if checks else "Terminé", done=True)

        footer = ("Aide à la décision : ne remplace pas le jugement clinique ni les sources officielles (RCP, recommandations)."
                  if profile == "pro" else
                  "Information générale : ne remplace pas l'avis d'un médecin ou d'un pharmacien.")
        if self.valves.SHOW_TRACE and checks:
            footer = "Contrôles : " + " · ".join(checks) + ". " + footer
        return f"{text}\n\n---\n*{footer}*"
