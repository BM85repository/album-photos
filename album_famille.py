#!/usr/bin/env python3
"""album_famille.py - reconnaître ses proches sur un disque de backup et en faire des albums.

LECTURE SEULE : les photos du disque de backup ne sont jamais modifiées, déplacées,
renommées ni supprimées. Tout ce que produit l'outil (base, rapports, copies, albums)
est écrit dans le dossier --sortie, qui doit être en dehors du disque de photos.
Tout tourne en local : aucune photo ni donnée de visage n'est envoyée en ligne.

Étapes :
  1. analyser      lit dates, GPS, netteté, doublons et visages de toutes les photos du disque
  2. trier         rapport_tri.csv : doublons, photos floues, photos sans date (rapport seulement)
  3. selectionner  reconnaît la famille et propose les photos essentielles (selection.csv + planche.html)
  4. extraire      copie les photos retenues, par personne et par souvenir, pour un montage ailleurs
  5. album         un album par personne : PDF prêt à imprimer et PowerPoint modifiable

Pour un livre photo complet d'une personne (150 photos, mise en page soignée) : voir livre_photo.py.

Voir le guide 20261029-Photos-2_Guide.md pour le détail.
"""
import argparse
import csv
import datetime as dt
import hashlib
import html
import math
import re
import shutil
import sqlite3
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import os

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")  # masque les avertissements internes d'OpenCV (sans conséquence)

import cv2  # noqa: E402  (doit être importé après le réglage ci-dessus)
import numpy as np
from PIL import Image, ImageOps

try:
    import pillow_heif  # photos iPhone (.heic)

    pillow_heif.register_heif_opener()
