#!/usr/bin/env python3
"""Album Photos - application de bureau : toutes les étapes du livre photo et de la planche lettres en boutons.

Bibliothèque standard uniquement (Tkinter) : l'application s'ouvre même avant l'installation des bibliothèques.
Chaque bouton lance l'étape correspondante de lanceur.py (comme les fichiers .bat), dont la sortie s'affiche
dans l'onglet Journal. Les réglages de parametres_livre.txt se modifient dans l'onglet Paramètres.
Les photos originales ne sont jamais modifiées.
"""
import datetime as dt
import importlib.util
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import textes_app  # noqa: E402
from textes_app import T, code_de, libelle  # noqa: E402

ICI = Path(__file__).resolve().parent
PARAMETRES = ICI / "parametres_livre.txt"
MODELE = ICI / "parametres_livre.modele.txt"
GUIDE_HTML = ICI / "Guide_application.html"
GUIDE_MD = ICI / "20261101-Photos-33_Guide-application.md"
GUIDE_HTML_EN = ICI / "Guide_application_EN.html"
GUIDE_MD_EN = ICI / "Guide_application_EN.md"
NOM_APPLI = "Album Photos"

AMBIANCES = ["elegant", "tendre", "carnet", "prestige", "prestige-compact", "prestige-mosaique",
             "prestige-mosaique-bd", "magazine", "bd", "bd-photo"]
COULEURS = ["", "noir", "blanc", "creme", "gris", "gris-clair", "anthracite", "bleu-nuit", "marine", "bleu",
            "bleu-ciel", "rose", "rose-poudre", "fuchsia", "rouge", "bordeaux", "vert", "vert-sauge", "beige",
            "kraft", "or", "argent", "lavande", "violet", "jaune", "orange"]

# (clé, libellé, type, choix, aide) ; types : dossier, texte, choix (liste fermée), libre (liste + saisie)
PARAMS = [
    ("Photos et personnes", [
        ("PHOTOS", "Dossier des photos", "dossier", None, "disque de backup : il n'est jamais modifié"),
        ("SORTIE", "Dossier de travail", "dossier", None, "sur le PC (ni sur le disque de backup, ni dans OneDrive)"),
        ("PERSONNE", "Personne du livre", "texte", None, "nom de son dossier de photos de référence ; changer de "
         "personne = un autre livre (dossier livre_<Prénom>), sans refaire l'analyse du disque"),
        ("AVEC", "Proches à mettre en avant", "texte", None, "séparés par des virgules (ex. son frère)"),
        ("NAISSANCE", "Date de naissance", "texte", None, "JJ/MM/AAAA (vide si inconnue)"),
        ("PAYS", "Pays « chez soi »", "texte", None, "codes à 2 lettres, ex. FR,PH : ailleurs = voyage"),
        ("SEUIL_VISAGE", "Exigence de ressemblance des visages", "libre", ["0.40", "0.45", "0.50", "0.55", "0.35"],
         "vide = 0.40 ; plus haut = moins de photos sans la personne, mais quelques oublis"),
    ]),
    ("Livre", [
        ("FORMAT", "Format du livre", "choix", ["carre30", "carre20", "a4-paysage", "a4-portrait"], ""),
        ("MAX", "Nombre maximum de photos", "texte", None, "ex. 150"),
        ("PAGES", "Nombre de pages visé", "texte", None, "vide = mise en page aérée"),
        ("ORGANISATION", "Organisation des chapitres", "choix", ["", "chrono-lieux", "chrono", "themes", "lieux"],
         "vide = celle de chaque ambiance"),
        ("AMBIANCE", "Ambiance du livre final", "choix", [""] + AMBIANCES, "choisie après les aperçus"),
        ("RELIURE", "Reliure", "choix", ["classique", "layflat"], "layflat = reliure à plat (panoramiques)"),
        ("BD_COULEUR", "Couleur des encadrés de légende (ambiances BD)", "libre",
         ["jaune", "bleu", "bleu-fonce", "vert", "vert-fonce", "rose", "orange", "rouge", "violet", "turquoise",
          "blanc", "creme", "gris"], "jaune par défaut ; ou un code #RRGGBB ; texte blanc sur les couleurs foncées"),
        ("LANGUE_LIVRE", "Langue du livre et de la planche lettres", "choix", ["fr", "en"],
         "titres, dates, âges, pays et bulles traduits ; les légendes saisies à la main restent telles quelles"),
        ("DEDICACE", "Dédicace (page de titre)", "texte", None, "vide = aucune"),
        ("PIED_DE_PAGE", "Pied de page", "texte", None, "petit texte en bas des pages, ex. Laura · 2012-2024 (vide = aucun)"),
        ("PIED_PAGES", "Pages avec le pied de page", "choix", ["toutes", "photos-uniques"],
         "toutes = toutes les pages après la première ; pages à photo unique = seulement celles-là"),
        ("TEXTE_FIN", "Texte de la fin de l'album", "multiligne", None,
         "dernière page (vide = « À suivre… ») ; retours à la ligne et paragraphes gardés ; la taille s'adapte"),
        ("SYMBOLE_FIN", "Symbole au-dessus du texte de fin", "symbole",
         ["coeurs", "coeur", "fleur", "ornement", "colombe", "etoiles", "aucun"], ""),
    ]),
    ("Planche lettres", [
        ("LETTRES_MOT", "Mot écrit", "texte", None, "vide = le prénom ; un espace = nouvelle ligne"),
        ("LETTRES_HAUT", "Texte au-dessus", "texte", None, "ex. On t'aime"),
        ("LETTRES_BAS", "Texte au-dessous", "texte", None, "ex. De la part de Papa (suivi d'un cœur)"),
        ("LETTRES_FORMAT", "Format", "choix", ["a4-paysage", "a3-paysage", "30x20", "40x30", "a4-portrait"], ""),
        ("LETTRES_POLICE", "Police des lettres", "choix", ["toutes", "arial-black", "impact", "georgia",
                                                            "segoe-black"], "toutes = celle de chaque modèle"),
        ("LETTRES_TAILLE", "Taille des lettres (%)", "libre", ["100", "90", "85", "80", "70"], "100 = maximum"),
        ("LETTRES_CREUX", "Creux des lettres (A, R, O)", "choix", ["non", "oui"], "non = la photo remplit tout"),
        ("LETTRES_FOND", "Couleur du fond", "libre", COULEURS, "vide = celle du modèle, ou #RRGGBB"),
        ("LETTRES_CONTOUR", "Couleur du contour", "libre", COULEURS + ["aucun"], "vide = celle du modèle"),
        ("LETTRES_TEXTE", "Couleur des textes", "libre", COULEURS, "vide = automatique"),
        ("LETTRES_TEINTE", "Photos", "choix", ["couleur", "noir-et-blanc", "sepia"], ""),
        ("LETTRES_DANS_LIVRE", "Mettre la planche dans le livre photo", "choix",
         ["non", "premiere-page", "premiere-et-derniere"],
         "première page = à la place de la page de titre ; première et dernière page = aussi avant la dernière page"),
        ("LETTRES_MODELE_LIVRE", "Modèle de planche pour le livre", "choix", ["1", "2", "3", "4", "5", "6"],
         "voir Comparaison_modeles.jpg ; mis au format du livre automatiquement"),
    ]),
    ("Mosaïque", [
        ("MOSAIQUE_MASTER", "Photo master", "fichier", None,
         "la photo à reconstituer ; vide = celle marquée « ◆ Master » dans l'écran de choix, sinon la couverture"),
        ("MOSAIQUE_FORMAT", "Format du poster", "choix",
         ["a4-portrait", "a3-portrait", "a2-portrait", "a1-portrait", "a0-portrait", "a4-paysage", "a3-paysage",
          "a2-paysage", "a1-paysage", "a0-paysage", "30x40", "40x50", "50x70", "carre30", "carre50"], ""),
        ("MOSAIQUE_COLONNES", "Petites photos en largeur", "libre", ["40", "60", "80", "100", "120"],
         "plus = visage plus net de loin, petites photos plus petites ; A0 : 80 à 120"),
        ("MOSAIQUE_MELANGE", "Visage fondu par-dessus", "libre", ["0.25", "0.35", "0.45", "0.55"],
         "0.25 discret, 0.35 conseillé, 0.50 visage très marqué"),
        ("MOSAIQUE_PHOTOS", "Petites photos utilisées", "choix",
         ["gardees", "toutes", "gardees+dossier", "toutes+dossier"],
         "sans dossier de miniatures : gardées = celles du livre, toutes = toutes les photos de la personne ; "
         "« + dossier » = l'album ET le dossier de miniatures"),
        ("MOSAIQUE_DOSSIER", "Dossier des photos en miniature (option)", "dossier", None,
         "rempli = les petites photos viennent de ce dossier (sous-dossiers compris, lu sans être modifié) ; "
         "vide = les photos sélectionnées de l'album"),
        ("MOSAIQUE_DPI", "Résolution d'impression", "libre", ["auto", "300", "200", "150"],
         "auto = 300 dpi jusqu'au A2, 200 en A1, 150 en A0 (norme des posters, vus à distance)"),
        ("MOSAIQUE_FONDU", "Rendu du visage", "choix", ["adaptatif", "naturel", "lumiere"],
         "adaptatif = conseillé (yeux, bouche, contours plus détaillés) ; lumière = les photos gardent leurs couleurs"),
        ("MOSAIQUE_TEINTE", "Teinte des petites photos", "libre", ["0.45", "0.30", "0.60", "0"],
         "photos teintées vers la couleur de leur case : 0 = couleurs d'origine, 0.6 = harmonie forte"),
        ("MOSAIQUE_JOINT", "Liseré entre les photos", "choix", ["aucun", "blanc-fin", "blanc", "noir-fin", "noir",
                                                                "creme"], "effet « carreaux » discret"),
        ("MOSAIQUE_ECART", "Écart entre deux mêmes photos", "libre", ["3", "2", "4", "5"],
         "nombre de cases minimum ; plus = plus de variété apparente"),
        ("MOSAIQUE_FOND_PERDU", "Fond perdu (mm)", "libre", ["3", "5", "0"],
         "marge rognée par l'imprimeur (3 mm en général) ; le texte reste à l'intérieur"),
        ("MOSAIQUE_TEXTE", "Texte sur la photo", "texte", None, "vide = aucun ; « | » = nouvelle ligne, ex. Laura | 2003 - 2026"),
        ("MOSAIQUE_TEXTE_POSITION", "Position du texte", "choix", ["auto", "bas", "haut", "centre", "bas-gauche",
                                                                    "bas-droite", "haut-gauche", "haut-droite"],
         "auto = là où il n'y a pas de visage"),
        ("MOSAIQUE_TEXTE_POLICE", "Police du texte", "choix", ["georgia", "script", "texte", "arial-black", "impact",
                                                                "segoe-black"], ""),
        ("MOSAIQUE_TEXTE_COULEUR", "Couleur du texte", "libre", ["blanc", "noir", "or", "creme", "rouge", "bleu-nuit"],
         "ou #RRGGBB"),
        ("MOSAIQUE_TEXTE_TAILLE", "Taille du texte", "libre", ["moyen", "petit", "grand", "tres-grand"],
         "ou un % de la largeur, ex. 7"),
        ("MOSAIQUE_TEXTE_STYLE", "Style du texte", "choix", ["ombre", "contour", "bandeau", "aucun"],
         "ombre = lisible partout ; bandeau = bande translucide derrière le texte"),
    ]),
]

# (titre de section, [(texte du bouton, étape de lanceur.py, explication)])
# fenêtre « Maintenance » : (texte, étape, explication, réservé à l'administrateur de l'outil)
MAINTENANCE = [
    ("Installer / réparer", "installer", "Installe les bibliothèques et crée les dossiers de photos de référence",
     False),
    ("Vérifier l'outil (tests)", "tests", "Tests automatiques sur des photos de synthèse (1 à 3 min) ; vos photos "
                                          "et réglages ne sont pas utilisés", False),
    ("Mettre à jour l'outil", "mettre_a_jour", "Récupère la dernière version (vos réglages et livres sont gardés)",
     True),
    ("Fabriquer le zip à partager", "partager", "Copie propre de l'outil, sans vos réglages, vos données ni le lien "
                                               "vers votre dépôt GitHub", True),
]


