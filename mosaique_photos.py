#!/usr/bin/env python3
"""mosaique_photos.py - une « photo master » reconstituée avec des centaines de petites photos de l'album.

Chaque case de la grande image reçoit la photo de la sélection dont les couleurs ressemblent le plus à cet
endroit de la photo master (vue en 3 x 3 zones, pour respecter les contours) ; une même photo n'est pas
répétée à côté d'elle-même ; la photo master est ensuite fondue légèrement par-dessus (réglable) pour que
le visage se lise de loin, et chaque petite photo reste reconnaissable de près.

Photo master, au choix (dans cet ordre) :
  --master (ou MOSAIQUE_MASTER) : un fichier (chemin complet, ou relatif au disque de photos) ;
  sinon la photo marquée « ◆ Master » dans l'écran de choix (mosaique_master.txt) ;
  sinon la photo de couverture du livre.
Petites photos : les photos gardées pour le livre (ou toutes celles de la personne : --photos toutes).

Résultat dans livre_<Prénom>/mosaique : Mosaique_<Prénom>.jpg (300 dpi, pour l'imprimeur), un aperçu réduit
et la liste des photos utilisées. Les photos originales ne sont que lues.

  python mosaique_photos.py --sortie C:\\AlbumsFamille --personne Laura [--format a3-portrait] [--colonnes 60]
         [--melange 0.35] [--master "D:\\Photos\\2024\\portrait.jpg"] [--photos gardees|toutes]
"""
import argparse
import csv
import hashlib
import os
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageDraw, ImageFilter, ImageOps

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

import album_famille as af
import livre_photo as lp
import planche_lettres as pl


def garde(ligne):
    return (ligne.get("garder") or "").strip().lower() in ("1", "oui", "x")

FORMATS = {  # largeur x hauteur en mm ; « master-… » = les proportions de la photo master
    "a4-portrait": (210, 297), "a4-paysage": (297, 210), "a3-portrait": (297, 420), "a3-paysage": (420, 297),
    "a2-portrait": (420, 594), "a2-paysage": (594, 420), "a1-portrait": (594, 841), "a1-paysage": (841, 594),
    "a0-portrait": (841, 1189), "a0-paysage": (1189, 841), "30x40": (300, 400), "40x30": (400, 300),
    "40x50": (400, 500), "50x70": (500, 700), "70x50": (700, 500), "carre30": (300, 300), "carre50": (500, 500),
    "master-40": 400, "master-80": 800,
}


def dpi_auto(largeur_mm, hauteur_mm):
    """Résolution d'impression conseillée : 300 dpi jusqu'au A2 (regardé de près), 200 dpi en A1, 150 dpi en A0
    (un poster se regarde à plus d'un mètre : c'est la norme des imprimeurs grand format)."""
    grand_cote = max(largeur_mm, hauteur_mm)
    return 300 if grand_cote <= 600 else 200 if grand_cote <= 850 else 150
GRILLE = 3  # chaque case et chaque petite photo sont comparées en 3 x 3 zones de couleur
VOISINAGE = 3  # une photo n'est pas réutilisée à moins de 3 cases d'elle-même
COTE_VIGNETTE = 480  # taille lue pour fabriquer les petites photos (cache dans vignettes_mosaique)


def lire_master(base, dossier, sujet, master):
    """Chemin de la photo master : --master, sinon le choix de l'écran (mosaique_master.txt), sinon la
    couverture du livre. Renvoie (chemin absolu, chemin relatif au disque ou "")."""
    racine = Path(af.meta(base, "racine") or "")
    if master:
        chemin = Path(master)
        if not chemin.is_absolute():
            chemin = racine / master
        if not chemin.exists():
            sys.exit(f"Photo master introuvable : {chemin}")
        try:
            relatif = chemin.resolve().relative_to(racine.resolve()).as_posix()
        except (ValueError, OSError):
            relatif = ""
        return chemin, relatif
    choix = dossier / "mosaique_master.txt"
    if choix.exists() and choix.read_text(encoding="utf-8-sig").strip():
        relatif = choix.read_text(encoding="utf-8-sig").strip()
        if (racine / relatif).exists():
            return racine / relatif, relatif
        print(f"  ATTENTION : la photo master choisie ({relatif}) n'est plus sur le disque : couverture utilisée.")
    selection = dossier / "selection_livre.csv"
    if selection.exists():
        lignes = af.lire_csv(selection)
        couverture = next((l for l in lignes if l.get("vedette", "").strip().lower() == "couverture"), None)
        if couverture is None:
            couverture = max((l for l in lignes if garde(l)), key=lambda l: float(l.get("score") or 0),
                             default=None)
        if couverture and (racine / couverture["fichier"]).exists():
            return racine / couverture["fichier"], couverture["fichier"]
    sys.exit("Pas de photo master : choisissez-en une (MOSAIQUE_MASTER, ou bouton « ◆ Master » dans l'écran "
             "« Choisir les photos »).")


