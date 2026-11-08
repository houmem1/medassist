# MCUCXR_0289_1.png (pro) — 244 s

Question : Homme de 45 ans, toux chronique et sueurs nocturnes depuis 6 semaines. Qu'en pensez-vous ?

```
    0s  Identification du type d'image…
    2s  Lecteur spécialisé de radiographie thoracique…
   16s  Latéralité : lecture visuelle…
   50s  Seconde lecture par le modèle de vision médical…
   60s  Contrôle des noms cités…
   90s  Rédaction…
  154s  Relecture critique…
  174s  Correction de 2 point(s)…
```

Trace : {'banners': ["> ⚠️ **Lecture d'image automatique : second avis seulement.** Mesurée uniquement sur des radiographies thoraciques de face (performances sous le tableau de lecture) ; aucune validation pour les autres images. Confrontez chaque élément à l'image et au compte rendu d'un radiologue."], 'unknown': [], 'issues': [{'type': 'erreur_factuelle', 'extrait': 'Appel SAMU (190 en Tunisie / 15 ou 112 en France)', 'correction': "Le numéro d'urgence standard en France est le 15 (SAMU) ou le 112. Le numéro 190 n'est pas un numéro d'urgence médical standard reconnu internationalement ou en France pour le SAMU (il peut s'agir d'une confusion avec d'autres services ou pays). Il faut utiliser les numéros standards : 15, 112 ou 114."}, {'type': 'erreur_factuelle', 'extrait': 'infiltrat sus-hilaire droit fréquent', 'correction': "La tuberculose primaire ou réactivation touche préférentiellement les segments apicaux et postérieurs des lobes supérieurs, ainsi que les segments apicaux des lobes inférieurs. Le terme 'sus-hilaire' est imprécis et potentiellement trompeur car la localisation typique est plus haute (apicale). De plus, l'anomalie signalée par le modèle est un 'infiltrat' dans l'étage supérieur, sans précision hilaire spécifique."}], 'cxr': ['adulte, verdict anormale']}

---

> ⚠️ **Lecture d'image automatique : second avis seulement.** Mesurée uniquement sur des radiographies thoraciques de face (performances sous le tableau de lecture) ; aucune validation pour les autres images. Confrontez chaque élément à l'image et au compte rendu d'un radiologue.

#### 🩻 Radiographie thoracique de face : double lecture automatique (adulte)
| Lecteur | Verdict |
|---|---|
| Spécialiste (TorchXRayVision) | pas de verdict : seuils non calibrés pour ce site (localisation et classement seulement) |
| Modèle de vision médical (medgemma:4b) | **anormale** (confiance 95 %) |

Verdict retenu (un seul lecteur) : radiographie **anormale**.

**Côté de l'anomalie principale (patient)** : **droit** (calcul et lecture visuelle concordants)

**Anomalies les plus suspectes selon le spécialiste (classement relatif, non calibré)**
| Anomalie | Score / seuil | Zone principale |
|---|---|---|
| fracture | 0.43 / 0.38 | bilatéral ou indéterminé, étage moyen |
| infiltrat | 0.56 / 0.49 | côté droit du patient, étage supérieur |

![Zones qui ont le plus influencé le lecteur (Fracture)](image annotée)
<sub>Mesures (adulte, dépistage de la tuberculose, 138 radios Montgomery) : MedGemma 4B sensibilité 88 % / spécificité 92 % (présence de ces radios dans son entraînement non vérifiable) ; côté atteint juste 17/17 quand calcul et lecture visuelle concordent. Spécialiste sans verdict faute de calibration locale (radiology/calibrate_local.py). Ce n'est pas un niveau de radiologue.</sub>

**Réponse directe :**
Cette association de symptômes (toux chronique > 3 semaines + sueurs nocturnes) chez un homme de 45 ans nécessite une investigation urgente pour éliminer une pathologie infectieuse chronique (notamment tuberculose), néoplasique ou inflammatoire systémique. La radiographie thoracique suggère des anomalies qui doivent être corrélées cliniquement.

**Analyse détaillée basée sur les données fournies :**

### 1. Contexte clinique
*   **Patient :** Homme, 45 ans.
*   **Symptômes :** Toux chronique (depuis 6 semaines) et sueurs nocturnes.
*   **Signes de gravité potentiels :** Perte de poids non mentionnée mais à rechercher, fièvre, dyspnée, hémoptysie.