except ImportError:
    pillow_heif = None

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif"}
MODELES = {
    "detection": (
        "face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    ),
    "reconnaissance": (
        "face_recognition_sface_2021dec.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    ),
}
SEUIL_VISAGE = 0.40  # similarité cosinus ; OpenCV conseille 0.363, un peu plus strict ici
TAILLE_MIN_VISAGE = 40  # pixels, sur une image ramenée à 1600 px
SEUIL_FLOU = 60.0  # variance du laplacien sous laquelle une photo est jugée floue
SEUIL_DOUBLON = 6  # distance de Hamming maximale entre deux empreintes dHash
ECART_EVENEMENT_H = 6  # au-delà de 6 h sans photo, on considère un nouveau souvenir
COTE_MIN_PHOTO = 400  # en dessous : vignette ou miniature de logiciel, ignorée
COTE_IMPRESSION = 2400  # pixels du grand côté pour l'album (≈ 20 cm à 300 dpi)
DOSSIERS_IGNORES = {"$recycle.bin", "system volume information", "@eadir", "thumbnails"}
CARACTERES_INTERDITS = re.compile(r'[<>:"/\\|?*]')
MOTIF_DATE_NOM = re.compile(r"((?:19|20)\d{2})[-_.]?(\d{2})[-_.]?(\d{2})")


# --------------------------------------------------------------------------- base de données

def ouvrir_base(sortie):
    sortie.mkdir(parents=True, exist_ok=True)
    base = sqlite3.connect(sortie / "base.sqlite")
    base.row_factory = sqlite3.Row
    try:  # à chaque ouverture (toutes les étapes) : jamais de dossier de travail dans le dossier des photos
        racine = base.execute("SELECT valeur FROM meta WHERE cle = 'racine'").fetchone()
    except sqlite3.OperationalError:  # base neuve : pas encore de table meta
        racine = None
    if racine:
        verifier_sortie(Path(racine[0]).resolve(), sortie)
    base.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT);
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY, chemin TEXT UNIQUE, taille INTEGER, mtime REAL,
            date TEXT, source_date TEXT, lat REAL, lon REAL, lieu TEXT,
            nettete REAL, luminosite REAL, dhash TEXT, nb_visages INTEGER);
        CREATE TABLE IF NOT EXISTS visages (
            id INTEGER PRIMARY KEY, photo_id INTEGER, x REAL, y REAL, l REAL, h REAL, emb BLOB);
        CREATE INDEX IF NOT EXISTS idx_visages_photo ON visages(photo_id);
        CREATE TABLE IF NOT EXISTS confirmations (
            visage_id INTEGER, nom TEXT, ok INTEGER, PRIMARY KEY (visage_id, nom));
        """
    )
    colonnes = {c[1] for c in base.execute("PRAGMA table_info(photos)")}
    for colonne in ("largeur_orig", "hauteur_orig"):  # bases créées avant la version livre
        if colonne not in colonnes:
            base.execute(f"ALTER TABLE photos ADD COLUMN {colonne} INTEGER")
    return base


def meta(base, cle, valeur=None):
    if valeur is not None:
        base.execute("REPLACE INTO meta VALUES (?, ?)", (cle, str(valeur)))
        return valeur
    ligne = base.execute("SELECT valeur FROM meta WHERE cle = ?", (cle,)).fetchone()
    return ligne[0] if ligne else None


# --------------------------------------------------------------------------- modèles visages

def modeles(sortie):
    dossier = sortie / "modeles"
    dossier.mkdir(parents=True, exist_ok=True)
    chemins = {}
    for cle, (nom, url) in MODELES.items():
        chemin = dossier / nom
        if not chemin.exists():
            print(f"Téléchargement du modèle {nom}...")
            urllib.request.urlretrieve(url, chemin)
        chemins[cle] = str(chemin)
    detecteur = cv2.FaceDetectorYN.create(chemins["detection"], "", (320, 320), 0.9, 0.3, 5000)
    reco = cv2.FaceRecognizerSF.create(chemins["reconnaissance"], "")
    return detecteur, reco


def detecter_visages(bgr, detecteur, reco):
    """Renvoie [(x, y, l, h relatifs, empreinte normalisée)] pour chaque visage assez grand."""
    hauteur, largeur = bgr.shape[:2]
    detecteur.setInputSize((largeur, hauteur))
    _, visages = detecteur.detect(bgr)
    resultat = []
    for v in visages if visages is not None else []:
        if v[2] < TAILLE_MIN_VISAGE or v[3] < TAILLE_MIN_VISAGE:
            continue
        emb = reco.feature(reco.alignCrop(bgr, v)).flatten().astype(np.float32)
        emb /= np.linalg.norm(emb) or 1.0
        resultat.append((v[0] / largeur, v[1] / hauteur, v[2] / largeur, v[3] / hauteur, emb))
    return resultat


# --------------------------------------------------------------------------- lecture des photos

def charger(chemin, cote_max=1600):
    """Ouvre une photo dans le bon sens (Pillow gère les chemins accentués sous Windows)."""
    with Image.open(chemin) as im:  # ouverture en lecture seule
        exif = im.getexif()
        im = ImageOps.exif_transpose(im).convert("RGB")
    taille_origine = im.size
    im.thumbnail((cote_max, cote_max))
    return im, exif, taille_origine


def degres(valeur):
    d, m, s = (float(x) for x in valeur)
    resultat = d + m / 60 + s / 3600
    return None if math.isnan(resultat) else resultat


def lire_exif(exif):
    sous_ifd = exif.get_ifd(0x8769)
    brut = sous_ifd.get(36867) or sous_ifd.get(36868) or exif.get(306)
    date = None
    if brut:
        try:
            date = dt.datetime.strptime(str(brut).strip("\x00 ")[:19], "%Y:%m:%d %H:%M:%S")
        except ValueError:
            pass
    lat = lon = None
    gps = exif.get_ifd(0x8825)
    try:
        if 2 in gps and 4 in gps:
            lat, lon = degres(gps[2]), degres(gps[4])
            if lat is not None and lon is not None:
                lat *= -1 if str(gps.get(1, "N")).upper().startswith("S") else 1
                lon *= -1 if str(gps.get(3, "E")).upper().startswith("W") else 1
            if not lat and not lon:
                lat = lon = None
    except (TypeError, ValueError, ZeroDivisionError):
        lat = lon = None
    return date, lat, lon


def date_depuis_nom(nom):
    """IMG_20190612_..., IMG-20190612-WA0001 (WhatsApp), 2019-06-12 ..."""
    for annee, mois, jour in MOTIF_DATE_NOM.findall(nom):
        try:
            return dt.datetime(int(annee), int(mois), int(jour), 12)
        except ValueError:
            continue
    return None


def mesures(image):
    gris = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    hauteur, largeur = gris.shape
    normalise = cv2.resize(gris, (1000, max(1, round(1000 * hauteur / largeur))))
    nettete = float(cv2.Laplacian(normalise, cv2.CV_64F).var())
    luminosite = float(normalise.mean())
    petit = cv2.resize(gris, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (petit[:, 1:] > petit[:, :-1]).flatten()
    empreinte = int("".join("1" if b else "0" for b in bits), 2)
    return nettete, luminosite, f"{empreinte:016x}"


def distance(h1, h2):
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def bits_differents(empreintes, h):
    """Nombre de bits différents entre une empreinte h et chacune d'un tableau d'empreintes (uint64), en une fois."""
    ecarts = np.bitwise_xor(empreintes, np.uint64(h))
    if hasattr(np, "bitwise_count"):
        return np.bitwise_count(ecarts)
    return np.unpackbits(ecarts.view(np.uint8).reshape(-1, 8), axis=1).sum(axis=1)


def bits(h):
    """Empreinte en nombre entier (calculée une fois par photo, au lieu d'une fois par comparaison)."""
    try:
        return int(h, 16) if h else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- 1. analyser

_PROGRESSION = {}


def progression(etape, fait, total=None):
    """Avancement d'une étape longue, lu par l'application (barre et temps restant) : une ligne
    « PROGRESSION fait/total étape », au plus deux fois par seconde (et toujours à la fin)."""
    maintenant = time.monotonic()
    if fait != total and maintenant - _PROGRESSION.get(etape, 0) < 0.5:
        return
    _PROGRESSION[etape] = maintenant
    print(f"PROGRESSION {fait}/{total if total else '?'} {etape}", flush=True)


def lister_photos(racine):
    """Chemins des photos (texte), dans l'ordre alphabétique, dossier par dossier. Les dossiers ignorés ne sont
    même pas parcourus, et seuls des textes sont gardés en mémoire (bien plus léger que des objets Path)."""
    vus = 0
    for dossier, sous_dossiers, fichiers in os.walk(racine):
        sous_dossiers[:] = sorted(d for d in sous_dossiers
                                  if d.lower() not in DOSSIERS_IGNORES and not d.startswith("."))
        for nom in sorted(fichiers):
            vus += 1
            progression("Inventaire du disque", vus)
            if os.path.splitext(nom)[1].lower() in EXTENSIONS and not nom.startswith("._"):
                yield os.path.join(dossier, nom)


def verifier_sortie(racine, sortie):
    sortie = Path(sortie).resolve()
    racine = Path(racine).resolve()
    if sortie == racine or racine in sortie.parents or sortie in racine.parents:
        sys.exit(f"Le dossier de sortie {sortie} est dans le dossier de photos : choisissez-en un autre, "
                 "l'outil n'écrit jamais sur le disque de backup.")


def original(base, relatif):
    """Chemin réel d'une photo ; les chemins sont relatifs pour survivre à un changement de lettre de disque."""
    racine = Path(meta(base, "racine"))
    if not racine.exists():
        sys.exit(f"Disque de photos introuvable ({racine}). Branchez-le, ou relancez "
                 "« analyser <nouveau chemin> » si sa lettre a changé (rien ne sera recalculé).")
    return racine / relatif


def cmd_analyser(args):
    racine = Path(args.photos).resolve()
    if not racine.is_dir():
        sys.exit(f"Dossier introuvable : {racine}")
    verifier_sortie(racine, args.sortie)
    base = ouvrir_base(args.sortie)
    meta(base, "racine", racine)
    base.commit()
    detecteur, reco = modeles(args.sortie)
    print(f"Recherche des photos dans {racine} (lecture seule)...")
    # une seule liste de chemins relatifs (texte) en mémoire, même pour des millions de fichiers
    prefixe = len(str(racine).rstrip("\\/")) + 1
    fichiers = [c[prefixe:].replace(os.sep, "/") for c in lister_photos(racine)]
    print(f"{len(fichiers)} photos trouvées")
    # photos disparues du disque depuis la dernière analyse : retirées de la base (sauf si c'est la majorité,
    # signe d'un mauvais dossier ou d'un disque incomplet : on ne touche alors à rien). La comparaison se fait
    # dans la base (table temporaire) plutôt qu'avec de grands ensembles Python.
    base.execute("CREATE TEMP TABLE IF NOT EXISTS trouvees (chemin TEXT PRIMARY KEY) WITHOUT ROWID")
    base.execute("DELETE FROM trouvees")
    for debut in range(0, len(fichiers), 50_000):
        base.executemany("INSERT OR IGNORE INTO trouvees VALUES (?)", ((c,) for c in fichiers[debut:debut + 50_000]))
    nombre_connues = base.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
    disparues = [l[0] for l in base.execute(
        "SELECT id FROM photos WHERE chemin NOT IN (SELECT chemin FROM trouvees)")]
    base.execute("DELETE FROM trouvees")
    if disparues and len(disparues) <= nombre_connues // 2:
        base.executemany("DELETE FROM visages WHERE photo_id = ?", [(i,) for i in disparues])
        base.executemany("DELETE FROM photos WHERE id = ?", [(i,) for i in disparues])
        base.commit()
        print(f"{len(disparues)} photo(s) qui ne sont plus sur le disque retirée(s) de la base")
    elif disparues:
        print(f"ATTENTION : {len(disparues)} photos de la base introuvables dans {racine} (plus de la moitié) : "
              "base laissée telle quelle. Vérifiez le dossier des photos.")
    nouvelles = erreurs = petites = 0
    for i, relatif in enumerate(fichiers, 1):
        progression("Analyse des photos", i, len(fichiers))
        chemin = racine / relatif
        try:
            stat = chemin.stat()
            connue = base.execute("SELECT id, taille, mtime FROM photos WHERE chemin = ?", (relatif,)).fetchone()
            if connue and connue["taille"] == stat.st_size and connue["mtime"] == stat.st_mtime:
                continue
            image, exif, taille = charger(chemin)
        except Exception as exc:  # fichier corrompu, format non lu, disque débranché...
            erreurs += 1
            print(f"  ignorée : {relatif} ({exc})")
            continue
        if min(taille) < COTE_MIN_PHOTO:
            petites += 1
            continue
        date, lat, lon = lire_exif(exif)
        source = "exif"
        if date is None:
            date, source = date_depuis_nom(chemin.name), "nom"
        if date is None:
            date, source = dt.datetime.fromtimestamp(stat.st_mtime), "fichier"
        try:
            nettete, luminosite, empreinte = mesures(image)
            visages = detecter_visages(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), detecteur, reco)
        except Exception as exc:  # une photo atypique ne doit pas arrêter des heures d'analyse
            erreurs += 1
            print(f"  ignorée : {relatif} (analyse impossible : {exc})")
            continue
        if connue:
            base.execute("DELETE FROM visages WHERE photo_id = ?", (connue["id"],))
            base.execute("DELETE FROM photos WHERE id = ?", (connue["id"],))
        curseur = base.execute(
            "INSERT INTO photos (chemin, taille, mtime, date, source_date, lat, lon, nettete, luminosite, dhash,"
            " nb_visages, largeur_orig, hauteur_orig) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (relatif, stat.st_size, stat.st_mtime, date.isoformat(), source, lat, lon,
             nettete, luminosite, empreinte, len(visages), taille[0], taille[1]),
        )
        base.executemany(
            "INSERT INTO visages (photo_id, x, y, l, h, emb) VALUES (?, ?, ?, ?, ?, ?)",
            [(curseur.lastrowid, float(x), float(y), float(l), float(h), emb.tobytes()) for x, y, l, h, emb in visages],
        )
        nouvelles += 1
        if nouvelles % 50 == 0:
            base.commit()
            print(f"  {i}/{len(fichiers)} lues")
    base.commit()
    geocoder(base)
    total, avec_visage = base.execute("SELECT COUNT(*), SUM(nb_visages > 0) FROM photos").fetchone()
    print(f"Terminé : {nouvelles} photos analysées, {erreurs} illisibles, {petites} miniatures ignorées.")
    print(f"Base : {total} photos, dont {avec_visage or 0} avec au moins un visage détecté.")
    print(f"Base : {args.sortie / 'base.sqlite'}  (aucun fichier du disque n'a été modifié)")


