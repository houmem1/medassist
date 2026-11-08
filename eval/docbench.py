"""Questions dont la réponse figure dans la base documentaire (réponses attendues relevées dans le texte des PDF).

Sources : HAS, synthèse « Choix et durées d'antibiothérapie », mise à jour décembre 2024 (pages 1 à 5) ;
OMS, tuberculose module 5 enfants et adolescents (2022) ; OMS, AWaRe antibiotic book (2022).
Même format que medbench.py : all = motifs tous requis, none = motifs interdits (texte sans accents, minuscules).
"""
ITEMS = [
    # --- HAS 2024 ---
    dict(id="d01", cat="has", q="Quel antibiotique en première intention pour une cystite aiguë simple chez la femme, et pour quelle durée ?",
         all=[r"fosfomycine", r"(prise|dose) unique"]),
    dict(id="d02", cat="has", q="Cystite aiguë à risque de complication : quel traitement probabiliste et quelle durée ?",
         all=[r"nitrofurantoine", r"\b7 jours"]),
    dict(id="d03", cat="has", q="Quelle est la durée totale d'antibiothérapie d'une pyélonéphrite aiguë simple de la femme ?",
         all=[r"\b10 jours"]),
    dict(id="d04", cat="has", q="Angine de l'adulte avec score de Mac Isaac ≥ 2 et TDR positif : quel antibiotique et quelle durée ?",
         all=[r"amoxicilline", r"\b6 jours"]),
    dict(id="d05", cat="has", q="Otite moyenne aiguë purulente chez un enfant de 4 ans avec symptômes modérés : faut-il des antibiotiques ?",
         all=[r"pas d.antibiotique|sans antibiotique|abstention|ne pas (prescrire|traiter)"
              r"|pas recommande d.(administrer|prescrire)[^.]{0,20}antibiotique"
              r"|pas necessaire de prescrire[^.]{0,20}antibiotique", r"48"]),
    dict(id="d06", cat="has", q="Otite moyenne aiguë purulente chez un nourrisson de 18 mois : antibiotique et durée ?",
         all=[r"amoxicilline", r"\b10 jours"]),
    dict(id="d07", cat="has", q="Exacerbation de BPCO sans facteur de risque d'échec ou de complication : quel antibiotique et combien de jours ?",
         all=[r"amoxicilline", r"\b5 jours"], none=[r"amoxicilline.acide clavulanique en (premiere|1re) intention"]),
    dict(id="d08", cat="has", q="Pneumonie aiguë communautaire sans gravité chez l'adulte, suspicion de pneumocoque : quelle durée de traitement ?",
         all=[r"\b7 jours", r"\b(3|5) jours", r"stabilite"]),
    dict(id="d09", cat="has", q="Coqueluche de l'adulte : durée du traitement par azithromycine ?",
         all=[r"azithromycine", r"\b3 jours"]),
    dict(id="d10", cat="has", q="Infection à Helicobacter pylori de l'adulte : quel traitement probabiliste de première intention et quelle durée ?",
         all=[r"\b14 jours", r"metronidazole", r"clarithromycine"]),
    dict(id="d11", cat="has", q="Urétrite non compliquée : quel traitement antibiotique probabiliste ?",
         all=[r"ceftriaxone", r"doxycycline", r"\b7 jours"]),
    dict(id="d12", cat="has", q="Diverticulite aiguë sigmoïdienne non compliquée sans signe de gravité : faut-il des antibiotiques ?",
         all=[r"(pas d.|sans )antibiotique|symptomatique"]),
    dict(id="d13", cat="has", q="Abcès cutané de l'adulte : quel antibiotique après drainage et quelle durée ?",
         all=[r"clindamycine|pristinamycine", r"\b5 jours", r"drainage|incision"]),
    dict(id="d14", cat="has", q="Dermohypodermite bactérienne non nécrosante non compliquée de l'adulte : antibiotique et durée ?",
         all=[r"amoxicilline", r"\b7 jours"]),
    dict(id="d15", cat="has", q="Cystite aiguë de la femme enceinte : quel traitement probabiliste ?",
         all=[r"fosfomycine"]),
    dict(id="d16", cat="has", q="Antibioprophylaxie des cystites récidivantes par triméthoprime : quelle dose ?",
         all=[r"150 ?mg"]),
    dict(id="d17", cat="has", q="Infection génitale haute non compliquée : quel traitement antibiotique probabiliste ?",
         all=[r"ceftriaxone", r"doxycycline", r"metronidazole", r"\b10 jours"]),
    # --- OMS tuberculose de l'enfant (module 5, 2022) ---
    dict(id="t01", cat="oms_tb", q="Selon l'OMS, quelle durée de traitement pour une tuberculose non sévère pharmacosensible chez un enfant de 5 ans ?",
         all=[r"\b4 mois|quatre mois", r"2hrz"]),
    dict(id="t02", cat="oms_tb", q="Selon l'OMS, enfant atteint de malnutrition aiguë sévère et de tuberculose non sévère : schéma de 4 ou de 6 mois ?",
         all=[r"\b6 mois|six mois"]),
    # --- OMS AWaRe (2022) ---
    dict(id="a01", cat="oms_aware", q="Selon le livre AWaRe de l'OMS, quelle durée de traitement pour une pneumonie communautaire légère de l'adulte, et quel antibiotique ?",
         all=[r"\b5 jours|5 days", r"amoxicilline|amoxicillin"]),
    dict(id="a02", cat="oms_aware", q="Selon le livre AWaRe de l'OMS, faut-il des antibiotiques dans la plupart des pharyngites légères ?",
         all=[r"(pas|non) necessaire|pas d.antibiotique|symptomatique"]),
]