### 2. Interprétation des résultats d'imagerie (selon les données fournies)
*Note : Cette analyse repose exclusivement sur le texte fourni dans la demande. Elle ne remplace pas l'expertise d'un radiologue.*

*   **Verdict retenu :** Radiographie anormale.
*   **Latéralité :** Côté droit (synthèse calculée et lecture visuelle concordantes).
*   **Anomalies suspectées par le modèle spécialisé (à confirmer) :**
    *   **Infiltrat :** Suspecté côté droit, étage supérieur (score 0.56 > seuil 0.49). Cela pourrait correspondre à une pneumopathie, une tuberculose ou une néoplasie.
    *   **Fracture :** Suspectée (bilatéral ou indéterminé, étage moyen) (score 0.43 > seuil 0.38). À vérifier cliniquement (douleur thoracique, antécédent traumatique).

*Note : La description du modèle de vision "medgemma" indiquant une image normale est contredite par le verdict retenu ("radiographie anormale") et les scores d'anomalies. Nous nous basons donc sur le verdict "anormal" et la latéralité "droite".*

### 3. Diagnostic différentiel (classé par probabilité)

| Hypothèse | Arguments en faveur | Examens complémentaires utiles |
| :--- | :--- | :--- |
| **1. Tuberculose pulmonaire** | Toux chronique > 3 semaines, sueurs nocturnes, atteinte préférentielle des segments apicaux/postérieurs des lobes supérieurs (étage supérieur). Facteurs de risque (voyages, immunodépression). | Expectorations (BAAR x3), Test IGRA/PPD, Scanner thoracique. |
| **2. Néoplasie bronchopulmonaire** | Toux chronique, sueurs nocturnes (syndrome paraneoplastic ou fièvre tumorale), âge > 40 ans. Tabagisme ? | Scanner thoracique avec injection, Biopsie si lésion visible. |
| **3. Pneumopathie atypique ou infectieuse chronique** | Infiltrat pulmonaire suspecté. Mycobactéries non tuberculeuses, champignons. | Hémocultures, sérologies, scanner thoracique. |
| **4. Pathologie inflammatoire systémique** | Sarcoidose, vascularite (GPA). Sueurs nocturnes, atteinte pulmonaire. | Bilan inflammatoire (CRP, VS), ANCA, ACE, scanner thoracique. |
| **5. Autres causes de sueurs nocturnes** | Hyperthyroïdie, lymphome (maladie de Hodgkin), apnée du sommeil (si ronflement). | TSH, bilan sanguin complet, polygraphie ventilatoire. |

### 4. Conduite à tenir

1.  **Urgence :**
    *   Si signes de détresse respiratoire, hémoptysie massive ou état septique : **Appel SAMU (15 en France / 112 en Europe)**.
    *   Isolement respiratoire si suspicion de tuberculose active (en attendant les résultats).

2.  **Examens complémentaires immédiats :**
    *   **Scanner thoracique avec injection** : Pour caractériser l'infiltrat suspecté côté droit, rechercher des adénopathies, des nodules ou une fracture non visible en radiographie standard.
    *   **Bilan sanguin complet** : NFS, CRP, VS, fonction hépatique et rénale, TSH.
    *   **Recherche de tuberculose** : Expectorations pour BAAR (bacillifacide) x3, Test IGRA (QuantiFERON-TB Gold).
    *   **Sérologies** : Selon l'épidémiologie locale (VIH, hépatites, etc.).

3.  **Suivi :**
    *   Consultation pneumologie en urgence ou sous 48-72h.
    *   Relecture de la radiographie par un radiologue pour confirmer la présence et la nature exacte des anomalies (infiltrat, fracture).

**Informations manquantes importantes [à compléter] :**
*   Antécédents médicaux (tabac, immunodépression, voyages, contact avec TB).
*   Signes associés (fièvre, perte de poids, douleur thoracique, hémoptysie).
*   Résultats de l'examen clinique (auscultation, palpation ganglionnaire).

**Conclusion :**
La combinaison de la toux chronique, des sueurs nocturnes et d'une radiographie thoracique anormale côté droit impose une investigation approfondie pour éliminer une tuberculose ou un néoplasme. La relecture par un radiologue est indispensable pour confirmer les anomalies suspectées par l'analyse automatique.