def geocoder(base):
    """Transforme les coordonnées GPS en nom de commune, hors ligne."""
    lignes = base.execute("SELECT id, lat, lon FROM photos WHERE lat IS NOT NULL AND lieu IS NULL").fetchall()
    if not lignes:
        return
    import reverse_geocode

    resultats = reverse_geocode.search([(l["lat"], l["lon"]) for l in lignes])
    for ligne, r in zip(lignes, resultats):
        lieu = ", ".join(x for x in (r.get("city"), r.get("county") or r.get("state")) if x) + f" ({r.get('country_code')})"
        base.execute("UPDATE photos SET lieu = ? WHERE id = ?", (lieu, ligne["id"]))
    base.commit()


# --------------------------------------------------------------------------- souvenirs, scores, doublons

def charger_photos(base):
    photos = [dict(l) for l in base.execute("SELECT * FROM photos")]
    for p in photos:
        p["date"] = dt.datetime.fromisoformat(p["date"])
    photos.sort(key=lambda p: p["date"])
    largeurs = defaultdict(float)
    for v in base.execute("SELECT photo_id, l FROM visages"):
        largeurs[v["photo_id"]] = max(largeurs[v["photo_id"]], v["l"])
    numero, precedente = 0, None
    for p in photos:
        if precedente is None or (p["date"] - precedente).total_seconds() > ECART_EVENEMENT_H * 3600:
            numero += 1
        p["evenement"], precedente = numero, p["date"]
        p["flou"] = p["nettete"] < SEUIL_FLOU
        p["largeur_visage"] = largeurs[p["id"]]
    lieux = defaultdict(Counter)
    for p in photos:
        if p["lieu"]:
            lieux[p["evenement"]][p["lieu"]] += 1
    for p in photos:
        p["lieu_evenement"] = lieux[p["evenement"]].most_common(1)[0][0] if lieux[p["evenement"]] else ""
    return photos


