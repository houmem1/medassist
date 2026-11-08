"""Génère une radiographie thoracique SYNTHÉTIQUE (schéma, pas un vrai patient) pour tester la vision.

Opacité volontaire au lobe inférieur droit (à gauche de l'image, convention radiologique).
Usage : python make_test_image.py [sortie.png]
"""
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

out = sys.argv[1] if len(sys.argv) > 1 else "synthetic_cxr.png"
W, H = 768, 896
img = Image.new("L", (W, H), 25)
d = ImageDraw.Draw(img)

# Tissus mous du thorax
d.ellipse([40, 60, W - 40, H + 200], fill=150)
# Champs pulmonaires (sombres)
d.ellipse([110, 130, 370, 760], fill=45)
d.ellipse([400, 130, 660, 760], fill=45)
# Médiastin + silhouette cardiaque (débordant vers la gauche du patient = droite de l'image)
d.rectangle([340, 90, 430, 520], fill=200)
d.ellipse([310, 430, 600, 740], fill=205)
# Coupoles diaphragmatiques
d.chord([100, 680, 380, 860], 180, 360, fill=170)
d.chord([390, 700, 670, 880], 180, 360, fill=170)
# Côtes
for i in range(9):
    y = 170 + i * 62
    d.arc([90, y - 40, 385, y + 70], 200, 340, fill=185, width=9)
    d.arc([385, y - 40, 680, y + 70], 200, 340, fill=185, width=9)
# Clavicules
d.line([140, 135, 350, 165], fill=210, width=14)
d.line([420, 165, 630, 135], fill=210, width=14)

img = img.filter(ImageFilter.GaussianBlur(4))

# Opacité de type consolidation, lobe inférieur droit
blob = Image.new("L", (W, H), 0)
ImageDraw.Draw(blob).ellipse([150, 500, 330, 690], fill=255)
blob = blob.filter(ImageFilter.GaussianBlur(25))
arr = np.array(img, dtype=np.float32) + np.array(blob, dtype=np.float32) * 0.45

# Bruit de film
arr += np.random.default_rng(0).normal(0, 6, arr.shape)
Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(out)
print(out)
