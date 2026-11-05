#!/usr/bin/env python3
"""planche_lettres.py - un prénom en grandes lettres, chaque lettre remplie d'une photo (de petite à maintenant).

Fabrique plusieurs modèles d'un coup (polices, une ou deux lignes, fonds), en JPEG 300 dpi et en PDF prêts
pour l'imprimeur, plus une planche de comparaison. Les photos originales ne sont que lues.

Photos : celles choisies avec 7a_choisir_photos_lettres.bat (lettres_photos.csv), sinon un choix automatique
réparti sur les âges (une photo par lettre, la mieux notée de chaque période, visage centré).

  python planche_lettres.py --sortie C:\\AlbumsFamille --personne Laura [--mot LAURA]
         [--haut "On t'aime"] [--bas "De la part de Papa"] [--naissance 10/11/2003] [--format a4-paysage]
"""
import argparse
import csv
import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

import album_famille as af
import livre_photo as lp
from traduction import traduire

LANGUE = ["fr"]  # option --langue

DPI = 300
FORMATS = {"a4-paysage": (297, 210), "a3-paysage": (420, 297), "30x20": (300, 200), "40x30": (400, 300),
           "a4-portrait": (210, 297)}
POLICES = {  # premier fichier trouvé ; repli DejaVu (Linux) puis police par défaut de Pillow
    "arial-black": ["C:/Windows/Fonts/ariblk.ttf", "/System/Library/Fonts/Supplemental/Arial Black.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "impact": ["C:/Windows/Fonts/impact.ttf", "/System/Library/Fonts/Supplemental/Impact.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "georgia": ["C:/Windows/Fonts/georgiab.ttf", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"],
    "segoe-black": ["C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/ariblk.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "script": ["C:/Windows/Fonts/segoesc.ttf", "C:/Windows/Fonts/LHANDW.TTF", "C:/Windows/Fonts/segoepr.ttf",
               "/System/Library/Fonts/Supplemental/Brush Script.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
    "texte": ["C:/Windows/Fonts/georgiai.ttf", "C:/Windows/Fonts/georgia.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
}
MODELES = [  # nom, police des lettres, disposition, fond, contour, ombre, âges sous les lettres
    {"nom": "1-classique", "police": "arial-black", "lignes": 1, "fond": "blanc", "contour": ("#2F2B28", 3),
     "ombre": True, "ages": True},
    {"nom": "2-aquarelle", "police": "arial-black", "lignes": 1, "fond": "aquarelle", "contour": ("#FFFFFF", 10),
     "ombre": True, "ages": False},
    {"nom": "3-impact", "police": "impact", "lignes": 1, "fond": "blanc", "contour": None, "ombre": True,
     "ages": True},
    {"nom": "4-deux-lignes", "police": "arial-black", "lignes": 2, "fond": "blanc", "contour": ("#2F2B28", 3),
     "ombre": True, "ages": False},
    {"nom": "5-elegant", "police": "georgia", "lignes": 1, "fond": "creme", "contour": ("#B8954F", 5),
     "ombre": False, "ages": True},
    {"nom": "6-prestige-noir", "police": "segoe-black", "lignes": 1, "fond": "noir", "contour": ("#C8A96A", 6),
     "ombre": False, "ages": False},
]
FONDS = {"blanc": "#FFFFFF", "creme": "#FBF6EC", "noir": "#161514", "aquarelle": "#EAF3FA"}
COULEURS = {  # noms utilisables pour le fond et le contour des lettres (ou un code #RRGGBB)
    "blanc": "#FFFFFF", "creme": "#FBF6EC", "noir": "#161514", "gris": "#9A9590", "gris-clair": "#E6E3DF",
    "anthracite": "#33302D", "bleu-nuit": "#1C2B44", "bleu": "#3A6EA5", "bleu-ciel": "#CFE6F5",
    "rose": "#F6D6DC", "rose-poudre": "#EBC8C4", "fuchsia": "#C2185B", "rouge": "#C62828", "bordeaux": "#6D1A2A",
    "vert": "#2E7D4F", "vert-sauge": "#C9D5C0", "beige": "#E9DCC8", "kraft": "#C8A97E", "or": "#C8A96A",
    "argent": "#BFC3C7", "lavande": "#D9D2EA", "violet": "#6A4C93", "marine": "#14213D", "jaune": "#F4D35E", "orange": "#E07A2F",
}


def couleur(nom):
    """« noir », « bleu-nuit », « #1C2B44 »... -> code couleur ; None si vide ou « aucun »."""
    nom = (nom or "").strip().lower()
    if nom in ("", "auto", "modele"):
        return None
    if nom in ("aucun", "sans", "non"):
        return "aucun"
    if nom in COULEURS:
        return COULEURS[nom]
    if nom.startswith("#") and len(nom) in (4, 7):
        return nom
    sys.exit(f"Couleur inconnue : « {nom} ». Possibles : {', '.join(COULEURS)}, ou un code comme #1C2B44.")


def clarte(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5)) if len(hexa) == 7 else (int(c * 2, 16) for c in hexa[1:])
    return 0.299 * r + 0.587 * g + 0.114 * b


def police(cle, taille):
    for chemin in POLICES[cle]:
        if Path(chemin).exists():
            return ImageFont.truetype(chemin, taille)
    return ImageFont.load_default(taille)


def ajuster(dessin, texte, cle, taille, largeur_max):
    """Police aussi grande que demandé, réduite si le texte libre est trop long pour la largeur."""
    f = police(cle, taille)
    while taille > 30 and dessin.textlength(texte, font=f) > largeur_max:
        taille = int(taille * 0.93)
        f = police(cle, taille)
    return f


def boucher_creux(masque, boite):
    """Remplit l'intérieur fermé d'une lettre (triangle du A, boucle du R, du O, du B...) : la photo n'est
    découpée que sur le contour extérieur de la lettre, et se voit en entier à l'intérieur."""
    x0, y0, x1, y1 = boite
    marge = 4
    zone = (max(0, x0 - marge), max(0, y0 - marge), min(masque.width, x1 + marge), min(masque.height, y1 + marge))
    morceau = masque.crop(zone)
    binaire = morceau.point(lambda v: 255 if v > 100 else 0)
    ImageDraw.floodfill(binaire, (0, 0), 128)  # tout ce qui est relié au bord = extérieur de la lettre
    creux = binaire.point(lambda v: 255 if v == 0 else 0).filter(ImageFilter.MaxFilter(5))  # recouvre l'anticrénelage
    masque.paste(ImageChops.lighter(morceau, creux), zone[:2])
    return masque


def mm(valeur):
    return round(valeur / 25.4 * DPI)


# --------------------------------------------------------------------------- choix des photos

def lire_choix_lettres(dossier, lignes):
    """Photos choisies avec 7a_choisir_photos_lettres.bat (lettres_photos.csv) ; à défaut, l'ancienne colonne
    « lettres » de selection_livre.csv."""
    fichier = dossier / "lettres_photos.csv"
    if fichier.exists():
        with open(fichier, newline="", encoding="utf-8-sig") as f:
            return {l["fichier"] for l in csv.DictReader(f, delimiter=";") if l.get("fichier")}
    return {l["fichier"] for l in lignes if (l.get("lettres") or "").strip() in ("1", "oui", "x")}


def choisir_photos(lignes, n, infos, choix_manuel=frozenset()):
    """Photos choisies à la main (dans l'ordre des dates) ; sinon une par période, de la plus ancienne à la
    plus récente : la mieux notée, avec un grand visage, de préférence seule sur la photo."""
    marquees = sorted((l for l in lignes if l["fichier"] in choix_manuel), key=cle_date)
    if len(marquees) > n:
        print(f"  {len(marquees)} photos choisies pour {n} lettres : les {n} plus anciennes sont utilisées.")
    if len(marquees) >= n:
        return marquees[:n], "choisies dans l'écran des lettres"
    if marquees:
        print(f"  {len(marquees)} photo(s) choisie(s) pour {n} lettres : l'outil complète automatiquement.")
    gardees = [l for l in lignes if l["garder"].strip().lower() in ("1", "oui", "x")] or lignes
    candidates = sorted(gardees, key=cle_date)
    if len(candidates) < n:
        sys.exit(f"Il faut au moins {n} photos ({len(candidates)} disponibles).")
    def valeur(l):
        info = infos.get(l["fichier"], {})
        return (float(l.get("score") or 0) + 1.5 * min(0.25, info.get("visage", 0))
                + (0.15 if info.get("nb_visages", 0) == 1 else 0) + 0.2 * min(1, info.get("cote", 0) / 2500))
    choix = list(marquees)
    reste = n - len(choix)
    periodes = [candidates[round(i * len(candidates) / reste): round((i + 1) * len(candidates) / reste)]
                for i in range(reste)]
    for periode in periodes:
        libres = [l for l in periode if l not in choix]
        if libres:
            choix.append(max(libres, key=valeur))
    return sorted(choix, key=cle_date)[:n], "choix automatique réparti sur les âges"


def cle_date(l):
    return dt.datetime.strptime(f"{l['date']} {l.get('heure') or '12:00'}", "%d/%m/%Y %H:%M")


# --------------------------------------------------------------------------- dessin

def fond(taille, modele):
    largeur, hauteur = taille
    image = Image.new("RGB", taille, FONDS.get(modele["fond"], modele["fond"]))
    if modele["fond"] == "aquarelle":  # taches d'aquarelle bleue, douces (comme les tableaux personnalisés)
        couche = Image.new("RGB", taille, "#FFFFFF")
        dessin = ImageDraw.Draw(couche)
        for i, (cx, cy, r, c) in enumerate(((0.15, 0.2, 0.35, "#9CC9E8"), (0.8, 0.15, 0.3, "#B9DBF0"),
                                            (0.5, 0.85, 0.45, "#A9D1EC"), (0.9, 0.8, 0.25, "#CFE6F5"),
                                            (0.3, 0.6, 0.3, "#D6EAF7"))):
            dessin.ellipse(((cx - r) * largeur, (cy - r) * hauteur, (cx + r) * largeur, (cy + r) * hauteur), fill=c)
        image = Image.blend(image, couche.filter(ImageFilter.GaussianBlur(largeur / 18)), 0.85)
    return image


def coeur(dessin, cx, cy, taille, couleur="#D7263D"):
    points = []
    for i in range(60):
        t = 2 * math.pi * i / 60
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append((cx + x * taille / 34, cy - y * taille / 34))
    dessin.polygon(points, fill=couleur)


_CACHE = {}


def ouvrir_photo(base, relatif):
    """Original lu une seule fois (lecture seule), réduit à 4000 px au plus : largement assez pour une lettre."""
    if relatif not in _CACHE:
        with Image.open(af.original(base, relatif)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((4000, 4000), Image.LANCZOS)
            _CACHE[relatif] = im
    return _CACHE[relatif]


ZOOMS = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.4)  # 1 = la photo couvre juste la lettre


def boites_visages(info):
    """Visages (fractions de la photo), agrandis pour garder les cheveux et le menton. En premier : le visage de
    la personne (reconnu), sinon le plus grand."""
    boites = []
    for i, (x, y, l, h) in enumerate(info["visages"]):
        boites.append((i == info.get("principal"), (x - 0.18 * l, y - 0.30 * h, x + 1.18 * l, y + 1.15 * h)))
    boites.sort(key=lambda b: (not b[0], -(b[1][2] - b[1][0]) * (b[1][3] - b[1][1])))
    return [b for _, b in boites]


def reperer_sujet(base, sortie, personne, photos, infos):
    """Sur chaque photo retenue, repère le visage de la personne (photos de référence de famille/<Prénom>), pour
    que ce soit lui qui tombe sur le plein de la lettre. Sans référence ni modèle : le plus grand visage."""
    import numpy as np
    dossier = next((d for d in (Path(sortie) / "famille").glob("*")
                    if d.is_dir() and d.name.lower() == personne.lower()), None)
    if dossier is None:
        return
    try:
        import cv2

        detecteur, reco = af.modeles(sortie)
        refs = []
        for chemin in dossier.iterdir():
            if chemin.suffix.lower() in af.EXTENSIONS:
                image, _, _ = af.charger(chemin)
                visages = af.detecter_visages(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), detecteur, reco)
                if visages:
                    refs.append(max(visages, key=lambda v: v[2])[4])
        if not refs:
            return
        refs = np.stack(refs)
        for p in photos:
            info = infos[p["fichier"]]
            embs = [np.frombuffer(v["emb"], dtype=np.float32) for v in base.execute(
                "SELECT emb FROM visages WHERE photo_id = ? ORDER BY id", (info["id"],))]
            if len(embs) == len(info["visages"]) and embs:
                similarites = [float((refs @ e).max()) for e in embs]
                if max(similarites) >= af.SEUIL_VISAGE:
                    info["principal"] = int(np.argmax(similarites))
    except Exception as erreur:  # modèles absents, etc. : on garde le plus grand visage
        print(f"  (visage de {personne} non repéré : {erreur} ; le plus grand visage sert de repère)")


def cadrage(info, plein):
    """Cherche le zoom et la position de la photo dans la lettre pour que les visages tombent sur la partie
    pleine (pas dans le vide du U, entre les jambes du A, hors du jambage du L...).
    plein : tableau booléen hauteur x largeur de la lettre. Renvoie (k, ox, oy) : largeur de la photo en pixels
    et position de son coin haut-gauche dans le rectangle de la lettre."""
    H, W = plein.shape
    ratio = info["ratio"]
    integrale = np.zeros((H + 1, W + 1))
    integrale[1:, 1:] = plein.cumsum(0).cumsum(1)
    total = max(1.0, integrale[-1, -1])

    def somme(x0, y0, x1, y1):  # pixels pleins dans des rectangles (tableaux numpy), bornés à la lettre
        x0, x1 = np.clip(x0, 0, W).astype(int), np.clip(x1, 0, W).astype(int)
        y0, y1 = np.clip(y0, 0, H).astype(int), np.clip(y1, 0, H).astype(int)
        return integrale[y1, x1] - integrale[y0, x1] - integrale[y1, x0] + integrale[y0, x0]

    visages = boites_visages(info)
    k0 = max(W, H * ratio)  # zoom 1 : la photo couvre tout le rectangle de la lettre
    if not visages:
        gauche, haut, _, _, _ = lp.fenetre(info, W / H)
        return k0, -gauche * k0, -haut * k0 / ratio
    meilleur = None
    for z in ZOOMS:
        k = k0 * z
        pw, ph = k, k / ratio
        ox = np.linspace(min(0, W - pw), max(0, W - pw), 25)[None, :]
        oy = np.linspace(min(0, H - ph), max(0, H - ph), 25)[:, None]
        score = np.zeros((25, 25))
        for i, (a, b, c, d) in enumerate(visages[:4]):
            x0, x1 = ox + a * k, ox + c * k
            y0, y1 = oy + b * k / ratio, oy + d * k / ratio
            aire = np.maximum(1.0, (x1 - x0) * (y1 - y0))
            couverture = somme(x0, y0, x1, y1) / aire  # part du visage sur le plein de la lettre
            score += (3.0 if i == 0 else 0.8) * couverture
            if i == 0:  # le visage principal doit être entier sur le plein : forte pénalité sinon
                score -= 6.0 * np.maximum(0, 0.97 - couverture)
                hauteur_visage = (d - b) * k / ratio
                score += 0.8 * np.minimum(1.0, hauteur_visage / (0.30 * H))  # visage assez grand pour être reconnu
                score -= 0.6 * np.maximum(0, hauteur_visage / H - 0.6)  # mais pas un gros plan coupé
        vide = 1 - somme(np.maximum(ox, 0) + 0 * oy, np.maximum(oy, 0) + 0 * ox,
                         np.minimum(ox + pw, W) + 0 * oy, np.minimum(oy + ph, H) + 0 * ox) / total
        score -= 2.5 * vide + 0.15 * abs(math.log(z))  # éviter le fond flou et les zooms extrêmes
        j = np.unravel_index(score.argmax(), score.shape)
        if meilleur is None or score[j] > meilleur[0]:
            meilleur = (score[j], k, float(ox[0, j[1]]), float(oy[j[0], 0]))
    return meilleur[1:]


def photo_dans_lettre(ligne, boite, base, infos, masque):
    """La photo placée dans le rectangle de la lettre, cadrée pour que les visages tombent sur le plein."""
    x0, y0, x1, y1 = boite
    largeur, hauteur = x1 - x0, y1 - y0
    info = infos[ligne["fichier"]]
    plein = np.asarray(masque.crop(boite)) > 127
    k, ox, oy = cadrage(info, plein)
    im = ouvrir_photo(base, ligne["fichier"])
    L, H = im.size
    echelle = k / L
    # partie de la photo visible dans le rectangle, redimensionnée directement (rapide et net)
    gauche, haut = max(0.0, -ox / echelle), max(0.0, -oy / echelle)
    droite, bas = min(L, (largeur - ox) / echelle), min(H, (hauteur - oy) / echelle)
    morceau = im.crop((round(gauche), round(haut), round(droite), round(bas)))
    cible = (max(1, round((droite - gauche) * echelle)), max(1, round((bas - haut) * echelle)))
    morceau = morceau.resize(cible, Image.LANCZOS)
    position = (round(max(0.0, ox)), round(max(0.0, oy)))
    if cible[0] >= largeur and cible[1] >= hauteur:
        return morceau.crop((0, 0, largeur, hauteur))
    # photo plus petite que la lettre (zoom arrière pour loger le visage dans le plein) : on prolonge ses bords
    # (couleurs étirées puis floutées, sans dupliquer de visage) et on fond la jonction en douceur
    gauche_px, haut_px = position
    pads = ((haut_px, max(0, hauteur - haut_px - cible[1])), (gauche_px, max(0, largeur - gauche_px - cible[0])), (0, 0))
    etendu = np.pad(np.asarray(morceau), pads, mode="edge")[:hauteur, :largeur]
    fond_flou = Image.fromarray(etendu).filter(ImageFilter.GaussianBlur(max(4, largeur / 30)))
    fondu = max(2, round(min(cible) * 0.05))
    bord = Image.new("L", cible, 0)
    ImageDraw.Draw(bord).rectangle((fondu, fondu, cible[0] - 1 - fondu, cible[1] - 1 - fondu), fill=255)
    bord = bord.filter(ImageFilter.GaussianBlur(fondu / 2))
    # pas de fondu sur les côtés où la photo touche le bord de la lettre
    tableau = np.asarray(bord).copy()
    if gauche_px == 0:
        tableau[:, :fondu * 2] = np.maximum(tableau[:, :fondu * 2], tableau[:, fondu * 2:fondu * 2 + 1])
    if haut_px == 0:
        tableau[:fondu * 2, :] = np.maximum(tableau[:fondu * 2, :], tableau[fondu * 2:fondu * 2 + 1, :])
    if gauche_px + cible[0] >= largeur:
        tableau[:, -fondu * 2:] = np.maximum(tableau[:, -fondu * 2:], tableau[:, -fondu * 2 - 1:-fondu * 2])
    if haut_px + cible[1] >= hauteur:
        tableau[-fondu * 2:, :] = np.maximum(tableau[-fondu * 2:, :], tableau[-fondu * 2 - 1:-fondu * 2, :])
    fond_flou.paste(morceau, position, Image.fromarray(tableau))
    return fond_flou


def composer(mot, photos, base, infos, modele, format_mm, haut, bas, naissance, echelle=1.0, evider=False):
    taille = (mm(format_mm[0]), mm(format_mm[1]))
    largeur, hauteur = taille
    image = fond(taille, modele)
    sombre = clarte(FONDS.get(modele["fond"], modele["fond"])) < 110  # texte clair sur fond sombre
    couleur_texte = modele.get("texte") or ("#E9E2D6" if sombre else "#2F2B28")
    mots = mot.split()
    if len(mots) > 1:  # plusieurs mots (« LAURA BO ») : un mot par ligne
        rangees = mots
    elif (modele["lignes"] == 2 or hauteur > 0.9 * largeur) and len(mot) >= 4:  # deux lignes (portrait, carré)
        rangees = [mot[:math.ceil(len(mot) / 2)], mot[math.ceil(len(mot) / 2):]]
    else:
        rangees = [mot]
    zone_haut = 0.20 * hauteur if haut else 0.08 * hauteur
    zone_bas = 0.17 * hauteur if (bas or modele["ages"]) else 0.08 * hauteur
    zone_lettres = hauteur - zone_haut - zone_bas
    # taille de police : la plus grande qui tient en largeur (88 %) et en hauteur
    plus_longue = max(rangees, key=len)
    taille_police = int(zone_lettres / len(rangees) * 1.25)
    while taille_police > 20:
        f = police(modele["police"], taille_police)
        espace = taille_police * 0.06
        l_rangee = sum(f.getbbox(c)[2] - f.getbbox(c)[0] for c in plus_longue) + espace * (len(plus_longue) - 1)
        h_lettre = max(f.getbbox(c)[3] - f.getbbox(c)[1] for c in "".join(mots))
        if l_rangee <= 0.88 * echelle * largeur and h_lettre * len(rangees) * 1.12 <= zone_lettres * echelle:
            break
        taille_police = int(taille_police * 0.96)
    f = police(modele["police"], taille_police)
    espace = taille_police * 0.06
    h_lettre = max(f.getbbox(c)[3] - f.getbbox(c)[1] for c in "".join(mots))
    h_rangee = zone_lettres / len(rangees)
    index_photo, positions = 0, []
    for r, rangee in enumerate(rangees):
        l_rangee = sum(f.getbbox(c)[2] - f.getbbox(c)[0] for c in rangee) + espace * (len(rangee) - 1)
        x = (largeur - l_rangee) / 2
        y_base = zone_haut + r * h_rangee + (h_rangee - h_lettre) / 2
        for c in rangee:
            g, t, d, b = f.getbbox(c)
            masque = Image.new("L", taille, 0)
            ImageDraw.Draw(masque).text((x - g, y_base - t), c, font=f, fill=255)
            boite = (round(x), round(y_base), round(x + d - g), round(y_base + b - t))
            if not evider:
                boucher_creux(masque, boite)
            positions.append((c, masque, boite, (x - g, y_base - t)))
            x += d - g + espace
    if modele["ombre"]:  # ombre portée douce sous toutes les lettres
        ombre = Image.new("L", taille, 0)
        for _, masque, _, _ in positions:
            ombre.paste(255, (0, 0), masque)
        decale = Image.new("L", taille, 0)
        decale.paste(ombre.filter(ImageFilter.GaussianBlur(taille_police / 40)), (round(taille_police / 45),) * 2)
        image.paste(Image.new("RGB", taille, "#000000"), (0, 0), decale.point(lambda v: v * 0.35))
    for i, (c, masque, boite, origine) in enumerate(positions):
        if modele["contour"]:  # contour de la lettre (dessiné sous la photo, il déborde autour)
            couleur, epaisseur = modele["contour"]
            contour = Image.new("L", taille, 0)  # le glyphe redessiné avec un trait épais (bien plus rapide qu'un filtre)
            ImageDraw.Draw(contour).text(origine, c, font=f, fill=255, stroke_width=max(1, round(
                epaisseur * taille_police / 900)), stroke_fill=255)
            image.paste(Image.new("RGB", taille, couleur), (0, 0), contour)
        remplissage = photo_dans_lettre(photos[index_photo % len(photos)], boite, base, infos, masque)
        if modele.get("teinte") == "noir-et-blanc":
            remplissage = ImageOps.grayscale(remplissage).convert("RGB")
        elif modele.get("teinte") == "sepia":
            remplissage = ImageOps.colorize(ImageOps.grayscale(remplissage), "#2B1D0E", "#F3E3C3", mid="#A07850")
        calque = Image.new("RGB", taille)
        calque.paste(remplissage, boite[:2])
        image.paste(calque, (0, 0), masque)
        index_photo += 1
    dessin = ImageDraw.Draw(image)
    if haut:
        fh = ajuster(dessin, haut, "script", int(zone_haut * 0.55), 0.86 * largeur)
        dessin.text((largeur / 2, zone_haut * 0.55), haut, font=fh, fill=modele.get("texte") or "#3A6EA5" if modele["fond"] == "aquarelle"
                    else couleur_texte, anchor="mm")
    y_ages = None
    if modele["ages"] and naissance:  # âge sous chaque lettre
        fa = police("texte", max(mm(6), int(taille_police * 0.09)))  # 6 mm ≈ 17 pt : toujours lisible
        for (c, _, boite, _), p in zip(positions, photos):
            d = cle_date(p).date()
            a = d.year - naissance.year - ((d.month, d.day) < (naissance.month, naissance.day))
            texte = traduire("naissance" if a <= 0 else f"{a} an{'s' * (a > 1)}", LANGUE[0])
            y_ages = boite[3] + taille_police * 0.05
            dessin.text(((boite[0] + boite[2]) / 2, y_ages), texte, font=fa, fill=couleur_texte, anchor="mt")
    if bas:
        fb = ajuster(dessin, bas, "texte", int(zone_bas * 0.28), 0.80 * largeur)
        y = hauteur - zone_bas * 0.42
        dessin.text((largeur / 2, y), bas, font=fb, fill=couleur_texte, anchor="mm")
        largeur_texte = dessin.textlength(bas, font=fb)
        coeur(dessin, largeur / 2 + largeur_texte / 2 + zone_bas * 0.22, y, zone_bas * 0.25)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sortie", type=Path, default=Path("albums_sortie"))
    parser.add_argument("--personne", required=True)
    parser.add_argument("--mot", help="mot à écrire (défaut : le prénom, en majuscules)")
    parser.add_argument("--haut", default="", help="texte libre au-dessus (ex. « On t'aime »)")
    parser.add_argument("--bas", default="", help="texte libre en dessous (ex. « De la part de Papa »)")
    parser.add_argument("--naissance", help="JJ/MM/AAAA : affiche l'âge sous les lettres (modèles 1, 3 et 5)")
    parser.add_argument("--format", choices=sorted(FORMATS), default="a4-paysage")
    parser.add_argument("--police", choices=["toutes"] + sorted(set(POLICES) - {"script", "texte"}), default="toutes",
                        help="impose une police à tous les modèles (défaut : chaque modèle a la sienne)")
    parser.add_argument("--taille", type=int, default=100,
                        help="taille des lettres en %% de la plus grande possible (ex. 80 = plus d'air autour)")
    parser.add_argument("--fond", default="", help="couleur du fond pour tous les modèles : noir, blanc, creme, "
                        "bleu-nuit, rose... ou #RRGGBB (vide = celle de chaque modèle)")
    parser.add_argument("--contour", default="", help="couleur du contour des lettres (or, blanc, noir... ou "
                        "#RRGGBB ; « aucun » = sans contour ; vide = celle de chaque modèle)")
    parser.add_argument("--texte", default="", help="couleur des textes (vide = automatique selon le fond)")
    parser.add_argument("--teinte", choices=["couleur", "noir-et-blanc", "sepia"], default="couleur",
                        help="photos en couleur, en noir et blanc ou en sépia")
    parser.add_argument("--modeles", default="tous", help="modèles à fabriquer : tous, ou des numéros (ex. 3 ou 1,3)")
    parser.add_argument("--langue", choices=["fr", "en"], default="fr", help="langue des âges sous les lettres")
    parser.add_argument("--page-livre", type=Path, help="fabrique seulement la page du livre (un seul modèle), "
                        "au format du livre fond perdu compris, dans ce fichier JPEG")
    parser.add_argument("--format-livre", choices=sorted(lp.FORMATS), default="carre30",
                        help="format du livre (avec --page-livre)")
    parser.add_argument("--fond-perdu", type=float, default=3, help="fond perdu du livre en mm (avec --page-livre)")
    parser.add_argument("--evider", action="store_true",
                        help="garde les creux des lettres (triangle du A, boucle du R) ; défaut : lettres pleines")
    args = parser.parse_args()

    LANGUE[0] = args.langue
    base = af.ouvrir_base(args.sortie)
    dossier = lp.dossier_livre(args.sortie, args.personne)
    fichier = dossier / "selection_livre.csv"
    if not fichier.exists():
        sys.exit("Lancez d'abord 3_preparer_selection.bat.")
    with open(fichier, newline="", encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    mot = " ".join((args.mot or dossier.name[len("livre_"):]).upper().split())  # espace = nouvelle ligne
    lettres = mot.replace(" ", "")
    infos = {}
    for p in base.execute("SELECT id, chemin, largeur_orig, hauteur_orig, nb_visages FROM photos"):
        infos[p["chemin"]] = {"largeur": p["largeur_orig"] or 1, "hauteur": p["hauteur_orig"] or 1,
                              "ratio": (p["largeur_orig"] or 1) / (p["hauteur_orig"] or 1), "id": p["id"],
                              "nb_visages": p["nb_visages"] or 0, "cote": min(p["largeur_orig"] or 0,
                                                                              p["hauteur_orig"] or 0)}
    par_id = {i["id"]: i for i in infos.values()}
    for v in base.execute("SELECT photo_id, x, y, l, h FROM visages ORDER BY id"):
        info = par_id.get(v["photo_id"])
        if info is not None:
            info.setdefault("visages", []).append((v["x"], v["y"], v["l"], v["h"]))
            info["visage"] = max(info.get("visage", 0), v["l"])
    for info in infos.values():
        info.setdefault("visages", [])
    lignes = af.retirer_absentes(base, [l for l in lignes if l["fichier"] in infos], "fichier")
    photos, origine = choisir_photos(lignes, len(lettres), infos, lire_choix_lettres(dossier, lignes))
    reperer_sujet(base, args.sortie, args.personne, photos, infos)
    naissance = dt.datetime.strptime(args.naissance, "%d/%m/%Y").date() if args.naissance else None
    sortie = dossier / "lettres"
    sortie.mkdir(exist_ok=True)
    print(f"« {mot} » : {len(photos)} photos ({origine}) :")
    for c, p in zip(lettres, photos):
        print(f"  {c} : {p['date']}  {p['fichier']}")
    vignettes = []
    format_mm = FORMATS[args.format]
    if args.page_livre:  # page du livre photo : au format du livre, fond perdu compris, un seul modèle
        l, h = lp.FORMATS[args.format_livre]
        format_mm = (l + 2 * args.fond_perdu, h + 2 * args.fond_perdu)
        if args.modeles.strip().lower() in ("", "tous", "toutes"):
            args.modeles = "1"
        args.modeles = args.modeles.replace(";", ",").split(",")[0].strip()
    echelle = min(100, max(40, args.taille)) / 100
    fond_choisi, contour_choisi, texte_choisi = couleur(args.fond), couleur(args.contour), couleur(args.texte)
    numeros = None if args.modeles.strip().lower() in ("", "tous", "toutes") else {
        n.strip() for n in args.modeles.replace(";", ",").split(",") if n.strip()}
    a_faire = [m for m in MODELES if not numeros or m["nom"].split("-")[0] in numeros]
    for rang, modele in enumerate(MODELES):
        if numeros and modele["nom"].split("-")[0] not in numeros:
            continue
        af.progression("Planche lettres", a_faire.index(modele) + 1, len(a_faire))
        modele = dict(modele, teinte=args.teinte)
        if args.police != "toutes":
            modele["police"] = args.police
        if fond_choisi and fond_choisi != "aucun":
            modele["fond"] = fond_choisi
        if contour_choisi == "aucun":
            modele["contour"] = None
        elif contour_choisi:
            modele["contour"] = (contour_choisi, modele["contour"][1] if modele["contour"] else 5)
        if texte_choisi and texte_choisi != "aucun":
            modele["texte"] = texte_choisi
        image = composer(mot, photos, base, infos, modele, format_mm, args.haut, args.bas, naissance,
                         echelle, args.evider)
        if args.page_livre:
            args.page_livre.parent.mkdir(parents=True, exist_ok=True)
            image.save(args.page_livre, quality=95, subsampling=0, dpi=(DPI, DPI))
            print(f"Page lettres du livre (modèle {modele['nom']}) : {args.page_livre}")
            return
        variantes = "".join(f"_{c}-{v.strip().lstrip('#').lower()}" for c, v in (
            ("fond", args.fond), ("contour", args.contour), ("texte", args.texte)) if v.strip())
        if args.teinte != "couleur":
            variantes += f"_{args.teinte}"
        nom = f"Lettres_{mot.replace(' ', '-')}_{modele['nom']}{variantes}"
        image.save(sortie / f"{nom}.jpg", quality=95, subsampling=0, dpi=(DPI, DPI))
        image.save(sortie / f"{nom}.pdf", resolution=DPI)
        vignettes.append((modele["nom"], image.copy()))
        print(f"  {nom}.jpg / .pdf")
    # planche de comparaison
    if not vignettes:
        sys.exit(f"Aucun modèle ne correspond à --modeles {args.modeles} (numéros possibles : 1 à {len(MODELES)}).")
    l, h = 900, round(900 * vignettes[0][1].height / vignettes[0][1].width)
    colonnes = min(2, len(vignettes))
    planche = Image.new("RGB", (colonnes * (l + 30) + 30, math.ceil(len(vignettes) / colonnes) * (h + 70) + 30),
                        "#E8E4DE")
    dessin = ImageDraw.Draw(planche)
    for i, (nom, im) in enumerate(vignettes):
        x, y = 30 + (i % colonnes) * (l + 30), 30 + (i // colonnes) * (h + 70)
        planche.paste(im.resize((l, h), Image.LANCZOS), (x, y))
        dessin.text((x, y + h + 10), nom, font=police("texte", 34), fill="#2F2B28")
    planche.save(sortie / "Comparaison_modeles.jpg", quality=90)
    print(f"Planche de comparaison : {sortie / 'Comparaison_modeles.jpg'}")


if __name__ == "__main__":
    main()