def score(photo, largeur_visage):
    s_nettete = min(1.0, math.log10(photo["nettete"] + 1) / 3)
    s_lumiere = 1.0 if 50 <= photo["luminosite"] <= 205 else 0.5
    s_visage = min(1.0, largeur_visage * 4)  # un visage sur 25 % de la largeur vaut le maximum
    return round(0.5 * s_nettete + 0.2 * s_lumiere + 0.3 * s_visage, 3)


def marquer_doublons(photos, largeur=lambda p: p["largeur_visage"]):
    """Dans chaque souvenir, garde la meilleure photo d'une rafale et marque les autres."""
    par_evenement = defaultdict(list)
    for p in photos:
        p["score"] = score(p, largeur(p))
        p["doublon_de"] = ""
        par_evenement[p["evenement"]].append(p)
    for groupe in par_evenement.values():
        # empreintes des photos retenues dans un tableau : chaque nouvelle photo est comparée à toutes d'un coup
        # (calcul vectoriel), ce qui reste rapide même pour une rafale de milliers de photos
        empreintes = np.zeros(len(groupe), dtype=np.uint64)
        retenues, n = [], 0
        for p in sorted(groupe, key=lambda q: -q["score"]):
            h = bits(p["dhash"])
            meilleure = None
            if h is not None and n:
                differences = bits_differents(empreintes[:n], h)
                proches = np.flatnonzero(differences <= SEUIL_DOUBLON)
                if proches.size:
                    meilleure = retenues[proches[0]]
            if meilleure:
                p["doublon_de"] = Path(meilleure["chemin"]).name
            elif h is not None:
                empreintes[n] = h
                retenues.append(p)
                n += 1


def date_fr(d):
    return d.strftime("%d/%m/%Y")


def ecrire_csv(chemin, entetes, lignes):
    # « ; » et UTF-8 avec BOM : s'ouvre correctement dans Excel en français
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.writer(f, delimiter=";")
        ecrivain.writerow(entetes)
        ecrivain.writerows(lignes)


def lire_csv(chemin):
    with open(chemin, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


# --------------------------------------------------------------------------- 2. trier

def cmd_trier(args):
    base = ouvrir_base(args.sortie)
    photos = charger_photos(base)
    marquer_doublons(photos)
    lignes = [
        (p["chemin"], date_fr(p["date"]), p["source_date"], p["lieu"] or "", p["evenement"],
         round(p["nettete"]), "oui" if p["flou"] else "", p["doublon_de"])
        for p in photos
    ]
    ecrire_csv(args.sortie / "rapport_tri.csv",
               ["fichier", "date", "source_date", "lieu", "souvenir", "nettete", "flou", "doublon_de"],
               lignes)
    doublons = sum(1 for p in photos if p["doublon_de"])
    print(f"{len(photos)} photos, {photos[-1]['evenement'] if photos else 0} souvenirs")
    print(f"  doublons / rafales : {doublons}")
    print(f"  floues             : {sum(p['flou'] for p in photos)}")
    print(f"  date incertaine    : {sum(p['source_date'] == 'fichier' for p in photos)}")
    print(f"  sans lieu GPS      : {sum(not p['lieu'] for p in photos)}")
    print(f"Rapport : {args.sortie / 'rapport_tri.csv'} (rapport seulement : rien n'est modifié sur le disque)")


# --------------------------------------------------------------------------- 3. selectionner

def references(dossier_famille, detecteur, reco):
    """famille/Prénom/*.jpg : 3 à 20 photos nettes du visage de chaque personne (à des âges différents).
    Contrôles : une photo avec plusieurs visages ne sert que si le plus grand est nettement le plus grand ;
    une référence qui ne ressemble pas aux autres de la même personne (autre personne, photo trompeuse) est
    écartée et signalée : une seule mauvaise référence suffisait à faire reconnaître la personne partout."""
    refs = {}
    for dossier in sorted(d for d in Path(dossier_famille).iterdir() if d.is_dir()):
        empreintes, noms = [], []
        for chemin in sorted(dossier.iterdir()):
            if chemin.suffix.lower() not in EXTENSIONS:
                continue
            image, _, _ = charger(chemin)
            visages = detecter_visages(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), detecteur, reco)
            if not visages:
                print(f"  aucun visage net dans {dossier.name}/{chemin.name} (photo inutile : visage plus grand et de face)")
                continue
            visages.sort(key=lambda v: -v[2] * v[3])
            if len(visages) > 1 and visages[1][2] * visages[1][3] > 0.5 * visages[0][2] * visages[0][3]:
                print(f"  {dossier.name}/{chemin.name} : plusieurs visages de taille proche, impossible de savoir "
                      "lequel est le bon : photo ignorée (mettez une photo où la personne est seule ou nettement "
                      "au premier plan)")
                continue
            empreintes.append(visages[0][4])
            noms.append(chemin.name)
        if len(empreintes) >= 4:  # référence qui ne ressemble à aucune autre de la même personne : écartée
            matrice = np.stack(empreintes)
            similarites = matrice @ matrice.T
            np.fill_diagonal(similarites, np.nan)
            ressemblance = np.nanmedian(similarites, axis=1)
            seuil_reference = min(0.25, float(np.median(ressemblance)) - 0.15)
            garder = ressemblance >= seuil_reference
            for nom, ok, r in zip(noms, garder, ressemblance):
                if not ok:
                    print(f"  {dossier.name}/{nom} : ne ressemble pas aux autres photos de {dossier.name} "
                          f"(ressemblance {r:.2f}) : photo écartée (autre personne ?)")
            empreintes = [e for e, ok in zip(empreintes, garder) if ok]
        if empreintes:
            refs[dossier.name] = np.stack(empreintes)
            print(f"  {dossier.name} : {len(empreintes)} photo(s) de référence utilisée(s)")
    if not refs:
        sys.exit("Aucune référence : créez un dossier par personne avec quelques photos de son visage.")
    return refs


