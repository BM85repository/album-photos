"""Données d'essai pour les tests automatiques : un petit « disque de photos » de synthèse, créé dans un dossier
temporaire (jamais dans vos photos), et un faux détecteur de visages (un visage = un disque de couleur).

Couleurs : rouge = Laura, bleu = Hugo, vert = Papa.
"""
import datetime as dt
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

DOSSIER_OUTIL = Path(__file__).resolve().parent.parent
if str(DOSSIER_OUTIL) not in sys.path:
    sys.path.insert(0, str(DOSSIER_OUTIL))

COULEURS = {"Laura": (230, 20, 20), "Hugo": (20, 20, 230), "Papa": (20, 200, 20)}
VENDEE, ROME = (46.67, -1.43), (41.9, 12.5)


def scene(largeur, hauteur, personnes, alea):
    """Fond dégradé + rectangles + un disque de couleur par personne (le « visage »)."""
    a = np.linspace(0, 1, hauteur)[:, None, None]
    c1, c2 = alea.integers(60, 200, 3), alea.integers(60, 200, 3)
    image = (c1 * (1 - a) + c2 * a).repeat(largeur, 1).astype("float32") + alea.normal(0, 12, (hauteur, largeur, 3))
    im = Image.fromarray(image.clip(0, 255).astype("uint8"))
    d = ImageDraw.Draw(im)
    for _ in range(5):
        x, y = alea.integers(0, largeur), alea.integers(0, hauteur)
        d.rectangle((x, y, x + alea.integers(30, 150), y + alea.integers(30, 150)),
                    fill=tuple(int(v) for v in alea.integers(90, 180, 3)))
    for i, nom in enumerate(personnes):
        r = int(min(largeur, hauteur) * (0.12 if len(personnes) > 1 else 0.18))
        cx, cy = int(largeur * (i + 1) / (len(personnes) + 1)), int(hauteur * 0.4)
        d.ellipse((cx - r, cy - r, cx + r, cy + int(r * 1.2)), fill=COULEURS[nom])
    return im


def enregistrer(chemin, image, date, gps=None):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = date.strftime("%Y:%m:%d %H:%M:%S")
    if gps:
        lat, lon = gps
        g = exif.get_ifd(0x8825)
        g[1], g[2], g[3], g[4] = ("N" if lat >= 0 else "S"), (abs(lat), 0.0, 0.0), ("E" if lon >= 0 else "W"), \
            (abs(lon), 0.0, 0.0)
    image.save(chemin, exif=exif, quality=85)


def creer_disque(racine, sortie):
    """Environ 45 photos sur 5 ans (anniversaires, Noëls, un voyage) + photos de référence de chaque personne."""
    alea, hasard = np.random.default_rng(3), random.Random(3)
    photos = racine / "photos"
    n = 0
    for an in range(2015, 2020):
        evenements = [(dt.datetime(an, 3, 12, 15), "Anniversaire", VENDEE, [["Laura"], ["Laura", "Hugo"]]),
                      (dt.datetime(an, 12, 24, 19), "Noel", VENDEE, [["Laura", "Hugo", "Papa"], ["Laura"]])]
        if an == 2017:
            evenements.append((dt.datetime(an, 8, 2, 10), "Voyage", ROME, [["Laura"], ["Laura", "Papa"]]))
        for debut, dossier, gps, qui in evenements:
            for _ in range(3):
                n += 1
                date = debut + dt.timedelta(minutes=hasard.randrange(120))
                largeur, hauteur = hasard.choice([(1200, 900), (900, 1200), (1000, 1000)])
                enregistrer(photos / str(an) / dossier / f"IMG_{n:04d}.jpg",
                            scene(largeur, hauteur, hasard.choice(qui), alea), date, gps)
    (photos / "$RECYCLE.BIN").mkdir(exist_ok=True)  # dossier à ignorer
    enregistrer(photos / "$RECYCLE.BIN" / "supprimee.jpg", scene(800, 600, ["Laura"], alea), dt.datetime(2016, 1, 1))
    for nom in COULEURS:
        for i in range(3):
            enregistrer(sortie / "famille" / nom / f"ref{i}.jpg", scene(800, 1000, [nom], alea),
                        dt.datetime(2020, 1, 1))
    return photos, n


class FauxDetecteur:
    """Remplace YuNet : chaque disque rouge, bleu ou vert est un visage."""

    def setInputSize(self, taille):
        pass

    def detect(self, bgr):
        import cv2

        resultats = []
        for couleur in ((20, 20, 230), (230, 20, 20), (20, 200, 20)):  # BGR
            masque = (np.abs(bgr.astype(int) - couleur).sum(2) < 60).astype("uint8")
            _, _, stats, _ = cv2.connectedComponentsWithStats(masque)
            for x, y, w, h, aire in stats[1:]:
                if aire > 300:
                    resultats.append([x, y, w, h] + [0] * 11)
        return 1, (np.array(resultats, dtype=np.float32) if resultats else None)


class FauxReconnaissance:
    """Remplace SFace : l'empreinte d'un visage est sa couleur moyenne."""

    def alignCrop(self, bgr, f):
        return bgr[int(f[1]):int(f[1] + f[3]), int(f[0]):int(f[0] + f[2])]

    def feature(self, crop):
        v = crop.reshape(-1, 3).mean(0).astype(np.float32)
        return (v - v.mean()).reshape(1, 3)


def installer_faux_modeles():
    import album_famille as af

    af.modeles = lambda sortie: (FauxDetecteur(), FauxReconnaissance())


def lancer(module, *arguments):
    """Lance la fonction main() d'un script de l'outil avec ces arguments, dans ce processus."""
    ancien = sys.argv
    sys.argv = [module.__file__, *map(str, arguments)]
    try:
        module.main()
    finally:
        sys.argv = ancien