def boite_visages(base, relatif):
    """Boîte (relative, 0-1) qui englobe les visages de la photo, d'après l'analyse ; None si aucun."""
    if not relatif:
        return None
    lignes = base.execute("SELECT v.x, v.y, v.l, v.h FROM visages v JOIN photos p ON p.id = v.photo_id "
                          "WHERE p.chemin = ?", (relatif,)).fetchall()
    if not lignes:
        return None
    x0 = min(v[0] for v in lignes)
    y0 = min(v[1] for v in lignes)
    x1 = max(v[0] + v[2] for v in lignes)
    y1 = max(v[1] + v[3] for v in lignes)
    return x0, y0, x1, y1


def recadrer(image, ratio, boite=None):
    """Recadre l'image aux proportions voulues, centrée sur les visages s'il y en a (sinon au centre)."""
    return image.crop(fenetre_recadrage(image.size, ratio, boite))


def fenetre_recadrage(taille, ratio, boite=None):
    w, h = taille
    if w / h > ratio:
        nw, nh = round(h * ratio), h
    else:
        nw, nh = w, round(w / ratio)
    cx, cy = (0.5, 0.45) if boite is None else ((boite[0] + boite[2]) / 2, (boite[1] + boite[3]) / 2)
    gauche = min(max(0, round(cx * w - nw / 2)), w - nw)
    haut = min(max(0, round(cy * h - nh / 2)), h - nh)
    return gauche, haut, gauche + nw, haut + nh


def signature(image):
    """Couleurs moyennes en 3 x 3 zones (27 nombres), dans un espace où la clarté compte plus (comme l'œil)."""
    petit = np.asarray(image.convert("RGB").resize((GRILLE, GRILLE), Image.BOX), dtype=np.float32)
    clarte = petit @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    teinte = petit - clarte[..., None]
    return np.concatenate([clarte[..., None] * 1.6, teinte], axis=2).reshape(-1)


EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp"}


def photos_du_dossier(dossier, exclure=None):
    """Toutes les photos d'un dossier (et de ses sous-dossiers), en lecture seule ; les petits fichiers (icônes,
    miniatures) et les dossiers cachés ou de corbeille sont ignorés."""
    trouvees = []
    exclure = Path(exclure).resolve() if exclure else None
    for courant, sous, fichiers in os.walk(dossier):
        if exclure and (Path(courant).resolve() == exclure or exclure in Path(courant).resolve().parents):
            sous[:] = []  # jamais les vignettes et livres du dossier de travail
            continue
        sous[:] = sorted(d for d in sous if not d.startswith((".", "$")) and d.lower() not in af.DOSSIERS_IGNORES)
        for nom in sorted(fichiers):
            chemin = Path(courant) / nom
            if chemin.suffix.lower() in EXTENSIONS and not nom.startswith("._"):
                try:
                    if chemin.stat().st_size >= 20_000:
                        trouvees.append({"fichier": str(chemin), "externe": True, "date": ""})
                except OSError:
                    continue
    return trouvees


