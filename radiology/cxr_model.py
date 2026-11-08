"""Lecteur spécialisé de radiographies thoraciques (TorchXRayVision, DenseNet121 « all »).

Entraîné sur NIH, PadChest, CheXpert, MIMIC, Google, OpenI et RSNA : à évaluer sur d'autres données.
Les seuils standard de TorchXRayVision (0,5) ne tiennent pas hors de ses données d'entraînement : on utilise
ceux de calibration.json, fixés par population (eval/cxr_calibrate.py).
À lancer avec le Python de <dossier d'installation>\\cxr-venv (voir README).
"""
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import torch
import torchvision
import torchxrayvision as xrv
from PIL import Image
from scipy.ndimage import gaussian_filter

WEIGHTS = "densenet121-res224-all"
MAX_PIXELS = 60_000_000  # au-delà, image refusée (une radio fait au plus ~5000 × 5000 px)
DEEP_MODES = ("I;16", "I;16B", "I;16L", "I;16N", "I", "F")
CALIBRATION = json.loads((Path(__file__).resolve().parent / "calibration.json").read_text(encoding="utf-8"))

FR = {
    "Atelectasis": "atélectasie", "Consolidation": "condensation (consolidation)", "Infiltration": "infiltrat",
    "Pneumothorax": "pneumothorax", "Edema": "œdème pulmonaire", "Emphysema": "emphysème", "Fibrosis": "fibrose",
    "Effusion": "épanchement pleural", "Pneumonia": "pneumonie", "Pleural_Thickening": "épaississement pleural",
    "Cardiomegaly": "cardiomégalie", "Nodule": "nodule", "Mass": "masse", "Hernia": "hernie (hiatale)",
    "Lung Lesion": "lésion pulmonaire", "Fracture": "fracture", "Lung Opacity": "opacité pulmonaire",
    "Enlarged Cardiomediastinum": "élargissement cardiomédiastinal",
}
# Anomalies sans latéralité utile (centrales ou diffuses par nature)
NO_SIDE = {"Cardiomegaly", "Enlarged Cardiomediastinum", "Hernia", "Edema", "Emphysema"}