def nom_etape(etape):
    """Texte du bouton d'une étape : colonne de gauche ou fenêtre Maintenance."""
    for _, boutons in ETAPES:
        for texte, code, _ in boutons:
            if code == etape:
                return texte
    return next((m[0] for m in MAINTENANCE if m[1] == etape), etape)


def mode_admin():
    """Administrateur = l'outil est la copie Git de l'auteur (mise à jour possible), ou un fichier admin.txt est
    présent à côté de l'application. Une copie partagée (zip) n'a ni l'un ni l'autre : pas de bouton GitHub."""
    return (ICI / "admin.txt").exists() or (ICI.parent.parent / ".git").exists()


ETAPES = [
    ("1. Analyse des photos", [
        ("Analyser le disque", "analyser", "Une seule fois pour toutes les personnes (lecture seule, des heures la "
                                            "1re fois) ; à relancer seulement si vous ajoutez des photos au disque"),
    ]),
    ("2. Sélection des photos", [
        ("Préparer la sélection", "preparer", "Reconnaît la personne du livre et propose ses photos, puis ouvre "
                                              "l'écran de choix ; à faire pour chaque nouvelle personne"),
        ("Vérifier la reconnaissance", "verifier_visages", "Visages mal reconnus : un clic confirme ou refuse ; "
                                                            "puis relancez « Préparer la sélection »"),
        ("Choisir les photos", "choisir", "Écran de choix dans le navigateur : un clic = garder / retirer"),
        ("Réduire la sélection", "reduire", "Seules les photos gardées, avec les candidates au retrait"),
        ("Proposer des améliorations", "proposer", "Propositions à accepter ou refuser d'un clic, puis appliquer"),
        ("Revoir les propositions", "appliquer", "Rouvre l'écran des propositions déjà faites (sans les recalculer)"),
    ]),
    ("3. Livre", [
        ("Aperçus des ambiances", "apercu", "Un PDF d'aperçu par ambiance ; vous cochez celles à (re)faire"),
        ("Livre final", "composer", "Le livre dans l'ambiance choisie + le dossier pour l'imprimeur"),
        ("Livre + PowerPoint modifiable", "powerpoint", "Comme le livre final, avec une version .pptx à retoucher"),
    ]),
    ("4. Planche lettres-photos", [
        ("Choisir les photos des lettres", "choisir_lettres", "Une photo par lettre ; le livre n'est pas modifié"),
        ("Créer la planche lettres", "lettres", "Les modèles en JPEG 300 dpi + PDF, et une planche de comparaison"),
    ]),
    ("5. Mosaïque de photos", [
        ("Aperçu de la mosaïque", "mosaique_apercu", "Rendu rapide (quelques secondes) avec les réglages actuels, "
                                                      "affiché dans Paramètres > Mosaïque"),
        ("Créer la mosaïque", "mosaique", "La photo master reconstituée avec les photos de l'album (A4 à A0) ; "
                                           "choix de la master : « ◆ Master » dans l'écran de choix ou Paramètres"),
    ]),
]


# modèles de la planche lettres (mêmes réglages que planche_lettres.py), pour l'aperçu schématique
MODELES_PLANCHE = [
    {"nom": "classique", "police": "Arial Black", "lignes": 1, "fond": "#FFFFFF", "contour": "#2F2B28", "ombre": True},
    {"nom": "aquarelle", "police": "Arial Black", "lignes": 1, "fond": "#EAF3FA", "contour": "#FFFFFF", "ombre": True},
    {"nom": "impact", "police": "Impact", "lignes": 1, "fond": "#FFFFFF", "contour": None, "ombre": True},
    {"nom": "deux-lignes", "police": "Arial Black", "lignes": 2, "fond": "#FFFFFF", "contour": "#2F2B28", "ombre": True},
    {"nom": "elegant", "police": "Georgia", "lignes": 1, "fond": "#FBF6EC", "contour": "#B8954F", "ombre": False},
    {"nom": "prestige-noir", "police": "Segoe UI Black", "lignes": 1, "fond": "#161514", "contour": "#C8A96A",
     "ombre": False},
]
CODES_COULEURS = {
    "blanc": "#FFFFFF", "creme": "#FBF6EC", "noir": "#161514", "gris": "#9A9590", "gris-clair": "#E6E3DF",
    "anthracite": "#33302D", "bleu-nuit": "#1C2B44", "bleu": "#3A6EA5", "bleu-ciel": "#CFE6F5", "rose": "#F6D6DC",
    "rose-poudre": "#EBC8C4", "fuchsia": "#C2185B", "rouge": "#C62828", "bordeaux": "#6D1A2A", "vert": "#2E7D4F",
    "vert-sauge": "#C9D5C0", "beige": "#E9DCC8", "kraft": "#C8A97E", "or": "#C8A96A", "argent": "#BFC3C7",
    "lavande": "#D9D2EA", "violet": "#6A4C93", "marine": "#14213D", "jaune": "#F4D35E", "orange": "#E07A2F",
}


def dessiner_symboles(toile, noms, choisi):
    """Les symboles proposés pour la fin de l'album, dessinés côte à côte ; le choisi est encadré."""
    import math as m

    toile.delete("all")
    rouge = "#D7263D"

    def coeur(cx, cy, t):
        pts = []
        for i in range(40):
            a = 2 * m.pi * i / 40
            pts += [cx + 16 * m.sin(a) ** 3 * t / 34,
                    cy - (13 * m.cos(a) - 5 * m.cos(2 * a) - 2 * m.cos(3 * a) - m.cos(4 * a)) * t / 34]
        toile.create_polygon(pts, fill=rouge, outline="")

    def etoile(cx, cy, r):
        pts = []
        for i in range(10):
            rr, a = (r if i % 2 == 0 else r * 0.45), m.pi * i / 5 - m.pi / 2
            pts += [cx + rr * m.cos(a), cy + rr * m.sin(a)]
        toile.create_polygon(pts, fill=rouge, outline="")
    for i, nom in enumerate(noms):
        cx, cy = 34 + i * 66, 26
        if nom == choisi:
            toile.create_rectangle(cx - 31, 2, cx + 31, 67, outline="#3A6EA5", width=2)
        if nom == "coeur":
            coeur(cx, cy, 26)
        elif nom == "coeurs":
            coeur(cx - 13, cy + 2, 14), coeur(cx, cy, 22), coeur(cx + 13, cy + 2, 14)
        elif nom == "etoiles":
            etoile(cx, cy, 12), etoile(cx - 16, cy - 8, 4), etoile(cx + 15, cy - 9, 4), etoile(cx + 12, cy + 10, 3)
        elif nom == "fleur":
            for k in range(5):
                a = m.radians(k * 72 - 90)
                px, py = cx + m.cos(a) * 8, cy + m.sin(a) * 8
                toile.create_oval(px - 6, py - 6, px + 6, py + 6, fill=rouge, outline="")
            toile.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="#E9C46A", outline="")
        elif nom == "ornement":
            toile.create_line(cx - 26, cy, cx - 6, cy, fill=rouge, width=1)
            toile.create_line(cx + 6, cy, cx + 26, cy, fill=rouge, width=1)
            toile.create_polygon(cx, cy - 4, cx + 4, cy, cx, cy + 4, cx - 4, cy, fill=rouge)
        elif nom == "colombe":
            toile.create_polygon(cx - 18, cy - 8, cx - 5, cy - 1, cx, cy + 3, cx + 5, cy - 1, cx + 18, cy - 8,
                                 cx + 8, cy + 4, cx, cy + 7, cx - 8, cy + 4, fill=rouge, outline="")
        else:
            toile.create_text(cx, cy, text="—", fill="#8C847C", font=("Segoe UI", 12))
        toile.create_text(cx, 58, text=libelle(nom), fill="#5A534C", font=("Segoe UI", 8))


def libelle_modele(code):
    if code == "tous":
        return T("tous (les 6 modèles, pour comparer)")
    if code.isdigit() and 1 <= int(code) <= 6:
        fr, en = textes_app.MODELES_LIBELLES[textes_app.MODELES_NOMS[int(code) - 1]]
        return f"{code} - {en if textes_app.LANGUE[0] == 'en' else fr}"
    return code