def vignette_externe(sortie, chemin, cote):
    """Copie réduite d'une photo hors de l'album (cache lié à la taille et à la date du fichier) ; None si
    illisible. L'original n'est que lu."""
    dossier = sortie / "vignettes_mosaique"
    dossier.mkdir(parents=True, exist_ok=True)
    try:
        etat = Path(chemin).stat()
        cible = dossier / f"ext_{hashlib.md5(f'{chemin}|{etat.st_size}|{etat.st_mtime}'.encode()).hexdigest()[:16]}_{cote}.jpg"
        if not cible.exists():
            with Image.open(chemin) as im:
                im.draft("RGB", (cote * 2, cote * 2))
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((cote, cote))
                im.save(cible, quality=90)
        return cible
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def preparer_petites(base, sortie, lignes, cote):
    """Petites photos carrées centrées sur les visages + leur signature de couleurs (cache dans
    vignettes_mosaique : un 2e passage est rapide)."""
    petites, signatures, utilisees = [], [], []
    for i, l in enumerate(lignes):
        af.progression("Préparation des petites photos", i + 1, len(lignes))
        taille = max(COTE_VIGNETTE, 2 * cote)
        chemin = (vignette_externe(sortie, l["fichier"], taille) if l.get("externe")
                  else af.apercu(base, sortie, l["fichier"], taille, "vignettes_mosaique"))
        if chemin is None:
            continue
        with Image.open(chemin) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
        visages = None if l.get("externe") else boite_visages(base, l["fichier"])
        carre = recadrer(im, 1.0, visages).resize((cote, cote), Image.LANCZOS)
        if cote >= 40:  # légère accentuation : chaque petite photo reste nette à l'impression
            carre = carre.filter(ImageFilter.UnsharpMask(radius=max(1, cote // 80), percent=60, threshold=2))
        petites.append(carre)
        signatures.append(signature(carre))
        utilisees.append(l)
    return petites, (np.stack(signatures) if signatures else np.zeros((0, GRILLE * GRILLE * 3))), utilisees


MEMOIRE_PETITES = 1200 * 1024 * 1024  # octets au plus pour les petites photos gardées en mémoire
MAX_PETITES = 5000  # au-delà, aucun gain visible : un échantillon varié suffit (et la préparation reste rapide)
MEMOIRE_DISTANCES = 64 * 1024 * 1024  # octets au plus pour les distances calculées d'un coup (par bloc de cases)


def attribuer(cibles, signatures, colonnes, lignes_grille, graine=7, ecart=VOISINAGE):
    """Pour chaque case, la photo la plus ressemblante ; pénalité pour une photo déjà très utilisée et jamais
    la même photo dans le voisinage (sinon des taches de photos identiques).
    Mémoire bornée : les distances sont calculées par blocs de cases (64 Mo au plus), jamais en une matrice
    complète cases x photos (qui dépasserait 4 Go en A0 dense avec 20 000 photos)."""
    n_cases, n_photos = len(cibles), len(signatures)
    signatures = np.ascontiguousarray(signatures, dtype=np.float32)
    s2 = (signatures ** 2).sum(axis=1)
    usages = np.zeros(n_photos, dtype=np.float32)
    choix = np.full((lignes_grille, colonnes), -1, dtype=np.int32)
    ordre = np.arange(n_cases)
    np.random.default_rng(graine).shuffle(ordre)  # au hasard : pas de « vague » de répétitions de haut en bas
    rayon = min(ecart, max(0, int(math.sqrt(n_photos / 4))))  # peu de photos : voisinage plus petit
    moyenne = n_cases / max(1, n_photos)
    bloc = max(1, min(4096, MEMOIRE_DISTANCES // (4 * 3 * max(1, n_photos))))  # ~3 tableaux de travail par bloc
    echelle = None
    for debut in range(0, n_cases, bloc):
        af.progression("Placement des photos", debut, n_cases)
        cases = ordre[debut:debut + bloc]
        c_bloc = cibles[cases].astype(np.float32)
        distances = c_bloc @ signatures.T  # (bloc x photos), réutilisé sur place
        distances *= -2
        distances += (c_bloc ** 2).sum(axis=1)[:, None]
        distances += s2[None, :]
        np.maximum(distances, 0, out=distances)
        np.sqrt(distances, out=distances)
        if echelle is None:  # échelle des distances, estimée sur le premier bloc
            echelle = float(np.median(distances)) or 1.0
        poids = 0.25 * echelle / moyenne
        for k, case in enumerate(cases):
            r, c = divmod(int(case), colonnes)
            voisines = set(choix[max(0, r - rayon):r + rayon + 1, max(0, c - rayon):c + rayon + 1].ravel()) - {-1}
            cout = distances[k] + poids * usages
            n = min(n_photos, len(voisines) + 1)
            candidates = np.argpartition(cout, n - 1)[:n] if n < n_photos else np.arange(n_photos)
            j = next(int(j) for j in candidates[np.argsort(cout[candidates])] if int(j) not in voisines) \
                if len(voisines) < n_photos else int(np.argmin(cout))
            choix[r, c] = j
            usages[j] += 1
    af.progression("Placement des photos", n_cases, n_cases)
    return choix, usages


JOINTS = {"aucun": None, "blanc-fin": ("#FFFFFF", 0.004), "blanc": ("#FFFFFF", 0.01), "noir-fin": ("#000000", 0.004),
          "noir": ("#000000", 0.01), "creme": ("#F4EBDD", 0.008)}  # couleur, épaisseur en part d'une case


def composer(master, petites, choix, cote, melange, correction=0.45, fondu="adaptatif", joint="aucun"):
    """Assemble la mosaïque case par case (mémoire limitée, même en A0).
    - chaque petite photo est teintée vers la couleur de sa case (correction : 0 = couleurs d'origine) ;
    - la photo master est fondue par-dessus : « naturel » (couleurs), « lumiere » (seulement la lumière : les
      petites photos gardent leurs couleurs), « adaptatif » (plus de master là où il y a des détails - yeux,
      bouche, contours - et moins dans les aplats : visage net de loin, photos bien visibles de près) ;
    - joint : fin liseré entre les cases (aucun, blanc-fin, blanc, noir-fin, noir, creme)."""
    lignes_grille, colonnes = choix.shape
    image = Image.new("RGB", (colonnes * cote, lignes_grille * cote))
    mw, mh = master.size
    moyennes = [np.asarray(p, dtype=np.float32).mean(axis=(0, 1)) for p in petites]
    poids = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    details = None
    if fondu == "adaptatif":  # quantité de détails de la master dans chaque case (écart de clarté)
        gris = np.asarray(master.convert("L").resize((colonnes * 8, lignes_grille * 8), Image.BOX), dtype=np.float32)
        details = gris.reshape(lignes_grille, 8, colonnes, 8).std(axis=(1, 3))
        details = details / (np.percentile(details, 90) or 1.0)
    ligne_joint = JOINTS.get(joint)
    for r in range(lignes_grille):
        af.progression("Assemblage", r + 1, lignes_grille)
        for c in range(colonnes):
            boite = (c * mw / colonnes, r * mh / lignes_grille, (c + 1) * mw / colonnes, (r + 1) * mh / lignes_grille)
            zone = np.asarray(master.resize((cote, cote), Image.BILINEAR, box=boite), dtype=np.float32)
            j = choix[r, c]
            photo = np.asarray(petites[j], dtype=np.float32)
            photo = photo + correction * (zone.mean(axis=(0, 1)) - moyennes[j])
            alpha = melange
            if details is not None:
                alpha = float(np.clip(melange * (0.65 + 0.7 * min(details[r, c], 1.5)), 0.05, 0.85))
            if fondu == "lumiere":  # seulement la clarté de la master : les couleurs des photos restent
                case = photo + alpha * ((zone @ poids) - (photo @ poids))[..., None]
            else:
                case = (1 - alpha) * photo + alpha * zone
            image.paste(Image.fromarray(np.clip(case, 0, 255).astype(np.uint8)), (c * cote, r * cote))
    if ligne_joint:
        teinte, part = ligne_joint
        epaisseur = max(1, round(cote * part))
        dessin = ImageDraw.Draw(image)
        for c in range(1, colonnes):
            dessin.rectangle((c * cote - epaisseur // 2, 0, c * cote + (epaisseur - 1) // 2, image.height), fill=teinte)
        for r in range(1, lignes_grille):
            dessin.rectangle((0, r * cote - epaisseur // 2, image.width, r * cote + (epaisseur - 1) // 2), fill=teinte)
    return image


POSITIONS = ["auto", "bas", "haut", "centre", "bas-gauche", "bas-droite", "haut-gauche", "haut-droite"]
TAILLES_TEXTE = {"petit": 0.035, "moyen": 0.055, "grand": 0.08, "tres-grand": 0.11}  # hauteur d'une ligne / largeur


def poser_texte(image, texte, position="auto", police="georgia", couleur="blanc", taille="moyen", style="ombre",
                marge=0.0, visages=None):
    """Texte par-dessus la mosaïque, net à toute taille (dessiné à la résolution finale).
    texte : « | » ou un retour à la ligne pour changer de ligne ; position : auto (là où il n'y a pas de visage),
    haut, bas, centre ou un coin ; style : ombre, contour, bandeau (bande translucide) ou aucun.
    marge : zone à laisser libre au bord (fond perdu + sécurité), en pixels ; visages : boîte (x0, y0, x1, y1)."""
    lignes = [l.strip() for l in texte.replace("\\n", "|").replace("\n", "|").split("|") if l.strip()]
    if not lignes:
        return image
    w, h = image.size
    part = TAILLES_TEXTE.get(taille)
    if part is None:
        try:
            part = float(str(taille).replace(",", ".").rstrip("%")) / 100
        except ValueError:
            part = TAILLES_TEXTE["moyen"]
    corps = max(10, round(w * part))
    teinte = pl.couleur(couleur) or "#FFFFFF"
    if teinte == "aucun":
        teinte = "#FFFFFF"
    clair = pl.clarte(teinte) > 128
    contraste = "#000000" if clair else "#FFFFFF"
    dessin = ImageDraw.Draw(image)
    largeur_max = w - 2 * marge - corps
    fonte = pl.police(police if police in pl.POLICES else "georgia", corps)
    while corps > 10 and max(dessin.textlength(l, font=fonte) for l in lignes) > largeur_max:  # texte trop long
        corps = int(corps * 0.92)
        fonte = pl.police(police if police in pl.POLICES else "georgia", corps)
    interligne = round(corps * 1.18)
    lt = max(dessin.textlength(l, font=fonte) for l in lignes)
    ht = interligne * len(lignes)
    bord = marge + corps * 0.8
    places = {
        "haut": ((w - lt) / 2, bord), "bas": ((w - lt) / 2, h - bord - ht), "centre": ((w - lt) / 2, (h - ht) / 2),
        "haut-gauche": (bord, bord), "haut-droite": (w - bord - lt, bord),
        "bas-gauche": (bord, h - bord - ht), "bas-droite": (w - bord - lt, h - bord - ht),
    }
    if position not in places:  # auto : la place qui recouvre le moins les visages (le bas à égalité)
        def gene(nom):
            x, y = places[nom]
            if not visages:
                return 0
            ix = max(0, min(x + lt, visages[2]) - max(x, visages[0]))
            iy = max(0, min(y + ht, visages[3]) - max(y, visages[1]))
            return ix * iy
        position = min(["bas", "haut", "bas-gauche", "bas-droite", "haut-gauche", "haut-droite"], key=gene)
    x, y = places[position]
    alignement = "left" if "gauche" in position else "right" if "droite" in position else "center"

    def x_ligne(l):
        lg = dessin.textlength(l, font=fonte)
        return x if alignement == "left" else x + lt - lg if alignement == "right" else x + (lt - lg) / 2

    if style == "bandeau":  # bande translucide derrière le texte
        calque = Image.new("RGBA", image.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(calque)
        fond = (0, 0, 0, 115) if clair else (255, 255, 255, 150)
        pad = corps * 0.45
        if position in ("haut", "bas", "centre"):
            d.rectangle((0, y - pad, w, y + ht + pad * 0.6), fill=fond)
        else:
            d.rounded_rectangle((x - pad, y - pad, x + lt + pad, y + ht + pad * 0.6), radius=pad, fill=fond)
        image = Image.alpha_composite(image.convert("RGBA"), calque).convert("RGB")
        dessin = ImageDraw.Draw(image)
    if style == "ombre":  # ombre douce : lisible sur toutes les photos
        ombre = Image.new("L", image.size, 0)
        d = ImageDraw.Draw(ombre)
        decalage = max(1, corps // 22)
        for i, l in enumerate(lignes):
            d.text((x_ligne(l) + decalage, y + i * interligne + decalage), l, font=fonte, fill=200)
        ombre = ombre.filter(ImageFilter.GaussianBlur(max(1, corps // 14)))
        image = Image.composite(Image.new("RGB", image.size, contraste), image, ombre)
        dessin = ImageDraw.Draw(image)
    epaisseur = max(1, corps // 28) if style == "contour" else 0
    for i, l in enumerate(lignes):
        dessin.text((x_ligne(l), y + i * interligne), l, font=fonte, fill=teinte,
                    stroke_width=epaisseur, stroke_fill=contraste)
    return image


def profil_srgb():
    """Profil couleur sRGB intégré au JPEG : l'imprimeur reproduit les couleurs telles qu'à l'écran."""
    try:
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    except Exception:  # Pillow sans LittleCMS : fichier sans profil (sRGB supposé par les imprimeurs)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sortie", type=Path, default=Path("albums_sortie"))
    parser.add_argument("--personne", required=True)
    parser.add_argument("--master", default="", help="photo à reconstituer (sinon : choix de l'écran, ou couverture)")
    parser.add_argument("--format", choices=sorted(FORMATS), default="a3-portrait")
    parser.add_argument("--colonnes", type=int, default=60, help="nombre de petites photos en largeur (20 à 150)")
    parser.add_argument("--melange", type=float, default=0.35,
                        help="part de la photo master fondue par-dessus (0 à 0.7 ; 0.35 par défaut)")
    parser.add_argument("--photos", choices=["gardees", "toutes", "dossier", "gardees+dossier", "toutes+dossier"],
                        default="gardees", help="petites photos : gardées pour le livre, toutes celles de la personne, "
                        "celles d'un autre dossier (--dossier), ou l'album + ce dossier")
    parser.add_argument("--dossier", default="", help="autre dossier de photos (lecture seule), avec --photos dossier")
    parser.add_argument("--fondu", choices=["adaptatif", "naturel", "lumiere"], default="adaptatif",
                        help="adaptatif (conseillé : plus de détails sur yeux et bouche), naturel, lumiere (les "
                        "petites photos gardent leurs couleurs)")
    parser.add_argument("--teinte", type=float, default=0.45,
                        help="petites photos teintées vers la couleur de leur case (0 = couleurs d'origine, 0.7 fort)")
    parser.add_argument("--joint", choices=sorted(JOINTS), default="aucun", help="liseré entre les cases")
    parser.add_argument("--ecart", type=int, default=VOISINAGE,
                        help="une même photo n'est pas reprise à moins de N cases (3 par défaut)")
    parser.add_argument("--fond-perdu", type=float, default=3.0,
                        help="fond perdu en mm de chaque côté, demandé par les imprimeurs (0 = aucun)")
    parser.add_argument("--texte", default="", help="texte par-dessus la photo (« | » = nouvelle ligne)")
    parser.add_argument("--texte-position", choices=POSITIONS, default="auto")
    parser.add_argument("--texte-police", choices=sorted(pl.POLICES), default="georgia")
    parser.add_argument("--texte-couleur", default="blanc")
    parser.add_argument("--texte-taille", default="moyen", help="petit, moyen, grand, tres-grand ou un %% de la largeur")
    parser.add_argument("--texte-style", choices=["ombre", "contour", "bandeau", "aucun"], default="ombre")
    parser.add_argument("--apercu", action="store_true",
                        help="aperçu rapide : mêmes réglages, petite image (quelques secondes), rien pour l'imprimeur")
    parser.add_argument("--dpi", default="auto", help="résolution d'impression : auto (300 jusqu'au A2, 200 en A1, "
                        "150 en A0) ou un nombre (100 à 300)")
    args = parser.parse_args()
    if not 10 <= args.colonnes <= 200:
        sys.exit("--colonnes : entre 10 et 200.")
    melange = min(max(args.melange, 0.0), 0.8)

    base = af.ouvrir_base(args.sortie)
    dossier = lp.dossier_livre(args.sortie, args.personne)
    sujet = dossier.name[len("livre_"):]
    fichier = dossier / "selection_livre.csv"
    if args.dossier.strip() and args.photos in ("gardees", "toutes"):
        args.photos = "dossier"  # dossier de miniatures rempli : les petites photos viennent de ce dossier
    if not args.dossier.strip() and args.photos.endswith("dossier") and args.photos != "dossier":
        args.photos = args.photos.split("+")[0]  # « + dossier » sans dossier : l'album seul
    avec_album = args.photos != "dossier"
    lignes = []
    if avec_album:
        if not fichier.exists():
            sys.exit("Lancez d'abord « Préparer la sélection » (ou MOSAIQUE_PHOTOS = dossier, avec un dossier de "
                     "photos).")
        lignes = af.lire_csv(fichier)
        if args.photos.startswith("gardees"):
            lignes = [l for l in lignes if garde(l)]
        else:
            lignes = [l for l in lignes if not (l.get("remarque") or "").startswith("pas ")]  # « pas Laura » exclues
        lignes = af.retirer_absentes(base, lignes, "fichier")
    if args.photos.endswith("dossier"):
        autre = Path(args.dossier.strip().strip('"')) if args.dossier.strip() else None
        if autre is None or not autre.is_dir():
            sys.exit(f"Dossier des photos en miniature introuvable : « {args.dossier} » (MOSAIQUE_DOSSIER).")
        externes = photos_du_dossier(autre, exclure=args.sortie)
        print(f"Dossier des photos en miniature : {autre} ({len(externes)} photos, lecture seule)")
        lignes += externes
    if len(lignes) < 20:
        sys.exit(f"Seulement {len(lignes)} photo(s) : il en faut au moins 20 (idéalement 150 ou plus) pour une "
                 "mosaïque. Essayez MOSAIQUE_PHOTOS = toutes, ou ajoutez un dossier de photos.")

    chemin_master, relatif_master = lire_master(base, dossier, sujet, args.master)
    print(f"Photo master : {relatif_master or chemin_master}")
    with Image.open(chemin_master) as im:  # lecture seule de l'original
        im.draft("RGB", (6000, 6000))
        master = ImageOps.exif_transpose(im).convert("RGB")
    if isinstance(FORMATS[args.format], int):  # proportions de la photo master, largeur donnée
        largeur_mm = FORMATS[args.format]
        hauteur_mm = largeur_mm * master.height / master.width
    else:
        largeur_mm, hauteur_mm = FORMATS[args.format]
    perdu = max(0.0, args.fond_perdu)
    format_mm = (largeur_mm, hauteur_mm)
    largeur_mm, hauteur_mm = largeur_mm + 2 * perdu, hauteur_mm + 2 * perdu  # le fichier inclut le fond perdu
    dpi = dpi_auto(*format_mm) if str(args.dpi).lower() in ("", "auto") else int(args.dpi)
    dpi = min(max(dpi, 72), 300)
    args.dpi = dpi
    largeur_px = round(largeur_mm / 25.4 * dpi)
    cote = max(8, largeur_px // args.colonnes)  # côté d'une petite photo, en pixels
    cote_reel = cote
    if args.apercu:  # même grille, petites photos de 16 à 40 px : l'image fait au plus ~1600 px
        cote = min(cote, max(16, 1600 // max(args.colonnes, round(args.colonnes * hauteur_mm / largeur_mm))))
    colonnes = args.colonnes
    lignes_grille = max(1, round(args.colonnes * hauteur_mm / largeur_mm))
    boite = boite_visages(base, relatif_master)
    mw0, mh0 = master.size
    fenetre = fenetre_recadrage(master.size, colonnes / lignes_grille, boite)
    master = master.crop(fenetre)
    visages_master = None  # visages de la master dans la mosaïque (en part de l'image), pour placer le texte
    if boite:
        fw, fh = fenetre[2] - fenetre[0], fenetre[3] - fenetre[1]
        visages_master = ((boite[0] * mw0 - fenetre[0]) / fw, (boite[1] * mh0 - fenetre[1]) / fh,
                          (boite[2] * mw0 - fenetre[0]) / fw, (boite[3] * mh0 - fenetre[1]) / fh)

    print(f"Mosaïque {args.format} à {dpi} dpi : {colonnes} x {lignes_grille} = {colonnes * lignes_grille} cases de "
          f"{cote_reel * 25.4 / dpi:.1f} mm ({cote_reel} px : chaque petite photo est nette), avec {len(lignes)} photos ; "
          f"photo master fondue à {melange:.0%}.")
    if colonnes * lignes_grille > 12 * len(lignes):
        print(f"  Conseil : chaque photo servira environ {colonnes * lignes_grille // len(lignes)} fois. Pour plus "
              "de variété : moins de colonnes, ou MOSAIQUE_PHOTOS = toutes.")

    plafond = max(20, min(MAX_PETITES, MEMOIRE_PETITES // (cote * cote * 3)))
    if len(lignes) > plafond:  # mémoire bornée : échantillon tiré au hasard (toujours le même), réparti sur tout
        tirage = np.random.default_rng(11).choice(len(lignes), plafond, replace=False)
        print(f"  {len(lignes)} photos disponibles : {plafond} tirées au hasard suffisent (mémoire limitée à "
              f"{MEMOIRE_PETITES // 2 ** 20} Mo pour les petites photos de {cote} px).")
        lignes = [lignes[i] for i in sorted(tirage)]
    petites, signatures, utilisees = preparer_petites(base, args.sortie, lignes, cote)
    if len(petites) < 20:
        sys.exit("Trop peu de photos lisibles sur le disque pour une mosaïque.")
    vue = master.resize((colonnes * GRILLE, lignes_grille * GRILLE), Image.BOX)
    cibles = np.stack([signature(vue.crop((c * GRILLE, r * GRILLE, (c + 1) * GRILLE, (r + 1) * GRILLE)))
                       for r in range(lignes_grille) for c in range(colonnes)])
    choix, usages = attribuer(cibles, signatures, colonnes, lignes_grille, ecart=max(0, args.ecart))
    image = composer(master, petites, choix, cote, melange, min(max(args.teinte, 0), 0.9), args.fondu, args.joint)
    if args.texte.strip():
        px_mm = image.width / largeur_mm
        boite_px = None if visages_master is None else tuple(
            v * (image.width if i % 2 == 0 else image.height) for i, v in enumerate(visages_master))
        image = poser_texte(image, args.texte, args.texte_position, args.texte_police, args.texte_couleur,
                            args.texte_taille, args.texte_style, marge=(perdu + 8) * px_mm, visages=boite_px)

    cible = dossier / "mosaique"
    cible.mkdir(exist_ok=True)
    nom = f"Mosaique_{sujet}"
    if args.apercu:  # aperçu rapide : une image pour l'écran (JPEG) et une petite pour l'application (PNG)
        image.save(cible / f"{nom}_apercu_rapide.jpg", quality=88)
        petit = image.copy()
        petit.thumbnail((340, 440))
        petit.save(cible / "apercu_application.png")
        print(f"Aperçu rapide : {cible / (nom + '_apercu_rapide.jpg')}  ({colonnes} x {lignes_grille} photos ; "
              f"le poster fera {format_mm[0] / 10:.0f} x {format_mm[1] / 10:.0f} cm)")
        print(f"Photos utilisées : {int((usages > 0).sum())} sur {len(utilisees)} (au plus {int(usages.max())} fois "
              "la même). Si le rendu vous plaît : « Créer la mosaïque ».")
        return
    # résolution notée dans le fichier : exactement le format demandé à l'impression (la grille arrondit au pixel)
    args.dpi = image.width / (largeur_mm / 25.4)
    icc = profil_srgb()
    options = {"icc_profile": icc} if icc else {}
    image.save(cible / f"{nom}.jpg", quality=95, subsampling=0, dpi=(args.dpi, args.dpi), **options)
    image.save(cible / f"{nom}.pdf", resolution=args.dpi)  # même image, au format exact (fond perdu compris)
    apercu = image.copy()
    apercu.thumbnail((1600, 1600))
    apercu.save(cible / f"{nom}_apercu.jpg", quality=88)
    zoom = image.crop((image.width // 2 - 6 * cote, image.height // 3 - 4 * cote,
                       image.width // 2 + 6 * cote, image.height // 3 + 4 * cote))
    zoom.save(cible / f"{nom}_detail.jpg", quality=90)
    with open(cible / f"{nom}_photos.csv", "w", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.writer(f, delimiter=";")
        ecrivain.writerow(["fichier", "date", "nombre de cases"])
        for l, n in sorted(zip(utilisees, usages), key=lambda x: -x[1]):
            ecrivain.writerow([l["fichier"], l.get("date", ""), int(n)])
    print(f"Photos utilisées : {int((usages > 0).sum())} sur {len(utilisees)} "
          f"(au plus {int(usages.max())} fois la même).")
    print(f"Mosaïque : {cible / (nom + '.jpg')} et .pdf ({image.width} x {image.height} px à {args.dpi:.0f} dpi, "
          f"profil sRGB) : format {format_mm[0] / 10:.1f} x {format_mm[1] / 10:.1f} cm"
          + (f" + {perdu:g} mm de fond perdu de chaque côté (à rogner par l'imprimeur ; le texte reste à "
             "l'intérieur)" if perdu else ""))
    print(f"Aperçu   : {cible / (nom + '_apercu.jpg')}  ·  détail de près : {nom}_detail.jpg")


if __name__ == "__main__":
    main()