class CXRReader:
    def __init__(self):
        self.model = xrv.models.DenseNet(weights=WEIGHTS).eval()
        self.labels = [p for p in self.model.pathologies if p]
        self.index = {p: i for i, p in enumerate(self.model.pathologies) if p}
        self.transform = torchvision.transforms.Compose([xrv.datasets.XRayCenterCrop(),
                                                         xrv.datasets.XRayResizer(224)])
        self._saliency_cache = {}  # (empreinte de l'image, anomalie) -> carte ; localize() et overlay_jpeg() la partagent

    def tensor(self, image_bytes):
        pil = Image.open(io.BytesIO(image_bytes))
        if pil.width * pil.height > MAX_PIXELS:
            raise ValueError(f"image trop grande ({pil.width}×{pil.height} px)")
        if pil.mode in DEEP_MODES:
            # Radios 12/16 bits (PNG export DICOM) : convert("L") les écrête à blanc ; échelle sur les centiles
            arr = np.asarray(pil, dtype=np.float32)
            lo, hi = np.percentile(arr, (0.5, 99.5))
            img = np.clip((arr - lo) / max(hi - lo, 1e-6), 0, 1) * 255
        else:
            img = np.asarray(pil.convert("L"), dtype=np.float32)
        img = xrv.datasets.normalize(img, 255)[None, ...]
        return torch.from_numpy(self.transform(img)).unsqueeze(0)

    def predict(self, image_bytes):
        with torch.no_grad():
            out = self.model(self.tensor(image_bytes))[0]
        return {p: float(out[i]) for p, i in self.index.items()}

    def saliency(self, image_bytes, pathology):
        """Carte de saillance lissée (gradient de la sortie par rapport aux pixels), somme = 1.
        Calculée une fois par (image, anomalie) : le côté et l'image annotée en ont besoin tous les deux."""
        key = (hashlib.sha1(image_bytes).hexdigest(), pathology)
        if key not in self._saliency_cache:
            if len(self._saliency_cache) >= 32:
                self._saliency_cache.clear()
            x = self.tensor(image_bytes).requires_grad_(True)
            self.model.zero_grad()
            self.model(x)[0, self.index[pathology]].backward()
            sal = gaussian_filter(x.grad[0, 0].abs().numpy(), sigma=6)
            self._saliency_cache[key] = (x.detach()[0, 0].numpy(), sal / (sal.sum() + 1e-12))
        return self._saliency_cache[key]

    def overlay_jpeg(self, image_bytes, pathology, size=448):
        """Radio 224 px agrandie, avec la carte de saillance en rouge : où le modèle a regardé."""
        img, sal = self.saliency(image_bytes, pathology)
        gray = (img - img.min()) / (np.ptp(img) + 1e-6)
        heat = sal / (sal.max() + 1e-12)
        rgb = np.stack([gray] * 3, axis=-1)
        alpha = np.clip(heat * 1.2, 0, 0.7)[..., None]
        rgb = rgb * (1 - alpha) + np.array([1.0, 0.15, 0.1]) * alpha
        pil = Image.fromarray((rgb * 255).astype(np.uint8)).resize((size, size), Image.BILINEAR)
        buf = io.BytesIO()
        pil.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def localize(self, image_bytes, pathology):
        """Côté du PATIENT et étage prédominants d'après la carte de saillance.
        Hypothèse : cliché de face en convention radiologique (droite du patient = gauche de l'image)."""
        _, sal = self.saliency(image_bytes, pathology)
        h, w = sal.shape
        image_left = sal[:, : w // 2].sum()
        if pathology in NO_SIDE:
            side = None
        elif image_left > 0.6:
            side = "droit"   # moitié gauche de l'image
        elif image_left < 0.4:
            side = "gauche"
        else:
            side = "bilatéral ou indéterminé"
        thirds = [sal[: h // 3].sum(), sal[h // 3: 2 * h // 3].sum(), sal[2 * h // 3:].sum()]
        level = ["supérieur", "moyen", "inférieur"][int(np.argmax(thirds))]
        return {"cote_patient": side, "etage": level, "part_gauche_image": round(float(image_left), 2)}

    def analyze(self, image_bytes, population="adulte", max_findings=4):
        """population : « enfant » ou « adulte ».

        Verdict normal/anormal seulement si les seuils sont validés pour ce contexte : enfant (Kermany), ou adulte
        avec une calibration locale (calibrate_local.py). Les seuils adultes de Shenzhen ne tiennent pas dans un
        autre hôpital (Montgomery : 99 % de fausses alertes) : on ne garde alors qu'un classement relatif."""
        name = "local" if population == "adulte" and "local" in CALIBRATION else population
        cal = CALIBRATION[name]
        validated = name in ("enfant", "local")
        probs = self.predict(image_bytes)
        # Seuil nul ou anomalie absente du modèle (calibration éditée à la main) : ignorés plutôt qu'une division par zéro
        thresholds = {p: t for p, t in cal["seuils_anomalies"].items() if p in probs and t > 0}
        # Score rapporté au seuil de chaque anomalie (> 1 = au-dessus) ; anomalies à sortie quasi nulle exclues
        ratio = {p: probs[p] / t for p, t in thresholds.items()}
        ranked = sorted(ratio, key=lambda p: -ratio[p])
        shown = [p for p in ranked if ratio[p] >= 1][:max_findings] if validated else ranked[:2]
        findings = [{"anomalie": p, "nom_fr": FR.get(p, p), "probabilite": round(probs[p], 2),
                     "seuil": round(thresholds[p], 2), **self.localize(image_bytes, p)} for p in shown]
        keys = probs.keys() if cal["score_global"] == "toutes" else [k for k in cal["score_global"] if k in probs]
        global_score = max(probs[k] for k in keys) if keys else 0.0
        return {"modele": WEIGHTS, "population": population, "calibration": name, "verdict_valide": validated,
                "anormale": global_score >= cal["seuil_global"] if validated else None,
                "score_global": round(global_score, 2), "seuil_global": round(cal["seuil_global"], 2),
                "anomalies": findings,
                "probabilites": {p: round(v, 3) for p, v in sorted(probs.items(), key=lambda kv: -kv[1])}}