def dessiner_planche(toile, v, modele, bx, by, bl, bh, zoom):
    """Une planche schématique dans le rectangle (bx, by, bl, bh) du canevas."""
    import tkinter.font as tkfont

    formats = {"a4-paysage": (297, 210), "a3-paysage": (420, 297), "30x20": (300, 200), "40x30": (400, 300),
               "a4-portrait": (210, 297)}
    fl, fh = formats.get(v.get("LETTRES_FORMAT") or "a4-paysage", (297, 210))
    echelle = min((bl - 10) / fl, (bh - 10) / fh)
    L, H = fl * echelle, fh * echelle
    x0, y0 = bx + (bl - L) / 2, by + (bh - H) / 2
    fond = couleur_nommee(v.get("LETTRES_FOND")) or modele["fond"]
    toile.create_rectangle(x0 + 3, y0 + 3, x0 + L + 3, y0 + H + 3, fill="#CFC8BE", outline="")
    toile.create_rectangle(x0, y0, x0 + L, y0 + H, fill=fond, outline="#B9B2A9")
    if modele["nom"] == "aquarelle" and not v.get("LETTRES_FOND"):
        for cx, cy, r, c in ((0.15, 0.2, 0.3, "#B9DBF0"), (0.8, 0.2, 0.25, "#CFE6F5"), (0.5, 0.85, 0.35, "#C3E0F3")):
            toile.create_oval(x0 + (cx - r) * L, y0 + (cy - r) * H, x0 + (cx + r) * L, y0 + (cy + r) * H, fill=c,
                              outline="")
    r, g, b = (int(fond[i:i + 2], 16) for i in (1, 3, 5))
    clair = 0.299 * r + 0.587 * g + 0.114 * b > 110
    texte_couleur = couleur_nommee(v.get("LETTRES_TEXTE")) or ("#2F2B28" if clair else "#E9E2D6")
    contour = v.get("LETTRES_CONTOUR", "").lower()
    couleur_contour = None if contour in ("aucun", "sans", "non") else (couleur_nommee(contour) or modele["contour"])
    mot = " ".join((v.get("LETTRES_MOT") or v.get("PERSONNE") or "LAURA").upper().split())
    mots = mot.split()
    if len(mots) > 1:
        rangees = mots
    elif (modele["lignes"] == 2 or fh > 0.9 * fl) and len(mot) >= 4:
        rangees = [mot[:(len(mot) + 1) // 2], mot[(len(mot) + 1) // 2:]]
    else:
        rangees = [mot]
    haut, bas = v.get("LETTRES_HAUT", ""), v.get("LETTRES_BAS", "")
    zone_haut, zone_bas = H * (0.2 if haut else 0.08), H * (0.17 if bas else 0.08)
    familles = familles_polices()
    police = {"arial-black": "Arial Black", "impact": "Impact", "georgia": "Georgia",
              "segoe-black": "Segoe UI Black"}.get(v.get("LETTRES_POLICE") or "toutes", modele["police"])
    if police not in familles:
        police = "Arial" if "Arial" in familles else "Helvetica"
    poids = "normal" if police in ("Arial Black", "Impact", "Segoe UI Black") else "bold"
    try:
        taille_pct = min(100, max(40, int(v.get("LETTRES_TAILLE") or 100))) / 100
    except ValueError:
        taille_pct = 1.0
    palette = {"couleur": ["#E07A5F", "#3D9970", "#3A6EA5", "#F2CC8F", "#9B5DE5", "#E5989B", "#81B29A"],
               "noir-et-blanc": ["#5E5E5E", "#8A8A8A", "#3F3F3F", "#A8A8A8", "#707070", "#9A9A9A", "#505050"],
               "sepia": ["#8B6B4A", "#A88462", "#6E5136", "#BE9B76", "#94714F", "#7C5D3F", "#B08A64"]}.get(
        v.get("LETTRES_TEINTE") or "couleur")
    hauteur_rangee = (H - zone_haut - zone_bas) / len(rangees)
    plus_longue = max(len(r_) for r_ in rangees)
    taille = int(min(hauteur_rangee * 0.75, L * 0.88 / max(plus_longue, 1) * 1.25) * taille_pct)
    taille = max(6, taille)
    largeur = police_mesuree(police, 100, poids).measure(max(rangees, key=len)) * taille / 100
    if largeur > L * 0.88 * taille_pct:  # une seule mesure (à 100 px) puis règle de trois : rapide
        taille = max(6, int(taille * L * 0.88 * taille_pct / largeur))
    f = police_mesuree(police, taille, poids)
    index = 0
    epaisseur = 0 if couleur_contour is None else max(1, taille // 30)
    for i, rangee in enumerate(rangees):
        cy = y0 + zone_haut + hauteur_rangee * (i + 0.5)
        x = x0 + (L - f.measure(rangee)) / 2
        for lettre in rangee:
            cx = x + f.measure(lettre) / 2
            if modele["ombre"] and clair:
                toile.create_text(cx + 2 * zoom, cy + 2 * zoom, text=lettre, font=f, fill="#B5AEA5")
            if epaisseur:
                for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)):
                    toile.create_text(cx + dx * epaisseur, cy + dy * epaisseur, text=lettre, font=f,
                                      fill=couleur_contour)
            toile.create_text(cx, cy, text=lettre, font=f, fill=palette[index % len(palette)])
            x += f.measure(lettre)
            index += 1
    if haut:
        script = [p_ for p_ in ("Segoe Script", "Lucida Handwriting", "Georgia") if p_ in familles]
        fh_ = police_mesuree((script or ["Times"])[0], max(5, int(zone_haut * 0.45)))
        toile.create_text(x0 + L / 2, y0 + zone_haut * 0.55, text=haut, font=fh_, width=L * 0.9,
                          fill="#3A6EA5" if modele["nom"] == "aquarelle" and not v.get("LETTRES_TEXTE")
                          else texte_couleur)
    if bas:
        fb = police_mesuree("Georgia" if "Georgia" in familles else "Times", max(5, int(zone_bas * 0.3)))
        toile.create_text(x0 + L / 2, y0 + H - zone_bas * 0.42, text=bas + "  ❤", font=fb, width=L * 0.9,
                          fill=texte_couleur)


def couleur_nommee(nom):
    nom = (nom or "").strip().lower()
    if nom in CODES_COULEURS:
        return CODES_COULEURS[nom]
    if re.fullmatch(r"#[0-9a-f]{6}", nom):
        return nom
    return None


# --------------------------------------------------------------------------- fichier de paramètres

def lire_texte():
    brut = PARAMETRES.read_bytes()
    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = brut.decode("cp1252", errors="replace")
    return normaliser_fins_de_ligne(texte)

def normaliser_fins_de_ligne(texte):
    """Fins de ligne cohérentes. Les anciennes versions écrivaient « \\r\\r\\n » sous Windows (une ligne vide
    fantôme après chaque ligne, qui doublait les paragraphes de la lettre) : on les répare à la lecture."""
    while "\r\r\n" in texte:
        texte = texte.replace("\r\r\n", "\r\n")
    return texte


def sans_lignes_vides_en_double(lignes):
    """Au plus une ligne vide d'affilée (nettoie les fichiers abîmés par les anciennes versions)."""
    propres = []
    for ligne in lignes:
        if not ligne.strip() and propres and not propres[-1].strip():
            continue
        propres.append(ligne)
    return propres



MULTILIGNES = ("TEXTE_FIN", "DEDICACE")  # réglages dont le texte peut continuer sur les lignes suivantes


def suite_de_texte(brute):
    """Vrai si la ligne continue un texte sur plusieurs lignes (ni commentaire, ni « CLE = »)."""
    return not brute.startswith("#") and not re.match(r"^[A-Za-z_]{3,}\s*=", brute)


def analyser_texte(texte):
    valeurs, multiligne = {}, None
    for ligne in texte.splitlines():
        brute = ligne.strip()
        if multiligne and suite_de_texte(brute):
            valeurs[multiligne] += "\n" + ligne.rstrip()
            continue
        multiligne = None
        if brute and not brute.startswith("#") and "=" in brute:
            cle, valeur = brute.split("=", 1)
            cle = cle.strip().upper()
            valeurs[cle] = valeur.strip().strip('"')
            multiligne = cle if cle in MULTILIGNES else None
    for cle in MULTILIGNES:
        if cle in valeurs:
            valeurs[cle] = valeurs[cle].strip()
    return valeurs


def texte_fin_complet(fichier, parametre):
    """Texte de fin le plus complet entre texte_fin.txt et TEXTE_FIN (une ancienne version pouvait couper la
    lettre en deux : 1re ligne d'un côté, suite de l'autre)."""
    fichier, parametre = (fichier or "").strip(), (parametre or "").replace("\\n", "\n").strip()
    if not parametre or parametre in fichier:
        return fichier
    if not fichier or fichier in parametre:
        return parametre
    if len(fichier.splitlines()) == 1 and len(fichier) <= 60:  # « Ma chérie, » seul + la suite dans le paramètre
        return fichier + "\n\n" + parametre
    return fichier if len(fichier) >= len(parametre) else parametre


def ecrire_sur(chemin, contenu):
    """Écriture sans risque : fichier temporaire puis remplacement en une fois (jamais de fichier vide ou à
    moitié écrit, même si le programme est fermé de force pendant l'écriture) ; l'ancienne version est gardée
    dans sauvegardes_parametres/ (10 dernières)."""
    chemin = Path(chemin)
    if chemin.exists() and chemin.stat().st_size > 0:
        dossier = chemin.parent / "sauvegardes_parametres"
        dossier.mkdir(exist_ok=True)
        shutil.copy2(chemin, dossier / f"{chemin.stem}_{dt.datetime.now():%Y%m%d-%H%M%S}{chemin.suffix}")
        for ancienne in sorted(dossier.glob(f"{chemin.stem}_*{chemin.suffix}"))[:-10]:
            ancienne.unlink()
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    with open(temporaire, "w", encoding="utf-8-sig", newline="") as f:  # newline="" : pas de « \r\r\n »
        f.write(contenu)
    os.replace(temporaire, chemin)


def parametres_retrouves():
    """Si parametres_livre.txt a été vidé : les derniers réglages connus, d'après les sauvegardes, sinon d'après
    journal.txt (le lanceur y note les réglages à chaque étape). Renvoie (valeurs, origine) ou (None, None)."""
    dossier = ICI / "sauvegardes_parametres"
    for sauvegarde in sorted(dossier.glob("parametres_livre_*.txt"), reverse=True) if dossier.exists() else []:
        try:
            valeurs = analyser_texte(sauvegarde.read_bytes().decode("utf-8-sig", errors="replace"))
        except OSError:
            continue
        if valeurs.get("PERSONNE") and valeurs.get("SORTIE"):
            return valeurs, sauvegarde.name
    journal = ICI / "journal.txt"
    if journal.exists():
        bloc, dernier, date = None, None, ""
        for ligne in journal.read_text(encoding="utf-8", errors="replace").splitlines():
            if ligne.startswith("====="):
                date = ligne.strip("= ").split(" - ")[0]
            if ligne.startswith("Paramètres lus dans"):
                bloc = {}
                continue
            if bloc is not None and ligne.startswith("  ") and " = " in ligne:
                cle, valeur = ligne.strip().split(" = ", 1) if not ligne.strip().endswith(" =") else (
                    ligne.strip()[:-2], "")
                bloc[cle.strip()] = valeur.strip()
                continue
            if bloc is not None:
                if bloc.get("PERSONNE") and bloc.get("SORTIE"):
                    dernier = (dict(bloc), f"journal.txt ({date})")
                bloc = None
        if bloc and bloc.get("PERSONNE") and bloc.get("SORTIE"):
            dernier = (dict(bloc), f"journal.txt ({date})")
        if dernier:
            return dernier
    return None, None


def lire_parametres():
    """Vos réglages ; un réglage absent (fichier d'une version plus ancienne) prend la valeur du modèle."""
    if not PARAMETRES.exists() and MODELE.exists():
        shutil.copy(MODELE, PARAMETRES)
    defauts = analyser_texte(MODELE.read_text(encoding="utf-8-sig")) if MODELE.exists() else {}
    valeurs = analyser_texte(lire_texte()) if PARAMETRES.exists() else {}
    return {**{c: v for c, v in defauts.items() if c not in ("PHOTOS", "SORTIE", "PERSONNE")}, **valeurs}


def ecrire_parametres(valeurs):
    """Remplace les lignes CLE = ... (en gardant les commentaires), supprime les doublons, ajoute les manquantes."""
    lignes, vues, saute = [], set(), False
    for ligne in (lire_texte().splitlines() if PARAMETRES.exists() else []):
        brute = ligne.strip()
        if saute and suite_de_texte(brute):  # suite d'un texte sur plusieurs lignes : remplacée aussi
            continue
        saute = False
        if not brute.startswith("#") and "=" in brute:
            cle = brute.split("=", 1)[0].strip().upper()
            if cle in valeurs:
                saute = cle in MULTILIGNES
                if cle in vues:
                    continue
                vues.add(cle)
                lignes.append(f"{cle} = {valeurs[cle]}".rstrip().replace("\n", " ") if valeurs[cle] else f"{cle} =")
                continue
        lignes.append(ligne)
    for cle, valeur in valeurs.items():
        if cle not in vues:
            lignes.append(f"{cle} = {valeur}".rstrip() if valeur else f"{cle} =")
    contenu = "\r\n".join(sans_lignes_vides_en_double(lignes)) + "\r\n"
    if PARAMETRES.exists() and lire_texte() == contenu:
        return  # rien n'a changé : pas d'écriture (disque, antivirus, OneDrive)
    ecrire_sur(PARAMETRES, contenu)


# --------------------------------------------------------------------------- outils

def python_console():
    """python.exe (avec sortie texte) à côté de pythonw.exe (qui lance l'application sans fenêtre noire)."""
    if os.environ.get("ALBUM_PYTHON"):
        return os.environ["ALBUM_PYTHON"]
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return str(exe.with_name("python.exe"))
    return sys.executable


def ouvrir(chemin):
    chemin = str(chemin)
    if chemin.startswith("http"):
        webbrowser.open(chemin)
    elif hasattr(os, "startfile"):
        os.startfile(chemin)
    elif shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", chemin])


def version():
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cd", "--date=format:%d/%m/%Y %H:%M"], cwd=ICI,
                           capture_output=True, text=True, timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


_FAMILLES, _POLICES = [], {}


def familles_polices():
    """Polices installées, lues une seule fois (sous Windows, la liste complète peut prendre une seconde)."""
    import tkinter.font as tkfont

    if not _FAMILLES:
        _FAMILLES.append(set(tkfont.families()))
    return _FAMILLES[0]


def police_mesuree(famille, taille, poids="normal"):
    """Objet police réutilisé (créer une police à chaque dessin est coûteux)."""
    import tkinter.font as tkfont

    cle = (famille, int(taille), poids)
    if cle not in _POLICES:
        _POLICES[cle] = tkfont.Font(family=famille, size=-int(taille), weight=poids)
    return _POLICES[cle]


_MANQUANTES = []


def bibliotheques_manquantes(rafraichir=False):
    """Bibliothèques absentes ; vérifié au démarrage et après Installer / Mettre à jour seulement."""
    if _MANQUANTES and not rafraichir:
        return _MANQUANTES[0]
    _MANQUANTES[:] = [_bibliotheques_manquantes()]
    return _MANQUANTES[0]


def _bibliotheques_manquantes():
    noms = {"cv2": "opencv-python", "numpy": "numpy", "PIL": "pillow", "fpdf": "fpdf2", "pptx": "python-pptx",
            "xlsxwriter": "XlsxWriter", "scipy": "scipy", "reverse_geocode": "reverse_geocode"}
    return [n for m, n in noms.items() if importlib.util.find_spec(m) is None]


# --------------------------------------------------------------------------- boutons dessinés

COULEURS_BOUTON = {  # fond, fond au survol, texte, bord
    "etape": ("#3A6EA5", "#4F86C0", "#FFFFFF", "#2C5682"),
    "conseil": ("#2E9D4F", "#3DB862", "#FFFFFF", "#1E6B35"),
    "secondaire": ("#FFFFFF", "#EEF4FA", "#2F2B28", "#9AA9BA"),
    "valider": ("#2E9D4F", "#3DB862", "#FFFFFF", "#1E6B35"),
    "danger": ("#C0392B", "#D9534F", "#FFFFFF", "#8E2A1F"),
    "inactif": ("#D9D4CC", "#D9D4CC", "#8C847C", "#C9C3BA"),
}


class Bouton(tk.Canvas):
    """Vrai bouton : coins arrondis, ombre, couleur au survol, effet enfoncé au clic, grisé si inactif."""

    def __init__(self, parent, texte, commande, style="etape", largeur=300, hauteur=40, taille=10, gras=True,
                 fond_parent="#F6F3EE"):
        super().__init__(parent, width=largeur, height=hauteur + 3, bg=fond_parent, highlightthickness=0,
                         cursor="hand2")
        self.texte, self.commande, self.style_bouton = T(texte), commande, style
        self.l, self.h, self.police = largeur, hauteur, ("Segoe UI", taille, "bold" if gras else "normal")
        self.actif, self.survol, self.enfonce = True, False, False
        self.bind("<Enter>", lambda e: self.changer(survol=True))
        self.bind("<Leave>", lambda e: self.changer(survol=False, enfonce=False))
        self.bind("<ButtonPress-1>", lambda e: self.changer(enfonce=True))
        self.bind("<ButtonRelease-1>", self.relache)
        self.dessiner()

    def arrondi(self, x0, y0, x1, y1, r, **options):
        points = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1,
                  x0, y1 - r, x0, y0 + r, x0, y0]
        return self.create_polygon(points, smooth=True, **options)

    def dessiner(self):
        self.delete("all")
        fond, survol, texte, bord = COULEURS_BOUTON[self.style_bouton if self.actif else "inactif"]
        decale = 2 if self.enfonce else 0
        if not self.enfonce:  # ombre portée
            self.arrondi(2, 4, self.l - 1, self.h + 2, 9, fill="#CFC8BE", outline="")
        self.arrondi(1, 1 + decale, self.l - 2, self.h - 1 + decale, 9,
                     fill=survol if (self.survol and self.actif) else fond, outline=bord, width=1)
        self.create_text(16, self.h / 2 + decale, text=self.texte, fill=texte, font=self.police, anchor="w")
        if self.actif and self.style_bouton in ("etape", "conseil"):
            self.create_text(self.l - 16, self.h / 2 + decale, text="▶", fill=texte, font=("Segoe UI", 9),
                             anchor="e")

    def changer(self, **etat):
        for cle, valeur in etat.items():
            setattr(self, cle, valeur)
        self.dessiner()

    def relache(self, evenement):
        dedans = 0 <= evenement.x <= self.l and 0 <= evenement.y <= self.h
        self.changer(enfonce=False)
        if dedans and self.actif and self.commande:
            self.commande()

    def activer(self, actif=True):
        self.actif = actif
        self.configure(cursor="hand2" if actif else "arrow")
        self.dessiner()

    def nouveau_style(self, style):
        if style != self.style_bouton:
            self.style_bouton = style
            self.dessiner()