class Exclusions(set):
    """Refus manuels {(visage_id, nom)} + empreintes des visages refusés par personne (« ce n'est pas X ») :
    un visage qui ressemble davantage à un visage refusé qu'à la personne ne lui est pas attribué."""
    def __init__(self, *a):
        super().__init__(*a)
        self.negatifs = {}


def charger_references(base, dossier_famille, detecteur, reco):
    """Références des photos du dossier famille + visages confirmés dans « Vérifier la reconnaissance »
    (« c'est bien X »), et liste des refus (« ce n'est pas X ») à ne plus jamais attribuer."""
    refs = references(dossier_famille, detecteur, reco)
    exclusions = Exclusions()
    confirmes, refuses = defaultdict(list), defaultdict(list)
    for c in base.execute("SELECT c.visage_id, c.nom, c.ok, v.emb FROM confirmations c "
                          "JOIN visages v ON v.id = c.visage_id"):
        emb = np.frombuffer(c["emb"], dtype=np.float32)
        if c["ok"]:
            confirmes[c["nom"]].append(emb)
        else:
            exclusions.add((c["visage_id"], c["nom"]))
            refuses[c["nom"]].append(emb)
    for nom, liste in confirmes.items():
        refs[nom] = np.vstack([refs[nom], np.stack(liste)]) if nom in refs else np.stack(liste)
    exclusions.negatifs = {nom: np.stack(liste) for nom, liste in refuses.items()}
    if confirmes or refuses:
        print("  corrections à la main : " + ", ".join(
            f"{n} {len(confirmes.get(n, []))} confirmé(s) / {len(refuses.get(n, []))} refusé(s)"
            for n in sorted(set(confirmes) | set(refuses))))
    return refs, exclusions


def ressemblances(refs, embs):
    """Pour chaque visage (lignes de embs) et chaque personne : moyenne des 2 meilleures ressemblances avec ses
    références (plus fiable qu'une seule : une référence trompeuse ne suffit plus)."""
    noms = sorted(refs)
    resultat = np.zeros((len(embs), len(noms)), dtype=np.float32)
    for j, nom in enumerate(noms):
        resultat[:, j] = ressemblance_moyenne(embs, refs[nom])
    return noms, resultat


def ressemblance_moyenne(embs, references_):
    """Moyenne des 2 meilleures ressemblances de chaque visage avec un ensemble d'empreintes."""
    s = embs @ references_.T
    k = min(2, s.shape[1])
    return np.sort(s, axis=1)[:, -k:].mean(axis=1)


MARGE_VISAGE = 0.04  # le gagnant doit dépasser nettement la 2e personne (frères et sœurs qui se ressemblent)
PETIT_VISAGE = 0.05  # visage de moins de 5 % de la largeur (≈ 80 px) : empreinte peu fiable (arrière-plan, foule)
SUPPLEMENT_PETIT = 0.06  # ... il doit ressembler nettement plus pour être attribué


def identifier(base, refs, exclusions=(), seuil=None, photos=None):
    """Qui est sur chaque visage : {visage_id: (photo_id, largeur, nom, ressemblance)}. Un visage n'est attribué
    que s'il ressemble assez à la personne ET nettement plus qu'aux autres ; un refus manuel est respecté."""
    seuil = SEUIL_VISAGE if seuil is None else seuil
    lignes = [v for v in base.execute("SELECT id, photo_id, l, emb FROM visages")
              if photos is None or v["photo_id"] in photos]
    if not lignes:
        return {}
    embs = np.stack([np.frombuffer(v["emb"], dtype=np.float32) for v in lignes])
    noms, sims = ressemblances(refs, embs)
    negatifs = getattr(exclusions, "negatifs", {})
    # ressemblance de chaque visage avec les visages refusés pour chaque personne (« ce n'est pas X »)
    contre = {nom: ressemblance_moyenne(embs, negatifs[nom]) for nom in noms if nom in negatifs}
    resultat = {}
    for i, v in enumerate(lignes):
        progression("Reconnaissance des visages", i + 1, len(lignes))
        ordre = np.argsort(-sims[i])
        candidats = [j for j in ordre if (v["id"], noms[j]) not in exclusions]
        if not candidats:
            continue
        j = candidats[0]
        deuxieme = sims[i, candidats[1]] if len(candidats) > 1 else -1
        exigence = seuil + (SUPPLEMENT_PETIT if v["l"] < PETIT_VISAGE else 0)
        if noms[j] in contre and contre[noms[j]][i] >= sims[i, j]:
            continue  # ressemble plus à un visage que vous avez refusé qu'à la personne
        if sims[i, j] >= exigence and sims[i, j] - deuxieme >= MARGE_VISAGE:
            resultat[v["id"]] = (v["photo_id"], v["l"], noms[j], float(sims[i, j]))
    return resultat


def refuser_photo(fichier_base, chemin, nom):
    """« nom n'est pas sur cette photo » : tous ses visages sont refusés pour nom (connexion propre à l'appel,
    utilisable depuis un serveur à plusieurs fils). Renvoie le nombre de visages refusés."""
    with sqlite3.connect(fichier_base) as connexion:
        ids = [r[0] for r in connexion.execute(
            "SELECT v.id FROM visages v JOIN photos p ON p.id = v.photo_id WHERE p.chemin = ?", (chemin,))]
        connexion.executemany("REPLACE INTO confirmations VALUES (?, ?, 0)", [(i, nom) for i in ids])
    return len(ids)

