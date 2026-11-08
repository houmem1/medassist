# MCUCXR_0001_0.png (pro) — 189 s

Question : Radio de dépistage avant embauche, adulte asymptomatique. Votre lecture ?

```
    0s  Identification du type d'image…
   10s  Lecteur spécialisé de radiographie thoracique…
   23s  Latéralité : lecture visuelle…
   55s  Seconde lecture par le modèle de vision médical…
   63s  Contrôle des noms cités…
   93s  Rédaction…
  132s  Relecture critique…
  151s  Correction de 2 point(s)…
```

Trace : {'banners': ["> ⚠️ **Lecture d'image automatique : second avis seulement.** Mesurée uniquement sur des radiographies thoraciques de face (performances sous le tableau de lecture) ; aucune validation pour les autres images. Confrontez chaque élément à l'image et au compte rendu d'un radiologue."], 'unknown': [], 'issues': [{'type': 'erreur_factuelle', 'extrait': "Je ne peux pas effectuer de lecture visuelle car je n'ai pas accès à l'image radiographique.", 'correction': "La consigne impose explicitement : 'n'écris pas que tu n'as pas accès à l'image'. La réponse doit être présentée comme la synthèse des lectures automatiques fournies dans le texte, sans mentionner l'absence d'accès visuel direct."}, {'type': 'erreur_factuelle', 'extrait': 'Lecteur spécialisé : pas de verdict (seuils non calibrés pour ce site) ; anomalies les plus suspectes dans son classement relatif : épanchement pleural (score 0.39 pour un seuil de 0.11, côté gauche du patient, étage moyen); condensation (consolidation) (score 0.51 pour un seuil de 0.27, côté gauche du patient, étage moyen).', 'correction': "La réponse attribue incorrectement le verdict 'Radiographie anormale' et la confiance de 90% au 'modèle de vision médical' comme s'il s'agissait d'une lecture indépendante validée, alors que les données indiquent que le 'Lecteur spécialisé' n'a pas donné de verdict. De plus, elle présente les scores comme des résultats factuels de l'examen plutôt que comme des suspicions algorithmiques à confronter à la clinique, bien que cela soit partiellement corrigé par les mises en garde, la structure impose de reprendre fidèlement le verdict retenu ('radiographie anormale') sans ambiguïté sur sa source (synthèse calculée)."}], 'cxr': ['adulte, verdict anormale']}

---

> ⚠️ **Lecture d'image automatique : second avis seulement.** Mesurée uniquement sur des radiographies thoraciques de face (performances sous le tableau de lecture) ; aucune validation pour les autres images. Confrontez chaque élément à l'image et au compte rendu d'un radiologue.

#### 🩻 Radiographie thoracique de face : double lecture automatique (adulte)
| Lecteur | Verdict |
|---|---|
| Spécialiste (TorchXRayVision) | pas de verdict : seuils non calibrés pour ce site (localisation et classement seulement) |
| Modèle de vision médical (medgemma:4b) | **anormale** (confiance 90 %) |

Verdict retenu (un seul lecteur) : radiographie **anormale**.

**Côté de l'anomalie principale (patient)** : **gauche** (calcul et lecture visuelle concordants)

**Anomalies les plus suspectes selon le spécialiste (classement relatif, non calibré)**
| Anomalie | Score / seuil | Zone principale |
|---|---|---|
| épanchement pleural | 0.39 / 0.11 | côté gauche du patient, étage moyen |
| condensation (consolidation) | 0.51 / 0.27 | côté gauche du patient, étage moyen |

![Zones qui ont le plus influencé le lecteur (Effusion)](image annotée)
<sub>Mesures (adulte, dépistage de la tuberculose, 138 radios Montgomery) : MedGemma 4B sensibilité 88 % / spécificité 92 % (présence de ces radios dans son entraînement non vérifiable) ; côté atteint juste 17/17 quand calcul et lecture visuelle concordent. Spécialiste sans verdict faute de calibration locale (radiology/calibrate_local.py). Ce n'est pas un niveau de radiologue.</sub>

**Réponse directe :**
La synthèse des lectures automatiques indique une **radiographie anormale**, avec des suspicions d'épanchement pleural et de condensation localisés à l'étage moyen du côté gauche. Ces résultats algorithmiques doivent être impérativement confrontés à la clinique et validés par un radiologue avant toute décision médicale ou administrative.

**Note importante :** Cette analyse repose exclusivement sur les données fournies par les modèles d'intelligence artificielle. Elle ne constitue pas un diagnostic médical établi mais une aide à la décision nécessitant une interprétation humaine experte.

---

### Synthèse des lectures automatiques fournies

**1. Technique et limites**
*   **Source des données :** Analyse croisée entre un lecteur spécialisé (scores de probabilité) et un modèle de vision médical (confiance globale).
*   **Limites :** Les scores fournis reflètent la probabilité algorithmique d'anomalie, non une certitude pathologique. La latéralité doit être confirmée par les marqueurs radiologiques standards (bouton aortique à gauche du patient, donc à droite de l'image en convention).

**2. Résultats de l'analyse automatique**
*   **Verdict retenu :** Radiographie anormale (Confiance 90 % selon la synthèse calculée).
*   **Latéralité :** Côté **gauche** du patient (synthèse calculée et lecture visuelle concordantes).
*   **Anomalies suspectes (classement relatif par le lecteur spécialisé) :**
    *   **Condensation (Consolidation) :** Score 0.51 (seuil de 0.27). Étage moyen, côté gauche.
    *   **Épanchement pleural :** Score 0.39 (seuil de 0.11). Étage moyen, côté gauche.

**3. Conclusion (Hypothèses classées par probabilité)**
*Attention : Il s'agit d'hypothèses issues d'une lecture automatique, à confronter à la clinique.*
1.  **Pathologie thoracique gauche :** La combinaison de suspicions de condensation et d'épanchement pleural du côté gauche évoque principalement une pathologie inflammatoire ou infectieuse (ex: pneumonie avec épanchement parapneumonique), mais aussi des causes non infectieuses (néoplasie, embolie pulmonaire avec infarctus).
2.  **Faux positif / Artefact :** Dans un contexte asymptomatique, la probabilité d'artefact (pli cutané, superposition osseuse) ou de variante anatomique bénigne reste significative et doit être écartée par l'expert.

**4. Conduite à tenir**
1.  **Relecture radiologique obligatoire :** Transmission du cas à un radiologue pour confirmation visuelle, vérification de la latéralité et exclusion des artéfacts. C'est le seul moyen d'établir un diagnostic fiable.
2.  **Évaluation clinique :** Interrogatoire approfondi (antécédents, symptômes subtils) et examen physique pulmonaire du patient asymptomatique déclaré.
3.  **Décision pré-embauche :** Suspendre toute décision d'aptitude jusqu'à réception du compte rendu radiologique officiel. Si la relecture confirme l'anomalie, envisager des examens complémentaires (scanner thoracique) selon le jugement du radiologue.

**Sécurité et Éthique :**
*   Anonymiser les données patient lors de tout transfert d'information.
*   Cette réponse est une aide à la documentation basée sur des données algorithmiques ; elle ne remplace ni le jugement clinique, ni l'expertise radiologique.