def zone_defilante(parent, fond="#F6F3EE", largeur=None):
    """Cadre avec barre de défilement verticale (molette comprise) ; renvoie le cadre intérieur."""
    toile = tk.Canvas(parent, highlightthickness=0, bg=fond, **({"width": largeur} if largeur else {}))
    barre = ttk.Scrollbar(parent, orient="vertical", command=toile.yview)
    interieur = tk.Frame(toile, bg=fond)
    interieur.bind("<Configure>", lambda e: toile.configure(scrollregion=toile.bbox("all")))
    fenetre = toile.create_window((0, 0), window=interieur, anchor="nw")
    if largeur is None:
        toile.bind("<Configure>", lambda e: toile.itemconfigure(fenetre, width=e.width))
    toile.configure(yscrollcommand=barre.set)
    toile.pack(side="left", fill="both", expand=largeur is None)
    barre.pack(side="left", fill="y")

    def molette(e):
        toile.yview_scroll(int(-e.delta / 120) if e.delta else (-1 if e.num == 4 else 1), "units")
    for widget in (toile, interieur):
        widget.bind("<Enter>", lambda e: (toile.bind_all("<MouseWheel>", molette),
                                          toile.bind_all("<Button-4>", molette), toile.bind_all("<Button-5>", molette)))
        widget.bind("<Leave>", lambda e: (toile.unbind_all("<MouseWheel>"), toile.unbind_all("<Button-4>"),
                                          toile.unbind_all("<Button-5>")))
    return interieur