def cmd_selectionner(args):
    fichier = args.sortie / "selection.csv"
    if fichier.exists() and not args.ecraser:
        sys.exit(f"{fichier} existe déjà (vos choix seraient perdus). Ajoutez --ecraser pour le refaire.")
    base = ouvrir_base(args.sortie)
    detecteur, reco = modeles(args.sortie)
    refs = references(args.famille, detecteur, reco)
    photos = {p["id"]: p for p in charger_photos(base)}

    # Pour chaque personne : photo -> largeur de son visage sur la photo
    presences = defaultdict(dict)
    for v in base.execute("SELECT photo_id, l, emb FROM visages"):
        emb = np.frombuffer(v["emb"], dtype=np.float32)
        similarites = {nom: float((ref @ emb).max()) for nom, ref in refs.items()}
        nom, sim = max(similarites.items(), key=lambda x: x[1])
        if sim >= args.seuil and v["photo_id"] in photos:
            presences[nom][v["photo_id"]] = max(presences[nom].get(v["photo_id"], 0), v["l"])

    lignes = []
    for nom in sorted(presences):
        selection = [dict(photos[i], largeur_personne=l) for i, l in presences[nom].items()]
        marquer_doublons(selection, largeur=lambda p: p["largeur_personne"])
        par_evenement = defaultdict(list)
        for p in selection:
            par_evenement[p["evenement"]].append(p)
        for groupe in par_evenement.values():
            candidates = [p for p in sorted(groupe, key=lambda q: -q["score"]) if not p["doublon_de"] and not p["flou"]]
            retenues = {p["id"] for p in candidates[: args.par_souvenir]}
            for p in sorted(groupe, key=lambda q: q["date"]):
                lignes.append((nom, p["evenement"], date_fr(p["date"]), p["lieu_evenement"], p["chemin"], p["score"],
                               "oui" if p["flou"] else "", p["doublon_de"], 1 if p["id"] in retenues else 0,
                               lieu_court(p["lieu_evenement"]), ""))
        print(f"  {nom} : {len(selection)} photos trouvées, {sum(1 for l in lignes if l[0] == nom and l[8])} proposées")
    lignes.sort(key=lambda l: (l[0], l[1]))
    ecrire_csv(fichier, COLONNES_SELECTION, lignes)
    planche(base, args.sortie, lignes)
    print(f"Sélection : {fichier}  (colonne « garder » : 1 = dans l'album, 0 = non)")
    print(f"Aperçu    : {args.sortie / 'planche.html'}")


COLONNES_SELECTION = ["personne", "souvenir", "date", "lieu", "fichier", "score", "flou", "doublon_de",
                      "garder", "titre", "legende"]


def lieu_court(lieu):
    return lieu.split(",")[0].split(" (")[0] if lieu else ""


def empreinte_fichier(base, relatif):
    """Taille et date du fichier d'origine (d'après la base) : font partie des noms de cache, pour qu'une autre
    photo arrivée au même chemin (dossiers réorganisés) ne réutilise jamais l'image en cache de l'ancienne."""
    ligne = base.execute("SELECT taille, mtime FROM photos WHERE chemin = ?", (relatif,)).fetchone()
    return f"{ligne['taille']}-{ligne['mtime']}" if ligne else ""


def apercu(base, sortie, relatif, cote, sous_dossier):
    """Copie réduite dans --sortie (cache) ; l'original n'est que lu."""
    dossier = sortie / sous_dossier
    dossier.mkdir(parents=True, exist_ok=True)
    cle = hashlib.md5(f"{relatif}|{empreinte_fichier(base, relatif)}".encode()).hexdigest()[:16]
    cible = dossier / f"{cle}_{cote}.jpg"
    if not cible.exists():
        try:
            image, _, _ = charger(original(base, relatif), cote)
        except OSError:  # photo déplacée, renommée ou supprimée depuis l'analyse : pas de vignette, pas d'arrêt
            return None
        image.save(cible, quality=90)
    return cible


def retirer_absentes(base, elements, cle, quoi="photo"):
    """Écarte les photos qui ne sont plus sur le disque (déplacées, renommées, supprimées depuis l'analyse) au
    lieu de tout arrêter ; le dit clairement. elements : liste de dictionnaires, cle : nom du champ chemin."""
    racine = Path(meta(base, "racine") or "")
    if not racine.exists():
        return elements
    presentes = [e for e in elements if (racine / e[cle]).exists()]
    absentes = len(elements) - len(presentes)
    if absentes:
        exemples = ", ".join(e[cle] for e in elements if not (racine / e[cle]).exists())
        print(f"  ATTENTION : {absentes} {quoi}(s) introuvable(s) sur le disque (déplacée(s), renommée(s) ou "
              f"supprimée(s) depuis l'analyse) : ignorée(s). Relancez « Analyser le disque » pour mettre la base à "
              f"jour. Ex. : {exemples[:300]}")
    return presentes


