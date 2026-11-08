r"""Génère le logo et les icônes MedAssist (dossier openwebui/static), à partir de primitives : aucune image externe.

  %USERPROFILE%\open-webui\venv\Scripts\python.exe openwebui\make_branding.py

Produit les fichiers qu'Open WebUI lit dans son dossier statique (favicon, logo, splash, icônes PWA) et deux
avatars (Pro, Patient). install.py copie le dossier statique d'Open WebUI puis ces fichiers par-dessus.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "static"
S = 2048  # rendu sur-échantillonné, réduit ensuite (anticrénelage)

PALETTES = {
    "pro": ((15, 139, 141), (9, 78, 104)),       # sarcelle -> bleu profond
    "patient": ((37, 99, 235), (30, 58, 138)),   # bleu -> indigo
}
INK = (11, 36, 61)  # tracé ECG


def gradient(c1, c2, size, mask):
    t = (np.add.outer(np.linspace(0, 1, size), np.linspace(0, 1, size)) / 2)[..., None]
    rgb = (np.array(c1) * (1 - t) + np.array(c2) * t).astype(np.uint8)
    img = Image.fromarray(rgb, "RGB").convert("RGBA")
    img.putalpha(mask)
    return img


def mark(palette, size=1024, background=True):
    c1, c2 = PALETTES[palette]
    mask = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(mask)
    if background:
        d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(0.225 * S), fill=255)
    img = gradient(c1, c2, S, mask) if background else Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Croix blanche aux coins arrondis
    w, l, r = 0.25 * S, 0.62 * S, 0.055 * S
    cx = cy = S / 2
    for box in ((cx - l / 2, cy - w / 2, cx + l / 2, cy + w / 2), (cx - w / 2, cy - l / 2, cx + w / 2, cy + l / 2)):
        d.rounded_rectangle(box, radius=int(r), fill=(255, 255, 255, 255))
    # Tracé ECG (P, QRS, T) sur toute la largeur de la croix
    pts = [(0.19, 0.50), (0.33, 0.50), (0.37, 0.455), (0.41, 0.50), (0.445, 0.50), (0.465, 0.545),
           (0.495, 0.30), (0.525, 0.68), (0.55, 0.50), (0.59, 0.50), (0.635, 0.445), (0.68, 0.50), (0.81, 0.50)]
    pts = [(x * S, y * S) for x, y in pts]
    ink = INK if background else (c1 if palette == "pro" else c2)
    width = int(0.042 * S)
    d.line(pts, fill=ink + (255,), width=width, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=ink + (255,))
    return img.resize((size, size), Image.LANCZOS)


def svg():
    c1, c2 = PALETTES["pro"]
    ink = "#%02x%02x%02x" % INK
    pts = " ".join(f"{x * 500:.1f},{y * 500:.1f}" for x, y in
                   [(0.19, 0.50), (0.33, 0.50), (0.37, 0.455), (0.41, 0.50), (0.445, 0.50), (0.465, 0.545),
                    (0.495, 0.30), (0.525, 0.68), (0.55, 0.50), (0.59, 0.50), (0.635, 0.445), (0.68, 0.50), (0.81, 0.50)])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#{c1[0]:02x}{c1[1]:02x}{c1[2]:02x}"/><stop offset="1" stop-color="#{c2[0]:02x}{c2[1]:02x}{c2[2]:02x}"/>
</linearGradient></defs>
<rect width="500" height="500" rx="112" fill="url(#g)"/>
<rect x="95" y="187.5" width="310" height="125" rx="27" fill="#fff"/>
<rect x="187.5" y="95" width="125" height="310" rx="27" fill="#fff"/>
<polyline points="{pts}" fill="none" stroke="{ink}" stroke-width="21" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def main():
    OUT.mkdir(exist_ok=True)
    logo = mark("pro", 1024)
    for name, size in (("favicon.png", 512), ("logo.png", 500), ("splash.png", 500), ("splash-dark.png", 500),
                       ("apple-touch-icon.png", 180), ("favicon-96x96.png", 96),
                       ("web-app-manifest-192x192.png", 192), ("web-app-manifest-512x512.png", 512)):
        logo.resize((size, size), Image.LANCZOS).save(OUT / name)
    logo.resize((256, 256), Image.LANCZOS).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    (OUT / "favicon.svg").write_text(svg(), encoding="utf-8")
    mark("pro", 256).save(OUT / "medassist_pro.png")
    mark("patient", 256).save(OUT / "medassist_patient.png")
    print(f"{len(list(OUT.iterdir()))} fichiers dans {OUT}")


if __name__ == "__main__":
    main()