# --------------------------------------------------------------------------- application

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(NOM_APPLI)
        self.geometry("1180x760")
        self.minsize(960, 600)
        icone = ICI / "album_photos.png"
        if icone.exists():
            try:
                self.iconphoto(True, tk.PhotoImage(file=str(icone)))
            except tk.TclError:
                pass
        self.processus = None
        self.file = queue.Queue()
        self.etape_en_cours = None
        self.dernieres_lignes = []
        self.boutons = {}
        self.vars = {}
        self.multilignes = {}
        self.prog = {}
        self.modifie = False
        self.toile_planche, self._apercu_prevu = None, None
        textes_app.LANGUE[0] = "en" if lire_parametres().get("LANGUE", "fr").lower() == "en" else "fr"
        self.style()
        self.construire()
        self.charger_parametres()
        self.after(100, self.lire_sortie)
        self.after(300, self.bilan)
        self.pouls = time.monotonic()
        threading.Thread(target=self.surveiller_blocage, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.quitter)

    # ---------------------------------------------------------------- apparence
    def style(self):
        s = ttk.Style(self)
        s.theme_use("clam")  # le seul thème qui respecte les couleurs des champs et des onglets
        self.configure(bg="#F6F3EE")
        s.configure("TFrame", background="#F6F3EE")
        s.configure("Carte.TFrame", background="#FFFFFF")
        s.configure("TLabel", background="#F6F3EE")
        s.configure("Carte.TLabel", background="#FFFFFF")
        s.configure("Titre.TLabel", font=("Segoe UI", 16, "bold"), background="#2F2B28", foreground="#FFFFFF")
        s.configure("SousTitre.TLabel", font=("Segoe UI", 9), background="#2F2B28", foreground="#D9D2C8")
        s.configure("Bandeau.TFrame", background="#2F2B28")
        s.configure("Section.TLabel", font=("Segoe UI", 10, "bold"), foreground="#7A5C2E", background="#F6F3EE")
        s.configure("Etape.TButton", font=("Segoe UI", 10), padding=(10, 5), anchor="w")
        s.configure("Conseil.TButton", font=("Segoe UI", 10, "bold"), padding=(10, 5), anchor="w",
                    foreground="#1E6B35")
        s.configure("Aide.TLabel", font=("Segoe UI", 8), foreground="#8C847C", background="#F6F3EE")
        s.configure("TNotebook", background="#F6F3EE", borderwidth=0)
        s.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(14, 6), background="#E3DDD3",
                    foreground="#5A534C")
        s.map("TNotebook.Tab", background=[("selected", "#FFFFFF")], foreground=[("selected", "#2F2B28")])
        # listes de choix : fond blanc, bord net, bleu quand on est dedans
        s.configure("Champ.TCombobox", fieldbackground="#FFFFFF", background="#FFFFFF", bordercolor="#9AA9BA",
                    lightcolor="#FFFFFF", darkcolor="#FFFFFF", arrowcolor="#3A6EA5", padding=6, arrowsize=16)
        s.map("Champ.TCombobox", fieldbackground=[("readonly", "#FFFFFF")], bordercolor=[("focus", "#3A6EA5")],
              selectbackground=[("readonly", "#FFFFFF")], selectforeground=[("readonly", "#2F2B28")])
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))
        self.option_add("*TCombobox*Listbox.selectBackground", "#3A6EA5")
        s.configure("Etat.TLabel", font=("Segoe UI", 10), background="#2F2B28", foreground="#FFE9A8")

    def construire(self):
        bandeau = ttk.Frame(self, style="Bandeau.TFrame", padding=(16, 10))
        bandeau.pack(fill="x")
        gauche = ttk.Frame(bandeau, style="Bandeau.TFrame")
        self.titre = ttk.Label(gauche, text=NOM_APPLI, style="Titre.TLabel")
        self.titre.pack(anchor="w")
        self.sous_titre = ttk.Label(gauche, text="", style="SousTitre.TLabel", wraplength=560)
        self.sous_titre.pack(anchor="w")
        if not hasattr(self, "version"):
            self.version = ""

            def lire_version():  # git peut prendre une seconde : sans bloquer l'ouverture ; le résultat passe par
                v = version()     # la file lue par la fenêtre (Tkinter ne doit être appelé que depuis son fil)
                if v:
                    self.file.put(("version", v))
            threading.Thread(target=lire_version, daemon=True).start()
        droite = ttk.Frame(bandeau, style="Bandeau.TFrame")
        droite.pack(side="right")  # placée avant la partie gauche : toujours visible, même fenêtre étroite
        gauche.pack(side="left", fill="x", expand=True)
        autre = "EN" if textes_app.LANGUE[0] == "fr" else "FR"
        Bouton(droite, f"🌐  {autre}", self.changer_langue, style="secondaire", largeur=70, hauteur=34,
               fond_parent="#2F2B28").pack(side="right", padx=(10, 0))
        Bouton(droite, "🔧  Maintenance", self.fenetre_maintenance, style="secondaire", largeur=140, hauteur=34,
               fond_parent="#2F2B28").pack(side="right", padx=(10, 0))
        self.bouton_arret = Bouton(droite, "■  Arrêter l'étape", self.arreter, style="danger", largeur=160,
                                   hauteur=34, fond_parent="#2F2B28")
        self.bouton_arret.activer(False)
        self.bouton_arret.pack(side="right", padx=(10, 0))
        self.barre = ttk.Progressbar(droite, mode="indeterminate", length=140)
        self.barre.pack(side="right", padx=(10, 0))
        self.etat = ttk.Label(droite, text=T("Prêt"), style="Etat.TLabel")
        self.etat.pack(side="right")

        corps = ttk.Frame(self, padding=(10, 8))
        corps.pack(fill="both", expand=True)
        # colonne des étapes, avec défilement
        colonne = ttk.Frame(corps)
        colonne.pack(side="left", fill="y")
        self.etapes = zone_defilante(colonne, largeur=340)
        for section, boutons in ETAPES:
            ttk.Label(self.etapes, text=T(section), style="Section.TLabel").pack(anchor="w", pady=(12, 4), padx=4)
            for texte, etape, aide in boutons:
                b = Bouton(self.etapes, texte, lambda e=etape: self.lancer(e), largeur=310)
                b.pack(anchor="w", padx=4, pady=(3, 0))
                ttk.Label(self.etapes, text=T(aide), style="Aide.TLabel", wraplength=300).pack(anchor="w", padx=10,
                                                                                         pady=(0, 3))
                self.boutons[etape] = b
        ttk.Label(self.etapes, text=T("Ouvrir"), style="Section.TLabel").pack(anchor="w", pady=(12, 2))
        grille = ttk.Frame(self.etapes)
        grille.pack(anchor="w", padx=2, pady=(0, 12))
        raccourcis = [("Dossier de travail", lambda: self.ouvrir_dossier("")),
                      ("Dossier du livre", lambda: self.ouvrir_dossier("livre")),
                      ("Photos de référence", lambda: self.ouvrir_dossier("famille")),
                      ("Planches lettres", lambda: self.ouvrir_dossier("lettres")),
                      ("Dossier de l'outil", lambda: ouvrir(ICI)),
                      ("journal.txt", lambda: ouvrir(ICI / "journal.txt"))]
        for i, (texte, action) in enumerate(raccourcis):
            Bouton(grille, texte, action, style="secondaire", largeur=152, hauteur=32, taille=9, gras=False).grid(
                row=i // 2, column=i % 2, padx=3, pady=2)

        # onglets
        self.onglets = ttk.Notebook(corps)
        self.onglets.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.onglet_journal()
        self.onglet_parametres()
        self.onglet_aide()

    def fenetre_maintenance(self):
        """Installation, tests ; pour l'administrateur seulement : mise à jour depuis GitHub et zip à partager."""
        fenetre = tk.Toplevel(self)
        fenetre.title(T("Maintenance"))
        fenetre.configure(bg="#FFFFFF")
        fenetre.transient(self)
        fenetre.resizable(False, False)
        admin = mode_admin()
        tk.Label(fenetre, text=T("Maintenance de l'outil"), bg="#FFFFFF", fg="#2F2B28",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(fenetre, text=T("Mode administrateur") if admin else T("Copie partagée : la mise à jour est réservée "
                                                                         "à l'auteur de l'outil"),
                 bg="#FFFFFF", fg="#1E6B35" if admin else "#8C847C", font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        def lancer(etape):
            fenetre.destroy()
            self.lancer(etape)
        for texte, etape, aide, reserve in MAINTENANCE:
            if reserve and not admin:
                continue
            Bouton(fenetre, texte, lambda e=etape: lancer(e), largeur=320, fond_parent="#FFFFFF").pack(
                anchor="w", padx=16, pady=(10, 0))
            tk.Label(fenetre, text=T(aide), bg="#FFFFFF", fg="#8C847C", font=("Segoe UI", 8), wraplength=320,
                     justify="left").pack(anchor="w", padx=20)
        Bouton(fenetre, "Fermer", fenetre.destroy, style="secondaire", largeur=100, hauteur=32, taille=9,
               gras=False, fond_parent="#FFFFFF").pack(anchor="e", padx=16, pady=14)
        fenetre.bind("<Escape>", lambda e: fenetre.destroy())
        fenetre.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - fenetre.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + 80
        fenetre.geometry(f"+{max(0, x)}+{max(0, y)}")
        fenetre.lift()
        fenetre.focus_force()

    def onglet_journal(self):
        cadre = ttk.Frame(self.onglets, padding=6)
        self.onglets.add(cadre, text=T("  Journal  "))
        self.conseil = ttk.Label(cadre, text="", font=("Segoe UI", 10, "bold"), foreground="#1E6B35",
                                 wraplength=760)
        self.conseil.pack(anchor="w", pady=(0, 6))
        self.journal = scrolledtext.ScrolledText(cadre, wrap="word", font=("Consolas", 10), bg="#FFFFFF",
                                                 relief="flat", padx=8, pady=6)
        self.journal.pack(fill="both", expand=True)
        self.journal.tag_configure("erreur", foreground="#B3261E", font=("Consolas", 10, "bold"))
        self.journal.tag_configure("suivante", foreground="#1E6B35", font=("Consolas", 10, "bold"))
        self.journal.tag_configure("titre", foreground="#7A5C2E", font=("Consolas", 10, "bold"))
        self.journal.tag_configure("doux", foreground="#8C847C")
        self.journal.configure(state="disabled")
        bas = ttk.Frame(cadre)
        bas.pack(fill="x", pady=(6, 0))
        Bouton(bas, "Effacer l'affichage", self.effacer, style="secondaire", largeur=150, hauteur=32, taille=9,
               gras=False).pack(side="left")
        Bouton(bas, "Copier le journal", self.copier, style="secondaire", largeur=150, hauteur=32, taille=9,
               gras=False).pack(side="left", padx=6)
        ttk.Label(bas, text=T("En cas de problème : envoyez journal.txt (bouton « journal.txt » à gauche) à Claude.")
                  + ("  " + T("Les messages détaillés du journal restent en français.")
                     if textes_app.LANGUE[0] == "en" else ""), style="Aide.TLabel").pack(side="left", padx=10)

    def onglet_parametres(self):
        cadre = ttk.Frame(self.onglets, padding=6)
        self.onglets.add(cadre, text=T("  Paramètres  "))
        haut = ttk.Frame(cadre)
        haut.pack(fill="x")
        Bouton(haut, "✔  Enregistrer les paramètres", self.enregistrer, style="valider", largeur=250,
               hauteur=36).pack(side="left")
        Bouton(haut, "Annuler les modifications", self.charger_parametres, style="secondaire", largeur=210,
               hauteur=36, gras=False).pack(side="left", padx=8)
        self.etat_params = ttk.Label(haut, text="", style="Aide.TLabel", wraplength=380)
        self.etat_params.pack(side="left", padx=6)
        sous = ttk.Notebook(cadre)
        sous.pack(fill="both", expand=True, pady=(8, 0))
        for section, champs in PARAMS:
            onglet = ttk.Frame(sous)
            sous.add(onglet, text=f"  {T(section)}  ")
            if section == "Planche lettres":  # aperçu schématique à droite des réglages
                droite = tk.Frame(onglet, bg="#F6F3EE")
                droite.pack(side="right", fill="y", padx=(6, 4), pady=6)
                gauche = tk.Frame(onglet, bg="#F6F3EE")
                gauche.pack(side="left", fill="both", expand=True)
                self.construire_apercu_planche(droite)
                page = zone_defilante(gauche, fond="#F6F3EE")
            elif section == "Mosaïque":  # aperçu rapide à droite des réglages
                self.sous_onglets, self.onglet_mosaique = sous, onglet
                droite = tk.Frame(onglet, bg="#F6F3EE")
                droite.pack(side="right", fill="y", padx=(6, 4), pady=6)
                gauche = tk.Frame(onglet, bg="#F6F3EE")
                gauche.pack(side="left", fill="both", expand=True)
                self.construire_apercu_mosaique(droite)
                page = zone_defilante(gauche, fond="#F6F3EE")
            else:
                page = zone_defilante(onglet, fond="#F6F3EE")
            for cle, libelle, type_, choix, aide in champs:
                carte = tk.Frame(page, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E2DBD0")
                carte.pack(fill="x", padx=10, pady=5)
                tk.Label(carte, text=T(libelle), bg="#FFFFFF", fg="#2F2B28", font=("Segoe UI", 10, "bold")).pack(
                    anchor="w", padx=12, pady=(8, 2))
                ligne = tk.Frame(carte, bg="#FFFFFF")
                ligne.pack(fill="x", padx=12)
                var = tk.StringVar()
                if cle == "PERSONNE":  # autre personne : le conseil (et le titre) changent aussitôt
                    var.trace_add("write", lambda *a: self.after(400, self.bilan_si_pret))
                if cle.startswith("LETTRES_") or cle == "PERSONNE":
                    var.trace_add("write", lambda *a: (self.marquer_modifie(), self.planifier_apercu()))
                else:
                    var.trace_add("write", lambda *a: self.marquer_modifie())
                self.vars[cle] = var
                if type_ == "multiligne":  # texte sur plusieurs lignes (gardé dans texte_fin.txt)
                    zone = tk.Text(ligne, height=9, wrap="word", font=("Segoe UI", 10), bg="#FFFFFF", fg="#2F2B28",
                                   relief="flat", highlightthickness=2, highlightbackground="#9AA9BA",
                                   highlightcolor="#3A6EA5", insertbackground="#3A6EA5", padx=6, pady=4)
                    zone.pack(side="left", fill="x", expand=True)
                    zone.bind("<<Modified>>", lambda e, z=zone: (z.edit_modified(False), self.marquer_modifie()))
                    self.multilignes[cle] = zone
                    del self.vars[cle]
                elif type_ == "symbole":  # liste + dessin des symboles proposés
                    self.relier_liste(ligne, var, choix, "readonly", 20).pack(side="left")
                    dessin = tk.Canvas(carte, width=470, height=70, bg="#FFFFFF", highlightthickness=0)
                    dessin.pack(anchor="w", padx=12, pady=(4, 0))
                    var.trace_add("write", lambda *a, d=dessin, v=var, c=choix: dessiner_symboles(d, c, v.get()))
                    dessiner_symboles(dessin, choix, "")
                    dessin.configure(cursor="hand2")  # un clic sur un dessin le choisit
                    dessin.bind("<Button-1>", lambda e, v=var, c=choix: v.set(c[max(0, min(len(c) - 1, e.x // 66))]))
                elif type_ in ("choix", "libre"):  # libellés traduits, code gardé dans le fichier
                    self.relier_liste(ligne, var, choix, "readonly" if type_ == "choix" else "normal", 44,
                                      libelle_modele if cle == "LETTRES_MODELE_LIVRE" else None).pack(side="left")
                    if type_ == "libre":
                        tk.Label(ligne, text=T("liste ou saisie libre"), bg="#FFFFFF", fg="#8C847C",
                                 font=("Segoe UI", 8, "italic")).pack(side="left", padx=8)
                else:
                    champ = tk.Entry(ligne, textvariable=var, font=("Segoe UI", 10), bg="#FFFFFF", fg="#2F2B28",
                                     relief="flat", highlightthickness=2, highlightbackground="#9AA9BA",
                                     highlightcolor="#3A6EA5", insertbackground="#3A6EA5")
                    champ.pack(side="left", fill="x", expand=True, ipady=5)
                if type_ == "dossier":
                    Bouton(ligne, "📁  Parcourir…", lambda v=var: self.parcourir(v), style="secondaire", largeur=130,
                           hauteur=32, taille=9, fond_parent="#FFFFFF").pack(side="left", padx=(8, 0))
                if type_ == "fichier":
                    Bouton(ligne, "📁  Parcourir…", lambda v=var: self.parcourir_fichier(v), style="secondaire",
                           largeur=130, hauteur=32, taille=9, fond_parent="#FFFFFF").pack(side="left", padx=(8, 0))
                tk.Label(carte, text=T(aide) or " ", bg="#FFFFFF", fg="#8C847C", font=("Segoe UI", 8)).pack(
                    anchor="w", padx=12, pady=(2, 8))

    # ---------------------------------------------------------------- aperçu schématique de la planche lettres
    def construire_apercu_planche(self, parent):
        """Aperçu schématique + choix des modèles à fabriquer (un seul réglage : ce qui est montré est ce qui
        sera fabriqué)."""
        tk.Label(parent, text=T("Aperçu schématique"), bg="#F6F3EE", fg="#7A5C2E",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ligne = tk.Frame(parent, bg="#F6F3EE")
        ligne.pack(anchor="w", pady=(2, 4))
        tk.Label(ligne, text=T("Modèles à fabriquer :"), bg="#F6F3EE", font=("Segoe UI", 9, "bold")).pack(side="left")
        codes = ["tous", "1", "2", "3", "4", "5", "6"]
        var = tk.StringVar()
        var.trace_add("write", lambda *a: (self.marquer_modifie(), self.planifier_apercu()))
        self.vars["LETTRES_MODELES"] = var
        self.relier_liste(ligne, var, codes, "readonly", 26, libelle_modele).pack(side="left", padx=4)
        self.toile_planche = tk.Canvas(parent, width=380, height=300, bg="#F6F3EE", highlightthickness=0)
        self.toile_planche.pack()
        self.toile_planche.bind("<Map>", lambda e: self.planifier_apercu() if getattr(
            self, "_apercu_a_refaire", True) else None)
        tk.Label(parent, text=T("Les lettres colorées représentent les photos.\nRendu exact : « Créer la planche lettres »."),
                 bg="#F6F3EE", fg="#8C847C", font=("Segoe UI", 8), justify="left").pack(anchor="w", pady=(4, 0))
        self._apercu_prevu = None

    def construire_apercu_mosaique(self, parent):
        tk.Label(parent, text=T("Aperçu de la mosaïque"), bg="#F6F3EE", fg="#7A5C2E",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        cadre = tk.Frame(parent, bg="#E9E2D6", width=344, height=444)  # taille fixe en pixels
        cadre.pack_propagate(False)
        cadre.pack(pady=(4, 6))
        self.image_mosaique = tk.Label(cadre, bg="#E9E2D6", text=T("Pas encore d'aperçu"), fg="#8C847C",
                                       font=("Segoe UI", 9))
        self.image_mosaique.pack(expand=True)
        Bouton(parent, "↻  Actualiser l'aperçu", lambda: self.lancer("mosaique_apercu"), style="valider", largeur=220,
               hauteur=34, fond_parent="#F6F3EE").pack(anchor="w")
        tk.Label(parent, text=T("Quelques secondes, avec les réglages de gauche (enregistrés d'abord).\n"
                                "Le poster pour l'imprimeur : « Créer la mosaïque »."),
                 bg="#F6F3EE", fg="#8C847C", font=("Segoe UI", 8), justify="left").pack(anchor="w", pady=(4, 0))
        self.after(500, self.afficher_apercu_mosaique)

    def afficher_apercu_mosaique(self):
        """Dernier aperçu rapide de la mosaïque de la personne du livre (s'il existe)."""
        if getattr(self, "image_mosaique", None) is None:
            return
        fichier = self.dossier_livre() / "mosaique" / "apercu_application.png"
        try:
            if fichier.exists():
                self.photo_mosaique = tk.PhotoImage(file=str(fichier))  # gardée : sinon Tk l'efface
                self.image_mosaique.configure(image=self.photo_mosaique, text="")
            else:
                self.photo_mosaique = None
                self.image_mosaique.configure(image="", text=T("Pas encore d'aperçu"))
        except tk.TclError:
            pass

    def relier_liste(self, parent, var, codes, etat, largeur, nommer=None, fond="#FFFFFF"):
        """Liste de choix qui affiche des libellés traduits mais garde le code dans var (et donc dans le fichier
        de paramètres) ; en saisie libre, un texte tapé (code, #RRGGBB) est gardé tel quel."""
        nommer = nommer or libelle
        affiche = tk.StringVar()
        liste = ttk.Combobox(parent, textvariable=affiche, values=[nommer(c) for c in codes], style="Champ.TCombobox",
                             state=etat, width=largeur, font=("Segoe UI", 10))
        verrou = [False]

        def vers_affichage(*_):
            if not verrou[0]:
                verrou[0] = True
                affiche.set(nommer(var.get()))
                verrou[0] = False

        def vers_code(*_):
            if not verrou[0]:
                verrou[0] = True
                texte = affiche.get()
                code = next((c for c in codes if nommer(c) == texte), None) or code_de(texte, codes)
                if code != var.get():
                    var.set(code)
                verrou[0] = False
        var.trace_add("write", vers_affichage)
        affiche.trace_add("write", vers_code)
        return liste

    def planifier_apercu(self):
        if getattr(self, "toile_planche", None) is None or self._apercu_prevu is not None:
            return
        self._apercu_prevu = self.after(250, self.dessiner_apercu_planche)

    def dessiner_apercu_planche(self):
        """Planche lettres dessinée en direct à partir des réglages (sans les photos) : le modèle choisi, ou les
        6 modèles en vignettes quand « tous » sont fabriqués."""
        self._apercu_prevu = None
        toile = self.toile_planche
        try:
            if not toile.winfo_viewable():  # onglet caché : on redessinera quand il sera affiché
                self._apercu_a_refaire = True
                return
            toile.delete("all")
        except tk.TclError:
            return
        self._apercu_a_refaire = False
        v = {cle: var.get().strip() for cle, var in self.vars.items()}
        choix = (v.get("LETTRES_MODELES") or "tous").replace(" ", "")
        numeros = [int(n) for n in choix.split(",") if n.isdigit() and 1 <= int(n) <= 6] or list(range(1, 7))
        if len(numeros) == 1:
            dessiner_planche(toile, v, MODELES_PLANCHE[numeros[0] - 1], 0, 0, 380, 300, 1.0)
            return
        colonnes = 2 if len(numeros) > 1 else 1
        rangs = (len(numeros) + colonnes - 1) // colonnes
        lw, lh = 380 / colonnes, 300 / rangs
        for i, n in enumerate(numeros):
            x, y = (i % colonnes) * lw, (i // colonnes) * lh
            dessiner_planche(toile, v, MODELES_PLANCHE[n - 1], x, y, lw, lh - 12, lh / 300)
            toile.create_text(x + lw / 2, y + lh - 7, text=libelle_modele(str(n)), fill="#5A534C",
                              font=("Segoe UI", 8))

    def onglet_aide(self):
        cadre = ttk.Frame(self.onglets, padding=6)
        self.onglets.add(cadre, text=T("  Aide  "))
        haut = ttk.Frame(cadre)
        haut.pack(fill="x")
        Bouton(haut, "Ouvrir le guide complet (navigateur)", self.ouvrir_guide, style="secondaire", largeur=290,
               hauteur=34, taille=10).pack(side="left")
        texte = scrolledtext.ScrolledText(cadre, wrap="word", font=("Segoe UI", 10), bg="#FFFFFF", relief="flat",
                                          padx=12, pady=8)
        texte.pack(fill="both", expand=True, pady=(6, 0))
        texte.tag_configure("h1", font=("Segoe UI", 15, "bold"), foreground="#2F2B28", spacing1=6, spacing3=4)
        texte.tag_configure("h2", font=("Segoe UI", 12, "bold"), foreground="#7A5C2E", spacing1=10, spacing3=2)
        texte.tag_configure("h3", font=("Segoe UI", 10, "bold"), spacing1=6)
        texte.tag_configure("code", font=("Consolas", 10), foreground="#1E4E8C")
        guide = GUIDE_MD_EN if textes_app.LANGUE[0] == "en" and GUIDE_MD_EN.exists() else GUIDE_MD
        contenu = guide.read_text(encoding="utf-8") if guide.exists() else "Guide introuvable."
        for ligne in contenu.splitlines():
            if ligne.startswith("# "):
                texte.insert("end", ligne[2:] + "\n", "h1")
            elif ligne.startswith("## "):
                texte.insert("end", ligne[3:] + "\n", "h2")
            elif ligne.startswith("### "):
                texte.insert("end", ligne[4:] + "\n", "h3")
            elif set(ligne.replace("|", "").strip()) <= set("-: "):
                continue  # ligne de séparation d'un tableau
            else:
                ligne = ligne.replace("**", "")
                if ligne.startswith("|"):
                    ligne = "   " + "  ·  ".join(c.strip() for c in ligne.strip("|").split("|"))
                for i, morceau in enumerate(ligne.split("`")):
                    texte.insert("end", morceau, "code" if i % 2 else ())
                texte.insert("end", "\n")
        texte.configure(state="disabled")

    # ---------------------------------------------------------------- paramètres
    def charger_parametres(self):
        valeurs = lire_parametres()
        if not valeurs.get("PERSONNE") and not valeurs.get("SORTIE"):  # fichier vidé (fermeture forcée...)
            retrouves, origine = parametres_retrouves()
            if retrouves and messagebox.askyesno(NOM_APPLI, T(
                    "Vos paramètres semblent vides (fichier abîmé lors d'une fermeture forcée ?).\n\nRestaurer les "
                    "derniers réglages connus ({origine}) ?\n\nPersonne : {personne}\nPhotos : {photos}\nTravail : "
                    "{travail}").format(origine=origine, personne=retrouves.get("PERSONNE", ""),
                                        photos=retrouves.get("PHOTOS", ""), travail=retrouves.get("SORTIE", ""))):
                valeurs.update({c: v for c, v in retrouves.items() if v or c not in valeurs})
                ecrire_parametres({c: valeurs.get(c, "") for c in set(valeurs) | set(self.vars)
                                   if c not in ("TEXTE_FIN",)})
        for cle, var in self.vars.items():
            var.set(valeurs.get(cle, ""))
        for cle, zone in self.multilignes.items():
            fichier = ICI / "texte_fin.txt"
            texte = texte_fin_complet(fichier.read_text(encoding="utf-8-sig") if fichier.exists() else "",
                                      valeurs.get(cle, ""))
            zone.delete("1.0", "end")
            zone.insert("1.0", texte)
            zone.edit_modified(False)
        if not valeurs.get("LETTRES_TEINTE"):
            self.vars["LETTRES_TEINTE"].set("couleur")
        self.modifie = False
        self.planifier_apercu()
        self.etat_params.configure(text=T("Fichier : {fichier}").format(fichier=PARAMETRES), foreground="#8C847C")
        self.maj_titre()

    def marquer_modifie(self):
        if self.modifie:
            return
        self.modifie = True
        if hasattr(self, "etat_params"):
            self.etat_params.configure(text=T("Modifié : pensez à enregistrer (fait aussi automatiquement avant "
                                              "chaque étape)."), foreground="#B3261E")

    def enregistrer(self, silencieux=False):
        valeurs = {cle: var.get().strip() for cle, var in self.vars.items()}
        actuels = lire_parametres() if PARAMETRES.exists() else {}
        if not valeurs.get("PERSONNE") and not valeurs.get("SORTIE") and (actuels.get("PERSONNE") or
                                                                         actuels.get("SORTIE")):
            # garde-fou : ne jamais écraser des réglages remplis par un formulaire vide
            self.charger_parametres()
            return True
        for cle, zone in self.multilignes.items():  # texte long : dans texte_fin.txt (une ligne ne suffit pas)
            texte = zone.get("1.0", "end-1c").strip()
            fichier = ICI / "texte_fin.txt"
            try:
                textes_app.enregistrer_texte_fin(fichier, texte)
            except PermissionError:
                messagebox.showerror(NOM_APPLI, T("{fichier} est ouvert dans un autre programme : fermez-le.").format(
                    fichier=fichier.name))
                return False
            valeurs[cle] = ""
        if "," in valeurs["PERSONNE"]:
            messagebox.showerror(NOM_APPLI, T("« Personne du livre » : une seule personne. Mettez les autres dans "
                                              "« Proches à mettre en avant »."))
            return False
        if valeurs.get("PHOTOS") and valeurs.get("SORTIE"):
            try:
                a, b = Path(valeurs["PHOTOS"]).resolve(), Path(valeurs["SORTIE"]).resolve()
                melanges = a == b or a in b.parents or b in a.parents
            except OSError:
                melanges = False
            if melanges:
                messagebox.showerror(NOM_APPLI, T("Le dossier de travail doit être en dehors du dossier des photos "
                                                  "(l'outil n'écrit jamais sur le disque de backup)."))
                return False
        if valeurs["NAISSANCE"] and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", valeurs["NAISSANCE"]):
            messagebox.showerror(NOM_APPLI, T("Date de naissance : format JJ/MM/AAAA (ex. 10/11/2003)."))
            return False
        try:
            ecrire_parametres(valeurs)
        except PermissionError:
            messagebox.showerror(NOM_APPLI, T("{fichier} est ouvert dans un autre programme : fermez-le.").format(
                fichier=PARAMETRES.name))
            return False
        self.modifie = False
        self.etat_params.configure(text=T("Enregistré à {heure} dans {fichier}").format(
                                       heure=f"{dt.datetime.now():%H:%M}", fichier=PARAMETRES.name),
                                   foreground="#1E6B35")
        self.maj_titre()
        if not silencieux:
            self.bilan()
        return True

    def parcourir(self, var):
        dossier = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if dossier:
            var.set(str(Path(dossier)))

    def parcourir_fichier(self, var):
        depart = Path(var.get()).parent if var.get() else Path(self.vars["PHOTOS"].get() or Path.home())
        fichier = filedialog.askopenfilename(initialdir=str(depart), filetypes=[
            (T("Photos"), "*.jpg *.jpeg *.png *.heic *.tif *.tiff *.webp"), (T("Tous les fichiers"), "*.*")])
        if fichier:
            var.set(str(Path(fichier)))

    def maj_titre(self):
        personne = self.vars["PERSONNE"].get() or "?"
        self.titre.configure(text=T("{nom} · livre de {personne}").format(nom=NOM_APPLI, personne=personne))
        self.sous_titre.configure(text=T("Photos : {photos}   ·   Travail : {travail}   ·   {version}").format(
            photos=self.vars['PHOTOS'].get() or '?', travail=self.vars['SORTIE'].get() or '?', version=self.version))

    def dossier_livre(self):
        sortie = Path(self.vars["SORTIE"].get() or ".")
        nom = self.vars["PERSONNE"].get()
        for d in sortie.glob("livre_*") if sortie.exists() else []:
            if d.is_dir() and d.name.lower() == f"livre_{nom}".lower():
                return d
        return sortie / f"livre_{nom}"

    def ouvrir_dossier(self, quoi):
        sortie = Path(self.vars["SORTIE"].get() or ".")
        cible = {"": sortie, "livre": self.dossier_livre(), "famille": sortie / "famille",
                 "lettres": self.dossier_livre() / "lettres"}[quoi]
        if not cible.exists():
            messagebox.showinfo(NOM_APPLI, T("Ce dossier n'existe pas encore :\n{dossier}\n\nIl sera créé par "
                                             "l'étape correspondante.").format(dossier=cible))
            return
        ouvrir(cible)

    # ---------------------------------------------------------------- bilan : prochaine étape conseillée
    def bilan(self):
        manquantes = bibliotheques_manquantes()
        sortie = Path(self.vars["SORTIE"].get() or ".")
        livre = self.dossier_livre()
        famille = sortie / "famille" / (self.vars["PERSONNE"].get() or "_")
        if manquantes:
            conseil, etape = (T("Bibliothèques à installer ({liste}) : bouton « 🔧 Maintenance » puis « Installer / réparer ».").format(
                liste=", ".join(manquantes[:4])), "installer")
        elif not famille.exists() or not any(famille.iterdir()):
            if (sortie / "base.sqlite").exists():  # analyse déjà faite : seules les photos de référence manquent
                conseil, etape = (T("Ajoutez 3 à 10 photos nettes du visage de {personne} dans {dossier} (bouton "
                                    "« Photos de référence »), puis « Préparer la sélection ». L'analyse du disque est "
                                    "déjà faite : inutile de la refaire.").format(
                    personne=self.vars['PERSONNE'].get(), dossier=famille), "preparer")
            else:
                conseil, etape = (T("Ajoutez 3 à 10 photos nettes du visage de {personne} dans {dossier} (bouton "
                                    "« Photos de référence »), puis « Analyser le disque ».").format(
                    personne=self.vars['PERSONNE'].get(), dossier=famille), "analyser")
        elif not (sortie / "base.sqlite").exists():
            conseil, etape = T("Prochaine étape : « Analyser le disque »."), "analyser"
        elif not (livre / "selection_livre.csv").exists():
            conseil, etape = (T("Livre de {personne} : prochaine étape « Préparer la sélection » (l'analyse du disque "
                                "est déjà faite et sert pour toutes les personnes).").format(
                personne=self.vars['PERSONNE'].get()), "preparer")
        elif not list(livre.glob("Apercu_*.pdf")):
            conseil, etape = (T("Prochaine étape : « Choisir les photos », puis « Aperçus des ambiances »."),
                              "choisir")
        elif not self.vars["AMBIANCE"].get():
            conseil, etape = (T("Regardez les aperçus (bouton « Dossier du livre »), choisissez l'ambiance dans "
                                "Paramètres > Livre, puis « Livre final »."), "composer")
        else:
            conseil, etape = (T("Ambiance choisie : {ambiance}. Prochaine étape : « Livre final ».").format(
                ambiance=self.vars['AMBIANCE'].get()), "composer")
        self.conseil.configure(text="➜ " + conseil)
        for e, b in self.boutons.items():
            b.nouveau_style("conseil" if e == etape else "etape")

    def bilan_si_pret(self):
        if hasattr(self, "conseil") and "PERSONNE" in self.vars and "SORTIE" in self.vars:
            self.maj_titre()
            self.bilan()
            self.afficher_apercu_mosaique()

    # ---------------------------------------------------------------- lancement des étapes
    def lancer(self, etape):
        if self.processus is not None and self.processus.poll() is not None and self.etape_en_cours is None:
            self.processus = None  # étape finie sans que la fenêtre l'ait su : on libère (plus de faux « en cours »)
        if self.processus is not None:
            messagebox.showinfo(NOM_APPLI, T("Une étape est déjà en cours. Attendez la fin ou cliquez sur "
                                             "« Arrêter l'étape »."))
            return
        if etape not in ("mettre_a_jour", "tests", "partager") and not self.enregistrer(silencieux=True):
            return
        environnement = dict(os.environ, LANCEUR_APP="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        if etape == "analyser" and not self.confirmer_nouvelle_analyse():
            return
        if etape == "analyser":
            photos = Path(self.vars["PHOTOS"].get() or "_")
            if not photos.is_dir():
                dossier = filedialog.askdirectory(title=T("Dossier des photos (disque de backup)"))
                if not dossier:
                    return
                self.vars["PHOTOS"].set(str(Path(dossier)))
                self.enregistrer(silencieux=True)
        if etape == "preparer" and (self.dossier_livre() / "selection_livre.csv").exists():
            reponse = messagebox.askyesnocancel(
                NOM_APPLI, T("Une sélection existe déjà pour {personne}.\n\nOui = la refaire (vos choix seront perdus ; "
                             "une copie est gardée)\nNon = garder la sélection actuelle et l'afficher").format(
                    personne=self.vars['PERSONNE'].get()))
            if reponse is None:
                return
            environnement["LANCEUR_REPONSE"] = "o" if reponse else "n"
            if reponse:
                selection = self.dossier_livre() / "selection_livre.csv"
                shutil.copy2(selection, selection.with_name(
                    f"selection_livre_avant_refaire_{dt.datetime.now():%Y%m%d-%H%M}.csv"))
        if etape == "apercu":
            choix = self.choisir_apercus()
            if choix is None:
                return
            environnement["LANCEUR_APERCUS"] = ",".join(choix)
        if etape in ("composer", "powerpoint") and not self.vars["AMBIANCE"].get():
            messagebox.showinfo(NOM_APPLI, T("Choisissez d'abord l'ambiance du livre dans Paramètres > Livre "
                                             "(après avoir regardé les aperçus)."))
            self.onglets.select(1)
            return
        commande = [python_console(), "-u", str(ICI / "lanceur.py"), etape]
        options = {}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        texte = T(nom_etape(etape))  # avant le lancement : une erreur ici ne laisse jamais une étape « fantôme »
        try:
            self.processus = subprocess.Popen(commande, cwd=ICI, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                              stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                              errors="replace", env=environnement, **options)
        except OSError as erreur:
            messagebox.showerror(NOM_APPLI, T("Impossible de lancer Python : {erreur}").format(erreur=erreur))
            self.processus = None
            return
        self.etape_en_cours = etape
        self.dernieres_lignes = []
        self.prog = {}
        self.ecrire(f"\n===== {dt.datetime.now():%d/%m/%Y %H:%M} · {texte} =====\n", "titre")
        if etape in ("choisir", "reduire", "choisir_lettres", "proposer", "appliquer", "preparer", "verifier_visages"):
            self.ecrire(T("L'écran de choix s'ouvre dans le navigateur. Quand c'est fini, cliquez sur « Terminer » "
                          "dans la page.\n"), "suivante")
        self.etat.configure(text=T("En cours : {etape}").format(etape=texte))
        self.barre.start(12)
        self.bouton_arret.activer(True)
        for b in self.boutons.values():
            b.activer(False)
        self.onglets.select(0)
        threading.Thread(target=self.lire_processus, args=(self.processus,), daemon=True).start()

    def confirmer_nouvelle_analyse(self):
        """Analyse déjà faite : la relancer ne sert qu'après l'ajout de photos sur le disque (pas pour une autre
        personne). On le dit avant de lancer une étape qui peut être longue."""
        import sqlite3

        base = Path(self.vars["SORTIE"].get() or ".") / "base.sqlite"
        if not base.exists():
            return True
        try:
            with sqlite3.connect(f"file:{base}?mode=ro", uri=True) as connexion:
                nombre = connexion.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
        except sqlite3.Error:
            return True
        return messagebox.askyesno(NOM_APPLI, T(
            "L'analyse est déjà faite ({nombre} photos). Elle sert pour toutes les personnes : pour faire le livre "
            "d'une autre personne, il suffit de changer « Personne du livre » puis de cliquer sur « Préparer la "
            "sélection ».\n\nLa relancer ne sert que si vous avez ajouté des photos sur le disque (seules les "
            "nouvelles seront analysées).\n\nRelancer l'analyse ?").format(nombre=nombre))

    def choisir_apercus(self):
        """Fenêtre : quelles ambiances (re)faire ; renvoie la liste, ou None si annulé."""
        fenetre = tk.Toplevel(self)
        fenetre.title(NOM_APPLI)
        fenetre.configure(bg="#FFFFFF")
        fenetre.transient(self)
        fenetre.resizable(False, False)
        tk.Label(fenetre, text=T("Quels aperçus faire ou refaire ?"), bg="#FFFFFF", fg="#2F2B28",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(fenetre, text=T("Les aperçus non cochés restent tels quels."), bg="#FFFFFF", fg="#8C847C",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 8))
        livre, cases = self.dossier_livre(), {}
        for cle in AMBIANCES:
            pdf = livre / f"Apercu_{self.vars['PERSONNE'].get()}_{cle}.pdf"
            date = (T("déjà fait le {date}").format(date=f"{dt.datetime.fromtimestamp(pdf.stat().st_mtime):%d/%m/%Y %H:%M}")
                    if pdf.exists() else T("pas encore fait"))
            var = tk.BooleanVar(value=not pdf.exists())
            ligne = tk.Frame(fenetre, bg="#FFFFFF")
            ligne.pack(fill="x", padx=16)
            tk.Checkbutton(ligne, text=libelle(cle), variable=var, bg="#FFFFFF", font=("Segoe UI", 10), width=22,
                           anchor="w", activebackground="#FFFFFF").pack(side="left")
            tk.Label(ligne, text=date, bg="#FFFFFF", fg="#8C847C", font=("Segoe UI", 9)).pack(side="left")
            cases[cle] = var
        resultat = {"choix": None}
        bas = tk.Frame(fenetre, bg="#FFFFFF")
        bas.pack(fill="x", padx=16, pady=14)

        def tout(valeur):
            for v in cases.values():
                v.set(valeur)

        def valider():
            choix = [c for c, v in cases.items() if v.get()]
            if not choix:
                messagebox.showinfo(NOM_APPLI, T("Cochez au moins une ambiance."), parent=fenetre)
                return
            resultat["choix"] = choix
            fenetre.destroy()
        Bouton(bas, "Tout cocher", lambda: tout(True), style="secondaire", largeur=120, hauteur=32, taille=9,
               gras=False, fond_parent="#FFFFFF").pack(side="left")
        Bouton(bas, "Tout décocher", lambda: tout(False), style="secondaire", largeur=120, hauteur=32, taille=9,
               gras=False, fond_parent="#FFFFFF").pack(side="left", padx=6)
        Bouton(bas, "✔  Lancer", valider, style="valider", largeur=120, hauteur=32,
               fond_parent="#FFFFFF").pack(side="right")
        Bouton(bas, "Annuler", fenetre.destroy, style="secondaire", largeur=100, hauteur=32, taille=9, gras=False,
               fond_parent="#FFFFFF").pack(side="right", padx=6)
        fenetre.bind("<Return>", lambda e: valider())
        fenetre.bind("<Escape>", lambda e: fenetre.destroy())
        # centrée sur l'application, au premier plan ; la fenêtre principale attend sans se figer
        fenetre.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - fenetre.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - fenetre.winfo_reqheight()) // 3
        fenetre.geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            fenetre.wait_visibility()
            fenetre.grab_set()  # garder la main sur cette fenêtre (sans planter si le système refuse)
        except tk.TclError:
            pass
        fenetre.lift()
        fenetre.focus_force()
        self.wait_window(fenetre)
        return resultat["choix"]

    def lire_processus(self, processus):
        for ligne in processus.stdout:
            self.file.put(("ligne", ligne))
        processus.wait()
        self.file.put(("fin", processus.returncode))

    def lire_sortie(self):
        self.pouls = time.monotonic()  # pour le détecteur de blocage
        lot = []  # lignes regroupées : une seule insertion et un seul défilement par passage (bien plus rapide)
        try:
            for _ in range(300):  # au plus 300 lignes par passage : la fenêtre reste réactive même si ça défile vite
                type_, contenu = self.file.get_nowait()
                if type_ != "ligne" and lot:
                    self.ecrire_lot(lot)
                    lot = []
                if type_ == "ligne" and contenu.startswith("PROGRESSION "):
                    self.maj_progression(contenu[12:].strip())
                    continue
                if type_ == "version":
                    self.version = T("version du {date}").format(date=contenu)
                    self.maj_titre()
                elif type_ == "ligne":
                    self.dernieres_lignes = (self.dernieres_lignes + [contenu])[-40:]
                    tag = ("erreur" if "ERREUR" in contenu or "Traceback" in contenu else
                           "suivante" if contenu.lstrip().startswith(("Étape suivante", "Livre terminé", "C'est fait", "Tous les tests", "VERDICT : tout", "✓ OK",
                                                              "Outil à jour", "6 modèles")) else
                           "doux" if contenu.startswith(">") else ())
                    lot.append((contenu, tag))
                else:
                    self.fin_etape(contenu)
        except queue.Empty:
            pass
        if lot:
            self.ecrire_lot(lot)
        self.after(100, self.lire_sortie)

    def maj_progression(self, texte):
        """« fait/total étape » : barre qui se remplit, pourcentage, temps restant estimé (et dans le titre de la
        fenêtre, visible même réduite dans la barre des tâches)."""
        compte, _, etape = texte.partition(" ")
        fait, _, total = compte.partition("/")
        if not fait.isdigit():
            return
        fait = int(fait)
        etape = T(etape)
        if textes_app.LANGUE[0] == "en":
            etape = etape.replace("Aperçu ", "Preview ")
        maintenant = time.monotonic()
        if self.prog.get("etape") != etape:  # nouvelle phase : on repart de zéro pour l'estimation
            self.prog = {"etape": etape, "debut": maintenant, "fait0": fait}
        if not total.isdigit() or not int(total):  # total inconnu (inventaire) : compteur seul
            self.etat.configure(text=f"{etape} : {fait:,}".replace(",", " ") + " " + T("fichiers parcourus"))
            return
        total = int(total)
        pct = min(100, fait * 100 // total)
        if str(self.barre.cget("mode")) != "determinate":
            self.barre.stop()
            self.barre.configure(mode="determinate")
        self.barre.configure(maximum=total, value=fait)
        reste = ""
        ecoule, faits = maintenant - self.prog["debut"], fait - self.prog["fait0"]
        if faits > 0 and ecoule > 5 and fait < total:
            secondes = ecoule / faits * (total - fait)
            heures, minutes = int(secondes // 3600), int(secondes % 3600 // 60)
            reste = " · " + T("reste ≈ {duree}").format(
                duree=f"{heures} h {minutes:02d}" if heures else (f"{minutes} min" if minutes else "< 1 min"))
        self.etat.configure(text=f"{etape} : {fait:,} / {total:,} ({pct} %){reste}".replace(",", " "))
        self.title(f"{pct} % · {NOM_APPLI}")

    def ecrire_lot(self, lot):
        """Ajoute plusieurs lignes au journal d'un coup ; le journal affiché garde les 3000 dernières lignes
        (le texte complet reste dans journal.txt) : au-delà, Windows ralentit beaucoup l'affichage."""
        j = self.journal
        j.configure(state="normal")
        for texte, tag in lot:
            j.insert("end", texte, tag)
        lignes = int(j.index("end-1c").split(".")[0])
        if lignes > 3000:
            j.delete("1.0", f"{lignes - 3000}.0")
        j.see("end")
        j.configure(state="disabled")

    def fin_etape(self, code):
        etape = self.etape_en_cours
        self.processus = None
        self.etape_en_cours = None
        self.barre.stop()
        self.barre.configure(mode="indeterminate", value=0)
        self.title(NOM_APPLI)
        self.bouton_arret.activer(False)
        for b in self.boutons.values():
            b.activer(True)
        if code == 0:
            self.etat.configure(text=T("Terminé ✓"))
            self.ecrire(T("✓ Étape terminée.\n"), "suivante")
        else:
            self.etat.configure(text=T("Arrêté / erreur"))
            self.ecrire(T("✗ L'étape s'est arrêtée (voir les messages ci-dessus).\n"), "erreur")
        if etape in ("installer", "mettre_a_jour"):
            bibliotheques_manquantes(rafraichir=True)
        self.charger_parametres()  # une étape peut avoir complété le fichier de paramètres
        self.bilan()
        if etape in ("mosaique", "mosaique_apercu"):
            self.afficher_apercu_mosaique()
            if etape == "mosaique_apercu" and code == 0:
                self.onglets.select(1)  # Paramètres > Mosaïque, où l'aperçu s'affiche
                self.sous_onglets.select(self.onglet_mosaique)
        self.revenir_au_premier_plan()  # après un écran dans le navigateur : l'application repasse devant
        if etape == "mettre_a_jour" and code == 0:
            self.apres_mise_a_jour()

    def revenir_au_premier_plan(self):
        try:
            if self.state() == "iconic":
                self.deiconify()
            self.lift()
            self.attributes("-topmost", True)  # Windows ne laisse pas toujours une fenêtre passer devant le navigateur
            self.after(400, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except tk.TclError:
            pass

    def apres_mise_a_jour(self):
        texte = "".join(self.dernieres_lignes)
        nouveau = re.search(r"Désormais, utilisez le dossier : (.+)", texte)
        if nouveau:  # outil copié dans %USERPROFILE%\AlbumPhotos : on y déplace les raccourcis
            dossier = Path(nouveau.group(1).strip())
            if messagebox.askyesno(NOM_APPLI, T("L'outil a été copié dans :\n{dossier}\n\nMettre les raccourcis "
                                                "« Album Photos » sur cette nouvelle copie et la lancer ?").format(
                                                    dossier=dossier)):
                subprocess.Popen([python_console(), str(dossier / "installer_app.py"), "--raccourcis"],
                                 cwd=dossier, **({"creationflags": subprocess.CREATE_NO_WINDOW}
                                                 if os.name == "nt" else {}))
                self.after(1500, self.destroy)
            return
        if messagebox.askyesno(NOM_APPLI, T("Mise à jour terminée. Redémarrer l'application pour utiliser la "
                                            "nouvelle version ?")):
            self.etat.configure(text=T("Redémarrage…"))
            self.update_idletasks()
            options = {"creationflags": subprocess.DETACHED_PROCESS} if os.name == "nt" else {}
            subprocess.Popen([sys.executable, str(Path(__file__).resolve())], cwd=ICI, close_fds=True, **options)
            self.after(300, self.destroy)  # la nouvelle fenêtre s'ouvre pendant que l'ancienne se ferme

    def arreter(self):
        if self.processus is None:
            return
        if not messagebox.askyesno(NOM_APPLI, T("Arrêter l'étape en cours ? (Le travail déjà fait est conservé : "
                                                "l'analyse reprendra où elle s'est arrêtée.)")):
            return
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.processus.pid)], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            self.processus.terminate()

    # ---------------------------------------------------------------- journal
    def surveiller_blocage(self):
        """Si la fenêtre ne répond plus pendant plus de 3 s, note dans journal.txt ce qu'elle était en train de
        faire (pour trouver la cause d'un « Ne répond pas » sous Windows). N'agit pas sur l'interface."""
        import traceback

        principal = threading.main_thread().ident
        deja = False
        while True:
            time.sleep(1)
            fige = time.monotonic() - self.pouls
            if fige > 3 and not deja:
                pile = sys._current_frames().get(principal)
                noter_erreur(f"Fenêtre figée depuis {fige:.0f} s, en train de :\n"
                             + "".join(traceback.format_stack(pile)[-8:] if pile else []))
                deja = True
            elif fige < 1:
                deja = False

    def ecrire(self, texte, tag=()):
        self.journal.configure(state="normal")
        self.journal.insert("end", texte, tag)
        self.journal.see("end")
        self.journal.configure(state="disabled")

    def effacer(self):
        self.journal.configure(state="normal")
        self.journal.delete("1.0", "end")
        self.journal.configure(state="disabled")

    def copier(self):
        self.clipboard_clear()
        self.clipboard_append(self.journal.get("1.0", "end"))
        self.etat.configure(text=T("Journal copié"))

    def ouvrir_guide(self):
        if textes_app.LANGUE[0] == "en" and GUIDE_HTML_EN.exists():
            ouvrir(GUIDE_HTML_EN)
        else:
            ouvrir(GUIDE_HTML if GUIDE_HTML.exists() else GUIDE_MD)

    def changer_langue(self):
        """Bouton FR / EN : change la langue de l'application (gardée dans LANGUE du fichier de paramètres)."""
        if self.processus is not None:
            messagebox.showinfo(NOM_APPLI, T("Attendez la fin de l'étape en cours pour changer de langue."))
            return
        self.enregistrer(silencieux=True)
        textes_app.LANGUE[0] = "en" if textes_app.LANGUE[0] == "fr" else "fr"
        valeurs = lire_parametres()
        valeurs["LANGUE"] = textes_app.LANGUE[0]
        ecrire_parametres({cle: valeurs.get(cle, "") for cle in list(self.vars) + ["LANGUE"]})
        journal = self.journal.get("1.0", "end-1c")
        for enfant in self.winfo_children():
            enfant.destroy()
        self.boutons, self.vars, self.multilignes = {}, {}, {}
        self.toile_planche, self._apercu_prevu = None, None
        self.construire()
        self.charger_parametres()
        self.ecrire(journal)
        self.bilan()

    def quitter(self):
        if self.processus is not None and not messagebox.askyesno(
                NOM_APPLI, T("Une étape est en cours. Quitter quand même ? (elle sera arrêtée)")):
            return
        if self.processus is not None:
            self.arreter_force()
        if self.modifie and messagebox.askyesno(NOM_APPLI, T("Enregistrer les paramètres modifiés ?")):
            self.enregistrer(silencieux=True)
        self.destroy()

    def arreter_force(self):
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.processus.pid)], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            self.processus.terminate()


def noter_erreur(texte):
    """Erreur inattendue : notée dans journal.txt (à envoyer à Claude) au lieu de disparaître sans trace."""
    try:
        with open(ICI / "journal.txt", "a", encoding="utf-8") as f:
            f.write(f"\n===== {dt.datetime.now():%d/%m/%Y %H:%M} - erreur de l'application =====\n{texte}\n")
    except OSError:
        pass


if __name__ == "__main__":
    import traceback

    try:
        appli = Application()

        def erreur_tk(type_, valeur, trace):  # erreur dans un bouton : notée, l'application continue
            noter_erreur("".join(traceback.format_exception(type_, valeur, trace)))
            messagebox.showerror(NOM_APPLI, T("Erreur inattendue (notée dans journal.txt) : {erreur}").format(
                erreur=valeur))
        appli.report_callback_exception = erreur_tk
        appli.mainloop()
    except Exception:
        noter_erreur(traceback.format_exc())
        raise