def planche(base, sortie, lignes):
    """Planche-contact HTML : vert = proposée, gris = écartée, pour vérifier avant d'éditer le CSV."""
    blocs, courant = [], None
    for nom, evenement, date, lieu, chemin, sc, flou, doublon, garder, _, _ in lignes:
        if (nom, evenement) != courant:
            if courant is not None:
                blocs.append("</div>")
            if courant is None or courant[0] != nom:
                blocs.append(f"<h2>{html.escape(nom)}</h2>")
            blocs.append(f"<h3>{date} – {html.escape(lieu or 'lieu inconnu')}</h3><div class='grille'>")
            courant = (nom, evenement)
        vignette = apercu(base, sortie, chemin, 320, "vignettes").relative_to(sortie).as_posix()
        note = "floue" if flou else (f"doublon de {doublon}" if doublon else f"score {sc}")
        classe = "garde" if garder else "ecarte"
        blocs.append(f"<figure class='{classe}'><img src='{vignette}' loading='lazy'>"
                     f"<figcaption>{html.escape(Path(chemin).name)}<br>{html.escape(note)}</figcaption></figure>")
    if courant is not None:
        blocs.append("</div>")
    (sortie / "planche.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Sélection des photos</title><style>"
        "body{font-family:sans-serif;margin:16px;background:#fafafa}"
        ".grille{display:flex;flex-wrap:wrap;gap:8px}"
        "figure{margin:0;width:170px;font-size:11px;border:4px solid #bbb;background:#fff}"
        "figure.garde{border-color:#2e9d4f}figure.ecarte{opacity:.45}"
        "img{width:100%;height:130px;object-fit:cover;display:block}figcaption{padding:4px;word-break:break-all}"
        "</style><p>Vert = proposée pour l'album. Pour changer : colonne « garder » de selection.csv.</p>"
        + "".join(blocs),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- photos retenues

def nettoyer(nom):
    return CARACTERES_INTERDITS.sub("-", nom).strip(" .")


def retenues(args):
    """Lit selection.csv et regroupe les photos gardées par personne puis par souvenir."""
    fichier = args.sortie / "selection.csv"
    if not fichier.exists():
        sys.exit("Lancez d'abord : python album_famille.py selectionner --famille <dossier>")
    lignes = [l for l in lire_csv(fichier) if l["garder"].strip().lower() in ("1", "oui", "x")]
    if args.personne:
        lignes = [l for l in lignes if l["personne"].lower() == args.personne.lower()]
    if not lignes:
        sys.exit("Aucune photo marquée « garder = 1 ».")
    personnes = defaultdict(lambda: defaultdict(list))
    for l in lignes:
        l["jour"] = dt.datetime.strptime(l["date"], "%d/%m/%Y")
        personnes[l["personne"]][int(l["souvenir"])].append(l)
    resultat = {}
    for nom, souvenirs in personnes.items():
        album = []
        for numero in sorted(souvenirs):
            groupe = sorted(souvenirs[numero], key=lambda l: l["jour"])
            debut, fin = groupe[0]["date"], groupe[-1]["date"]
            lieu = groupe[0]["lieu"]
            # le premier titre renseigné dans Excel l'emporte, sinon la commune
            titre = next((l["titre"].strip() for l in groupe if l.get("titre", "").strip()), "") or lieu_court(lieu) or "Souvenir"
            sous_titre = debut if debut == fin else f"Du {debut} au {fin}"
            if lieu and lieu != titre:
                sous_titre += f" – {lieu}"
            album.append({"titre": titre, "sous_titre": sous_titre, "debut": groupe[0]["jour"], "photos": groupe})
        resultat[nom] = album
    return resultat


def legende(ligne):
    texte = ligne.get("legende", "").strip()
    return f"{ligne['date']} – {texte}" if texte else ligne["date"]


def periode(album):
    annees = sorted({p["jour"].year for s in album for p in s["photos"]})
    return f"Souvenirs {annees[0]}" if annees[0] == annees[-1] else f"Souvenirs {annees[0]} – {annees[-1]}"


# --------------------------------------------------------------------------- 4. extraire

def cmd_extraire(args):
    """Copie (jamais déplace) les photos retenues en pleine résolution, prêtes pour un montage."""
    base = ouvrir_base(args.sortie)
    for nom, album in retenues(args).items():
        dossier = args.sortie / f"Extrait_{nettoyer(nom)}"
        if dossier.exists():
            if not args.ecraser:
                print(f"  {dossier} existe déjà : ignoré (ajoutez --ecraser pour le refaire)")
                continue
            shutil.rmtree(dossier)  # dossier produit par l'outil, dans --sortie
        lignes = []
        for i, souvenir in enumerate(album, 1):
            sous = dossier / nettoyer(f"{i:03d} {souvenir['debut']:%Y-%m-%d} {souvenir['titre']}")[:80]
            sous.mkdir(parents=True, exist_ok=True)
            for j, l in enumerate(souvenir["photos"], 1):
                cible = sous / f"{i:03d}-{j:02d}_{Path(l['fichier']).name}"
                shutil.copy2(original(base, l["fichier"]), cible)  # lecture seule de l'original
                lignes.append((cible.relative_to(dossier).as_posix(), l["date"], l["lieu"], souvenir["titre"],
                               l.get("legende", ""), l["fichier"]))
        ecrire_csv(dossier / "legendes.csv", ["copie", "date", "lieu", "titre", "legende", "original"], lignes)
        print(f"  {dossier}  ({len(lignes)} photos copiées, {len(album)} souvenirs)")


# --------------------------------------------------------------------------- 5. album

MARGE, ENTETE, ECART = 12, 22, 6
COLONNES, RANGEES = 2, 2
A4_L, A4_H = 210, 297


def cases():
    l = (A4_L - 2 * MARGE - ECART) / COLONNES
    h = (A4_H - 2 * MARGE - ENTETE - ECART) / RANGEES
    return [(MARGE + c * (l + ECART), MARGE + ENTETE + r * (h + ECART), l, h)
            for r in range(RANGEES) for c in range(COLONNES)]


def placer(image, case):
    """Position (mm) de la photo dans sa case, proportions conservées, légende en dessous."""
    x0, y0, l, h = case
    zone_h = h - 7
    with Image.open(image) as im:
        rapport = im.width / im.height
    l_img, h_img = (l, l / rapport) if rapport > l / zone_h else (zone_h * rapport, zone_h)
    return x0 + (l - l_img) / 2, y0, l_img, h_img


def pages(album):
    for souvenir in album:
        for depart in range(0, len(souvenir["photos"]), COLONNES * RANGEES):
            yield souvenir, souvenir["photos"][depart: depart + COLONNES * RANGEES]


def police(pdf):
    candidates = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for normale, grasse in candidates:
        if Path(normale).exists() and Path(grasse).exists():
            pdf.add_font("Corps", "", normale)
            pdf.add_font("Corps", "B", grasse)
            return "Corps", lambda t: t
    return "helvetica", lambda t: t.encode("latin-1", "replace").decode("latin-1")


def album_pdf(base, sortie, nom, album, chemin):
    from fpdf import FPDF

    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(False)
    famille, texte = police(pdf)
    largeur = A4_L - 2 * MARGE
    pdf.add_page()
    pdf.set_font(famille, "B", 36)
    pdf.set_xy(MARGE, 110)
    pdf.cell(largeur, 16, texte(nom), align="C")
    pdf.set_font(famille, "", 16)
    pdf.set_xy(MARGE, 132)
    pdf.cell(largeur, 10, texte(periode(album)), align="C")
    for souvenir, groupe in pages(album):
        pdf.add_page()
        pdf.set_font(famille, "B", 15)
        pdf.set_xy(MARGE, MARGE)
        pdf.cell(largeur, 8, texte(souvenir["titre"]))
        pdf.set_font(famille, "", 11)
        pdf.set_xy(MARGE, MARGE + 8)
        pdf.cell(largeur, 7, texte(souvenir["sous_titre"]))
        for case, l in zip(cases(), groupe):
            image = apercu(base, sortie, l["fichier"], COTE_IMPRESSION, "cache_impression")
            x, y, l_img, h_img = placer(image, case)
            pdf.image(str(image), x, y, l_img, h_img)
            pdf.set_font(famille, "", 9)
            pdf.set_xy(case[0], y + h_img + 1)
            pdf.cell(case[2], 5, texte(legende(l)), align="C")
    pdf.output(str(chemin))


def album_pptx(base, sortie, nom, album, chemin):
    """Même mise en page, mais chaque photo et chaque texte reste déplaçable et modifiable."""
    from pptx import Presentation
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Mm, Pt

    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Mm(A4_L), Mm(A4_H)
    vide = presentation.slide_layouts[6]

    def texte(diapo, x, y, l, h, contenu, taille, gras=False, centre=False):
        cadre = diapo.shapes.add_textbox(Mm(x), Mm(y), Mm(l), Mm(h)).text_frame
        cadre.word_wrap = True
        paragraphe = cadre.paragraphs[0]
        paragraphe.text = contenu
        paragraphe.font.size, paragraphe.font.bold = Pt(taille), gras
        if centre:
            paragraphe.alignment = PP_ALIGN.CENTER

    largeur = A4_L - 2 * MARGE
    diapo = presentation.slides.add_slide(vide)
    texte(diapo, MARGE, 105, largeur, 18, nom, 36, gras=True, centre=True)
    texte(diapo, MARGE, 130, largeur, 10, periode(album), 16, centre=True)
    for souvenir, groupe in pages(album):
        diapo = presentation.slides.add_slide(vide)
        texte(diapo, MARGE, MARGE, largeur, 9, souvenir["titre"], 15, gras=True)
        texte(diapo, MARGE, MARGE + 8, largeur, 7, souvenir["sous_titre"], 11)
        for case, l in zip(cases(), groupe):
            image = apercu(base, sortie, l["fichier"], COTE_IMPRESSION, "cache_impression")
            x, y, l_img, h_img = placer(image, case)
            diapo.shapes.add_picture(str(image), Mm(x), Mm(y), Mm(l_img), Mm(h_img))
            texte(diapo, case[0], y + h_img, case[2], 6, legende(l), 9, centre=True)
    presentation.save(str(chemin))


def cmd_album(args):
    base = ouvrir_base(args.sortie)
    for nom, album in retenues(args).items():
        nb = sum(len(s["photos"]) for s in album)
        for format_ in ("pdf", "pptx"):
            if args.format in (format_, "les-deux"):
                chemin = args.sortie / f"Album_{nettoyer(nom)}.{format_}"
                (album_pdf if format_ == "pdf" else album_pptx)(base, args.sortie, nom, album, chemin)
                print(f"  {chemin}  ({nb} photos, {len(album)} souvenirs)")


# --------------------------------------------------------------------------- ligne de commande

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sortie", type=Path, default=Path("albums_sortie"),
                        help="dossier de travail, en dehors du disque de photos (défaut : albums_sortie)")
    sous = parser.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("analyser", help="lire (sans les modifier) toutes les photos du disque de backup")
    p.add_argument("photos", help="dossier des photos sur le disque de backup (ex. E:\\Photos)")
    p.set_defaults(fonction=cmd_analyser)
    sous.add_parser("trier", help="rapport doublons / floues / sans date").set_defaults(fonction=cmd_trier)
    p = sous.add_parser("selectionner", help="reconnaître la famille et proposer les photos essentielles")
    p.add_argument("--famille", required=True, help="dossier contenant un sous-dossier par personne")
    p.add_argument("--par-souvenir", type=int, default=3, help="photos proposées par souvenir (défaut 3)")
    p.add_argument("--seuil", type=float, default=SEUIL_VISAGE, help=f"exigence de ressemblance (défaut {SEUIL_VISAGE})")
    p.add_argument("--ecraser", action="store_true", help="refaire selection.csv même s'il existe")
    p.set_defaults(fonction=cmd_selectionner)
    p = sous.add_parser("extraire", help="copier les photos retenues par personne et par souvenir")
    p.add_argument("--personne", help="ne faire que l'extrait de cette personne")
    p.add_argument("--ecraser", action="store_true", help="refaire un extrait déjà produit")
    p.set_defaults(fonction=cmd_extraire)
    p = sous.add_parser("album", help="un album par personne à partir de selection.csv")
    p.add_argument("--personne", help="ne faire que l'album de cette personne")
    p.add_argument("--format", choices=["pdf", "pptx", "les-deux"], default="les-deux",
                   help="pdf = prêt à imprimer, pptx = modifiable dans PowerPoint (défaut : les deux)")
    p.set_defaults(fonction=cmd_album)
    args = parser.parse_args()
    args.fonction(args)


if __name__ == "__main__":
    main()
