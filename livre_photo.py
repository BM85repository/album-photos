#!/usr/bin/env python3
"""livre_photo.py - le livre photo complet d'une personne, prêt pour l'imprimeur.

Générique : --personne désigne la vedette du livre (un sous-dossier du dossier famille),
--avec les proches à mettre en avant (frère, sœur, grands-parents...).

Prérequis : avoir lancé « album_famille.py analyser » sur le disque de photos.
Les photos originales ne sont jamais modifiées : tout est écrit dans --sortie.

Étapes :
  1. preparer   trouve toutes les photos de la personne, repère les événements marquants
                et choisit au plus --max photos comme le ferait un photographe
                -> livre_<Prénom>/selection_livre.csv (modifiable dans Excel) + planche_livre.html
  2. composer   met en page le livre (gabarits variés, recadrage centré sur les visages,
                fond perdu, illustrations) et copie les photos retenues
                -> Livre_<Prénom>_interieur.pdf, Livre_<Prénom>_couverture.pdf,
                   photos_selectionnees/, contenu_livre.csv, rapport_impression.txt

Exemple :
  python livre_photo.py --sortie C:\\AlbumsFamille preparer --personne Laura --avec Hugo
         --famille C:\\AlbumsFamille\\famille --naissance 12/03/2012
  python livre_photo.py --sortie C:\\AlbumsFamille composer --personne Laura
"""
import argparse
import datetime as dt
import hashlib
import html
import itertools
import math
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

import album_famille as af
from traduction import traduire

TYPES = ["voyage", "anniversaire", "noel", "nouvel-an", "mariage", "bapteme", "naissance", "fete", "vacances"]
TYPES_SPECIAUX = set(TYPES)
FORMATS = {"carre30": (300, 300), "carre20": (200, 200), "a4-paysage": (297, 210), "a4-portrait": (210, 297)}
COLONNES = ["chapitre", "souvenir", "date", "heure", "titre", "type", "lieu", "fichier", "personnes",
            "score", "garder", "vedette", "legende", "remarque"]
COTE_MIN_LIVRE = 700  # pixels : en dessous, même une petite case serait floue à l'impression
DPI_CIBLE, DPI_ALERTE = 300, 200
TAILLE_LEGENDE = 14  # points : jamais plus petit, même sur un A4
HAUTEUR_LEGENDE = 8  # mm réservés sous une photo légendée
SEUIL_PEU_NET = 100  # netteté (variance du laplacien) sous laquelle une photo est montrée plus petite
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]
PAYS = {
    "FR": "France", "PH": "Philippines", "IT": "Italie", "ES": "Espagne", "PT": "Portugal", "DE": "Allemagne",
    "BE": "Belgique", "CH": "Suisse", "LU": "Luxembourg", "NL": "Pays-Bas", "GB": "Royaume-Uni", "IE": "Irlande",
    "AT": "Autriche", "GR": "Grèce", "HR": "Croatie", "MC": "Monaco", "MA": "Maroc", "TN": "Tunisie",
    "US": "États-Unis", "CA": "Canada", "MX": "Mexique", "BR": "Brésil", "JP": "Japon", "KR": "Corée du Sud",
    "CN": "Chine", "HK": "Hong Kong", "SG": "Singapour", "TH": "Thaïlande", "VN": "Vietnam", "ID": "Indonésie",
    "MY": "Malaisie", "KH": "Cambodge", "AU": "Australie", "NZ": "Nouvelle-Zélande", "IN": "Inde",
    "AE": "Émirats arabes unis", "TR": "Turquie", "EG": "Égypte", "RE": "La Réunion", "MU": "Maurice",
    "PL": "Pologne", "HU": "Hongrie", "CZ": "Tchéquie", "RU": "Russie", "UA": "Ukraine", "NO": "Norvège",
    "SE": "Suède", "DK": "Danemark", "FI": "Finlande", "IS": "Islande", "TW": "Taïwan",
}
DRAPEAUX = {  # (sens des bandes, couleurs) ; quelques drapeaux particuliers sont dessinés à part
    "FR": ("v", ["#002395", "#FFFFFF", "#ED2939"]), "IT": ("v", ["#009246", "#FFFFFF", "#CE2B37"]),
    "BE": ("v", ["#000000", "#FDDA24", "#EF3340"]), "IE": ("v", ["#169B62", "#FFFFFF", "#FF883E"]),
    "DE": ("h", ["#000000", "#DD0000", "#FFCE00"]), "NL": ("h", ["#AE1C28", "#FFFFFF", "#21468B"]),
    "LU": ("h", ["#EA141D", "#FFFFFF", "#51ADDA"]), "AT": ("h", ["#C8102E", "#FFFFFF", "#C8102E"]),
    "ES": ("h", ["#AA151B", "#F1BF00", "#F1BF00", "#AA151B"]), "ID": ("h", ["#CE1126", "#FFFFFF"]),
    "MC": ("h", ["#CE1126", "#FFFFFF"]), "PL": ("h", ["#FFFFFF", "#DC143C"]), "UA": ("h", ["#0057B7", "#FFD700"]),
    "HU": ("h", ["#CE2939", "#FFFFFF", "#477050"]), "RU": ("h", ["#FFFFFF", "#0039A6", "#D52B1E"]),
    "TH": ("h", ["#A51931", "#F4F5F8", "#2D2A4A", "#2D2A4A", "#F4F5F8", "#A51931"]),
}
PALETTE = ["#8A6F5C", "#5E7D8C", "#7C8C5E", "#A0645A", "#6B5E8C", "#5C8A80"]  # tons doux, imprimables
FOND, TEXTE, TEXTE_CLAIR = "#FBF8F3", "#2F2B28", "#8C847C"
AMBIANCES = {  # trois partis pris de photographe ; tous aérés (4 photos par page au plus, pages de respiration)
    "elegant": {"nom": "Élégant", "fond": "#FFFFFF", "photo": "classique", "petits": "classique",
                "ouverture": "cadre", "ouverture_fond": "blanc", "titres": "serif", "legendes": "serif",
                "marge": 22, "ecart": 7, "max_par_page": 4, "respiration": 3, "organisation": "chrono-lieux",
                "scotch": False, "palette": ["#7D7468", "#6E7F86", "#8A7D6B", "#6F6A7E"]},
    "tendre": {"nom": "Tendre", "fond": FOND, "photo": "arrondi", "petits": "polaroid",
               "ouverture": "cercle", "ouverture_fond": "couleur", "titres": "serif", "legendes": "serif",
               "marge": 18, "ecart": 6, "max_par_page": 4, "respiration": 3, "organisation": "themes",
               "scotch": False, "palette": PALETTE},
    "carnet": {"nom": "Carnet souvenirs", "fond": "#F3ECDF", "photo": "polaroid", "petits": "polaroid",
               "ouverture": "cercle", "ouverture_fond": "couleur", "titres": "main", "legendes": "main",
               "marge": 17, "ecart": 8, "max_par_page": 4, "respiration": 2, "organisation": "chrono-lieux",
               "scotch": True, "palette": ["#C9826B", "#7FA3A8", "#B7A15B", "#9A85B0", "#86A77C"]},
    # composées par double page, à la manière des albums de mariage
    "prestige": {"nom": "Prestige", "fond": "#161514", "photo": "classique", "petits": "classique",
                 "ouverture": "cadre", "ouverture_fond": "couleur", "titres": "serif", "legendes": "serif",
                 "marge": 13, "ecart": 3, "max_par_page": 6, "respiration": 99, "organisation": "themes",
                 "scotch": False, "palette": ["#C8A96A"], "planches": True, "or": "#C8A96A", "texte": "#E9E2D6",
                 "sombre": True},
    # variantes plus denses du prestige (mêmes couleurs, plus de photos par planche)
    "prestige-compact": {"nom": "Prestige compact", "fond": "#161514", "photo": "classique", "petits": "classique",
                         "ouverture": "cadre", "ouverture_fond": "couleur", "titres": "serif", "legendes": "serif",
                         "marge": 11, "ecart": 2.5, "max_par_page": 8, "respiration": 99, "organisation": "themes",
                         "scotch": False, "palette": ["#C8A96A"], "planches": True, "or": "#C8A96A", "texte": "#E9E2D6",
                         "sombre": True, "caps": (8, 7, 6),  # 1re valeur = densité par défaut
                         "regle": {"ouverture": "page", "heros_min": 10, "insets": 4, "ecrin_max": 5}},
    "prestige-mosaique": {"nom": "Prestige mosaïque", "fond": "#161514", "photo": "classique", "petits": "classique",
                          "ouverture": "cadre", "ouverture_fond": "couleur", "titres": "serif", "legendes": "serif",
                          "marge": 10, "ecart": 2, "max_par_page": 9, "respiration": 99, "organisation": "chrono",
                          "scotch": False, "palette": ["#C8A96A"], "planches": True, "or": "#C8A96A",
                          "texte": "#E9E2D6", "sombre": True, "caps": (9, 8, 7),
                          "regle": {"ouverture": "bandeau", "heros_min": 9999, "insets": 0, "ecrin_max": 0,
                                    "enchainer": True}},
    # bande dessinée : cases à gros trait, encadrés jaunes, bulles ; « bd » transforme les photos en dessin
    "bd": {"nom": "BD cartoon", "fond": "#FFFFFF", "photo": "bd", "petits": "bd", "ouverture": "bd",
           "ouverture_fond": "blanc", "titres": "impact", "legendes": "bd", "marge": 12, "ecart": 4.5,
           "max_par_page": 5, "respiration": 99, "organisation": "chrono-lieux", "scotch": False,
           "palette": ["#E63946", "#1D3557", "#F4A261", "#2A9D8F"], "effet": "cartoon", "bd": True},
    "bd-photo": {"nom": "BD photo", "fond": "#FFFFFF", "photo": "bd", "petits": "bd", "ouverture": "bd",
                 "ouverture_fond": "blanc", "titres": "impact", "legendes": "bd", "marge": 12, "ecart": 4.5,
                 "max_par_page": 5, "respiration": 99, "organisation": "chrono-lieux", "scotch": False,
                 "palette": ["#E63946", "#1D3557", "#F4A261", "#2A9D8F"], "bd": True},
    "prestige-mosaique-bd": {"nom": "Prestige mosaïque BD photo", "fond": "#FFFFFF", "photo": "bd", "petits": "bd",
                             "ouverture": "bd", "ouverture_fond": "blanc", "titres": "impact", "legendes": "bd",
                             "marge": 10, "ecart": 4, "max_par_page": 9, "respiration": 99, "organisation": "chrono",
                             "scotch": False, "palette": ["#E63946"], "planches": True, "or": "#E63946",
                             "texte": "#151515", "bd": True, "caps": (9, 8, 7),
                             "regle": {"ouverture": "bandeau", "heros_min": 9999, "insets": 0, "ecrin_max": 0,
                                       "enchainer": True}},
    "magazine": {"nom": "Magazine", "fond": "#FFFFFF", "photo": "classique", "petits": "classique",
                 "ouverture": "cadre", "ouverture_fond": "blanc", "titres": "serif", "legendes": "serif",
                 "marge": 12, "ecart": 3, "max_par_page": 6, "respiration": 99, "organisation": "themes",
                 "scotch": False, "palette": ["#8C7B65"], "planches": True, "or": "#8C7B65", "texte": TEXTE,
                 "sombre": False},
}


# =========================================================================== 1. préparer

def trouver_nom(nom, refs):
    for cle in refs:
        if cle.lower() == nom.lower():
            return cle
    sys.exit(f"« {nom} » n'a pas de dossier de référence. Dossiers trouvés : {', '.join(refs)}")


def code_pays(lieu):
    return lieu[-3:-1] if lieu and lieu.endswith(")") else ""


def nom_pays(code):
    return PAYS.get(code, code)


def age(naissance, jour):
    if not naissance:
        return None
    return jour.year - naissance.year - ((jour.month, jour.day) < (naissance.month, naissance.day))


def type_auto(photos, naissance, maison):
    """Reconnaît ce qui peut l'être d'après les dates et le GPS ; mariage, baptême... se saisissent dans Excel."""
    jours = {p["date"].date() for p in photos}
    if naissance and any(0 <= (j - naissance).days <= 10 for j in jours):
        return "naissance"
    if naissance and any(j.year > naissance.year and abs((j - naissance.replace(year=j.year)).days) <= 1
                         for j in jours if not (naissance.month == 2 and naissance.day == 29)):
        return "anniversaire"
    if any(j.month == 12 and j.day in (24, 25) for j in jours):
        return "noel"
    if any((j.month, j.day) in ((12, 31), (1, 1)) for j in jours):
        return "nouvel-an"
    pays = {code_pays(p["lieu"]) for p in photos if p["lieu"]}
    if pays - maison - {""}:
        return "voyage"
    return ""


def titre_auto(type_, photos, sujet, naissance):
    debut = photos[0]["date"]
    pays = Counter(code_pays(p["lieu"]) for p in photos if p["lieu"])
    if type_ == "naissance":
        return f"Bienvenue {sujet}"
    if type_ == "anniversaire":
        a = age(naissance, max(p["date"] for p in photos))
        if a is None or a < 1:  # date de naissance inconnue ou incohérente : pas de « Les 0 ans »
            return f"Anniversaire de {sujet}"
        return f"Le premier anniversaire de {sujet}" if a == 1 else f"Les {a} ans de {sujet}"
    if type_ == "noel":
        return f"Noël {debut.year}"
    if type_ == "nouvel-an":
        return f"Nouvel An {debut.year + 1 if debut.month == 12 else debut.year}"
    if type_ == "voyage" and pays:
        return f"Voyage – {nom_pays(pays.most_common(1)[0][0])}"
    lieu = af.lieu_court(photos[0]["lieu_evenement"])
    return lieu or f"{MOIS[debut.month - 1].capitalize()} {debut.year}"


def cmd_preparer(args):
    base = af.ouvrir_base(args.sortie)
    detecteur, reco = af.modeles(args.sortie)
    refs, exclusions = af.charger_references(base, args.famille, detecteur, reco)
    sujet = trouver_nom(args.personne, refs)
    avec = [trouver_nom(n.strip(), refs) for n in args.avec.split(",")] if args.avec else []
    naissance = dt.datetime.strptime(args.naissance, "%d/%m/%Y").date() if args.naissance else None
    photos = {p["id"]: p for p in af.charger_photos(base)}

    # qui est sur chaque photo
    presents = defaultdict(dict)
    for photo_id, largeur, nom, _ in af.identifier(base, refs, exclusions, args.seuil, photos).values():
        presents[photo_id][nom] = max(presents[photo_id].get(nom, 0), largeur)
    candidates = []
    for pid, noms in presents.items():
        if sujet in noms:
            p = dict(photos[pid])
            p["personnes"] = sorted(noms)
            p["avec"] = any(n in noms for n in avec)
            p["largeur_sujet"] = noms[sujet]
            candidates.append(p)
    candidates = af.retirer_absentes(base, candidates, "chemin")
    if not candidates:
        sys.exit(f"Aucune photo de {sujet} trouvée : vérifiez les photos de référence ou baissez --seuil.")
    print(f"  {len(candidates)} photos de {sujet} : doublons, souvenirs et choix des plus belles...", flush=True)
    af.marquer_doublons(candidates, largeur=lambda p: p["largeur_sujet"])
    eligibles = [p for p in candidates if not p["doublon_de"] and not p["flou"]
                 and min(p["largeur_orig"] or 9999, p["hauteur_orig"] or 9999) >= COTE_MIN_LIVRE]

    # les événements : taille, proches présents, type
    maison = set(args.pays_maison.upper().split(",")) if args.pays_maison else {
        Counter(code_pays(p["lieu"]) for p in photos.values() if p["lieu"]).most_common(1)[0][0]
        if any(p["lieu"] for p in photos.values()) else ""}
    total_par_evenement = Counter(p["evenement"] for p in photos.values())
    for p in candidates:
        p["evenement_brut"] = p["evenement"]
    regrouper_sejours(eligibles, maison, total_par_evenement)
    evenements = defaultdict(list)
    for p in sorted(eligibles, key=lambda p: p["date"]):
        evenements[p["evenement"]].append(p)
    infos = {}
    for numero, groupe in evenements.items():
        type_ = type_auto(groupe, naissance, maison)
        membres = set().union(*(p["personnes"] for p in groupe))
        importance = (math.log1p(total_par_evenement[numero]) + 0.5 * math.log1p(len(groupe))
                      + 1.0 * any(p["avec"] for p in groupe) + 0.4 * (len(membres) - 1) + 1.5 * bool(type_))
        infos[numero] = {"type": type_, "importance": importance, "titre": titre_auto(type_, groupe, sujet, naissance)}
    for p in eligibles:
        p["valeur"] = (p["score"] + 0.35 * p["avec"] + 0.15 * (len(p["personnes"]) >= 2 or p["nb_visages"] >= 3)
                       + 0.1 * (p["nb_visages"] == 1 and p["largeur_sujet"] > 0.15))

    choisies = choisir(evenements, infos, args.max)
    marquer_vedettes(evenements, infos, choisies, args.max)

    dossier = dossier_livre(args.sortie, sujet)
    fichier = dossier / "selection_livre.csv"
    if fichier.exists() and not args.ecraser:
        sys.exit(f"{fichier} existe déjà (vos choix seraient perdus). Ajoutez --ecraser pour le refaire.")
    # toutes les photos de la personne vont dans le fichier : les écartées (doublon, floue, trop petite) aussi,
    # non gardées et marquées, pour pouvoir les voir et en reprendre une dans l'écran de choix
    gardees_ids = {id(p) for p in eligibles}
    vers_souvenir = {p["evenement_brut"]: p["evenement"] for p in eligibles}
    ecartees = defaultdict(list)
    for p in candidates:
        if id(p) in gardees_ids:
            continue
        cote = min(p["largeur_orig"] or 9999, p["hauteur_orig"] or 9999)
        p["remarque"] = (f"doublon de {p['doublon_de']}" if p["doublon_de"] else "floue" if p["flou"]
                         else f"petite ({cote} px)")
        p["valeur"] = p["score"]
        ecartees[vers_souvenir.get(p["evenement"], f"e{p['evenement']}")].append(p)
    for cle, groupe in ecartees.items():
        if cle not in evenements:  # souvenir sans aucune photo exploitable : il est créé, non gardé
            groupe.sort(key=lambda p: p["date"])
            evenements[cle] = []
            infos[cle] = {"type": "", "titre": af.lieu_court(groupe[0].get("lieu_evenement") or groupe[0]["lieu"] or "")
                          or f"{MOIS[groupe[0]['date'].month - 1].capitalize()} {groupe[0]['date'].year}"}
    lignes = []
    for numero in sorted(evenements, key=lambda n: min(p["date"] for p in evenements[n] + ecartees.get(n, []))):
        groupe = sorted(evenements[numero] + ecartees.get(numero, []), key=lambda p: p["date"])
        for p in groupe:
            lignes.append((groupe[0]["date"].year, numero,
                           af.date_fr(p["date"]), f"{p['date']:%H:%M}", infos[numero]["titre"], infos[numero]["type"],
                           p.get("lieu_evenement") or p["lieu"] or "", p["chemin"], ", ".join(p["personnes"]),
                           round(p["valeur"], 3), 1 if p["id"] in choisies else 0, p.get("vedette", ""), "",
                           p.get("remarque", "")))
    af.ecrire_csv(fichier, COLONNES, lignes)
    planche_livre(base, args.sortie, dossier, sujet, {n: g for n, g in evenements.items() if g}, infos, choisies,
                  args.max)
    annees = Counter(evenements[n][0]["date"].year for n in evenements for p in evenements[n] if p["id"] in choisies)
    print(f"{sujet} : {len(candidates)} photos trouvées, {len(eligibles)} exploitables, {len(choisies)} retenues "
          f"(max {args.max}) sur {len(annees)} années, {sum(1 for i in infos.values() if i['type'])} événements spéciaux")
    print("  par année : " + ", ".join(f"{a} : {n}" for a, n in sorted(annees.items())))
    print(f"Sélection : {fichier}")
    print(f"Aperçu    : {dossier / 'planche_livre.html'}")


def regrouper_sejours(photos, maison, totaux):
    """Un voyage ou un séjour de plusieurs jours = un seul souvenir (les nuits coupent les événements).
    Les photos sont rangées par souvenir : une fusion ne déplace que les photos concernées (rapide même pour
    des dizaines de milliers de photos)."""
    photos.sort(key=lambda p: p["date"])
    membres = defaultdict(list)
    for p in photos:
        membres[p["evenement"]].append(p)
    precedent = None
    for p in photos:
        if precedent and p["evenement"] != precedent["evenement"]:
            pays, pays_avant = code_pays(p["lieu_evenement"]), code_pays(precedent["lieu_evenement"])
            ecart = (p["date"] - precedent["date"]).total_seconds() / 86400
            meme_voyage = pays and pays == pays_avant and pays not in maison and ecart <= 3
            meme_sejour = (p["lieu_evenement"] and p["lieu_evenement"] == precedent["lieu_evenement"]
                           and ecart <= 1.5 and p["date"].date() != precedent["date"].date())
            if meme_voyage or meme_sejour:
                cible, ancien = precedent["evenement"], p["evenement"]
                totaux[cible] += totaux.pop(ancien, 0)
                for q in membres.pop(ancien, []):
                    q["evenement"] = cible
                    membres[cible].append(q)
        precedent = p


def choisir(evenements, infos, maximum):
    """Sélection d'un photographe : chaque année représentée, les grands moments d'abord,
    rendement décroissant pour ne pas noyer le livre sous un seul événement, variété dans chaque événement."""
    choisies, par_evenement, par_annee = set(), Counter(), Counter()
    annee = {n: g[0]["date"].year for n, g in evenements.items()}

    def plafond(n):
        return 20 if infos[n]["type"] else 12

    def suivante(n):
        prises = [p for p in evenements[n] if p["id"] in choisies]
        meilleure, note_max = None, -9
        for p in evenements[n]:
            if p["id"] in choisies:
                continue
            note = p["valeur"]
            note -= 0.4 * any(abs((p["date"] - q["date"]).total_seconds()) < 90 for q in prises)
            note -= 0.4 * any(af.distance(p["dhash"], q["dhash"]) <= 12 for q in prises)
            if note > note_max:
                meilleure, note_max = p, note
        return meilleure

    def prendre(n):
        p = suivante(n)
        if p:
            choisies.add(p["id"])
            par_evenement[n] += 1
            par_annee[annee[n]] += 1
        return p

    for a in sorted(set(annee.values())):  # au moins le plus beau moment de chaque année
        if len(choisies) < maximum:
            prendre(max((n for n in evenements if annee[n] == a), key=lambda n: infos[n]["importance"]))
    while len(choisies) < maximum:
        ouverts = [n for n in evenements if par_evenement[n] < min(plafond(n), len(evenements[n]))]
        if not ouverts:
            break
        # importance au carré : les grands moments prennent nettement plus de place que les petits
        n = max(ouverts, key=lambda n: infos[n]["importance"] ** 2 / (1 + par_evenement[n]) ** 1.5
                / (1 + par_annee[annee[n]] / 15))
        if not prendre(n):
            par_evenement[n] = plafond(n)
    return choisies


def marquer_vedettes(evenements, infos, choisies, maximum):
    """Pleine page pour la plus belle photo des grands événements ; une photo de couverture."""
    retenues = []
    for n, groupe in evenements.items():
        prises = [p for p in groupe if p["id"] in choisies]
        if (infos[n]["type"] and len(prises) >= 4) or len(prises) >= 6:
            retenues.append((infos[n]["importance"], max(prises, key=lambda p: p["valeur"])))
    for _, p in sorted(retenues, key=lambda x: -x[0])[: max(1, maximum // 15)]:
        p["vedette"] = "1"
    portraits = [p for g in evenements.values() for p in g if p["id"] in choisies and p["nb_visages"] <= 2]
    if portraits:
        recent = max(p["date"].year for p in portraits) - 3  # une photo récente, la personne telle qu'elle est
        couverture = max(portraits, key=lambda p: p["score"] + p["largeur_sujet"] + 0.3 * (p["date"].year >= recent))
        couverture["vedette"] = "couverture"


def dossier_livre(sortie, nom):
    for dossier in sortie.glob("livre_*"):  # « laura » retrouve livre_Laura
        if dossier.is_dir() and dossier.name.lower() == f"livre_{af.nettoyer(nom)}".lower():
            return dossier
    dossier = sortie / f"livre_{af.nettoyer(nom)}"
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def planche_livre(base, sortie, dossier, sujet, evenements, infos, choisies, maximum):
    """Page de contrôle (planche_livre.html) : seulement les photos retenues. Les autres se voient dans l'écran
    de choix ; fabriquer leurs vignettes ici prenait jusqu'à une heure sur un grand disque, sans rien afficher."""
    blocs, annee_courante = [], None
    total, faites = len(choisies), 0
    for n in sorted(evenements, key=lambda n: evenements[n][0]["date"]):
        groupe = evenements[n]
        annee = groupe[0]["date"].year
        if annee != annee_courante:
            blocs.append(f"<h2>{annee}</h2>")
            annee_courante = annee
        prises = [p for p in groupe if p["id"] in choisies]
        if not prises:
            continue
        etiquette = f" <span class='type'>{infos[n]['type']}</span>" if infos[n]["type"] else ""
        blocs.append(f"<h3>{html.escape(infos[n]['titre'])}{etiquette} <small>{af.date_fr(groupe[0]['date'])} · "
                     f"{len(prises)} retenue(s) sur {len(groupe)}</small></h3><div class='grille'>")
        for p in prises:
            faites += 1
            af.progression("Vignettes de la sélection", faites, total)
            vignette = af.apercu(base, sortie, p["chemin"], 320, "vignettes")
            if vignette is None:  # photo introuvable sur le disque
                continue
            chemin = Path("..") / vignette.relative_to(sortie)
            classe = "garde" if p["id"] in choisies else "ecarte"
            marque = {"1": " ★ pleine page", "couverture": " ★ couverture"}.get(p.get("vedette", ""), "")
            blocs.append(f"<figure class='{classe}'><img src='{chemin.as_posix()}' loading='lazy'><figcaption>"
                         f"{html.escape(Path(p['chemin']).name)}{marque}<br>{html.escape(', '.join(p['personnes']))}"
                         "</figcaption></figure>")
        blocs.append("</div>")
    (dossier / "planche_livre.html").write_text(
        f"<!doctype html><meta charset='utf-8'><title>Livre de {html.escape(sujet)}</title><style>"
        "body{font-family:Georgia,serif;margin:16px;background:#fbf8f3;color:#2f2b28}"
        "h2{border-bottom:1px solid #ccc;margin-top:32px}h3{font-size:16px}small{color:#888;font-weight:normal}"
        ".type{background:#8a6f5c;color:#fff;border-radius:4px;padding:1px 6px;font-size:12px}"
        ".grille{display:flex;flex-wrap:wrap;gap:8px}"
        "figure{margin:0;width:170px;font:11px sans-serif;border:4px solid #bbb;background:#fff}"
        "figure.garde{border-color:#2e9d4f}figure.ecarte{opacity:.45}"
        "img{width:100%;height:130px;object-fit:cover;display:block}figcaption{padding:4px;word-break:break-all}"
        f"</style><h1>Livre de {html.escape(sujet)}</h1><p>{len(choisies)} photos retenues sur {maximum} maximum. "
        "Pour changer la sélection : bouton « Choisir les photos » de l'application.</p>" + "".join(blocs),
        encoding="utf-8",
    )


# =========================================================================== 1 bis. proposer des améliorations

def cmd_proposer(args):
    """Part de la sélection déjà faite (garder = 1) et propose, sans rien changer :
    - REMPLACER une photo trop peu définie, peu nette, ou nettement moins belle qu'une autre du même souvenir ;
    - AJOUTER des photos dans les années peu représentées, en particulier les plus récentes ;
    - RETIRER, pour garder le même total, les photos les moins fortes des années sur-représentées."""
    base = af.ouvrir_base(args.sortie)
    dossier = dossier_livre(args.sortie, args.personne)
    fichier = dossier / "selection_livre.csv"
    if not fichier.exists():
        sys.exit(f"Lancez d'abord : python livre_photo.py preparer --personne {args.personne} ...")
    lignes = af.lire_csv(fichier)
    garde = lambda l: l["garder"].strip().lower() in ("1", "oui", "x")
    choisies = [l for l in lignes if garde(l)]
    if not choisies:
        sys.exit("Aucune photo marquée garder = 1 : rien à améliorer.")
    # les photos écartées à la préparation (doublon, floue, trop petite) ne sont jamais proposées
    lignes = [l for l in lignes if garde(l) or not (l.get("remarque") or "").strip()]

    infos = {p["chemin"]: dict(p) for p in base.execute(
        "SELECT id, chemin, largeur_orig, hauteur_orig, nettete, dhash FROM photos")}
    proches = set()
    if args.avec and args.famille:  # proches à mettre en avant : on regarde qui est sur chaque photo
        detecteur, reco = af.modeles(args.sortie)
        refs, exclusions = af.charger_references(base, args.famille, detecteur, reco)
        avec = {trouver_nom(n.strip(), refs) for n in args.avec.split(",") if n.strip()}
        par_id = {p["id"]: c for c, p in infos.items()}
        for photo_id, _, nom, _ in af.identifier(base, refs, exclusions, args.seuil, set(par_id)).values():
            if nom in avec:
                proches.add(par_id[photo_id])

    def cote(l):
        p = infos.get(l["fichier"])
        return min(p["largeur_orig"] or 0, p["hauteur_orig"] or 0) if p else 0

    def valeur(l):
        """Ce qu'un photographe regarde : beauté (score), définition, présence des proches."""
        return (float(l["score"] or 0) + 0.25 * min(1.0, cote(l) / 3000)
                + (0.25 if l["fichier"] in proches else 0))

    def faible(l):
        p = infos.get(l["fichier"]) or {}
        return cote(l) and cote(l) < 1200 or (p.get("nettete") is not None and p["nettete"] < SEUIL_PEU_NET)

    def proche_doublon(l, autour):
        h = (infos.get(l["fichier"]) or {}).get("dhash")
        return bool(h) and any(af.distance(h, infos[a["fichier"]]["dhash"]) <= 10 for a in autour
                               if a is not l and (infos.get(a["fichier"]) or {}).get("dhash"))

    par_souvenir = defaultdict(list)
    for l in lignes:
        par_souvenir[l["souvenir"]].append(l)
    selection = list(choisies)
    utilisees = {l["fichier"] for l in choisies}
    propositions = []

    def meilleure_alternative(l, exigence):
        candidates = [a for a in par_souvenir[l["souvenir"]] if a["fichier"] not in utilisees and exigence(a)
                      and not proche_doublon(a, [s for s in selection if s is not l])]
        return max(candidates, key=valeur, default=None)

    # 1. remplacements : qualité d'abord, puis « nettement plus belle » dans le même souvenir
    for l in sorted(choisies, key=valeur):
        if l.get("vedette", "").strip().lower() == "couverture":
            continue
        if faible(l):
            alt = meilleure_alternative(l, lambda a: cote(a) >= max(1500, 1.3 * cote(l)) and not faible(a)
                                        and valeur(a) >= valeur(l) - 0.05)
            raison = f"meilleure qualité ({cote(l)} px -> {cote(alt)} px de petit côté)" if alt else ""
        else:
            alt = meilleure_alternative(l, lambda a: valeur(a) > valeur(l) + 0.30 and not faible(a))
            raison = "plus belle photo du même souvenir" + (" (avec un proche)" if alt and alt["fichier"] in proches
                                                           else "") if alt else ""
        if alt:
            propositions.append(("REMPLACER", raison, l, alt))
            utilisees.add(alt["fichier"])
            selection[selection.index(l)] = alt
    remplacements = [p for p in propositions if p[0] == "REMPLACER"]
    propositions = sorted(remplacements, key=lambda p: valeur(p[2]) - valeur(p[3]))[:args.max_remplacements]
    selection, utilisees = list(choisies), {l["fichier"] for l in choisies}
    for _, _, ancienne, nouvelle in propositions:
        selection[selection.index(ancienne)] = nouvelle
        utilisees.add(nouvelle["fichier"])

    # 2. équilibre des années : objectif proportionnel (racine du nombre de photos), récent favorisé
    annee = lambda l: int(l["date"][-4:])
    disponibles = Counter(annee(l) for l in lignes)
    derniere = max(disponibles)
    poids = {a: math.sqrt(n) * (1.6 if a >= derniere - args.recent + 1 else 1.0) for a, n in disponibles.items()}
    total = len(selection)
    objectif = {a: min(disponibles[a], max(2, round(total * w / sum(poids.values())))) for a, w in poids.items()}
    actuel = Counter(annee(l) for l in selection)
    ajouts = []
    for a in sorted(objectif, key=lambda a: -(objectif[a] - actuel[a])):
        manque = objectif[a] - actuel[a]
        if manque < 2:
            continue
        candidates = sorted((l for l in lignes if annee(l) == a and l["fichier"] not in utilisees and not faible(l)),
                            key=valeur, reverse=True)
        par_souv = Counter()
        for tour in (1, 2, 99):  # d'abord un par souvenir, pour la variété
            for l in candidates:
                if manque <= 0:
                    break
                if l["fichier"] in utilisees or par_souv[l["souvenir"]] >= tour or proche_doublon(l, selection):
                    continue
                ajouts.append(("AJOUTER", f"{a} : {actuel[a]} photo(s) gardée(s) pour {disponibles[a]} disponibles"
                               + (" (année récente)" if a >= derniere - args.recent + 1 else ""), None, l))
                utilisees.add(l["fichier"])
                selection.append(l)
                par_souv[l["souvenir"]] += 1
                manque -= 1
    # 3. retraits pour garder le total : les moins fortes des années sur-représentées
    retraits = []
    a_retirer = len(ajouts) if not args.garder_total else 0
    actuel = Counter(annee(l) for l in selection)
    while a_retirer > 0:
        surplus = {a: actuel[a] - objectif.get(a, 0) for a in actuel}
        a = max(surplus, key=surplus.get)
        if surplus[a] <= 0:
            break
        candidates = [l for l in selection if annee(l) == a and l.get("vedette", "").strip().lower() != "couverture"
                      and l not in [x[3] for x in ajouts]]
        if not candidates:
            break
        l = min(candidates, key=valeur)
        retraits.append(("RETIRER", f"{a} : {actuel[a]} photos pour un objectif de {objectif[a]} (la moins forte)",
                         l, None))
        selection.remove(l)
        actuel[a] -= 1
        a_retirer -= 1
    propositions += ajouts + retraits

    # sorties : CSV à valider dans Excel + planche visuelle
    nom = lambda l: l["fichier"] if l else ""
    sortie_csv = dossier / "propositions.csv"
    af.ecrire_csv(sortie_csv, ["accepter", "action", "raison", "annee", "souvenir", "titre", "photo_actuelle",
                               "photo_proposee", "valeur_actuelle", "valeur_proposee"],
                  [(1, action, raison, (nouvelle or ancienne)["date"][-4:], (nouvelle or ancienne)["souvenir"],
                    (nouvelle or ancienne)["titre"], nom(ancienne), nom(nouvelle),
                    round(valeur(ancienne), 2) if ancienne else "", round(valeur(nouvelle), 2) if nouvelle else "")
                   for action, raison, ancienne, nouvelle in propositions])
    planche_propositions(base, args.sortie, dossier, propositions)
    print(f"{len(choisies)} photos dans votre sélection.")
    print(f"  {sum(p[0] == 'REMPLACER' for p in propositions)} remplacement(s) proposé(s) "
          "(qualité ou photo plus belle du même souvenir)")
    print(f"  {len(ajouts)} ajout(s) pour les années peu représentées, {len(retraits)} retrait(s) pour garder le total")
    print("  par année après propositions : " + ", ".join(
        f"{a} : {n}" for a, n in sorted(Counter(annee(l) for l in selection).items())))
    print(f"Propositions : {sortie_csv}  (colonne accepter : 1 = oui, 0 = non)")
    print(f"Aperçu       : {dossier / 'planche_propositions.html'}")


def planche_propositions(base, sortie, dossier, propositions):
    def vignette(l):
        if not l:
            return "<div class='vide'>—</div>"
        try:
            vignette = af.apercu(base, sortie, l["fichier"], 320, "vignettes")
            if vignette is None:
                raise SystemExit
            chemin = Path("..") / vignette.relative_to(sortie)
            return (f"<figure><img src='{chemin.as_posix()}' loading='lazy'><figcaption>{html.escape(l['date'])}<br>"
                    f"{html.escape(Path(l['fichier']).name)}</figcaption></figure>")
        except SystemExit:  # disque débranché : pas de vignette
            return f"<div class='vide'>{html.escape(Path(l['fichier']).name)}</div>"
    blocs = []
    for titre, action in (("Remplacements proposés", "REMPLACER"), ("Ajouts proposés", "AJOUTER"),
                          ("Retraits proposés", "RETIRER")):
        lot = [p for p in propositions if p[0] == action]
        if not lot:
            continue
        blocs.append(f"<h2>{titre} ({len(lot)})</h2>")
        for i, (_, raison, ancienne, nouvelle) in enumerate(lot, 1):
            fleche = "→" if action == "REMPLACER" else ""
            blocs.append(f"<div class='ligne'><span class='num'>{action[0]}{i}</span>{vignette(ancienne)}"
                         f"<span class='fleche'>{fleche}</span>{vignette(nouvelle)}"
                         f"<p>{html.escape(raison)}</p></div>")
    (dossier / "planche_propositions.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Propositions</title><style>"
        "body{font-family:Georgia,serif;margin:16px;background:#fbf8f3;color:#2f2b28}"
        ".ligne{display:flex;align-items:center;gap:12px;margin:8px 0;padding:6px;background:#fff;border-radius:6px}"
        "figure{margin:0;width:170px;font:11px sans-serif}img{width:100%;height:120px;object-fit:cover}"
        ".vide{width:170px;height:120px;display:flex;align-items:center;justify-content:center;color:#aaa;"
        "font:11px sans-serif;border:1px dashed #ccc}.fleche{font-size:28px;color:#8a6f5c}"
        ".num{font:bold 13px sans-serif;width:42px;color:#8a6f5c}p{font:13px sans-serif;flex:1}"
        "</style><h1>Propositions d'amélioration</h1><p>Rien n'est encore changé. Ouvrez propositions.csv dans "
        "Excel : accepter = 1 pour appliquer, 0 pour refuser, puis lancez l'application des propositions.</p>"
        + "".join(blocs), encoding="utf-8")


def cmd_appliquer(args):
    """Applique les propositions acceptées (accepter = 1) à selection_livre.csv, après une copie de sauvegarde."""
    dossier = dossier_livre(args.sortie, args.personne)
    fichier, propositions = dossier / "selection_livre.csv", dossier / "propositions.csv"
    if not propositions.exists():
        sys.exit("Aucune proposition : lancez d'abord la commande proposer.")
    lignes = af.lire_csv(fichier)
    par_fichier = {l["fichier"]: l for l in lignes}
    sauvegarde = dossier / f"selection_livre_avant_{dt.datetime.now():%Y%m%d-%H%M}.csv"
    shutil.copy2(fichier, sauvegarde)
    faites = Counter()
    for p in af.lire_csv(propositions):
        if p["accepter"].strip().lower() not in ("1", "oui", "x"):
            continue
        if p["photo_actuelle"] in par_fichier:
            par_fichier[p["photo_actuelle"]]["garder"] = "0"
        if p["photo_proposee"] in par_fichier:
            par_fichier[p["photo_proposee"]]["garder"] = "1"
        faites[p["action"]] += 1
    entetes = list(lignes[0].keys())
    af.ecrire_csv(fichier, entetes, [[l[c] for c in entetes] for l in lignes])
    gardees = sum(l["garder"].strip().lower() in ("1", "oui", "x") for l in lignes)
    print(f"Appliqué : {dict(faites)}. Sélection : {gardees} photos. Sauvegarde de l'ancienne : {sauvegarde.name}")


# =========================================================================== 2. composer : plan du livre

THEMES = [("naissance", "Les premiers jours"), ("anniversaire", "Joyeux anniversaire !"), ("voyage", "Voyages"),
          ("vacances", "Vacances"), ("fetes", "Fêtes et grands moments"), ("", "Au fil des jours")]
NIVEAUX = [  # du plus aéré au plus dense ; on retient le plus aéré qui tient dans --pages
    {"par_page": 4, "ouverture": 6, "pleines": True, "regrouper": False},
    {"par_page": 5, "ouverture": 10, "pleines": True, "regrouper": False},
    {"par_page": 6, "ouverture": 16, "pleines": False, "regrouper": False},
    {"par_page": 4, "ouverture": 12, "pleines": False, "regrouper": True},
    {"par_page": 5, "ouverture": 16, "pleines": False, "regrouper": True},
    {"par_page": 5, "ouverture": None, "pleines": False, "regrouper": True},
    {"par_page": 6, "ouverture": None, "pleines": False, "regrouper": True},
]


def lire_selection(args):
    dossier = dossier_livre(args.sortie, args.personne)
    fichier = dossier / "selection_livre.csv"
    if not fichier.exists():
        sys.exit(f"Lancez d'abord : python livre_photo.py preparer --personne {args.personne} ...")
    lignes = [l for l in af.lire_csv(fichier) if l["garder"].strip().lower() in ("1", "oui", "x")]
    lignes = af.retirer_absentes(af.ouvrir_base(args.sortie), lignes, "fichier")
    if not lignes:
        sys.exit("Aucune photo marquée garder = 1.")
    if len(lignes) > args.max:
        sys.exit(f"{len(lignes)} photos marquées garder = 1, pour {args.max} maximum : retirez-en "
                 f"{len(lignes) - args.max} dans selection_livre.csv, ou relancez avec --max {len(lignes)}.")
    for l in lignes:
        l["jour"] = dt.datetime.strptime(f"{l['date']} {l.get('heure') or '12:00'}", "%d/%m/%Y %H:%M")
        l["vedette"] = l.get("vedette", "").strip().lower()
        l["type"] = l.get("type", "").strip().lower()
    lignes.sort(key=lambda l: l["jour"])
    souvenirs = {}
    for l in lignes:
        s = souvenirs.setdefault(l["souvenir"], {"photos": [], "titre": "", "type": "", "lieu": l["lieu"]})
        s["photos"].append(l)
        s["titre"] = s["titre"] or l["titre"].strip()
        s["type"] = s["type"] or l["type"]
    for s in souvenirs.values():
        s["debut"], s["fin"] = s["photos"][0]["jour"], s["photos"][-1]["jour"]
        s["annee"] = s["debut"].year
    return dossier, sorted(souvenirs.values(), key=lambda s: s["debut"]), lignes


def dates_souvenir(s, avec_annee=True):
    d, f = s["debut"], s["fin"]
    an = f" {f.year}" if avec_annee else ""
    if d.date() == f.date():
        return f"{d.day} {MOIS[d.month - 1]}{an}"
    if (d.year, d.month) == (f.year, f.month):
        return f"Du {d.day} au {f.day} {MOIS[d.month - 1]}{an}"
    return f"Du {d.day} {MOIS[d.month - 1]} au {f.day} {MOIS[f.month - 1]}{an}"


def periode_de(souvenirs):
    annees = sorted({s["annee"] for s in souvenirs})
    return str(annees[0]) if annees[0] == annees[-1] else f"{annees[0]} – {annees[-1]}"


def age_souvenir(s, naissance):
    if naissance:
        return age(naissance, s["fin"].date())
    chiffres = [int(m) for m in s["titre"].split() if m.isdigit()]
    return chiffres[0] if chiffres else None


def construire_chapitres(souvenirs, organisation, naissance, sujet, maison, palette=PALETTE):
    """Découpe le livre en chapitres : par année, par thème ou par lieu (chronologique à l'intérieur).
    chrono-lieux : par année, et chaque changement de lieu commence une nouvelle page."""
    precedent = ("", "")
    for s in sorted(souvenirs, key=lambda s: s["debut"]):  # lieu de chaque souvenir (hérité si pas de GPS)
        code = code_pays(s["lieu"])
        if s["lieu"]:
            ville = af.lieu_court(s["lieu"])
            etranger = code and code not in maison
            precedent = ((nom_pays(code) if etranger else ville),
                         (f"{ville} · {nom_pays(code)}" if etranger and ville else ville or nom_pays(code)))
        s["cle_lieu"], s["nom_lieu"] = precedent
    groupes = defaultdict(list)
    if organisation == "themes":
        for s in souvenirs:
            t = s["type"]
            cle = "fetes" if t in ("noel", "nouvel-an", "mariage", "bapteme", "fete") else (
                t if t in ("naissance", "anniversaire", "voyage", "vacances") else "")
            groupes[cle].append(s)
        ordre = [(cle, titre) for cle, titre in THEMES if groupes[cle]]
    elif organisation == "lieux":
        for s in souvenirs:
            code = code_pays(s["lieu"])
            cle = (nom_pays(code) if code and code not in maison else af.lieu_court(s["lieu"])) or "Au fil des jours"
            groupes[cle].append(s)
        petits = [c for c, l in groupes.items() if sum(len(s["photos"]) for s in l) < 3 and c != "Au fil des jours"]
        for c in petits:  # les lieux à 1 ou 2 photos rejoignent un chapitre « Ici et là »
            groupes["Ici et là"].extend(groupes.pop(c))
        ordre = [(c, c) for c in sorted(groupes, key=lambda c: min(s["debut"] for s in groupes[c]))]
    else:
        for s in souvenirs:
            groupes[s["annee"]].append(s)
        ordre = [(a, str(a)) for a in sorted(groupes)]
    chapitres = []
    for numero, (cle, titre) in enumerate(ordre):
        liste = sorted(groupes[cle], key=lambda s: s["debut"])
        if organisation in ("chrono", "chrono-lieux"):
            a = age(naissance, dt.date(cle, 12, 31)) if naissance else None
            sous_titre = "" if a is None else ("Naissance" if a <= 0 else f"{sujet} a {a} an{'s' * (a > 1)}")
            etiquette = titre if a is None else (f"{titre} · naissance" if a <= 0 else f"{titre} · {a} an{'s' * (a > 1)}")
        else:
            sous_titre = periode_de(liste)
            etiquette = titre
        chapitres.append({"titre": titre, "sous_titre": sous_titre, "etiquette": etiquette, "souvenirs": liste,
                          "couleur": palette[numero % len(palette)], "type": cle if organisation == "themes" else "",
                          "separer": organisation == "chrono-lieux"})
    return chapitres


def decouper(n, maxi=4):
    """Répartit n photos en pages d'au plus maxi photos, aussi égales que possible (pas de page orpheline)."""
    if n <= maxi:
        return [n] if n else []
    pages = max(1, round(n / (maxi - 0.5)))
    while math.ceil(n / pages) > maxi:
        pages += 1
    return [n // pages + (1 if i < n % pages else 0) for i in range(pages)]


MOIS_COURT = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]
JOURS_IMPORTANTS = ("naissance", "anniversaire", "noel", "nouvel-an", "mariage", "bapteme", "baptême")
_MOTS_DE_DATE = {m for m in ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre",
                             "octobre", "novembre", "decembre", "january", "february", "march", "april", "may",
                             "june", "july", "august", "september", "october", "november", "december"]}
_MOTS_DE_DATE |= {m[:3] for m in _MOTS_DE_DATE} | {m[:4] for m in _MOTS_DE_DATE} | {"sept", "le", "du", "au", "en"}


def sans_accents(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def titre_repete_la_date(titre):
    """« Octobre 2010 », « Oct-10 », « 31/10/2010 »... : le titre ne dit rien de plus que la date."""
    mots = [m for m in re.split(r"[^0-9a-z]+", sans_accents(titre).lower()) if m]
    return bool(mots) and all(m.isdigit() or m in _MOTS_DE_DATE for m in mots)


def legende_mixte(p, s, organisation):
    """Sous la première photo d'un souvenir sur une page partagée : « Oct 2010 » (le jour aussi pour un jour
    important : anniversaire, Noël, Nouvel An...), puis le titre s'il ne répète pas la date."""
    d = p["jour"]
    mois = f"{MOIS_COURT[d.month - 1]} {d.year}"
    date = f"{d.day} {mois}" if s.get("type", "") in JOURS_IMPORTANTS else mois
    titre = (s.get("titre") or "").strip()
    if titre_repete_la_date(titre):
        titre = ""
    elif re.search(rf"\s{d.year}$", titre):  # « Noël 2013 » : l'année est déjà dans la date
        titre = titre[: -len(str(d.year))].strip()
    return " · ".join(x for x in (date, titre, p.get("legende", "").strip()) if x)


def legende_seule(p, deja=""):
    """Légende d'une photo seule sur sa page : « Oct 2010 · Paris » (le jour pour un jour important), puis la
    légende écrite à la main. Le lieu n'est pas répété s'il figure déjà dans le titre de la page."""
    d = p["jour"]
    mois = f"{MOIS_COURT[d.month - 1]} {d.year}"
    date = f"{d.day} {mois}" if (p.get("type") or "") in JOURS_IMPORTANTS else mois
    lieu = af.lieu_court(p.get("lieu") or "")
    if lieu and lieu.lower() in (deja or "").lower():
        lieu = ""
    return " · ".join(x for x in (date, lieu, (p.get("legende") or "").strip()) if x)


def planifier(chapitres, niveau, pleine_ok, naissance, organisation):
    pages = [{"modele": "titre"}]
    maxi = niveau["par_page"]
    for chap in chapitres:
        souvenirs = [dict(s, photos=list(s["photos"])) for s in chap["souvenirs"]]
        toutes = [p for s in souvenirs for p in s["photos"]]
        commun_chap = {"chapitre": chap["etiquette"], "couleur": chap["couleur"]}
        premiere_du_chapitre = True
        if niveau["ouverture"] and len(toutes) >= niveau["ouverture"]:
            photo = max((p for p in toutes if p["vedette"] != "1"), key=lambda p: float(p["score"] or 0), default=None)
            if photo:
                for s in souvenirs:
                    if photo in s["photos"]:
                        s["photos"].remove(photo)
                pages.append(dict(commun_chap, modele="chapitre", titre=chap["titre"], sous_titre=chap["sous_titre"],
                                  photo=photo, type=chap["type"]))
                premiere_du_chapitre = False

        def badge(s, p):
            if s["type"] == "anniversaire" and p is s["photos"][0]:
                a = age_souvenir(s, naissance)
                return f"{a} an{'s' * (a > 1)}" if a else ""
            return ""

        separer = chap.get("separer")
        dernier_lieu = None

        def page_mixte(lot, petits_moments=False):
            nonlocal premiere_du_chapitre, dernier_lieu
            vus, legendes = set(), []
            for s, p in lot:
                legendes.append(legende_mixte(p, s, organisation) if id(s) not in vus else p.get("legende", "").strip())
                vus.add(id(s))
            nouveau_lieu = separer and lot[0][0]["cle_lieu"] != dernier_lieu
            if separer:  # en-tête au nom du lieu à chaque changement de lieu
                titre = lot[0][0]["nom_lieu"] if nouveau_lieu else ""
                d, f = lot[0][1]["jour"], lot[-1][1]["jour"]
                sous_titre = dates_souvenir({"debut": d, "fin": f}) if nouveau_lieu else ""
            else:
                titre, sous_titre = (chap["titre"] if premiere_du_chapitre else ""), chap["sous_titre"]
            pages.append(dict(commun_chap, modele="photos", photos=[p for _, p in lot], legendes=legendes,
                              badges=[badge(s, p) for s, p in lot], mixte=True, petits_moments=petits_moments,
                              entete=premiere_du_chapitre or bool(nouveau_lieu), titre=titre, sous_titre=sous_titre,
                              type=chap["type"], souvenir=None))
            premiere_du_chapitre = False
            dernier_lieu = lot[-1][0]["cle_lieu"]

        def par_lieu(plat):
            """Coupe une suite de photos à chaque changement de lieu (chrono-lieux) : jamais deux lieux par page."""
            if not separer:
                return [plat] if plat else []
            series = []
            for element in plat:
                if not series or series[-1][-1][0]["cle_lieu"] != element[0]["cle_lieu"]:
                    series.append([])
                series[-1].append(element)
            return series

        if niveau["regrouper"]:  # densité maximale : les souvenirs se suivent sur des pages partagées
            for serie in par_lieu([(s, p) for s in souvenirs for p in s["photos"]]):
                for taille in decouper(len(serie), maxi):
                    page_mixte(serie[:taille])
                    serie = serie[taille:]
            continue

        en_attente = []

        def vider():
            for serie in par_lieu(list(en_attente)):
                for taille in decouper(len(serie), maxi):
                    page_mixte(serie[:taille], petits_moments=True)
                    serie = serie[taille:]
            en_attente.clear()

        for s in souvenirs:
            if not s["photos"]:
                continue
            vedettes = [p for p in s["photos"] if niveau["pleines"] and p["vedette"] == "1" and pleine_ok(p)]
            if len(s["photos"]) <= 2 and not vedettes and not s["type"]:
                if separer and en_attente and en_attente[-1][0]["cle_lieu"] != s["cle_lieu"]:
                    vider()  # changement de lieu : nouvelle page
                en_attente.extend((s, p) for p in s["photos"])
                if len(en_attente) >= maxi:
                    vider()
                continue
            vider()
            sous_titre = " · ".join(x for x in (dates_souvenir(s), s["lieu"]) if x)
            commun = dict(commun_chap, titre=s["titre"], sous_titre=sous_titre, type=s["type"], souvenir=s, mixte=False)
            reste = [p for p in s["photos"] if p not in vedettes]
            for k, v in enumerate(vedettes):
                pages.append(dict(commun, modele="pleine", photo=v, bandeau=k == 0))
            for k, taille in enumerate(decouper(len(reste), maxi)):
                lot, reste = reste[:taille], reste[taille:]
                pages.append(dict(commun, modele="photos", photos=lot, entete=k == 0 and not vedettes,
                                  legendes=[p.get("legende", "").strip() for p in lot],
                                  badges=[badge(s, p) for p in lot]))
            premiere_du_chapitre = False
            dernier_lieu = s["cle_lieu"]
        vider()
    pages.append({"modele": "fin"})
    return pages


def nombre_de_pages(pages, multiple):
    n = len(pages)
    return n + (-n) % multiple


# =========================================================================== mise en page

def gabarits(n, x, y, w, h, g):
    """Gabarits de montage de 1 à 6 photos : la case 0 est toujours la plus grande."""
    if n == 1:
        return {"une": [(x, y, w, h)]}
    if n == 2:
        a = (w - g) * 0.62
        return {"deux-colonnes": [(x, y, (w - g) / 2, h), (x + (w + g) / 2, y, (w - g) / 2, h)],
                "deux-rangees": [(x, y, w, (h - g) / 2), (x, y + (h + g) / 2, w, (h - g) / 2)],
                "deux-asymetrique": [(x, y, a, h), (x + a + g, y, w - a - g, h)]}
    if n == 3:
        a, b = (w - g) * 0.6, (h - g) * 0.6
        c = (w - 2 * g) / 3
        return {"trois-gauche": [(x, y, a, h), (x + a + g, y, w - a - g, (h - g) / 2),
                                 (x + a + g, y + (h + g) / 2, w - a - g, (h - g) / 2)],
                "trois-haut": [(x, y, w, b), (x, y + b + g, (w - g) / 2, h - b - g),
                               (x + (w + g) / 2, y + b + g, (w - g) / 2, h - b - g)],
                "trois-bas": [(x, y + h - b, w, b), (x, y, (w - g) / 2, h - b - g),
                              (x + (w + g) / 2, y, (w - g) / 2, h - b - g)],
                "trois-colonnes": [(x + i * (c + g), y, c, h) for i in range(3)]}
    if n == 4:
        a, b = (w - g) * 0.6, (h - g) * 0.6
        c, d = (h - 2 * g) / 3, (w - 2 * g) / 3
        return {"quatre-grille": [(x + (i % 2) * (w + g) / 2, y + (i // 2) * (h + g) / 2, (w - g) / 2, (h - g) / 2)
                                  for i in range(4)],
                "quatre-gauche": [(x, y, a, h)] + [(x + a + g, y + i * (c + g), w - a - g, c) for i in range(3)],
                "quatre-haut": [(x, y, w, b)] + [(x + i * (d + g), y + b + g, d, h - b - g) for i in range(3)]}
    if n == 5:
        a, b = (w - g) * 0.5, (h - g) * 0.55
        q, r = (w - 3 * g) / 4, (w - 2 * g) / 3
        petite_l, petite_h = (w - a - 2 * g) / 2, (h - g) / 2
        return {"cinq-gauche": [(x, y, a, h)] + [(x + a + g + (i % 2) * (petite_l + g), y + (i // 2) * (petite_h + g),
                                                   petite_l, petite_h) for i in range(4)],
                "cinq-haut": [(x, y, w, b)] + [(x + i * (q + g), y + b + g, q, h - b - g) for i in range(4)],
                "cinq-rangees": [(x, y, (w - g) / 2, (h - g) / 2), (x + (w + g) / 2, y, (w - g) / 2, (h - g) / 2)]
                + [(x + i * (r + g), y + (h + g) / 2, r, (h - g) / 2) for i in range(3)]}
    c3, r3 = (w - 2 * g) / 3, (h - 2 * g) / 3
    return {"six-grille-3x2": [(x + (i % 3) * (c3 + g), y + (i // 3) * ((h + g) / 2), c3, (h - g) / 2) for i in range(6)],
            "six-grille-2x3": [(x + (i % 2) * ((w + g) / 2), y + (i // 2) * (r3 + g), (w - g) / 2, r3) for i in range(6)],
            "six-mosaique": [(x, y, 2 * c3 + g, 2 * r3 + g)]
            + [(x + 2 * (c3 + g), y + i * (r3 + g), c3, r3) for i in range(2)]
            + [(x + i * (c3 + g), y + 2 * (r3 + g), c3, r3) for i in range(3)]}


def visage_au_bord(photo):
    """Vrai si un visage détecté touche le bord de la photo d'origine (déjà coupé à la prise de vue)."""
    return any(x < 0.01 or y < 0.01 or x + l > 0.99 or y + h > 0.99 for x, y, l, h in photo["visages"])


def fenetre(photo, ratio_case):
    """Recadrage (fractions de l'image) au format de la case, centré sur les visages, un peu d'air au-dessus."""
    ratio = photo["ratio"]
    if ratio > ratio_case:
        cw, ch = ratio_case / ratio, 1.0
    else:
        cw, ch = 1.0, ratio / ratio_case
    if photo["visages"]:  # tête entière : cheveux, oreilles et menton autour du visage détecté (bornés à la photo)
        x0 = max(0.0, min(v[0] - 0.12 * v[2] for v in photo["visages"]))
        x1 = min(1.0, max(v[0] + 1.12 * v[2] for v in photo["visages"]))
        y0 = max(0.0, min(v[1] - 0.22 * v[3] for v in photo["visages"]))
        y1 = min(1.0, max(v[1] + 1.08 * v[3] for v in photo["visages"]))
        cx, haut = (x0 + x1) / 2, (y0 + y1) / 2 - 0.40 * ch
    else:
        x0 = x1 = y0 = y1 = None
        cx, haut = 0.5, 0.45 - ch / 2
    gauche = min(max(cx - cw / 2, 0), 1 - cw)
    haut = min(max(haut, 0), 1 - ch)
    coupe = bool(photo["visages"]) and (x0 < gauche - 0.01 or x1 > gauche + cw + 0.01
                                       or y0 < haut - 0.01 or y1 > haut + ch + 0.01)
    return gauche, haut, cw, ch, coupe


def rangees(comptes, x, y, w, h, g):
    """Rangées de photos de même hauteur (comptes = nombre de photos par rangée)."""
    cases, hr = [], (h - (len(comptes) - 1) * g) / len(comptes)
    for r, c in enumerate(comptes):
        wc = (w - (c - 1) * g) / c
        cases += [(x + i * (wc + g), y + r * (hr + g), wc, hr) for i in range(c)]
    return cases


def gabarits_denses(n, x, y, w, h, g):
    """Mosaïques de 7 à 9 photos (variantes denses du prestige), gouttières fines."""
    c3, r3 = (w - 2 * g) / 3, (h - 2 * g) / 3
    c4 = (w - 3 * g) / 4
    if n == 7:
        a = (w - g) * 0.5
        droite = [(x + a + g + (i % 2) * ((w - a - g - g) / 2 + g), y + (i // 2) * (r3 + g), (w - a - 2 * g) / 2, r3)
                  for i in range(6)]
        return {"sept-3-4": rangees([3, 4], x, y, w, h, g), "sept-4-3": rangees([4, 3], x, y, w, h, g),
                "sept-2-3-2": rangees([2, 3, 2], x, y, w, h, g), "sept-grand": [(x, y, a, h)] + droite}
    if n == 8:
        return {"huit-4-4": rangees([4, 4], x, y, w, h, g), "huit-3-2-3": rangees([3, 2, 3], x, y, w, h, g),
                "huit-2-3-3": rangees([2, 3, 3], x, y, w, h, g)}
    grand = [(x, y, 2 * c4 + g, 2 * r3 + g)] + [(x + (2 + i % 2) * (c4 + g), y + (i // 2) * (r3 + g), c4, r3)
                                                  for i in range(4)] + [(x + i * (c4 + g), y + 2 * (r3 + g), c4, r3)
                                                                        for i in range(4)]
    return {"neuf-3-3-3": [(x + (i % 3) * (c3 + g), y + (i // 3) * (r3 + g), c3, r3) for i in range(9)],
            "neuf-2-3-4": rangees([2, 3, 4], x, y, w, h, g), "neuf-grand": grand}


def gabarits_aeres(n, x, y, w, h, g):
    """Pages de respiration : moins de surface photo, du blanc assumé (comme dans un livre d'auteur)."""
    if n == 1:
        return {"une-centree": [(x + 0.14 * w, y + 0.10 * h, 0.72 * w, 0.72 * h)]}
    if n == 2:
        return {"deux-diagonale": [(x, y, 0.56 * w, 0.48 * h), (x + 0.44 * w, y + 0.48 * h + g, 0.56 * w, 0.52 * h - g)],
                "deux-bande": [(x + i * ((w + g) / 2), y + 0.2 * h, (w - g) / 2, 0.6 * h) for i in range(2)]}
    if n == 3:
        c = (w - 2 * g) / 3
        return {"trois-bande": [(x + i * (c + g), y + 0.24 * h, c, 0.52 * h) for i in range(3)]}
    if n == 4:
        cw, ch = 0.8 * (w - g) / 2, 0.8 * (h - g) / 2
        x0, y0 = x + (w - 2 * cw - g) / 2, y + (h - 2 * ch - g) / 2
        return {"quatre-ilot": [(x0 + (i % 2) * (cw + g), y0 + (i // 2) * (ch + g), cw, ch) for i in range(4)]}
    return {}


def choisir_gabarit(photos, cadre, ecart, precedent, aere=False):
    """Essaie chaque gabarit et chaque placement ; garde celui qui coupe le moins (surtout pas les visages),
    évite d'agrandir une photo trop peu définie et met la meilleure photo dans la plus grande case."""
    x, y, w, h = cadre
    meilleur = None
    if len(photos) > 6:
        choix = gabarits_denses(len(photos), x, y, w, h, ecart)
    else:
        choix = (aere and gabarits_aeres(len(photos), x, y, w, h, ecart)) or gabarits(len(photos), x, y, w, h, ecart)
    for nom, cases in choix.items():
        couts = [[0.0] * len(cases) for _ in photos]  # coût de chaque photo dans chaque case
        for i, p in enumerate(photos):
            for j, case in enumerate(cases):
                part = case[2] * case[3] / (w * h)
                _, _, cw, ch, coupe = fenetre(p, case[2] / case[3])
                flou = cw * p["largeur"] / (case[2] / 25.4) < DPI_ALERTE
                # un visage coupé est rédhibitoire quelle que soit la taille de la case
                couts[i][j] = part * ((1 - cw * ch) + 1.0 * flou - 0.3 * p["note"]) + 0.6 * coupe
        if len(photos) <= 6:
            ordres = itertools.permutations(range(len(photos)))
        else:  # au-delà de 6 photos : affectation optimale directe (9! essais serait trop long)
            from scipy.optimize import linear_sum_assignment

            lignes_opt, colonnes_opt = linear_sum_assignment(np.array(couts))
            ordre = [0] * len(cases)
            for i, j in zip(lignes_opt, colonnes_opt):
                ordre[j] = i
            ordres = [ordre]
        for ordre in ordres:
            cout = (0.15 if nom == precedent else 0.0) + sum(couts[i][j] for j, i in enumerate(ordre))
            if meilleur is None or cout < meilleur[0]:
                meilleur = (cout, nom, [(case, photos[i]) for case, i in zip(cases, ordre)])
    return meilleur[1], meilleur[2]


# =========================================================================== planches (doubles pages) : prestige, magazine

REGLE_PLANCHES = {"ouverture": "planche", "heros_min": 5, "insets": 2, "ecrin_max": 4}


def planifier_planches(chapitres, cap, pleine_ok, pano_ok, organisation, regle=None):
    """Composition par double page, comme un album de mariage : chaque chapitre s'ouvre sur une planche
    titre + grande photo, chaque grand souvenir sur une photo héros (avec médaillons), le reste en écrin et en
    mosaïque à gouttières fines. Chaque chapitre occupe un nombre pair de pages : les planches restent entières."""
    regle = dict(REGLE_PLANCHES, **(regle or {}))
    pages = [{"modele": "titre"}]

    def score(p):
        return float(p["score"] or 0)

    for chap in chapitres:
        souvenirs = [dict(s, photos=list(s["photos"])) for s in chap["souvenirs"]]
        toutes = [p for s in souvenirs for p in s["photos"]]
        if not toutes:
            continue
        commun = {"chapitre": chap["etiquette"], "couleur": chap["couleur"], "type": chap["type"]}
        pages_ouverture = {"planche": 2, "page": 1}.get(regle["ouverture"], 0)
        if pages_ouverture:  # page titre du chapitre (+ grande photo en face pour une ouverture en planche)
            pages.append(dict(commun, modele="chapitre_p", titre=chap["titre"], sous_titre=chap["sous_titre"]))
        if pages_ouverture == 2:
            ouverture = max(toutes, key=lambda p: score(p) + (0.3 if pleine_ok(p) else -1))
            for s in souvenirs:
                if ouverture in s["photos"]:
                    s["photos"].remove(ouverture)
            if pleine_ok(ouverture):
                pages.append(dict(commun, modele="heros", photo=ouverture, insets=[], titre="", sous_titre="",
                                  souvenir=None))
            else:  # pas assez définie pour une pleine page : encadrée et centrée
                pages.append(dict(commun, modele="respiration", photo=ouverture, titre=""))
        contenu, petits = [], []
        separer = chap.get("separer")
        dernier_lieu = [None]

        def numero_suivant():
            return len(pages) + len(contenu) + 1

        def vider_petits():
            while petits:
                lot = petits[:cap]
                del petits[:cap]
                nouveau = separer and lot[0][0]["cle_lieu"] != dernier_lieu[0]
                vus = set()
                bulles, legendes = [], []
                for s, p in lot:  # légende (et bulle BD si souvenir spécial) sur la 1re photo de chaque souvenir
                    premiere = id(s) not in vus
                    bulles.append(BULLES.get(s["type"], "") if premiere else "")
                    legendes.append(legende_mixte(p, s, organisation) if premiere else p.get("legende", "").strip())
                    vus.add(id(s))
                contenu.append(dict(commun, modele="mosaique", photos=[p for _, p in lot],
                                    titre=lot[0][0]["nom_lieu"] if nouveau else "", sous_titre="", bulles=bulles,
                                    souvenir=None, legendes=legendes))
                dernier_lieu[0] = lot[-1][0]["cle_lieu"]

        for s in souvenirs:
            photos = sorted(s["photos"], key=lambda p: p["jour"])
            if not photos:
                continue
            if (len(photos) <= 2 and not s["type"]) or regle.get("enchainer"):  # enchainer : pages pleines
                if separer and petits and petits[-1][0]["cle_lieu"] != s["cle_lieu"]:
                    vider_petits()  # changement de lieu : nouvelle page
                if petits and len(petits) + len(photos) > cap:
                    # ce souvenir (avec les photos du même lieu juste avant) ne tient plus sur la page : on tourne
                    # la page avant lui plutôt que de couper un même lieu en deux pages
                    k = 0
                    while k < len(petits) and petits[-1 - k][0]["cle_lieu"] == s["cle_lieu"]:
                        k += 1
                    if k + len(photos) > cap:  # le lieu entier ne tient pas : au moins ce souvenir ensemble
                        k = 0
                    if len(photos) <= cap and len(petits) > k:
                        meme_lieu = petits[len(petits) - k:]
                        del petits[len(petits) - k:]
                        vider_petits()
                        petits.extend(meme_lieu)
                petits.extend((s, p) for p in photos)
                if len(petits) >= cap:
                    vider_petits()
                continue
            vider_petits()
            dernier_lieu[0] = s["cle_lieu"]
            titre = s["titre"]
            sous_titre = " · ".join(x for x in (dates_souvenir(s), s["lieu"]) if x)
            premier = True
            candidats = [p for p in photos if pleine_ok(p)]
            if len(photos) >= regle["heros_min"] and candidats:  # grand souvenir : photo héros + médaillons
                heros = max(candidats, key=score)
                photos.remove(heros)
                insets = sorted(photos, key=score, reverse=True)[:regle["insets"]]
                for p in insets:
                    photos.remove(p)
                donnees = dict(commun, photo=heros, insets=insets, titre=titre, sous_titre=sous_titre, souvenir=s)
                if pano_ok(heros) and numero_suivant() % 2 == 0:  # panoramique : seulement sur une planche entière
                    contenu.append(dict(donnees, modele="pano"))
                    contenu.append(dict(donnees, modele="pano_suite"))
                else:
                    contenu.append(dict(donnees, modele="heros"))
                premier = False
            for taille in decouper(len(photos), cap):
                lot, photos = photos[:taille], photos[taille:]
                contenu.append(dict(commun, modele="ecrin" if premier and taille <= regle["ecrin_max"] else "mosaique",
                                    photos=lot,
                                    titre=titre if premier else "", sous_titre=sous_titre if premier else "",
                                    souvenir=s, legendes=[""] * len(lot)))
                premier = False
        vider_petits()
        if regle["ouverture"] == "bandeau" and contenu:  # pas de page d'ouverture : le titre du chapitre en tête
            premiere = contenu[0]
            premiere["titre"] = chap["titre"] + (f" · {premiere['titre']}" if premiere.get("titre") else "")
        if (pages_ouverture + len(contenu)) % 2:  # planche incomplète : une page de respiration
            sources = [pg for pg in contenu if pg["modele"] in ("mosaique", "ecrin") and len(pg["photos"]) >= 3]
            if sources:
                source = max(sources, key=lambda pg: len(pg["photos"]))
                i = max(range(len(source["photos"])), key=lambda i: score(source["photos"][i]))
                photo = source["photos"].pop(i)
                source["legendes"].pop(i)
                contenu.insert(contenu.index(source) + 1, dict(commun, modele="respiration", photo=photo, titre=""))
            else:
                contenu.append(dict(commun, modele="ornement", titre=chap["titre"]))
        pages.extend(contenu)
    pages.append({"modele": "fin"})
    return pages


class PlanchesMixin:
    """Modèles de page des ambiances composées par double page (prestige, magazine)."""

    def accent(self):
        return self.amb.get("or", TEXTE)

    def filet_cadre(self, retrait):
        """Filet fin (or en prestige) à l'intérieur du format fini."""
        self.couleur(self.accent(), "draw")
        self.pdf.set_line_width(0.35)
        self.pdf.rect(self.b + retrait, self.b + retrait, self.l - 2 * retrait, self.h - 2 * retrait, "D")
        self.pdf.set_line_width(0.2)

    def ornement(self, cx, y, largeur):
        """Deux filets et un losange : séparateur classique des livres de prestige."""
        self.couleur(self.accent(), "draw")
        self.couleur(self.accent())
        self.pdf.set_line_width(0.3)
        d = 1.6 * self.k
        self.pdf.line(cx - largeur / 2, y, cx - 2.5 * d, y)
        self.pdf.line(cx + 2.5 * d, y, cx + largeur / 2, y)
        self.pdf.polygon([(cx, y - d), (cx + d, y), (cx, y + d), (cx - d, y)], style="F")
        self.pdf.set_line_width(0.2)

    def tirage(self, ligne, case, bord=2.5):
        """Photo posée : bord blanc et ombre douce (médaillons sur la photo héros)."""
        case = self.entiere_si_coupe(ligne, case)
        case, motifs = self.controler(ligne, case)
        self.reduite = bool(motifs)
        x, y, w, h = case
        e = bord * self.k
        self.ombre(x - e, y - e, w + 2 * e, h + 2 * e)
        self.couleur("#FFFFFF")
        self.pdf.rect(x - e, y - e, w + 2 * e, h + 2 * e, "F")
        self.style_courant = "médaillon"
        self.dessiner(self.image_imprimable(ligne, case), x, y, w, h)
        self.reduite = False
        if motifs and self.apercu:
            self.etiquette_qualite(case, motifs)

    def boite_visages(self, ligne, case):
        """Zone des visages de la photo, en coordonnées de page, pour ne jamais poser un médaillon dessus."""
        x, y, w, h = case
        v = self.visages[ligne["fichier"]]
        if not v["visages"]:
            return None
        g, hh, cw, ch, _ = fenetre(v, w / h)
        x0 = min(f[0] for f in v["visages"])
        x1 = max(f[0] + f[2] for f in v["visages"])
        y0 = min(f[1] for f in v["visages"])
        y1 = max(f[1] + f[3] for f in v["visages"])
        return (x + (x0 - g) / cw * w - 0.04 * w, y + (y0 - hh) / ch * h - 0.04 * h,
                x + (x1 - g) / cw * w + 0.04 * w, y + (y1 - hh) / ch * h + 0.04 * h)

    def poser_medaillons(self, insets, visages_page, cote_exterieur, bas_libre):
        """Médaillons côté extérieur de préférence (loin de la reliure), jamais sur les visages ni sur le titre."""
        self.medaillons_poses = []
        marge = 14 * self.k
        positions = []
        for vertical in ("haut", "bas"):
            for cote in (cote_exterieur, "droite" if cote_exterieur == "gauche" else "gauche"):
                positions.append((vertical, cote))
        occupe = []
        for ligne in insets:
            ratio = min(max(self.visages[ligne["fichier"]]["ratio"], 0.75), 1.5)
            meilleur = None
            for taille in (0.30, 0.24, 0.19):  # plus petit plutôt que sur un visage
                w = taille * self.l
                h = w / ratio
                for rang, (vertical, cote) in enumerate(positions):
                    x = self.b + marge if cote == "gauche" else self.b + self.l - marge - w
                    y = self.b + marge if vertical == "haut" else self.b + bas_libre - marge - h
                    cout = rang * 0.01 + (0.30 - taille)  # à recouvrement égal : le plus grand médaillon
                    for zone in [visages_page] + occupe:
                        if zone:
                            ix = max(0, min(x + w, zone[2]) - max(x, zone[0]))
                            iy = max(0, min(y + h, zone[3]) - max(y, zone[1]))
                            cout += 3 * ix * iy / (w * h)
                    if meilleur is None or cout < meilleur[0]:
                        meilleur = (cout, (x, y, w, h))
            case = meilleur[1]
            self.medaillons_poses.append(case)
            occupe.append((case[0] - 4 * self.k, case[1] - 4 * self.k, case[0] + case[2] + 4 * self.k,
                           case[1] + case[3] + 4 * self.k))
            self.tirage(ligne, case)

    def legende_sur_photo(self, ligne, case, deja=""):
        """Photo seule sur la page (pleine page, héros sans titre) : petite légende date + lieu dans un coin libre
        (encadré en BD), jamais sur un visage ni sur un médaillon."""
        texte = legende_seule(ligne, deja)
        if not texte:
            return
        obstacles = self.visages_dans_case(ligne, case) + list(getattr(self, "medaillons_poses", []))
        zone = self.zone_utile()
        if self.amb.get("bd"):
            ex, ey, le, he, largeur_max, taille = self.placer_encadre(texte, zone, obstacles)
            self.encadre(texte, ex, ey, largeur_max, taille)
            return
        x, y, w, h = zone
        taille = 8
        self.pdf.set_font(self.sans, "", taille)
        largeur = min(w * 0.6, self.pdf.get_string_width(self.t(traduire(texte, self.langue))) + 6 * self.k)
        hauteur = 6 * self.k
        coins = [(x, y + h - hauteur), (x + w - largeur, y + h - hauteur), (x, y), (x + w - largeur, y)]
        lx, ly = min(coins, key=lambda c: recouvrement((c[0], c[1], largeur, hauteur), obstacles))
        with self.pdf.local_context(fill_opacity=0.5):
            self.couleur("#000000")
            self.pdf.rect(lx, ly, largeur, hauteur, "F")
        self.ecrire(texte, lx + 3 * self.k, ly + 1.6 * self.k, largeur - 6 * self.k, taille, "sans", "", "#FFFFFF",
                    "L", ajuster=True, minimum=6)

    def bandeau_titre(self, titre, sous_titre, x, largeur):
        """Titre posé en bas d'une photo pleine page."""
        hauteur = 30 * self.k
        y = self.b + self.h - hauteur
        sombre = self.amb.get("sombre")
        with self.pdf.local_context(fill_opacity=0.55 if sombre else 0.82):
            self.couleur("#000000" if sombre else "#FFFFFF")
            self.pdf.rect(x - self.b if x <= self.b + 1 else x - 6 * self.k, y, largeur + 12 * self.k,
                          hauteur + self.b, "F")
        couleur = self.accent() if sombre else TEXTE
        self.ecrire(titre.upper(), x, y + 8 * self.k, largeur, 15, self.amb["titres"], "B", couleur, "L",
                    espacement=1.2, ajuster=True)
        if sous_titre:
            self.ecrire(sous_titre, x, y + 17 * self.k, largeur, 10, "serif", "I",
                        self.amb.get("texte", TEXTE) if sombre else TEXTE_CLAIR, "L", ajuster=True)
        return y

    # ------------------------------------------------------------------ modèles
    def page_chapitre_planche(self, page):
        self.nouvelle_page(description=f"Ouverture de chapitre : {page['titre']}")
        x, y, w, h = self.zone_utile()
        if self.amb.get("bd"):  # explosion « POW » sur trame de points
            self.trame()
            cx, cy = x + w / 2, y + h * 0.45
            self.explosion(cx, cy, min(w, h) * 0.42, JAUNE_BD)
            self.ecrire(page["titre"].upper(), cx - w * 0.3, cy - 14 * self.k, w * 0.6, 72, "impact", "", ROUGE_BD,
                        "C", ajuster=True, minimum=24)
            if page["sous_titre"]:
                self.ecrire(page["sous_titre"].upper(), cx - w * 0.3, cy + 16 * self.k, w * 0.6, 18, "bd", "B",
                            NOIR_BD, "C", ajuster=True, minimum=TAILLE_LEGENDE)
            return
        if self.amb.get("sombre"):
            self.filet_cadre(10 * self.k)
        self.ornement(x + w / 2, y + h * 0.40, w * 0.35)
        self.ecrire(page["titre"].upper(), x, y + h * 0.40 + 12 * self.k, w, 34, self.amb["titres"], "B",
                    self.accent(), "C", espacement=3, ajuster=True)
        if page["sous_titre"]:
            self.ecrire(page["sous_titre"], x, y + h * 0.40 + 30 * self.k, w, 14, "serif", "I",
                        self.amb.get("texte", TEXTE), "C")
        self.ornement(x + w / 2, y + h * 0.40 + 44 * self.k, w * 0.35)

    def page_heros(self, page):
        self.nouvelle_page(description=f"Photo héros : {page['titre'] or page['chapitre']}")
        plein = (0, 0, self.l + 2 * self.b, self.h + 2 * self.b)
        self.style_courant = "pleine page"
        self.dessiner(self.image_imprimable(page["photo"], plein), *plein)
        exterieur = "droite" if self.numero % 2 else "gauche"
        bas_libre = self.h
        if page["titre"]:
            x = self.b + self.marge + (self.reliure if self.numero % 2 else 0)
            bas_libre = self.bandeau_titre(page["titre"], page["sous_titre"], x, self.l * 0.62) - self.b
        self.poser_medaillons(page["insets"], self.boite_visages(page["photo"], plein), exterieur, bas_libre)
        if not page["titre"]:
            self.legende_sur_photo(page["photo"], plein)

    def page_pano(self, page):
        """Photo sur toute la double page (reliure à plat) : la moitié gauche ici, la droite sur la page suivante."""
        largeur, hauteur = 2 * self.l + 2 * self.b, self.h + 2 * self.b
        planche = (0, 0, largeur, hauteur)
        self.nouvelle_page(description=f"Panoramique (pages {self.numero + 1}-{self.numero + 2}) : {page['titre']}")
        self.style_courant = "panoramique sur 2 pages"
        image = self.image_imprimable(page["photo"], planche)
        self.dessiner(image, 0, 0, largeur, hauteur)
        visages = self.boite_visages(page["photo"], planche)
        x = self.b + self.marge
        bas_libre = self.bandeau_titre(page["titre"], page["sous_titre"], x, self.l * 0.62) - self.b
        self.poser_medaillons(page["insets"][:1], visages, "gauche", bas_libre)
        self.nouvelle_page(description=f"Panoramique (suite) : {page['titre']}")
        self.dessiner(image, -self.l, 0, largeur, hauteur)
        suite = dict(self.placements[-1], page=self.numero, absolu=(-self.l, 0, largeur, hauteur), pptx_seulement=True)
        self.placements_pptx.append(suite)  # moitié droite du panoramique, pour PowerPoint
        if visages:
            visages = (visages[0] - self.l, visages[1], visages[2] - self.l, visages[3])
        self.poser_medaillons(page["insets"][1:], visages, "droite", self.h)

    def page_ecrin(self, page):
        """Grande photo + colonne de vignettes dans un cadre (filet or en prestige), titre en dessous."""
        self.nouvelle_page(description=page["titre"] or page["chapitre"])
        x, y, w, h = self.zone_utile()
        if self.amb.get("sombre"):
            self.filet_cadre(8 * self.k)
        bas = 26 * self.k if page["titre"] else 0
        h -= bas
        g = self.ecart
        photos = page["photos"]
        if len(photos) == 1:
            ratio = min(max(self.visages[photos[0]["fichier"]]["ratio"], 0.7), 1.5)
            cw = min(w, h * ratio)
            ch = cw / ratio
            self.photo(photos[0], (x + (w - cw) / 2, y + (h - ch) / 2, cw, ch))
            if not page["titre"] and legende_seule(photos[0]):
                self.ecrire(legende_seule(photos[0]), x, y + (h + ch) / 2 + 3 * self.k, w, TAILLE_LEGENDE, "serif",
                            "I", self.amb.get("texte", TEXTE_CLAIR), "C", ajuster=True, minimum=8)
        elif len(photos) == 2:  # deux photos : le montage qui les coupe le moins
            infos = [dict(self.visages[p["fichier"]], note=float(p["score"] or 0), ligne=p) for p in photos]
            for case, info in choisir_gabarit(infos, (x, y, w, h), g, None)[1]:
                self.photo(info["ligne"], case)
        else:
            grande = w * 0.66
            colonne = w - grande - g
            n = len(photos) - 1
            hauteur_vignette = (h - (n - 1) * g) / n
            gauche = bool(self.numero % 2)  # colonne côté extérieur
            xg = x if not gauche else x + colonne + g
            xc = x + grande + g if not gauche else x
            infos = sorted(photos, key=lambda p: float(p["score"] or 0), reverse=True)
            self.photo(infos[0], (xg, y, grande, h))
            for i, ligne in enumerate(infos[1:]):
                self.photo(ligne, (xc, y + i * (hauteur_vignette + g), colonne, hauteur_vignette))
        if page["titre"]:
            self.ecrire(page["titre"].upper(), x, y + h + 8 * self.k, w, 14, self.amb["titres"], "B", self.accent(),
                        "C", espacement=2, ajuster=True)
            if page["sous_titre"]:
                self.ecrire(page["sous_titre"], x, y + h + 17 * self.k, w, 10, "serif", "I",
                            self.amb.get("texte", TEXTE_CLAIR), "C", ajuster=True)
        self.folio()

    def page_mosaique(self, page, precedent):
        self.nouvelle_page(description=page["titre"] or page["chapitre"])
        x, y, w, h = self.zone_utile()
        h -= 5 * self.k
        if page["titre"] and self.amb.get("bd"):  # en BD : petite explosion « POW » avec l'année
            annee, _, reste = page["titre"].partition(" · ")
            rayon = 13 * self.k
            self.explosion(x + rayon * 1.25, y + rayon * 0.8, rayon, JAUNE_BD, 12)
            self.ecrire(annee.upper(), x + 2 * self.k, y + rayon * 0.8 - 4 * self.k, rayon * 2.5 - 4 * self.k, 20,
                        "impact", "", ROUGE_BD, "C", ajuster=True, minimum=12)
            if reste:
                self.ecrire(reste.upper(), x + rayon * 2.7, y + rayon * 0.8 - 4 * self.k, w - rayon * 2.8, 18, "impact",
                            "", NOIR_BD, "L", ajuster=True, minimum=TAILLE_LEGENDE)
            y, h = y + rayon * 1.75, h - rayon * 1.75
        elif page["titre"]:  # nouveau lieu (chrono-lieux)
            self.ecrire(page["titre"].upper(), x, y, w, 12, self.amb["titres"], "B", self.accent(), "L", espacement=1.5,
                        ajuster=True)
            y, h = y + 10 * self.k, h - 10 * self.k
        style = self.amb["photo"]
        legendes = any(page["legendes"]) and style != "bd"  # en BD, la légende va dans l'encadré jaune
        infos = [dict(self.visages[p["fichier"]], note=float(p["score"] or 0), ligne=p) for p in page["photos"]]
        nom, placement = choisir_gabarit(infos, (x, y, w, h), self.ecart, precedent)
        textes = dict(zip(map(id, page["photos"]), page["legendes"]))
        bulles = dict(zip(map(id, page["photos"]), page.get("bulles") or [""] * len(page["photos"])))
        for (cx, cy, cw, ch), info in placement:
            texte = textes[id(info["ligne"])]
            if legendes:
                ch -= min(max(HAUTEUR_LEGENDE * self.k, self.hauteur_legende(texte, cw)), 0.45 * ch)
            if style == "bd":
                self.photo(info["ligne"], (cx, cy, cw, ch), "bd", texte, bulles[id(info["ligne"])])
            else:
                self.photo(info["ligne"], (cx, cy, cw, ch))
            if legendes and texte:
                self.ecrire(texte, cx, cy + ch + 1.2 * self.k, cw, TAILLE_LEGENDE, "serif", "I",
                            self.amb.get("texte", TEXTE_CLAIR), "C", minimum=TAILLE_LEGENDE, plusieurs_lignes=True)
        self.folio()
        return nom

    def page_respiration(self, page):
        self.nouvelle_page(description="Page de respiration")
        x, y, w, h = self.zone_utile()
        ratio = min(max(self.visages[page["photo"]["fichier"]]["ratio"], 0.7), 1.5)
        cw = min(w * 0.70, h * 0.70 * ratio)
        ch = cw / ratio
        cx, cy = x + (w - cw) / 2, y + (h - ch) / 2
        legende = legende_seule(page["photo"])
        if self.amb.get("bd"):
            self.photo(page["photo"], (cx, cy, cw, ch), "bd", legende)
            self.folio()
            return
        if legende:
            self.ecrire(legende, x, cy + ch + 9 * self.k, w, TAILLE_LEGENDE, "serif", "I",
                        self.amb.get("texte", TEXTE_CLAIR), "C", ajuster=True, minimum=8)
        self.couleur(self.accent(), "draw")
        self.pdf.set_line_width(0.3)
        self.pdf.rect(cx - 4 * self.k, cy - 4 * self.k, cw + 8 * self.k, ch + 8 * self.k, "D")
        self.pdf.set_line_width(0.2)
        self.photo(page["photo"], (cx, cy, cw, ch))
        self.folio()

    def page_ornement(self, page):
        self.nouvelle_page(description="Page d'ornement (sans photo)")
        x, y, w, h = self.zone_utile()
        if self.amb.get("sombre"):
            self.filet_cadre(10 * self.k)
        self.ornement(x + w / 2, y + h / 2, w * 0.3)
        self.ecrire(page["titre"], x, y + h / 2 + 8 * self.k, w, 12, "serif", "I", self.accent(), "C")

    def couverture_prestige(self, ligne, sujet, periode):
        """Couverture écrin : fond sombre, filet or, photo encadrée, titre or (comme un album de mariage)."""
        self.filet_cadre(10 * self.k)
        cw, ch = self.l * 0.62, self.h * 0.56
        x, y = self.b + (self.l - cw) / 2, self.b + self.h * 0.10
        self.couleur(self.accent(), "draw")
        self.pdf.set_line_width(0.4)
        self.pdf.rect(x - 3 * self.k, y - 3 * self.k, cw + 6 * self.k, ch + 6 * self.k, "D")
        self.pdf.set_line_width(0.2)
        self.photo(ligne, (x, y, cw, ch))
        self.ornement(self.b + self.l / 2, y + ch + 16 * self.k, self.l * 0.25)
        self.ecrire(sujet.upper(), self.b, y + ch + 24 * self.k, self.l, 40, self.amb["titres"], "B", self.accent(),
                    "C", espacement=4, ajuster=True)
        self.ecrire(periode, self.b, y + ch + 42 * self.k, self.l, 13, "serif", "I", self.amb.get("texte", TEXTE), "C")


# =========================================================================== bande dessinée (ambiances bd et bd-photo)

BULLES = {"anniversaire": "Joyeux anniversaire !", "noel": "Joyeux Noël !", "nouvel-an": "Bonne année !",
          "vacances": "Vive les vacances !", "naissance": "Coucou le monde !",
          "mariage": "Vive les mariés !", "bapteme": "Quel beau jour !", "fete": "C'est la fête !"}
JAUNE_BD, ROUGE_BD, NOIR_BD = "#FFE14D", "#E63946", "#151515"
COULEURS_BD = {  # couleur des encadrés de légende des ambiances BD (option --couleur-bd)
    "jaune": "#FFE14D", "bleu": "#8EC9F2", "bleu-fonce": "#1F5AA6", "vert": "#9BE07A", "vert-fonce": "#2E7D4F",
    "rose": "#FFB3CF", "orange": "#FFB347", "rouge": "#E63946", "violet": "#C9A7F2", "turquoise": "#6FE0D4",
    "blanc": "#FFFFFF", "creme": "#FFF4D6", "gris": "#D9D9D9", "noir": "#151515"}


def couleur_bd(nom):
    nom = (nom or "jaune").strip().lower()
    if nom in COULEURS_BD:
        return COULEURS_BD[nom]
    if re.fullmatch(r"#[0-9a-fA-F]{6}", nom):
        return nom
    sys.exit(f"Couleur BD inconnue : « {nom} ». Possibles : {', '.join(COULEURS_BD)}, ou un code #RRGGBB.")


def cartoon(im):
    """Effet dessin animé : couleurs en aplats (quantification), contours noirs, couleurs plus vives.
    Calculé à 1400 px au plus puis remis à la taille d'impression (rapide et sans grain)."""
    import cv2
    from PIL import ImageEnhance

    largeur, hauteur = im.size
    f = min(1.0, 1400 / max(largeur, hauteur))
    petit = im.resize((max(1, round(largeur * f)), max(1, round(hauteur * f))), Image.LANCZOS) if f < 1 else im
    bgr = cv2.cvtColor(np.asarray(petit), cv2.COLOR_RGB2BGR)
    lisse = bgr
    for _ in range(2):  # lissage qui garde les bords nets
        lisse = cv2.bilateralFilter(lisse, 9, 60, 60)
    pixels = lisse.reshape(-1, 3).astype(np.float32)
    echantillon = pixels[np.random.default_rng(0).choice(len(pixels), min(20000, len(pixels)), replace=False)]
    _, _, centres = cv2.kmeans(echantillon, 16, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0),
                               2, cv2.KMEANS_PP_CENTERS)
    distances = ((pixels[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
    aplats = centres.astype(np.uint8)[distances.argmin(axis=1)].reshape(lisse.shape)
    gris = cv2.medianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 5)
    contours = cv2.adaptiveThreshold(gris, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 5)
    dessin = cv2.bitwise_and(aplats, aplats, mask=contours)
    resultat = ImageEnhance.Color(Image.fromarray(cv2.cvtColor(dessin, cv2.COLOR_BGR2RGB))).enhance(1.3)
    return resultat.resize((largeur, hauteur), Image.LANCZOS) if f < 1 else resultat


def recouvrement(boite, autres):
    """Plus grande part d'un des rectangles « autres » cachée par « boite » (rectangles x, y, l, h)."""
    x, y, l, h = boite
    pire = 0.0
    for ax, ay, al, ah in autres:
        cache = max(0.0, min(x + l, ax + al) - max(x, ax)) * max(0.0, min(y + h, ay + ah) - max(y, ay))
        pire = max(pire, cache / max(al * ah, 1e-9))
    return pire


class BDMixin:
    """Modèles de page « bande dessinée » : cases à gros trait, encadrés de narration, bulles, explosions."""

    def explosion(self, cx, cy, rayon, couleur=JAUNE_BD, branches=14):
        """Explosion « POW » : étoile irrégulière à contour noir."""
        points = []
        for i in range(2 * branches):
            r = rayon * (1 if i % 2 == 0 else 0.68) * (1 + 0.08 * math.sin(i * 2.3))
            a = math.pi * i / branches
            points.append((cx + r * math.cos(a), cy + r * 0.78 * math.sin(a)))
        self.couleur(couleur)
        self.couleur(NOIR_BD, "draw")
        self.pdf.set_line_width(1.2 * self.k)
        self.pdf.polygon(points, style="DF")
        self.pdf.set_line_width(0.2)

    def trame(self, couleur="#F6D3CF", pas=4.0, rayon=0.55):
        """Trame de points façon impression de comics, sur toute la page."""
        self.couleur(couleur)
        y = 0.0
        ligne = 0
        while y < self.h + 2 * self.b:
            x = (pas / 2) * (ligne % 2)
            while x < self.l + 2 * self.b:
                self.pdf.ellipse(x - rayon, y - rayon, 2 * rayon, 2 * rayon, "F")
                x += pas * self.k
            y += pas * self.k * 0.87
            ligne += 1

    def mesure_encadre(self, texte, largeur_max, taille=TAILLE_LEGENDE):
        self.pdf.set_font(self.bd or self.sans, "B", taille)
        lignes = self.couper_lignes(texte.upper(), largeur_max - 6 * self.k, taille, "bd", "B")
        largeur = max(self.pdf.get_string_width(self.t(l)) for l in lignes) + 6 * self.k
        return largeur, len(lignes) * taille * (0.47 if len(lignes) > 1 else 0.45) + 3 * self.k

    couleur_encadre = JAUNE_BD  # option --couleur-bd

    def encadre(self, texte, x, y, largeur_max, taille=TAILLE_LEGENDE):
        """Encadré de narration (jaune par défaut) dans un coin d'une case ; texte blanc sur couleur foncée."""
        texte = texte.upper()
        largeur, hauteur = self.mesure_encadre(texte, largeur_max, taille)
        r, g, b = hexa_rgb(self.couleur_encadre)
        encre = "#FFFFFF" if 0.299 * r + 0.587 * g + 0.114 * b < 120 else NOIR_BD
        self.couleur(self.couleur_encadre)
        self.couleur(NOIR_BD, "draw")
        self.pdf.set_line_width(0.6 * self.k)
        self.pdf.rect(x, y, largeur, hauteur, "DF")
        self.pdf.set_line_width(0.2)
        self.ecrire(texte, x + 3 * self.k, y + 1.5 * self.k, largeur - 6 * self.k + 0.5, taille, "bd", "B", encre,
                    "L", minimum=taille, plusieurs_lignes=True)
        return hauteur

    def placer_encadre(self, texte, case, visages, espace=None):
        """Choisit coin, largeur et taille de police de l'encadré pour ne cacher aucun visage : d'abord la police
        normale (14 pt) dans les quatre coins, puis plus étroit ou plus large (bandeau d'une ligne), puis une
        police plus petite (jusqu'à 9 pt). À défaut, la position qui cache le moins."""
        x, y, w, h = case
        d = 0.6 * self.k
        meilleur = None
        if espace is not None:  # photo réduite dans sa case : l'encadré dans la place libre, hors de la photo
            ox, oy, ow, oh = espace
            for taille in (TAILLE_LEGENDE, 12, 11, 10):
                le, he = self.mesure_encadre(texte, ow, taille)
                for ex, ey in ((ox, oy), (ox, oy + oh - he), (ox + ow - le, oy), (ox + ow - le, oy + oh - he)):
                    if (ex >= ox - 0.1 and ey >= oy - 0.1 and ex + le <= ox + ow + 0.1 and ey + he <= oy + oh + 0.1
                            and recouvrement((ex, ey, le, he), [(x + 1, y + 1, w - 2, h - 2)]) == 0):
                        return ex, ey, le, he, ow, taille
        for taille in (TAILLE_LEGENDE, 12, 11, 10, 9):
            for fraction in (0.85, 0.6, 1.0, 0.45):
                le, he = self.mesure_encadre(texte, w * fraction + 2 * d, taille)
                if he > h * 0.35 or le * he > 0.35 * w * h:  # jamais un encadré qui mange la photo
                    continue
                for ex, ey in ((x - d, y - d), (x + w - le + d, y - d), (x - d, y + h - he + d),
                               (x + w - le + d, y + h - he + d)):
                    gene = recouvrement((ex, ey, le, he), visages)
                    if gene <= 0.01:
                        return ex, ey, le, he, w * fraction + 2 * d, taille
                    cle = (gene, le * he)
                    if meilleur is None or cle < meilleur[0]:
                        meilleur = (cle, (ex, ey, le, he, w * fraction + 2 * d, taille))
        if meilleur is None:  # case minuscule : petit encadré en haut à gauche
            le, he = self.mesure_encadre(texte, w + 2 * d, 9)
            return x - d, y - d, le, he, w + 2 * d, 9
        return meilleur[1]

    def mesure_bulle(self, texte, largeur_max):
        taille = TAILLE_LEGENDE + 2
        self.pdf.set_font(self.bd or self.sans, "B", taille)
        lignes = self.couper_lignes(texte, largeur_max - 14 * self.k, taille, "bd", "B")
        largeur = max(self.pdf.get_string_width(self.t(l)) for l in lignes) + 14 * self.k
        return lignes, largeur, len(lignes) * taille * 0.47 + 9 * self.k

    def bulle(self, texte, x, y, largeur_max, gauche=True, bas=True):
        """Bulle de dialogue blanche à contour noir ; sa pointe part vers le bas (ou le haut) à gauche (ou à
        droite), du côté de la personne qui parle."""
        taille = TAILLE_LEGENDE + 2
        lignes, largeur, hauteur = self.mesure_bulle(texte, largeur_max)
        self.couleur("#FFFFFF")
        self.couleur(NOIR_BD, "draw")
        self.pdf.set_line_width(0.8 * self.k)
        fx = (lambda f: x + largeur * f) if gauche else (lambda f: x + largeur * (1 - f))
        if bas:
            pointe = [(fx(0.22), y + hauteur * 0.8), (fx(0.12), y + hauteur + 6 * self.k), (fx(0.36), y + hauteur * 0.86)]
            raccord = [(pointe[0][0], pointe[0][1] - 0.8), (pointe[2][0], pointe[2][1] - 1.2),
                       ((pointe[0][0] + pointe[2][0]) / 2, pointe[0][1] - 2)]
        else:
            pointe = [(fx(0.22), y + hauteur * 0.2), (fx(0.12), y - 6 * self.k), (fx(0.36), y + hauteur * 0.14)]
            raccord = [(pointe[0][0], pointe[0][1] + 0.8), (pointe[2][0], pointe[2][1] + 1.2),
                       ((pointe[0][0] + pointe[2][0]) / 2, pointe[0][1] + 2)]
        self.pdf.polygon(pointe, style="DF")
        self.pdf.ellipse(x, y, largeur, hauteur, "DF")
        self.couleur("#FFFFFF")
        self.pdf.polygon(raccord, style="F")  # efface le raccord entre la pointe et la bulle
        self.pdf.set_line_width(0.2)
        self.ecrire(texte, x + 7 * self.k, y + hauteur / 2 - len(lignes) * taille * 0.235, largeur - 14 * self.k + 0.5,
                    taille, "bd", "B", NOIR_BD, "C", minimum=TAILLE_LEGENDE, plusieurs_lignes=True)

    def case_bd(self, ligne, case, legende="", bulle=""):
        """Une case de BD : photo, gros cadre noir, encadré de narration et bulle éventuels."""
        x, y, w, h = case
        self.dessiner(self.image_imprimable(ligne, case), x, y, w, h)
        self.couleur(NOIR_BD, "draw")
        self.pdf.set_line_width(1.1 * self.k)
        self.pdf.rect(x, y, w, h, "D")
        self.pdf.set_line_width(0.2)
        visages = self.visages_dans_case(ligne, case)
        occupe = []
        if legende:  # encadré dans le coin où il ne cache aucun visage (police réduite si besoin)
            ex, ey, le, he, largeur_max, taille = self.placer_encadre(legende, case, visages,
                                                                      getattr(self, "case_origine", None))
            self.encadre(legende, ex, ey, largeur_max, taille)
            occupe.append((ex, ey, le, he))
        if bulle and w >= 75 * self.k and h >= 55 * self.k:  # pas de bulle qui cache une petite case
            _, lb, hb = self.mesure_bulle(bulle, w * 0.6)
            m = 4 * self.k
            positions = [(x + w - lb - m, y + m + 3 * self.k), (x + m, y + m + 3 * self.k),
                         (x + (w - lb) / 2, y + m + 3 * self.k), (x + w - lb - m, y + h - hb - m - 4 * self.k),
                         (x + m, y + h - hb - m - 4 * self.k)]
            def gene(bx, by):  # visages cachés (priorité absolue), puis chevauchement de l'encadré
                boite = (bx, by - 1.5 * self.k, lb, hb + 7 * self.k)  # pointe comprise
                return 10 * recouvrement(boite, visages) + recouvrement(boite, occupe)
            bx, by = min(positions, key=lambda pos: gene(*pos))
            if recouvrement((bx, by, lb, hb), visages) <= 0.03:  # sinon pas de bulle : jamais sur un visage
                cible = min(visages, key=lambda v: abs(v[0] + v[2] / 2 - (bx + lb / 2)), default=None)
                gauche = cible is None or cible[0] + cible[2] / 2 <= bx + lb / 2
                bas = by < y + h / 2
                self.bulle(bulle, bx, by, w * 0.6, gauche=gauche, bas=bas)

    def visages_dans_case(self, ligne, case):
        """Visages de la photo, en mm sur la page, tels que la photo est recadrée dans la case (cheveux compris)."""
        x, y, w, h = case
        p = self.visages[ligne["fichier"]]
        gauche, haut, cw, ch, _ = fenetre(p, w / h)
        boites = []
        for vx, vy, vl, vh in p["visages"]:
            bx, by = vx - 0.15 * vl, vy - 0.25 * vh
            bl, bh = vl * 1.3, vh * 1.4
            boites.append((x + (bx - gauche) / cw * w, y + (by - haut) / ch * h, bl / cw * w, bh / ch * h))
        return boites

    def page_chapitre_bd(self, page):
        """Ouverture de chapitre façon couverture de comics : trame, explosion avec le titre, une case."""
        self.nouvelle_page(description=f"Ouverture de chapitre : {page['titre']}")
        self.trame()
        x, y, w, h = self.zone_utile()
        cx, cy = x + w / 2, y + h * 0.22
        self.explosion(cx, cy, min(w, h) * 0.30, JAUNE_BD)
        self.ecrire(page["titre"].upper(), cx - w * 0.25, cy - 12 * self.k, w * 0.5, 60, "impact", "",
                    ROUGE_BD, "C", ajuster=True, minimum=20)
        if page["sous_titre"]:
            self.ecrire(page["sous_titre"].upper(), cx - w * 0.25, cy + 13 * self.k, w * 0.5, 16, "bd", "B", NOIR_BD,
                        "C", ajuster=True, minimum=TAILLE_LEGENDE)
        ratio = min(max(self.visages[page["photo"]["fichier"]]["ratio"], 0.75), 1.6)
        case_h = h * 0.48
        case_w = min(case_h * ratio, w * 0.8)
        case_h = case_w / ratio
        self.photo(page["photo"], (x + (w - case_w) / 2, y + h - case_h - h * 0.03, case_w, case_h), "bd")

    def couverture_bd(self, ligne, sujet, periode):
        """Couverture de comics : bandeau titre, encart « N°1 », grande case."""
        k = self.k
        self.trame("#FBE3B0")
        bandeau = 34 * k
        self.couleur(ROUGE_BD)
        self.pdf.rect(0, 0, self.l + 2 * self.b, self.b + bandeau, "F")
        self.ecrire("LES AVENTURES DE", self.b + 40 * k, self.b + 5 * k, self.l - 50 * k, 14, "bd", "B", "#FFFFFF")
        self.ecrire(sujet.upper(), self.b + 40 * k, self.b + 13 * k, self.l - 50 * k, 44, "impact", "", JAUNE_BD,
                    ajuster=True, minimum=24)
        self.couleur(JAUNE_BD)
        self.couleur(NOIR_BD, "draw")
        self.pdf.set_line_width(1.0 * k)
        self.pdf.rect(self.b + 8 * k, self.b + 5 * k, 26 * k, 24 * k, "DF")
        self.ecrire("N°1", self.b + 8 * k, self.b + 9 * k, 26 * k, 22, "impact", "", NOIR_BD, "C")
        self.ecrire(periode, self.b + 8 * k, self.b + 21 * k, 26 * k, 8, "bd", "B", NOIR_BD, "C", ajuster=True)
        marge = 12 * k
        case = (self.b + marge, self.b + bandeau + marge, self.l - 2 * marge, self.h - bandeau - 2 * marge)
        self.photo(ligne, case, "bd")
        self.explosion(self.b + self.l - 32 * k, self.b + self.h - 30 * k, 26 * k, JAUNE_BD)
        self.ecrire("SOUVENIRS", self.b + self.l - 52 * k, self.b + self.h - 33 * k, 40 * k, 13, "impact", "",
                    ROUGE_BD, "C", ajuster=True, minimum=10)


class Livre(PlanchesMixin, BDMixin):
    def __init__(self, base, sortie, dossier, format_, fond_perdu, visages, ambiance="tendre", apercu=False):
        from fpdf import FPDF

        self.base, self.sortie, self.dossier = base, sortie, dossier
        self.l, self.h = FORMATS[format_]
        self.b = fond_perdu
        self.k = max(1.0, min(self.l, self.h) / 300)  # échelle : jamais réduite sous celle d'un livre de 30 cm
        self.amb = AMBIANCES[ambiance]
        self.marge, self.reliure, self.ecart = self.amb["marge"] * self.k, 5 * self.k, self.amb["ecart"] * self.k
        self.visages = visages
        self.apercu = apercu  # aperçu léger pour comparer les ambiances (100 dpi), sinon qualité imprimeur
        self.pages_photos = 0
        self.fond = self.amb["fond"]
        self.pdf = FPDF(unit="mm", format=(self.l + 2 * self.b, self.h + 2 * self.b))
        self.pdf.set_auto_page_break(False)
        self.pdf.set_margins(0, 0, 0)
        self.polices()
        self.numero = 0
        self.placements = []  # chaque photo posée : page, case (mm), recadrage, dpi... pour l'imprimeur
        self.descriptions = {}  # page -> contenu, pour le plan de montage
        self.angle, self.style_courant = 0.0, ""
        self.reduite = False
        self.controle = []  # photos réduites pour cause de qualité : page, fichier, motifs
        self.coupees_origine = []  # photos dont un visage touche déjà le bord de la photo d'origine
        self.entieres = 0  # photos montrées entières pour ne couper aucun visage
        self.textes = []  # textes posés (pour la version PowerPoint)
        self.placements_pptx = []  # images posées en plus (moitié droite des panoramiques)
        self.angle_texte = 0.0
        self.decor_seul = False  # True : seulement le décor (fonds, filets, cadres), pour la version PowerPoint
        (dossier / "cache_livre").mkdir(exist_ok=True)

    # ------------------------------------------------------------------ outils
    def polices(self):
        serif = [("C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/georgiai.ttf"),
                 ("/System/Library/Fonts/Supplemental/Georgia.ttf", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
                  "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"),
                 ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf")]
        sans = [("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
                ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
        self.unicode = False
        for normale, grasse, italique in serif:
            if Path(normale).exists() and Path(grasse).exists():
                self.pdf.add_font("Titre", "", normale)
                self.pdf.add_font("Titre", "B", grasse)
                self.pdf.add_font("Titre", "I", italique if Path(italique).exists() else normale)
                self.unicode = True
                break
        for normale, grasse in sans:
            if Path(normale).exists() and Path(grasse).exists():
                self.pdf.add_font("Texte", "", normale)
                self.pdf.add_font("Texte", "B", grasse)
                break
        if not self.unicode:
            self.serif, self.sans = "times", "helvetica"
        else:
            self.serif, self.sans = "Titre", "Texte"
        self.bd = self.impact = None  # bande dessinée : Comic Sans MS (textes) et Impact (titres)
        for nom, normale, grasse in (("BD", "C:/Windows/Fonts/comic.ttf", "C:/Windows/Fonts/comicbd.ttf"),
                                     ("Impact", "C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/impact.ttf"),
                                     ("BD", "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
                                      "/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf"),
                                     ("Impact", "/System/Library/Fonts/Supplemental/Impact.ttf",
                                      "/System/Library/Fonts/Supplemental/Impact.ttf")):
            if getattr(self, nom.lower()) is None and Path(normale).exists():
                self.pdf.add_font(nom, "", normale)
                self.pdf.add_font(nom, "B", grasse if Path(grasse).exists() else normale)
                self.pdf.add_font(nom, "I", normale)
                setattr(self, nom.lower(), nom)
        self.main = None  # écriture manuscrite (Windows : Segoe Print ou Ink Free) pour l'ambiance carnet
        for normale, grasse in (("C:/Windows/Fonts/segoepr.ttf", "C:/Windows/Fonts/segoeprb.ttf"),
                                ("C:/Windows/Fonts/Inkfree.ttf", "C:/Windows/Fonts/Inkfree.ttf"),
                                ("/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
                                 "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf")):
            if Path(normale).exists():
                self.pdf.add_font("Main", "", normale)
                self.pdf.add_font("Main", "B", grasse if Path(grasse).exists() else normale)
                self.pdf.add_font("Main", "I", normale)
                self.main = "Main"
                break
        # Georgia et Segoe Print n'ont pas le vietnamien (ậ, ộ, ố, ơ, ư...) : police de secours, par caractère manquant
        if self.unicode:
            secours = [("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf", "C:/Windows/Fonts/timesi.ttf"),
                       ("/System/Library/Fonts/Supplemental/Times New Roman.ttf",
                        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
                        "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf"),
                       ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf")]
            for normale, grasse, italique in secours:
                if Path(normale).exists() and Path(grasse).exists() and Path(italique).exists():
                    self.pdf.add_font("Secours", "", normale)
                    self.pdf.add_font("Secours", "B", grasse)
                    self.pdf.add_font("Secours", "I", italique)
                    self.pdf.set_fallback_fonts(["Secours"])
                    break

    def t(self, texte):
        return texte if self.unicode else texte.encode("latin-1", "replace").decode("latin-1")

    def couleur(self, hexa, quoi="fill"):
        r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
        {"fill": self.pdf.set_fill_color, "draw": self.pdf.set_draw_color, "text": self.pdf.set_text_color}[quoi](r, g, b)

    def police_reelle(self, police, style):
        if police == "main" and not self.main:  # pas de police manuscrite : italique élégante
            police, style = "serif", "I"
        if police in ("bd", "impact") and not getattr(self, police):  # polices Windows absentes : sans empattement
            police, style = "sans", "B"
        return police, style, {"serif": self.serif, "sans": self.sans, "main": self.main, "bd": self.bd,
                               "impact": self.impact}[police]

    texte_libre = False  # vrai pendant l'écriture d'un texte saisi à la main (lettre, pied de page) : jamais traduit
    langue = "fr"  # langue des textes du livre (option --langue) ; les textes saisis à la main restent tels quels

    def couper_lignes(self, texte, w, taille, police="serif", style=""):
        """Découpe un texte en lignes (aux espaces) qui tiennent dans la largeur w, à cette taille."""
        texte = texte if self.texte_libre else traduire(texte, self.langue)
        _, style, famille = self.police_reelle(police, style)
        self.pdf.set_font(famille, style, taille)
        lignes, courante = [], ""
        for mot in texte.split():
            essai = f"{courante} {mot}".strip()
            if courante and self.pdf.get_string_width(self.t(essai)) > w:
                lignes.append(courante)
                courante = mot
            else:
                courante = essai
        return lignes + ([courante] if courante else [])

    def hauteur_legende(self, texte, w, police="serif", style="I"):
        """Hauteur (mm) d'une légende 14 pt sur plusieurs lignes si besoin (jamais tronquée)."""
        if not texte:
            return 0.0
        lignes = len(self.couper_lignes(texte, w, TAILLE_LEGENDE, police, style))
        return lignes * TAILLE_LEGENDE * 0.47 + 2 * self.k

    def ecrire(self, texte, x, y, w, taille, police="serif", style="", couleur=TEXTE, align="L", espacement=0,
               ajuster=False, minimum=8, plusieurs_lignes=False):
        """Écrit un texte. ajuster : réduit la taille jusqu'au minimum pour tenir sur une ligne ;
        plusieurs_lignes : passe ensuite à la ligne (jamais tronqué). Renvoie la hauteur utilisée (mm)."""
        texte = texte if self.texte_libre else traduire(texte, self.langue)
        pdf = self.pdf
        police, style, famille = self.police_reelle(police, style)
        taille = max(taille * self.k, minimum if minimum > 8 else 0)
        pdf.set_font(famille, style, taille)
        if ajuster:  # réduit la taille pour que le texte tienne sur une ligne, sans descendre sous le minimum
            while taille * 0.92 >= minimum and pdf.get_string_width(self.t(texte)) > w:
                taille *= 0.92
                pdf.set_font(famille, style, taille)
        if plusieurs_lignes and pdf.get_string_width(self.t(texte)) > w:
            lignes = self.couper_lignes(texte, w, taille, police, style)
        else:
            lignes = [texte]
            if ajuster:
                while len(texte) > 4 and pdf.get_string_width(self.t(texte)) > w:  # titre trop long : coupé
                    texte = texte[:-2].rstrip() + "…"
                lignes = [texte]
        interligne = taille * (0.47 if len(lignes) > 1 else 0.45)
        pdf.set_font(famille, style, taille)
        for i, ligne in enumerate(lignes):
            self.textes.append({"page": self.numero, "texte": ligne, "x": x, "y": y + i * interligne, "w": w,
                                "h": taille * 0.45, "police": police, "style": style, "taille": taille,
                                "couleur": couleur, "align": align, "angle": self.angle_texte})
            if self.decor_seul:
                continue
            self.couleur(couleur, "text")
            pdf.set_char_spacing(espacement)
            pdf.set_xy(x, y + i * interligne)
            pdf.cell(w, taille * 0.45, self.t(ligne), align=align)
            pdf.set_char_spacing(0)
        return len(lignes) * interligne

    def dessiner(self, image, x, y, w, h):
        """Pose une image dans le PDF (sauf pour le calque « décor » de la version PowerPoint)."""
        if image is not None and not self.decor_seul and w > 0 and h > 0:
            self.pdf.image(str(image), x, y, w, h)

    def nouvelle_page(self, fond=None, description=""):
        fond = fond or self.amb["fond"]
        self.pdf.add_page()
        self.numero += 1
        self.descriptions[self.numero] = description
        self.fond = fond
        self.couleur(fond)
        self.pdf.rect(0, 0, self.l + 2 * self.b, self.h + 2 * self.b, "F")

    def zone_utile(self):
        """Zone de sécurité de la page : marges + reliure côté intérieur (page impaire = page de droite)."""
        gauche = self.b + self.marge + (self.reliure if self.numero % 2 else 0)
        droite = self.b + self.l - self.marge - (0 if self.numero % 2 else self.reliure)
        return gauche, self.b + self.marge, droite - gauche, self.h - 2 * self.marge

    def folio(self):
        self.ecrire(str(self.numero), self.b, self.b + self.h - self.marge * 0.55, self.l, 8, "sans",
                    couleur=TEXTE_CLAIR, align="C")

    def ombre(self, x, y, w, h, rayon=0.0):
        """Ombre douce : quelques rectangles très transparents, décalés vers le bas à droite."""
        self.couleur("#000000")
        for i in range(4):
            e = (i + 1) * 0.45 * self.k
            with self.pdf.local_context(fill_opacity=0.045):
                self.pdf.rect(x - e / 2 + 0.8 * self.k, y - e / 2 + 1.2 * self.k, w + e, h + e, "F",
                              round_corners=rayon > 0, corner_radius=rayon + e / 2)

    def image_imprimable(self, ligne, case, coins=None):
        """Recadre, convertit en sRGB, réduit à 300 dpi au plus et accentue légèrement pour l'impression.
        coins = (rayon_mm, couleur du fond) pour des coins arrondis fondus dans la page."""
        x, y, w, h = case
        if w < 1 or h < 1:  # case dégénérée (ne devrait pas arriver) : on n'imprime rien plutôt que de planter
            return None
        p = self.visages[ligne["fichier"]]
        gauche, haut, cw, ch, _ = fenetre(p, w / h)
        largeur_px = cw * p["largeur"]
        dpi = largeur_px / (w / 25.4)
        dpi_max = 100 if self.apercu else DPI_CIBLE
        echelle = min(1.0, (w / 25.4 * dpi_max) / largeur_px)  # jamais d'agrandissement artificiel
        cible_px = (max(1, round(largeur_px * echelle)), max(1, round(ch * p["hauteur"] * echelle)))
        effet = self.amb.get("effet")
        cle = hashlib.md5(f"v3|{ligne['fichier']}|{af.empreinte_fichier(self.base, ligne['fichier'])}|{gauche:.4f}|{haut:.4f}|{cw:.4f}|{ch:.4f}|{cible_px}|{coins}|{effet}-v2"
                          .encode()).hexdigest()
        image = self.dossier / "cache_livre" / f"{cle[:20]}.jpg"
        if self.decor_seul:
            return image
        if not image.exists():
            # aperçus : depuis une copie moyenne gardée sur le PC (lue une seule fois sur le disque de backup),
            # pour que les aperçus restent rapides même quand le cadrage change ; livre final : depuis l'original
            source = (af.apercu(self.base, self.sortie, ligne["fichier"], 2000, "sources_apercu") if self.apercu
                      else None) or af.original(self.base, ligne["fichier"])
            preparer_image(source, (gauche, haut, cw, ch), cible_px, echelle,
                           None if coins is None else (coins[0] / w * cible_px[0], coins[1]), image,
                           qualite=80 if self.apercu else 95, effet=effet)
        self.placements.append({"page": self.numero, "ligne": ligne, "dpi": round(dpi), "fenetre": (gauche, haut, cw, ch),
                                "case": (x - self.b, y - self.b, w, h),  # en mm depuis le coin du format fini
                                "absolu": (x, y, w, h), "forme": {"arrondi": "arrondi", "cercle": "ovale"}.get(
                                    self.style_courant, "rect"),
                                "angle": self.angle,
                                "style": (self.style_courant or "pleine page") + (" (réduite : qualité)" if self.reduite
                                                                                  else "")})
        return image

    def controler(self, ligne, case):
        """Photo trop peu définie pour sa case, ou peu nette : on la montre plus petite (centrée dans sa case),
        jusqu'à retrouver 200 dpi. Le problème est noté pour l'aperçu et le rapport."""
        x, y, w, h = case
        v = self.visages[ligne["fichier"]]
        dpi = fenetre(v, w / h)[2] * v["largeur"] / (w / 25.4)
        facteur, motifs = 1.0, []
        if dpi < DPI_ALERTE:
            facteur = max(0.45, dpi / DPI_ALERTE)
            motifs.append(f"résolution faible ({round(dpi)} dpi)")
        if v.get("nettete") is not None and v["nettete"] < SEUIL_PEU_NET:
            facteur = min(facteur, 0.75)
            motifs.append("peu nette")
        if not motifs:
            return case, []
        nw, nh = w * facteur, h * facteur
        self.controle.append({"page": self.numero, "fichier": ligne["fichier"], "motifs": motifs,
                              "taille": round(facteur * 100), "dpi_final": round(dpi / facteur)})
        return (x + (w - nw) / 2, y + (h - nh) / 2, nw, nh), motifs

    def etiquette_qualite(self, case, motifs):
        """Aperçu seulement : étiquette orange sur la photo concernée."""
        x, y, w, h = case
        texte = "Qualité : " + ", ".join(motifs) + " - réduite"
        largeur = min(w, 70 * self.k)
        y = y + h - 6 * self.k  # en bas de la photo : ne gêne ni l'encadré ni les visages
        with self.pdf.local_context(fill_opacity=0.9):
            self.couleur("#E67E22")
            self.pdf.rect(x, y, largeur, 6 * self.k, "F")
        self.ecrire(texte, x + 1 * self.k, y + 1.6 * self.k, largeur - 2 * self.k, 7, "sans", "B", "#FFFFFF", "L",
                    ajuster=True)

    def entiere_si_coupe(self, ligne, case, style="classique"):
        """Si aucun recadrage ne garde tous les visages dans la case, la photo est montrée entière
        (ajustée dans la case, centrée) plutôt que de couper quelqu'un."""
        x, y, w, h = case
        v = self.visages[ligne["fichier"]]
        if style == "polaroid":
            bord, bas = 2.8 * self.k, max(9, HAUTEUR_LEGENDE + 2) * self.k
            interieur = (w * 0.9 - 2 * bord, h * 0.9 - bord - bas)
        else:
            interieur = (w, h)
        if interieur[0] <= 0 or interieur[1] <= 0 or not fenetre(v, interieur[0] / interieur[1])[4]:
            return case
        r = v["ratio"]
        if style == "polaroid":  # tirage aux proportions de la photo, bords compris
            iw = w * 0.9 - 2 * bord
            ih = iw / r
            if (ih + bord + bas) / 0.9 > h:
                ih = h * 0.9 - bord - bas
                iw = ih * r
            nw, nh = (iw + 2 * bord) / 0.9, (ih + bord + bas) / 0.9
        else:
            nw, nh = (w, w / r) if w / h < r else (h * r, h)
        self.entieres += 1
        return (x + (w - nw) / 2, y + (h - nh) / 2, nw, nh)

    def photo(self, ligne, case, style="classique", legende="", badge="", graine=0):
        self.case_origine = case  # espace prévu : si la photo y est réduite, l'encadré BD va dans la place libre
        if style != "cercle":
            case = self.entiere_si_coupe(ligne, case, style)
        case, motifs = self.controler(ligne, case)
        self.reduite = bool(motifs)
        self._photo(ligne, case, style, legende, badge, graine)
        self.reduite = False
        if motifs and self.apercu:
            self.etiquette_qualite(case, motifs)
        if self.apercu and style != "cercle" and visage_au_bord(self.visages[ligne["fichier"]]):
            self.coupees_origine.append({"page": self.numero, "fichier": ligne["fichier"]})
            self.etiquette_bord(case)

    def etiquette_bord(self, case):
        """Aperçu seulement : un visage est déjà coupé par le bord de la photo d'origine (aucun recadrage ne peut
        le rattraper) ; à remplacer si possible."""
        x, y, w, h = case
        largeur = min(w, 62 * self.k)
        with self.pdf.local_context(fill_opacity=0.9):
            self.couleur("#B3261E")
            self.pdf.rect(x + w - largeur, y + h - 6 * self.k, largeur, 6 * self.k, "F")
        self.ecrire("Visage coupé sur la photo d'origine", x + w - largeur + 1 * self.k, y + h - 4.4 * self.k,
                    largeur - 2 * self.k, 7, "sans", "B", "#FFFFFF", "L", ajuster=True)

    def _photo(self, ligne, case, style="classique", legende="", badge="", graine=0):
        """Place une photo dans sa case selon le style : classique, arrondi, polaroid ou cercle."""
        x, y, w, h = case
        pdf = self.pdf
        self.style_courant = style
        if style == "polaroid":
            # cadre blanc à bord épais en bas, légèrement incliné, avec ombre : l'effet tirage posé sur la page
            echelle = 0.90
            cw_, ch_ = w * echelle, h * echelle
            cx, cy = x + (w - cw_) / 2, y + (h - ch_) / 2
            bord, bas = 2.8 * self.k, max(9, HAUTEUR_LEGENDE + 2) * self.k
            if legende:
                bas = max(bas, self.hauteur_legende(legende, cw_ - 2 * bord, self.amb["legendes"]) + 3 * self.k)
            if ch_ - bord - bas < max(12 * self.k, 0.45 * ch_) or cw_ - 2 * bord < 12 * self.k:
                # case trop petite pour un polaroïd lisible avec sa légende : photo simple, légende dessous
                haut_legende = min(self.hauteur_legende(legende, w, self.amb["legendes"]), 0.45 * h) if legende else 0
                self._photo(ligne, (x, y, w, h - haut_legende), "classique", "", badge, graine)
                if legende:
                    self.ecrire(legende, x, y + h - haut_legende + 1.2 * self.k, w, TAILLE_LEGENDE,
                                self.amb["legendes"], "I", TEXTE, "C", minimum=TAILLE_LEGENDE, plusieurs_lignes=True)
                return
            angle = ((graine * 7919) % 50 - 25) / 10  # entre -2,5° et +2,5°, stable d'une composition à l'autre
            with pdf.rotation(angle, cx + cw_ / 2, cy + ch_ / 2):
                self.ombre(cx, cy, cw_, ch_)
                self.couleur("#FFFFFF")
                pdf.rect(cx, cy, cw_, ch_, "F")
                interieur = (cx + bord, cy + bord, cw_ - 2 * bord, ch_ - bord - bas)
                self.angle = angle
                self.dessiner(self.image_imprimable(ligne, interieur), *interieur)
                self.angle = 0.0
                if legende:
                    self.angle_texte = angle
                    self.ecrire(legende, cx + bord, cy + ch_ - bas + 2.2 * self.k, cw_ - 2 * bord, TAILLE_LEGENDE,
                                self.amb["legendes"], "I", TEXTE, "C", minimum=TAILLE_LEGENDE, plusieurs_lignes=True)
                    self.angle_texte = 0.0
                if self.amb["scotch"]:  # morceau de ruban adhésif décoratif sur le haut du tirage
                    couleur = self.amb["palette"][graine % len(self.amb["palette"])]
                    with pdf.rotation(((graine // 7) % 30) - 15, cx + cw_ / 2, cy):
                        with pdf.local_context(fill_opacity=0.55):
                            self.couleur(couleur)
                            pdf.rect(cx + cw_ / 2 - 11 * self.k, cy - 3.5 * self.k, 22 * self.k, 7 * self.k, "F")
            if badge:
                self.pastille(badge, cx + 1 * self.k, cy - 3 * self.k)
            return
        if style == "bd":
            self.case_bd(ligne, case, legende, badge)
            return
        if style == "cercle":
            cote = min(w, h)
            cx, cy = x + (w - cote) / 2, y + (h - cote) / 2
            image = self.image_imprimable(ligne, (cx, cy, cote, cote))
            self.couleur("#FFFFFF")
            anneau = 2.5 * self.k
            pdf.ellipse(cx - anneau, cy - anneau, cote + 2 * anneau, cote + 2 * anneau, "F")
            with pdf.elliptic_clip(cx, cy, cote, cote):
                self.dessiner(image, cx, cy, cote, cote)
            return
        rayon = min(4 * self.k, 0.06 * min(w, h)) if style == "arrondi" else 0
        if rayon:
            self.ombre(x, y, w, h, rayon)
        image = self.image_imprimable(ligne, case, (rayon, self.fond) if rayon else None)
        self.dessiner(image, x, y, w, h)
        if badge:
            self.pastille(badge, x + 3 * self.k, y + 3 * self.k)

    def pastille(self, texte, x, y):
        """Pastille ronde colorée (âge sur les photos d'anniversaire)."""
        d = 17 * self.k
        self.couleur(self.amb["palette"][3 % len(self.amb["palette"])])
        self.couleur("#FFFFFF", "draw")
        self.pdf.set_line_width(0.8 * self.k)
        self.pdf.ellipse(x, y, d, d, "DF")
        self.pdf.set_line_width(0.2)
        self.ecrire(texte, x, y + d / 2 - 2.2 * self.k, d, 10, "sans", "B", "#FFFFFF", "C", ajuster=True)

    # ------------------------------------------------------------------ modèles de page
    page_lettres = None  # planche lettres-photos à la place de la page de titre (option)
    lettres_fin = False  # ... et aussi avant la dernière page

    def page_planche_lettres(self, description):
        """Planche lettres-photos en pleine page (fond perdu compris). Fait partie du décor : elle reste aussi
        dans la version PowerPoint."""
        self.nouvelle_page("#FFFFFF", description)
        image = Path(self.page_lettres)
        if self.apercu:  # aperçu léger
            reduite = image.with_name(image.stem + "_apercu.jpg")
            if not reduite.exists() or reduite.stat().st_mtime < image.stat().st_mtime:
                with Image.open(image) as im:
                    im.thumbnail((1400, 1400))
                    im.save(reduite, quality=85)
            image = reduite
        self.pdf.image(str(image), 0, 0, self.l + 2 * self.b, self.h + 2 * self.b)

    def page_titre(self, sujet, periode, dedicace):
        if self.page_lettres:
            self.page_planche_lettres("Page de titre : planche lettres-photos")
            return
        self.nouvelle_page(description="Page de titre")
        x, y, w, h = self.zone_utile()
        illustration(self, "coeur", x + w / 2 - 6 * self.k, y + h * 0.28, 12 * self.k, self.amb["palette"][0])
        self.ecrire(sujet, x, y + h * 0.40, w, 54, self.amb["titres"], style="B", couleur=self.amb.get("texte", TEXTE),
                    align="C", ajuster=True)
        self.ecrire(periode.upper(), x, y + h * 0.40 + 24 * self.k, w, 11, "sans", couleur=TEXTE_CLAIR, align="C",
                    espacement=2)
        if dedicace:
            self.pdf.set_font(self.serif, "I", 14 * self.k)
            self.couleur(self.amb.get("texte", TEXTE), "text")
            self.pdf.set_xy(x + w * 0.15, y + h * 0.62)
            self.textes.append({"page": self.numero, "texte": dedicace, "x": x + w * 0.15, "y": y + h * 0.62,
                                "w": w * 0.7, "h": 21 * self.k, "police": "serif", "style": "I", "taille": 14 * self.k,
                                "couleur": self.amb.get("texte", TEXTE), "align": "C", "angle": 0.0, "multiligne": True})
            if not self.decor_seul:
                self.pdf.multi_cell(w * 0.7, 7 * self.k, self.t(dedicace), align="C")

    def page_chapitre(self, page):
        """Ouverture de chapitre : grand titre et portrait rond, ou photo en passe-partout (selon l'ambiance)."""
        if self.amb.get("bd"):
            self.page_chapitre_bd(page)
            return
        blanc = self.amb["ouverture_fond"] == "blanc"
        self.nouvelle_page(None if blanc else page["couleur"], f"Ouverture de chapitre : {page['titre']}")
        texte = page["couleur"] if blanc else "#FFFFFF"
        x, y, w, h = self.zone_utile()
        self.ecrire(page["titre"], x, y + h * 0.08, w, 80 if len(page["titre"]) <= 6 else 54, self.amb["titres"],
                    style="B", couleur=texte, align="C", ajuster=True)
        if page["sous_titre"]:
            self.ecrire(page["sous_titre"].upper(), x, y + h * 0.08 + 36 * self.k, w, 12, "sans", couleur=texte,
                        align="C", espacement=2)
        if blanc:  # filet fin sous le titre, à la manière d'un livre d'art
            self.couleur(page["couleur"], "draw")
            self.pdf.set_line_width(0.3)
            self.pdf.line(x + w * 0.42, y + h * 0.08 + 46 * self.k, x + w * 0.58, y + h * 0.08 + 46 * self.k)
            self.pdf.set_line_width(0.2)
        elif page.get("type"):
            illustration(self, {"fetes": "fete"}.get(page["type"], page["type"]), x + w / 2 - 13 * self.k,
                         y + h * 0.08 + 46 * self.k, 26 * self.k, "#FFFFFF")
        if self.amb["ouverture"] == "cercle":
            cote = h * 0.48
            self.photo(page["photo"], (x + (w - cote) / 2, y + h - cote - h * 0.05, cote, cote), "cercle")
            return
        ratio = min(max(self.visages[page["photo"]["fichier"]]["ratio"], 0.75), 1.4)
        case_h = h * 0.50
        case_w = min(case_h * ratio, w * 0.8)
        case_h = case_w / ratio
        cx, cy = x + (w - case_w) / 2, y + h - case_h - h * 0.04
        if not blanc:
            bord = 3 * self.k  # passe-partout blanc
            self.couleur("#FFFFFF")
            self.pdf.rect(cx - bord, cy - bord, case_w + 2 * bord, case_h + 2 * bord, "F")
        self.photo(page["photo"], (cx, cy, case_w, case_h))

    def page_pleine(self, page):
        self.nouvelle_page(description=f"Pleine page : {page['titre']}")
        self.style_courant = "pleine page"
        image = self.image_imprimable(page["photo"], (0, 0, self.l + 2 * self.b, self.h + 2 * self.b))
        self.dessiner(image, 0, 0, self.l + 2 * self.b, self.h + 2 * self.b)
        if not page["bandeau"]:
            self.medaillons_poses = []
            self.legende_sur_photo(page["photo"], (0, 0, self.l + 2 * self.b, self.h + 2 * self.b))
        if page["bandeau"]:
            hauteur = 30 * self.k
            y = self.b + self.h - self.marge - hauteur
            with self.pdf.local_context(fill_opacity=0.45):
                self.couleur("#000000")
                self.pdf.rect(0, y - 4 * self.k, self.l + 2 * self.b, hauteur + self.marge + self.b + 4 * self.k, "F")
            x = self.b + self.marge + (self.reliure if self.numero % 2 else 0)
            largeur = self.l - 2 * self.marge - self.reliure - 30 * self.k
            self.ecrire(page["titre"], x, y + 4 * self.k, largeur, 24, self.amb["titres"], style="B", couleur="#FFFFFF",
                        ajuster=True)
            self.ecrire(page["sous_titre"], x, y + 16 * self.k, largeur, 11, "sans", couleur="#FFFFFF", ajuster=True)
            if page["type"]:
                illustration(self, page["type"], x + largeur + 4 * self.k, y - 1 * self.k, 26 * self.k, "#FFFFFF",
                             page["souvenir"])

    def page_photos(self, page, precedent):
        self.nouvelle_page(description=page["titre"] or page.get("chapitre", ""))
        x, y, w, h = self.zone_utile()
        h -= 6 * self.k  # place du folio
        style = self.amb["petits"] if page.get("petits_moments") else self.amb["photo"]
        self.pages_photos += 1
        aere = len(page["photos"]) <= 4 and self.pages_photos % self.amb["respiration"] == 0
        if page["entete"]:
            haut = 30 * self.k
            self.ecrire(page["chapitre"].upper(), x, y, w, 8, "sans", couleur=page["couleur"], espacement=1.5)
            largeur_titre = w - (30 * self.k if page["type"] else 0)
            if page["titre"]:
                self.ecrire(page["titre"], x, y + 6 * self.k, largeur_titre, 22, self.amb["titres"], style="B",
                            ajuster=True)
            if page["sous_titre"]:
                self.ecrire(page["sous_titre"], x, y + 17 * self.k, largeur_titre, 10, "sans", couleur=TEXTE_CLAIR,
                            ajuster=True)
            if page["type"]:
                illustration(self, {"fetes": "fete"}.get(page["type"], page["type"]), x + w - 26 * self.k,
                             y - 2 * self.k, 26 * self.k, page["couleur"], page.get("souvenir"))
            y, h = y + haut, h - haut
        textes = dict(zip(map(id, page["photos"]), page["legendes"]))
        badges = dict(zip(map(id, page["photos"]), page["badges"]))
        if style == "bd":  # narration dans un encadré jaune, bulle sur les grands moments
            premiere = page["photos"][0]
            if not textes[id(premiere)]:
                d = premiere["jour"]
                lieu = af.lieu_court(premiere.get("lieu", ""))
                textes[id(premiere)] = f"{d.day} {MOIS[d.month - 1]} {d.year}" + (f" · {lieu}" if lieu else "")
            for p in page["photos"]:
                if badges[id(p)]:
                    badges[id(p)] = f"{badges[id(p)]} !"
            if page["entete"] and page.get("type") in BULLES and not badges[id(premiere)]:
                badges[id(premiere)] = BULLES[page["type"]]
        sous_photo = style not in ("polaroid", "bd") and any(textes.values())  # légende dans le cadre
        infos = [dict(self.visages[p["fichier"]], note=float(p["score"] or 0), ligne=p) for p in page["photos"]]
        if style == "polaroid":  # le cadre blanc mange de la place en hauteur : on raisonne sur l'image intérieure
            for info in infos:
                info["ratio"] = info["ratio"] * 1.08
        nom, placement = choisir_gabarit(infos, (x, y, w, h), self.ecart * (1.8 if style == "polaroid" else 1), precedent,
                                         aere)
        for (cx, cy, cw, ch), info in placement:
            ligne = info["ligne"]
            if sous_photo:
                ch -= min(max(HAUTEUR_LEGENDE * self.k, self.hauteur_legende(textes[id(ligne)], cw, self.amb["legendes"])),
                          0.45 * ch)
            graine = int(hashlib.md5(ligne["fichier"].encode()).hexdigest()[:6], 16)
            self.photo(ligne, (cx, cy, cw, ch), style, textes[id(ligne)], badges[id(ligne)], graine)
            if sous_photo and textes[id(ligne)]:
                self.ecrire(textes[id(ligne)], cx, cy + ch + 1.5 * self.k, cw, TAILLE_LEGENDE, self.amb["legendes"], "I",
                            TEXTE_CLAIR, "C", minimum=TAILLE_LEGENDE, plusieurs_lignes=True)
        self.folio()
        return nom

    def page_couverture(self, ligne, sujet, periode):
        """Couverture : pleine photo et bandeau (tendre, carnet) ou photo en passe-partout sur blanc (élégant)."""
        self.nouvelle_page(description="Couverture")
        self.style_courant = "couverture"
        k = self.k
        if self.amb.get("sombre"):
            self.couverture_prestige(ligne, sujet, periode)
            return
        if self.amb.get("bd"):
            self.couverture_bd(ligne, sujet, periode)
            return
        if self.amb["ouverture_fond"] == "blanc":
            x, y, w, h = self.b + self.l * 0.14, self.b + self.h * 0.10, self.l * 0.72, self.h * 0.62
            self.photo(ligne, (x, y, w, h))
            self.ecrire(sujet, self.b, y + h + 16 * k, self.l, 44, self.amb["titres"], "B", TEXTE, "C", ajuster=True)
            self.ecrire(periode.upper(), self.b, y + h + 34 * k, self.l, 11, "sans", couleur=TEXTE_CLAIR, align="C",
                        espacement=2)
            return
        plein = (0, 0, self.l + 2 * self.b, self.h + 2 * self.b)
        self.dessiner(self.image_imprimable(ligne, plein), *plein)
        with self.pdf.local_context(fill_opacity=0.40):
            self.couleur("#000000")
            self.pdf.rect(0, self.b + self.h * 0.70, self.l + 2 * self.b, 42 * k, "F")
        self.ecrire(sujet, self.b, self.b + self.h * 0.70 + 8 * k, self.l, 48, self.amb["titres"], style="B",
                    couleur="#FFFFFF", align="C", ajuster=True)
        self.ecrire(periode.upper(), self.b, self.b + self.h * 0.70 + 30 * k, self.l, 11, "sans", couleur="#FFFFFF",
                    align="C", espacement=2)

    def page_controle(self):
        """Dernière page de l'aperçu : photos réduites pour cause de qualité, et photos dont un visage est déjà
        coupé sur l'original."""
        lignes = [f"Page {c['page']} : {Path(c['fichier']).name} - {', '.join(c['motifs'])} - affichée à "
                  f"{c['taille']} % ({c['dpi_final']} dpi)" for c in self.controle]
        lignes += [f"Page {c['page']} : {Path(c['fichier']).name} - visage coupé sur la photo d'origine "
                   "(à remplacer si possible)" for c in self.coupees_origine]
        par_page = 30
        for debut in range(0, max(len(lignes), 1), par_page):
            self.nouvelle_page("#FFFFFF", "Contrôle qualité (aperçu seulement)")
            x, y, w, h = self.zone_utile()
            self.ecrire("Contrôle qualité (cette page n'est pas dans le livre final)", x, y, w, 16, "serif", "B", TEXTE)
            texte = (f"{len(lignes)} photo(s) réduite(s) pour rester nette(s) à l'impression. Pour les garder grandes, "
                     "remplacez-les par une meilleure version (garder = 0 / 1 dans selection_livre.csv).")
            self.ecrire(texte if lignes else "Aucune photo réduite : toutes sont assez définies et nettes.",
                        x, y + 9 * self.k, w, 9, "sans", "", TEXTE_CLAIR, ajuster=True)
            for i, ligne in enumerate(lignes[debut: debut + par_page]):
                self.ecrire(ligne, x, y + (20 + i * 7.5) * self.k, w, 8.5, "sans", "", TEXTE, ajuster=True)

    def page_notes(self, sujet):
        """Page à remplir à la main (sert aussi à atteindre le nombre pair de pages demandé par l'imprimeur)."""
        self.nouvelle_page(description="Page de notes (sans photo)")
        x, y, w, h = self.zone_utile()
        illustration(self, "coeur", x, y + 2 * self.k, 9 * self.k, self.amb["palette"][0])
        self.ecrire("Mes souvenirs à écrire", x + 13 * self.k, y + 4 * self.k, w, 20, self.amb["titres"], style="I",
                    couleur=self.amb.get("texte", TEXTE))
        self.couleur("#4A4640" if self.amb.get("sombre") else "#D9D2C8", "draw")
        self.pdf.set_line_width(0.25)
        ligne_y = y + 28 * self.k
        while ligne_y < y + h - 8 * self.k:
            self.pdf.line(x, ligne_y, x + w, ligne_y)
            ligne_y += 11 * self.k
        self.pdf.set_line_width(0.2)

    symbole_fin = "etoiles"  # option --symbole-fin

    def symbole(self, nom, cx, y, taille, couleur):
        """Petit motif au-dessus du texte de fin : coeur, coeurs, etoiles, fleur, ornement, colombe ou aucun."""
        pdf, k = self.pdf, taille / 26
        if nom in ("", "aucun"):
            return 0
        if nom in ("coeur", "etoiles"):
            illustration(self, nom, cx - taille / 2, y, taille, couleur)
        elif nom == "coeurs":  # trois coeurs, celui du milieu plus grand
            self.couleur(couleur)
            for dx, t in ((-0.55, 0.32), (0, 0.5), (0.55, 0.32)):
                pdf.polygon(coeur(cx + dx * taille, y + taille * 0.5, taille * t), style="F")
        elif nom == "fleur":  # fleur à cinq pétales, coeur doré
            self.couleur(couleur)
            for i in range(5):
                a = math.radians(i * 72 - 90)
                px, py = cx + math.cos(a) * 6 * k, y + taille / 2 + math.sin(a) * 6 * k
                pdf.ellipse(px - 4.5 * k, py - 4.5 * k, 9 * k, 9 * k, "F")
            self.couleur("#E9C46A")
            pdf.ellipse(cx - 3.5 * k, y + taille / 2 - 3.5 * k, 7 * k, 7 * k, "F")
        elif nom == "ornement":  # deux filets et un losange
            self.couleur(couleur, "draw")
            self.couleur(couleur)
            pdf.set_line_width(0.3)
            d, ym = 1.8 * self.k, y + taille / 2
            pdf.line(cx - taille * 1.6, ym, cx - 2.5 * d, ym)
            pdf.line(cx + 2.5 * d, ym, cx + taille * 1.6, ym)
            pdf.polygon([(cx, ym - d), (cx + d, ym), (cx, ym + d), (cx - d, ym)], style="F")
            pdf.set_line_width(0.2)
        elif nom == "colombe":  # silhouette d'oiseau en vol (deux ailes)
            self.couleur(couleur)
            ym = y + taille / 2
            pdf.polygon([(cx - 13 * k, ym - 6 * k), (cx - 4 * k, ym - 1 * k), (cx, ym + 2 * k), (cx + 4 * k, ym - 1 * k),
                         (cx + 13 * k, ym - 6 * k), (cx + 6 * k, ym + 3 * k), (cx, ym + 5 * k), (cx - 6 * k, ym + 3 * k)],
                        style="F")
        return taille

    def page_fin(self, sujet, periode, mot):
        """Dernière page : un symbole, le texte de fin (paragraphes et retours à la ligne gardés, taille ajustée
        pour que tout tienne, jamais tronqué), puis le prénom et la période."""
        self.nouvelle_page(description="Dernière page (sans photo)")
        x, y, w, h = self.zone_utile()
        texte = mot or traduire("À suivre…", self.langue)  # le texte écrit à la main reste dans sa langue
        self.texte_libre = bool(mot)
        coeur_final = any(c in texte for c in "❤♥")
        for emoji in ("❤️", "❤", "♥", "\ufe0f"):  # pas d'emoji dans les polices d'impression : coeur dessiné
            texte = texte.replace(emoji, "")
        lignes = [l.rstrip() for l in texte.replace("\r", "").split("\n")]
        while lignes and not lignes[-1]:
            lignes.pop()
        couleur = self.amb.get("texte", TEXTE)
        court = len(lignes) == 1 and len(lignes[0]) <= 40
        if court:  # « À suivre… » ou une phrase courte : grand, au centre (comme avant)
            haut = self.symbole(self.symbole_fin, x + w / 2, y + h * 0.36, 30 * self.k, self.amb["palette"][0])
            hauteur = self.ecrire(lignes[0] if lignes else "", x, y + h * 0.52, w, 20, self.amb["titres"], style="I",
                                  align="C", couleur=couleur, ajuster=True, minimum=14)
            y_fin = y + h * 0.52 + max(14 * self.k, hauteur + 6 * self.k)
        else:  # lettre : paragraphes centrés, police de texte, taille la plus grande qui tient
            largeur = w * 0.84
            dispo = h * 0.70
            # 1re ligne courte (« Ma chérie, ») : un peu plus grande, comme l'en-tête d'une lettre
            entete = len(lignes) > 2 and len(lignes[0]) <= 30 and not lignes[1].strip()

            def hauteur_ligne(l, t):
                n = len(self.couper_lignes(l, largeur, t, "serif", "I"))
                return n * t * (0.47 if n > 1 else 0.45)
            for taille in (26, 24, 22, 20, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9):
                total = sum(hauteur_ligne(l, taille * (1.3 if entete and i == 0 else 1)) if l.strip()
                            else taille * 0.35 for i, l in enumerate(lignes))
                if total <= dispo:
                    break
            taille_symbole = 18 * self.k
            y_texte = y + max(0.0, (h - total - taille_symbole - 30 * self.k) / 2) + taille_symbole + 6 * self.k
            self.symbole(self.symbole_fin, x + w / 2, y_texte - taille_symbole - 4 * self.k, taille_symbole,
                         self.amb["palette"][0])
            yy = y_texte
            for i, l in enumerate(lignes):
                if not l.strip():
                    yy += taille * 0.35
                    continue
                t = taille * (1.3 if entete and i == 0 else 1)
                yy += self.ecrire(l.strip(), x + (w - largeur) / 2, yy, largeur, t, "serif", "I", couleur, "C",
                                  plusieurs_lignes=True)
            y_fin = yy + 8 * self.k
        if coeur_final:
            self.couleur(self.amb["palette"][0])
            self.pdf.polygon(coeur(x + w / 2, y_fin - 1.5 * self.k, 6 * self.k), style="F")
            y_fin += 8 * self.k
        self.texte_libre = False
        self.ecrire(f"{sujet} · {periode}".upper(), x, min(y_fin, y + h - 8 * self.k), w, 9, "sans",
                    couleur=TEXTE_CLAIR, align="C", espacement=2)

    def pied_de_page(self, premier, dernier, texte, sur_photo=False):
        """Pied de page (option --pied-de-page) sur les pages premier..dernier déjà dessinées : petit texte côté
        extérieur, à hauteur du numéro de page ; sur une photo pleine page, en blanc sur un léger bandeau."""
        if not texte:
            return
        courante, decalage, numero_courant = self.pdf.page, self.pdf.page - self.numero, self.numero
        for numero in range(premier, dernier + 1):
            self.pdf.page = numero + decalage
            self.numero = numero  # pour la version PowerPoint : le texte va sur la bonne diapositive
            y = self.b + self.h - self.marge * 0.55
            largeur = min(self.l * 0.45, self.pdf.get_string_width(self.t(texte)) + 20 * self.k)
            droite = numero % 2 == 1  # page impaire = page de droite : texte à droite (côté extérieur)
            x = self.b + self.l - self.marge - largeur if droite else self.b + self.marge
            if sur_photo:
                with self.pdf.local_context(fill_opacity=0.35):
                    self.couleur("#000000")
                    self.pdf.rect(x - 2 * self.k, y - 1.5 * self.k, largeur + 4 * self.k, 6.5 * self.k, "F")
            self.texte_libre = True  # pied de page saisi à la main : jamais traduit
            self.ecrire(texte, x, y, largeur, 8, "serif", "I", "#FFFFFF" if sur_photo else TEXTE_CLAIR,
                        "R" if droite else "L", ajuster=True, minimum=6)
            self.texte_libre = False
        self.pdf.page, self.numero = courante, numero_courant


CONVERSIONS_RATEES = []  # photos dont le profil couleur n'a pas pu être converti en sRGB (rapport d'impression)


def preparer_image(source, fenetre_rel, cible_px, echelle, coins, destination, qualite=95, effet=None):
    """Chaîne de qualité d'impression : profil couleur -> sRGB, recadrage, réduction Lanczos,
    accentuation légère (une réduction adoucit l'image), coins arrondis éventuels, JPEG qualité 95 + profil sRGB."""
    import io

    from PIL import ImageCms, ImageDraw, ImageFilter

    srgb = ImageCms.createProfile("sRGB")
    with Image.open(source) as im:  # lecture seule de l'original
        icc = im.info.get("icc_profile")
        im = ImageOps.exif_transpose(im)
        profil_sortie = ImageCms.ImageCmsProfile(srgb).tobytes()
        if icc:  # iPhone récents : Display P3 ; sans conversion les couleurs virent à l'impression
            try:
                im = ImageCms.profileToProfile(im, ImageCms.ImageCmsProfile(io.BytesIO(icc)), srgb,
                                               outputMode="RGB")
            except (ImageCms.PyCMSError, OSError, ValueError) as erreur:
                # profil illisible : on garde les couleurs ET le profil d'origine (le marquer sRGB fausserait
                # les couleurs à l'impression) et on le signale
                profil_sortie = icc
                CONVERSIONS_RATEES.append(f"{Path(str(source)).name} ({erreur})")
        im = im.convert("RGB")
        L, H = im.size
        gauche, haut, cw, ch = fenetre_rel
        g, t = min(max(round(gauche * L), 0), L - 1), min(max(round(haut * H), 0), H - 1)
        boite = (g, t, max(g + 1, min(L, round((gauche + cw) * L))), max(t + 1, min(H, round((haut + ch) * H))))
        im = im.crop(boite).resize((max(1, cible_px[0]), max(1, cible_px[1])), Image.LANCZOS)
    if effet == "cartoon":
        im = cartoon(im)
    elif echelle < 0.9:
        im = im.filter(ImageFilter.UnsharpMask(radius=1.0, percent=45, threshold=3))
    if coins:
        rayon_px, couleur = coins
        masque = Image.new("L", (im.width * 2, im.height * 2), 0)  # dessiné en 2x puis réduit : bords lissés
        ImageDraw.Draw(masque).rounded_rectangle((0, 0, masque.width - 1, masque.height - 1), radius=rayon_px * 2,
                                                 fill=255)
        masque = masque.resize(im.size, Image.LANCZOS)
        fond = Image.new("RGB", im.size, tuple(int(couleur[i:i + 2], 16) for i in (1, 3, 5)))
        im = Image.composite(im, fond, masque)
    im.save(destination, quality=qualite, subsampling=0, dpi=(DPI_CIBLE, DPI_CIBLE), icc_profile=profil_sortie)


# =========================================================================== illustrations vectorielles

def hexa_rgb(hexa):
    return tuple(int(hexa[i:i + 2], 16) for i in (1, 3, 5))


def coeur(cx, cy, taille):
    points = []
    for i in range(60):
        t = 2 * math.pi * i / 60
        px = 16 * math.sin(t) ** 3
        py = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append((cx + px * taille / 34, cy - py * taille / 34))
    return points


def etoile(cx, cy, r, branches=5, creux=0.45):
    return [(cx + (r if i % 2 == 0 else r * creux) * math.sin(math.pi * i / branches),
             cy - (r if i % 2 == 0 else r * creux) * math.cos(math.pi * i / branches)) for i in range(2 * branches)]


def drapeau(livre, code, x, y, w, h):
    pdf = livre.pdf
    if code in DRAPEAUX:
        sens, couleurs = DRAPEAUX[code]
        for i, c in enumerate(couleurs):
            livre.couleur(c)
            if sens == "v":
                pdf.rect(x + i * w / len(couleurs), y, w / len(couleurs) + 0.05, h, "F")
            else:
                pdf.rect(x, y + i * h / len(couleurs), w, h / len(couleurs) + 0.05, "F")
    elif code == "JP":
        livre.couleur("#FFFFFF"); pdf.rect(x, y, w, h, "F")
        livre.couleur("#BC002D"); pdf.ellipse(x + w / 2 - h * 0.3, y + h * 0.2, h * 0.6, h * 0.6, "F")
    elif code == "CH":
        livre.couleur("#DA291C"); pdf.rect(x, y, w, h, "F")
        livre.couleur("#FFFFFF")
        pdf.rect(x + w / 2 - h * 0.1, y + h * 0.2, h * 0.2, h * 0.6, "F")
        pdf.rect(x + w / 2 - h * 0.3, y + h * 0.4, h * 0.6, h * 0.2, "F")
    elif code == "PH":
        livre.couleur("#0038A8"); pdf.rect(x, y, w, h / 2, "F")
        livre.couleur("#CE1126"); pdf.rect(x, y + h / 2, w, h / 2, "F")
        livre.couleur("#FFFFFF"); pdf.polygon([(x, y), (x + h * 0.866, y + h / 2), (x, y + h)], style="F")
        livre.couleur("#FCD116"); pdf.ellipse(x + h * 0.22, y + h * 0.4, h * 0.2, h * 0.2, "F")
    else:
        return False
    livre.couleur("#BBBBBB", "draw")
    pdf.set_line_width(0.15)
    pdf.rect(x, y, w, h, "D")
    return True


def illustration(livre, type_, x, y, taille, couleur, souvenir=None):
    """Petits dessins vectoriels (nets à toutes les tailles d'impression), dans un carré de côté taille."""
    pdf, k = livre.pdf, taille / 26
    cx, cy = x + taille / 2, y + taille / 2
    livre.couleur(couleur, "draw")
    livre.couleur(couleur)
    pdf.set_line_width(0.5 * k)
    if type_ in ("coeur", "naissance", "bapteme"):
        pdf.polygon(coeur(cx, cy + 1 * k, taille * 0.55), style="F")
        if type_ != "coeur":
            for dx, dy, r in ((-10, -8, 2.2), (10, -9, 1.6), (9, 8, 1.8), (-9, 9, 1.4)):
                pdf.polygon(etoile(cx + dx * k, cy + dy * k, r * k), style="F")
    elif type_ == "etoiles":
        pdf.polygon(etoile(cx, cy, taille * 0.3), style="F")
        for dx, dy, r in ((-11, -4, 2.5), (11, -6, 2), (8, 8, 1.6), (-8, 9, 1.4)):
            pdf.polygon(etoile(cx + dx * k, cy + dy * k, r * k), style="F")
    elif type_ == "anniversaire":
        chiffres = [int(m) for m in souvenir["titre"].split() if m.isdigit()] if souvenir else []
        a = chiffres[0] if chiffres else 1  # une bougie par an, d'après le titre « Les 5 ans de ... »
        livre.couleur(couleur)
        pdf.rect(cx - 10 * k, cy + 1 * k, 20 * k, 9 * k, "F")
        pdf.rect(cx - 7 * k, cy - 5 * k, 14 * k, 6.5 * k, "F")
        livre.couleur(FOND if couleur != "#FFFFFF" else "#888888")
        for i in range(5):  # nappage festonné
            pdf.ellipse(cx - 10 * k + i * 4 * k, cy + 0.2 * k, 4 * k, 2.4 * k, "F")
        bougies = min(max(a, 1), 7)
        for i in range(bougies):
            bx = cx - 6 * k + (i + 0.5) * 12 * k / bougies
            livre.couleur(couleur)
            pdf.rect(bx - 0.5 * k, cy - 10 * k, 1 * k, 5 * k, "F")
            livre.couleur("#F2A93B")
            pdf.ellipse(bx - 0.9 * k, cy - 13 * k, 1.8 * k, 2.8 * k, "F")
        if a > 7:
            livre.ecrire(str(a), cx - 10 * k, cy + 4 * k, 20 * k, 9 * k / livre.k, "sans", "B",
                         FOND if couleur != "#FFFFFF" else "#555555", "C")
    elif type_ == "noel":
        for i, (largeur, haut) in enumerate(((18, 8), (14, 7), (10, 6))):
            base_y = cy + 7 * k - i * 5.5 * k
            livre.couleur("#3E7A4F" if couleur != "#FFFFFF" else "#FFFFFF")
            pdf.polygon([(cx - largeur / 2 * k, base_y), (cx + largeur / 2 * k, base_y), (cx, base_y - haut * k)], style="F")
        livre.couleur("#7A5233" if couleur != "#FFFFFF" else "#FFFFFF")
        pdf.rect(cx - 1.5 * k, cy + 7 * k, 3 * k, 3.5 * k, "F")
        livre.couleur("#F2C23B")
        pdf.polygon(etoile(cx, cy - 11 * k, 2.6 * k), style="F")
        for bx, by, c in ((-4, 4, "#C0392B"), (3, 1, "#2E6DB4"), (-1, -3, "#C0392B"), (5, 6, "#F2C23B")):
            livre.couleur(c)
            pdf.ellipse(cx + bx * k - 0.9 * k, cy + by * k - 0.9 * k, 1.8 * k, 1.8 * k, "F")
    elif type_ == "nouvel-an":
        for (bx, by, r), c in zip(((-5, -3, 7), (6, 2, 5.5), (-2, 7, 4)), ("#F2C23B", couleur, "#C0392B")):
            livre.couleur(c, "draw")
            for i in range(12):
                angle = 2 * math.pi * i / 12
                pdf.line(cx + bx * k + math.cos(angle) * r * 0.35 * k, cy + by * k + math.sin(angle) * r * 0.35 * k,
                         cx + bx * k + math.cos(angle) * r * k, cy + by * k + math.sin(angle) * r * k)
    elif type_ == "mariage":
        livre.couleur("#C9A54A" if couleur != "#FFFFFF" else "#FFFFFF", "draw")
        pdf.set_line_width(1.3 * k)
        pdf.ellipse(cx - 10 * k, cy - 3 * k, 12 * k, 12 * k, "D")
        pdf.ellipse(cx - 2 * k, cy - 3 * k, 12 * k, 12 * k, "D")
        livre.couleur(couleur if couleur != "#FFFFFF" else "#FFFFFF")
        pdf.polygon(coeur(cx, cy - 8 * k, 6 * k), style="F")
    elif type_ == "vacances":
        livre.couleur("#F2B33B" if couleur != "#FFFFFF" else "#FFFFFF")
        livre.couleur("#F2B33B" if couleur != "#FFFFFF" else "#FFFFFF", "draw")
        pdf.ellipse(cx - 4 * k, cy - 10 * k, 8 * k, 8 * k, "F")
        for i in range(10):
            angle = 2 * math.pi * i / 10
            pdf.line(cx + math.cos(angle) * 5.5 * k, cy - 6 * k + math.sin(angle) * 5.5 * k,
                     cx + math.cos(angle) * 8 * k, cy - 6 * k + math.sin(angle) * 8 * k)
        livre.couleur("#3D7FB0" if couleur != "#FFFFFF" else "#FFFFFF", "draw")
        pdf.set_line_width(0.9 * k)
        for ligne in range(3):
            points = [(cx - 12 * k + i * k, cy + (4 + 3 * ligne) * k + math.sin(i / 1.6) * 1.1 * k) for i in range(25)]
            pdf.polyline(points)
    elif type_ == "fete":
        for bx, by, c in ((-6, -4, "#C0392B"), (1, -7, "#2E6DB4"), (7, -3, "#F2C23B")):
            livre.couleur(c if couleur != "#FFFFFF" else "#FFFFFF")
            pdf.ellipse(cx + bx * k - 3.2 * k, cy + by * k - 4 * k, 6.4 * k, 8 * k, "F")
            livre.couleur(couleur, "draw")
            pdf.set_line_width(0.3 * k)
            pdf.line(cx + bx * k, cy + by * k + 4 * k, cx + bx * k * 0.3, cy + 11 * k)
    elif type_ == "voyage":  # tampon de passeport + drapeau
        code = ""
        if souvenir:
            pays = Counter(code_pays(p["lieu"]) for p in souvenir["photos"] if p["lieu"])
            code = pays.most_common(1)[0][0] if pays else ""
        livre.couleur(couleur, "draw")
        pdf.set_line_width(0.6 * k)
        pdf.ellipse(x + 1 * k, y + 1 * k, taille - 2 * k, taille - 2 * k, "D")
        pdf.set_line_width(0.25 * k)
        pdf.ellipse(x + 2.5 * k, y + 2.5 * k, taille - 5 * k, taille - 5 * k, "D")
        livre.couleur(couleur)
        avion = [(0, -6), (1, -4), (1, -1), (7, 2), (7, 3.2), (1, 1.5), (1, 4.5), (2.8, 6), (2.8, 7), (0, 6.2),
                 (-2.8, 7), (-2.8, 6), (-1, 4.5), (-1, 1.5), (-7, 3.2), (-7, 2), (-1, -1), (-1, -4)]
        pdf.polygon([(cx + px * 0.55 * k, cy - 6 * k + py * 0.55 * k) for px, py in avion], style="F")
        nom = nom_pays(code).upper() if code else "VOYAGE"
        taille_texte = min(6.5, 60 / max(len(nom), 1)) * k / livre.k
        livre.ecrire(nom, x, cy + 2 * k, taille, taille_texte, "sans", "B", couleur, "C")
        if souvenir:
            livre.ecrire(str(souvenir["annee"]), x, cy + 6 * k, taille, 5 * k / livre.k, "sans", "", couleur, "C")
        if code:
            drapeau(livre, code, cx - 4 * k, cy + 9.5 * k, 8 * k, 5.3 * k)
    livre.pdf.set_line_width(0.2)


# =========================================================================== dossier pour l'imprimeur

def position_sur_page(case, largeur, hauteur):
    x, y, w, h = case
    if w >= largeur * 0.95 and h >= hauteur * 0.95:
        return "pleine page"
    cx, cy = x + w / 2, y + h / 2
    ligne = "haut" if cy < hauteur / 3 else ("bas" if cy > 2 * hauteur / 3 else "milieu")
    colonne = "gauche" if cx < largeur / 3 else ("droite" if cx > 2 * largeur / 3 else "centre")
    return f"{ligne}-{colonne}"


def ordre_de_lecture(placements):
    """Ordre de lecture d'une page : par le bord haut des photos (rangées à 25 mm près), puis de gauche à droite.
    Une grande photo à gauche passe donc avant les petites empilées à sa droite."""
    return sorted(placements, key=lambda p: (p["page"], round(p["case"][1] / 25), p["case"][0]))


def archiver_anciennes_sorties(dossier):
    """Range dans ancienne_version/ les fichiers produits par les versions précédentes de l'outil
    (rien n'est supprimé), pour ne pas mélanger avec le dossier imprimeur."""
    anciens = [dossier / "photos_selectionnees", dossier / "contenu_livre.csv", dossier / "rapport_impression.txt"]
    anciens += [f for f in dossier.glob("Livre_*.pdf")]
    anciens = [f for f in anciens if f.exists()]
    if anciens:
        archive = dossier / "ancienne_version"
        archive.mkdir(exist_ok=True)
        for f in anciens:
            cible = archive / f.name
            if cible.exists():
                cible = archive / f"{f.stem}_{dt.datetime.now():%Y%m%d-%H%M%S}{f.suffix}"
            shutil.move(str(f), str(cible))
        print(f"  Anciennes sorties rangées dans {archive}")


def exporter_powerpoint(base, dossier, sortie, nom_fichier, livre, decor):
    """Version modifiable : une diapositive par page, au format exact (fond perdu compris).
    Le décor (fonds, filets, cadres, ornements) est une image de fond ; chaque photo est une image séparée,
    entière avec son recadrage PowerPoint (modifiable : Format de l'image > Rogner) ; chaque texte est une zone
    de texte. On peut ainsi déplacer, permuter ou recadrer les photos d'une planche, puis exporter en PDF."""
    import pypdfium2
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Mm, Pt

    calques = dossier / "cache_pptx"
    calques.mkdir(exist_ok=True)
    fichier_decor = calques / "decor.pdf"
    decor.pdf.output(str(fichier_decor))
    largeur, hauteur = livre.l + 2 * livre.b, livre.h + 2 * livre.b
    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Mm(largeur), Mm(hauteur)
    vide = presentation.slide_layouts[6]
    images = defaultdict(list)
    for p in livre.placements + livre.placements_pptx:
        images[p["page"]].append(p)
    textes = defaultdict(list)
    for t in livre.textes:
        textes[t["page"]].append(t)
    polices = {"serif": "Georgia", "sans": "Arial", "main": "Segoe Print", "bd": "Comic Sans MS", "impact": "Impact"}
    document = pypdfium2.PdfDocument(str(fichier_decor))
    for numero in range(1, len(document) + 1):
        diapo = presentation.slides.add_slide(vide)
        fond = calques / f"decor_{numero:03d}.png"
        document[numero - 1].render(scale=200 / 72).to_pil().save(fond)  # décor à 200 dpi (le PDF reste la référence)
        diapo.shapes.add_picture(str(fond), 0, 0, Mm(largeur), Mm(hauteur))
        for p in images[numero]:
            ligne = p["ligne"]
            v = livre.visages[ligne["fichier"]]
            x, y, w, h = p["absolu"]
            gauche, haut, cw, ch = p["fenetre"]
            # photo entière, à 300 dpi au plus pour la partie visible : on peut la recadrer dans PowerPoint
            echelle = min(1.0, (w / 25.4 * DPI_CIBLE) / (cw * v["largeur"]))
            taille = (max(1, round(v["largeur"] * echelle)), max(1, round(v["hauteur"] * echelle)))
            effet = livre.amb.get("effet")
            image = calques / (hashlib.md5(f"{ligne['fichier']}|{taille}|{effet}-v2".encode()).hexdigest()[:20] + ".jpg")
            if not image.exists():
                preparer_image(af.original(base, ligne["fichier"]), (0, 0, 1, 1), taille, echelle, None, image,
                               qualite=92, effet=effet)
            photo = diapo.shapes.add_picture(str(image), Mm(x), Mm(y), Mm(w), Mm(h))
            photo.crop_left, photo.crop_top = gauche, haut
            photo.crop_right, photo.crop_bottom = max(0.0, 1 - gauche - cw), max(0.0, 1 - haut - ch)
            if p.get("angle"):
                photo.rotation = -p["angle"]
            if p.get("forme") == "ovale":
                photo.auto_shape_type = MSO_SHAPE.OVAL
            elif p.get("forme") == "arrondi":
                photo.auto_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE
            photo.name = f"{Path(ligne['fichier']).name} ({ligne['date']})"
        for t in textes[numero]:
            boite = diapo.shapes.add_textbox(Mm(t["x"]), Mm(t["y"]), Mm(t["w"]), Mm(max(t["h"], 4)))
            cadre = boite.text_frame
            cadre.margin_left = cadre.margin_right = cadre.margin_top = cadre.margin_bottom = 0
            cadre.word_wrap = bool(t.get("multiligne"))
            cadre.vertical_anchor = MSO_ANCHOR.MIDDLE if not t.get("multiligne") else MSO_ANCHOR.TOP
            paragraphe = cadre.paragraphs[0]
            paragraphe.alignment = {"C": PP_ALIGN.CENTER, "R": PP_ALIGN.RIGHT}.get(t["align"], PP_ALIGN.LEFT)
            morceau = paragraphe.add_run()
            morceau.text = t["texte"]
            police = morceau.font
            police.name = polices.get(t["police"], "Georgia")
            police.size = Pt(t["taille"])
            police.bold, police.italic = "B" in t["style"], "I" in t["style"]
            police.color.rgb = RGBColor.from_string(t["couleur"].lstrip("#").upper())
            if t.get("angle"):
                boite.rotation = -t["angle"]
    fichier = sortie / nom_fichier
    presentation.save(str(fichier))
    return fichier


def exporter_imprimeur(base, dossier, cle, amb, sujet, periode, args, livre, couverture, rapport_lignes):
    """Dossier complet à remettre à l'imprimeur : PDF, photos numérotées dans l'ordre du livre (originales et
    recadrées), instructions Excel et plan de montage. Les originaux du disque ne sont que lus."""
    import xlsxwriter
    from PIL import ImageCms

    sortie = dossier / f"imprimeur_{cle}"
    for sous in ("photos_originales", "photos_recadrees"):
        if (sortie / sous).exists():
            shutil.rmtree(sortie / sous)  # dossiers produits par l'outil, dans --sortie
        (sortie / sous).mkdir(parents=True)
    l_fini, h_fini = FORMATS[args.format]
    srgb = ImageCms.createProfile("sRGB")

    elements = [dict(p, ordre=0, rang=1) for p in couverture.placements[:1]]
    rang_page = Counter()
    for numero, p in enumerate(ordre_de_lecture(livre.placements), 1):
        rang_page[p["page"]] += 1
        elements.append(dict(p, ordre=numero, rang=rang_page[p["page"]]))
    largeur_page = max(len(str(livre.numero)), 2)
    lignes = []
    for e in elements:
        ligne = e["ligne"]
        date = f"{ligne['jour']:%Y-%m-%d}"
        if e["ordre"] == 0:
            nom = f"000_couverture_{date}.jpg"
            position = "couverture"
        else:
            nom = f"{e['ordre']:03d}_p{e['page']:0{largeur_page}d}-{e['rang']}_{date}.jpg"
            position = position_sur_page(e["case"], l_fini, h_fini)
        af.progression("Dossier de l'imprimeur", e["ordre"] + 1, len(elements))
        source = af.original(base, ligne["fichier"])
        originale = sortie / "photos_originales" / (nom if source.suffix.lower() in (".jpg", ".jpeg")
                                                    else nom[:-4] + source.suffix.lower())
        if source.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
            shutil.copy2(source, originale)  # copie à l'identique : l'original n'est que lu
        else:  # HEIC, WEBP... : JPEG haute qualité, lisible par tous les imprimeurs
            originale = originale.with_suffix(".jpg")
            with Image.open(source) as im:
                ImageOps.exif_transpose(im).convert("RGB").save(originale, quality=97, subsampling=0,
                                                                icc_profile=ImageCms.ImageCmsProfile(srgb).tobytes())
        # même cadrage que dans le livre, rectangle simple (sans coins arrondis ni cadre), 300 dpi au plus
        x, y, w, h = e["case"]
        v = livre.visages[ligne["fichier"]]
        largeur_px = e["fenetre"][2] * v["largeur"]
        echelle = min(1.0, (w / 25.4 * DPI_CIBLE) / largeur_px)
        cible = (max(1, round(largeur_px * echelle)), max(1, round(e["fenetre"][3] * v["hauteur"] * echelle)))
        preparer_image(source, e["fenetre"], cible, echelle, None, sortie / "photos_recadrees" / nom)
        lignes.append({"ordre": e["ordre"], "originale": originale.name, "recadree": nom,
                       "page": "couverture" if e["ordre"] == 0 else e["page"], "rang": e["rang"],
                       "position": position, "x": round(x, 1), "y": round(y, 1), "l": round(w, 1), "h": round(h, 1),
                       "angle": round(e["angle"], 1), "style": e["style"], "date": ligne["date"],
                       "titre": ligne["titre"], "lieu": ligne["lieu"], "dpi": e["dpi"],
                       "source": ligne["fichier"], "case": e["case"], "page_num": 0 if e["ordre"] == 0 else e["page"]})

    # ---------------------------------------------------------------- Excel d'instructions
    classeur = xlsxwriter.Workbook(str(sortie / "Instructions_imprimeur.xlsx"))
    gras = classeur.add_format({"bold": True})
    entete = classeur.add_format({"bold": True, "bg_color": "#E8E1D6", "border": 1, "text_wrap": True,
                                  "valign": "top"})
    alerte = classeur.add_format({"bg_color": "#F8D7D3"})
    resume = classeur.add_worksheet("Résumé")
    resume.set_column(0, 0, 34)
    resume.set_column(1, 1, 90)
    infos = [
        ("Livre", f"{sujet} - {periode}"),
        ("Ambiance", amb["nom"]),
        ("Format fini", f"{l_fini} x {h_fini} mm"),
        ("Fond perdu", f"{args.fond_perdu} mm de chaque côté (PDF : {l_fini + 2 * args.fond_perdu} x "
                       f"{h_fini + 2 * args.fond_perdu} mm)"),
        ("Pages intérieures", livre.numero),
        ("Photos dans l'intérieur", "=COUNTIF('Ordre des photos'!A:A,\">0\")"),
        ("Fichier à imprimer (intérieur)", f"Livre_{af.nettoyer(sujet)}_{cle}_interieur.pdf"),
        ("Fichier à imprimer (couverture)", f"Livre_{af.nettoyer(sujet)}_{cle}_couverture.pdf (face avant seule : "
                                            "dos et 4e de couverture à ajouter selon votre gabarit)"),
        ("Couleurs", "sRGB, profil intégré dans chaque image ; JPEG qualité 95 ; 300 dpi au maximum"),
        ("Dossier photos_originales", "Fichiers d'origine, renommés dans l'ordre d'apparition dans le livre"),
        ("Dossier photos_recadrees", "Même cadrage que dans le livre, en rectangle simple, 300 dpi au maximum"),
        ("Nom des fichiers", "ORDRE_pPAGE-RANG_DATE.jpg : ordre de lecture dans le livre, page, rang sur la page "
                             "(de haut en bas puis de gauche à droite), date de la photo"),
        ("Positions (mm)", "X et Y depuis le coin haut-gauche du format fini (valeurs négatives = dans le fond perdu)"),
    ]
    for i, (cle_info, valeur) in enumerate(infos):
        resume.write(i, 0, cle_info, gras)
        resume.write(i, 1, valeur)

    feuille = classeur.add_worksheet("Ordre des photos")
    colonnes = [("Ordre", 7), ("Fichier original fourni", 30), ("Fichier recadré fourni", 30), ("Page", 7),
                ("Rang sur la page", 8), ("Position", 16), ("X (mm)", 8), ("Y (mm)", 8), ("Largeur (mm)", 9),
                ("Hauteur (mm)", 9), ("Rotation (°, + = sens antihoraire)", 11), ("Style", 12), ("Date de la photo", 12),
                ("Souvenir", 30), ("Lieu", 30), ("Résolution imprimée (dpi)", 11), ("Original sur le disque", 60)]
    for j, (titre, largeur) in enumerate(colonnes):
        feuille.write(0, j, titre, entete)
        feuille.set_column(j, j, largeur)
    for i, r in enumerate(lignes, 1):
        valeurs = [r["ordre"], r["originale"], r["recadree"], r["page"], r["rang"], r["position"], r["x"], r["y"],
                   r["l"], r["h"], r["angle"], r["style"], r["date"], r["titre"], r["lieu"], r["dpi"], r["source"]]
        for j, valeur in enumerate(valeurs):
            feuille.write(i, j, valeur, alerte if j == 15 and r["dpi"] < DPI_ALERTE else None)
    feuille.write(len(lignes) + 1, 0, "Total", gras)
    feuille.write_formula(len(lignes) + 1, 1, f"=COUNTA(B2:B{len(lignes) + 1})")
    feuille.freeze_panes(1, 1)
    feuille.autofilter(0, 0, len(lignes), len(colonnes) - 1)

    pages = classeur.add_worksheet("Pages")
    for j, (titre, largeur) in enumerate((("Page", 10), ("Contenu", 50), ("Nombre de photos", 12))):
        pages.write(0, j, titre, entete)
        pages.set_column(j, j, largeur)
    pages.write(1, 0, "couverture")
    pages.write(1, 1, "Couverture (face avant)")
    pages.write_formula(1, 2, "=COUNTIF('Ordre des photos'!D:D,A2)")
    for i in range(1, livre.numero + 1):
        pages.write(i + 1, 0, i)
        pages.write(i + 1, 1, livre.descriptions.get(i, ""))
        pages.write_formula(i + 1, 2, f"=COUNTIF('Ordre des photos'!D:D,A{i + 2})")
    pages.freeze_panes(1, 0)
    classeur.close()

    # ---------------------------------------------------------------- plan de montage (chemin de fer)
    from fpdf import FPDF

    plan = FPDF("L", "mm", "A4")
    plan.set_auto_page_break(False)
    police, texte = af.police(plan)
    colonnes_plan, rangees_plan = 4, 2
    vignette = min((297 - 20 - (colonnes_plan - 1) * 8) / colonnes_plan / l_fini,
                   (210 - 30 - (rangees_plan - 1) * 16) / rangees_plan / h_fini)
    vl, vh = l_fini * vignette, h_fini * vignette
    par_page = defaultdict(list)
    for r in lignes:
        par_page[r["page_num"]].append(r)
    numeros = [0] + list(range(1, livre.numero + 1))
    for debut in range(0, len(numeros), colonnes_plan * rangees_plan):
        plan.add_page()
        plan.set_font(police, "B", 12)
        plan.set_xy(10, 8)
        plan.cell(277, 6, texte(f"Plan de montage - Livre de {sujet} ({amb['nom']}) - {l_fini} x {h_fini} mm - "
                                f"{livre.numero} pages intérieures + couverture"))
        for k, numero in enumerate(numeros[debut: debut + colonnes_plan * rangees_plan]):
            x0 = 10 + (k % colonnes_plan) * (vl + 8)
            y0 = 22 + (k // colonnes_plan) * (vh + 16)
            plan.set_fill_color(250, 247, 242)
            plan.set_draw_color(120, 120, 120)
            plan.rect(x0, y0, vl, vh, "DF")
            for r in par_page.get(numero, []):
                x, y, w, h = r["case"]
                rx, ry = x0 + max(x, 0) * vignette, y0 + max(y, 0) * vignette
                rw = min(w, l_fini - max(x, 0)) * vignette
                rh = min(h, h_fini - max(y, 0)) * vignette
                plan.set_fill_color(214, 205, 192)
                plan.set_draw_color(90, 80, 70)
                plan.rect(rx, ry, rw, rh, "DF")
                plan.set_font(police, "B", 9)
                plan.set_xy(rx, ry + rh / 2 - 2.5)
                plan.cell(rw, 5, f"{r['ordre']:03d}", align="C")
            plan.set_font(police, "B", 8)
            plan.set_xy(x0, y0 + vh + 1.5)
            titre = "Couverture" if numero == 0 else f"Page {numero}"
            plan.cell(vl, 4, texte(titre))
            plan.set_font(police, "", 7)
            plan.set_xy(x0, y0 + vh + 5.5)
            description = "Face avant" if numero == 0 else livre.descriptions.get(numero, "")
            plan.cell(vl, 4, texte(description[:48]))
    plan.output(str(sortie / "Plan_de_montage.pdf"))

    # ---------------------------------------------------------------- lisez-moi et rapport
    (sortie / "rapport_impression.txt").write_text("\n".join(rapport_lignes), encoding="utf-8")
    (sortie / "LISEZ-MOI_imprimeur.txt").write_text("\n".join([
        f"Livre photo de {sujet} ({periode}) - ambiance {amb['nom']}",
        "",
        "À IMPRIMER :",
        f"  Livre_{af.nettoyer(sujet)}_{cle}_interieur.pdf   {livre.numero} pages, {l_fini} x {h_fini} mm fini, "
        f"fond perdu {args.fond_perdu} mm",
        f"  Livre_{af.nettoyer(sujet)}_{cle}_couverture.pdf  face avant (dos et 4e de couverture à ajouter)",
        "",
        "POUR REFAIRE OU VÉRIFIER LA MISE EN PAGE :",
        "  photos_originales\\  fichiers d'origine, renommés dans l'ordre d'apparition",
        "  photos_recadrees\\   même cadrage que dans le livre (rectangle, 300 dpi au maximum)",
        "  Instructions_imprimeur.xlsx  page, rang, position, dimensions en mm et rotation de chaque photo",
        "  Plan_de_montage.pdf          schéma de chaque page avec le numéro des photos",
        "",
        "NOM DES FICHIERS : ORDRE_pPAGE-RANG_DATE.jpg",
        "  ex. 014_p07-2_2016-08-03.jpg = 14e photo du livre, page 7, 2e photo de la page (lecture de haut en bas",
        "  puis de gauche à droite), prise le 03/08/2016. 000_couverture_... = photo de couverture.",
    ]), encoding="utf-8")
    return sortie, len(lignes) - 1, [r for r in lignes if r["dpi"] < DPI_ALERTE]


# =========================================================================== composer

def cmd_composer(args):
    base = af.ouvrir_base(args.sortie)
    BDMixin.couleur_encadre = couleur_bd(args.couleur_bd)
    Livre.langue = args.langue
    Livre.symbole_fin = args.symbole_fin
    if args.mot_fin_fichier and args.mot_fin_fichier.exists():
        args.mot_fin = args.mot_fin_fichier.read_text(encoding="utf-8-sig").strip() or args.mot_fin
    if args.page_lettres:  # planche lettres-photos à la place de la page de titre (option)
        if not args.page_lettres.exists():
            sys.exit(f"Planche lettres introuvable : {args.page_lettres}")
        Livre.page_lettres, Livre.lettres_fin = args.page_lettres, args.lettres_fin
    dossier, souvenirs, lignes = lire_selection(args)
    sujet = dossier.name[len("livre_"):]
    naissance = dt.datetime.strptime(args.naissance, "%d/%m/%Y").date() if args.naissance else None

    # taille d'origine et visages de chaque photo, pour le recadrage
    visages = {}
    for l in lignes:
        p = base.execute("SELECT id, largeur_orig, hauteur_orig, nettete FROM photos WHERE chemin = ?",
                         (l["fichier"],)).fetchone()
        if p is None:
            sys.exit(f"Photo inconnue de la base : {l['fichier']} (relancez album_famille.py analyser).")
        largeur, hauteur = p["largeur_orig"], p["hauteur_orig"]
        if not largeur:
            with Image.open(af.original(base, l["fichier"])) as im:
                largeur, hauteur = ImageOps.exif_transpose(im).size
        boites = [(v["x"], v["y"], v["l"], v["h"]) for v in
                  base.execute("SELECT x, y, l, h FROM visages WHERE photo_id = ?", (p["id"],))]
        visages[l["fichier"]] = {"largeur": largeur, "hauteur": hauteur, "ratio": largeur / hauteur, "visages": boites,
                                 "nettete": p["nettete"]}

    contexte = {"base": base, "dossier": dossier, "souvenirs": souvenirs, "lignes": lignes, "sujet": sujet,
                "naissance": naissance, "visages": visages, "periode": periode_de(souvenirs),
                "maison": {c for c in (args.pays_maison or "").upper().split(",") if c} or {
                    Counter(code_pays(l["lieu"]) for l in lignes if l["lieu"]).most_common(1)[0][0]
                    if any(l["lieu"] for l in lignes) else ""}}
    if args.ambiance == "toutes" or args.apercus:  # aperçus légers pour choisir, sans fichiers imprimeur
        choisies = [c.strip() for c in (args.apercus or "").split(",") if c.strip()] or list(AMBIANCES)
        inconnues = [c for c in choisies if c not in AMBIANCES]
        if inconnues:
            sys.exit(f"Ambiance(s) inconnue(s) : {', '.join(inconnues)}. Possibles : {', '.join(AMBIANCES)}")
        print(f"Aperçus de {len(choisies)} ambiance(s) : {', '.join(choisies)} (100 dpi, pour choisir à l'écran)...")
        for rang, cle in enumerate(choisies, 1):
            args.etiquette_progression = f"Aperçu {rang}/{len(choisies)} ({cle})"
            composer_ambiance(args, contexte, cle, apercu=True)
        print(f"Choisissez une ambiance (AMBIANCE = {', '.join(AMBIANCES)}), puis lancez la version finale.")
        return
    composer_ambiance(args, contexte, args.ambiance, apercu=False)


def rendre_pages(livre, pages, sujet, periode, args):
    """Dessine toutes les pages du plan dans le livre (PDF), page après page."""
    precedent = None
    etiquette = getattr(args, "etiquette_progression", None) or "Mise en page du livre"
    for numero_page, page in enumerate(pages, 1):
        af.progression(etiquette, numero_page, len(pages))
        avant = livre.numero
        reference = [precedent]
        dessiner_page(livre, page, pages, sujet, periode, args, reference)
        precedent = reference[0]
        pied = getattr(args, "pied_de_page", None)
        if pied and page["modele"] not in ("titre", "fin") and livre.numero > avant:
            unique = page["modele"] in ("pleine", "heros", "respiration", "pano") and not page.get("insets") or len(
                page.get("photos") or []) == 1
            if getattr(args, "pied_pages", "toutes") == "toutes" or unique:
                livre.pied_de_page(max(avant + 1, 2), livre.numero, pied,
                                   sur_photo=page["modele"] in ("pleine", "heros", "pano"))


def dessiner_page(livre, page, pages, sujet, periode, args, precedent_ref):
    """Dessine une page du plan (ou une planche entière pour les panoramiques)."""
    precedent = precedent_ref[0]
    if True:
        if page["modele"] == "titre":
            livre.page_titre(sujet, periode, args.dedicace)
        elif page["modele"] == "chapitre":
            livre.page_chapitre(page)
        elif page["modele"] == "pleine":
            livre.page_pleine(page)
        elif page["modele"] == "photos":
            precedent = livre.page_photos(page, precedent)
        elif page["modele"] == "chapitre_p":
            livre.page_chapitre_planche(page)
        elif page["modele"] == "heros":
            livre.page_heros(page)
        elif page["modele"] == "pano":
            livre.page_pano(page)  # dessine les deux pages de la planche (« pano_suite » ne fait rien)
        elif page["modele"] == "ecrin":
            livre.page_ecrin(page)
        elif page["modele"] == "mosaique":
            precedent = livre.page_mosaique(page, precedent)
        elif page["modele"] == "respiration":
            livre.page_respiration(page)
        elif page["modele"] == "ornement":
            livre.page_ornement(page)
        elif page["modele"] == "fin":
            if livre.page_lettres and livre.lettres_fin:
                livre.page_planche_lettres("Planche lettres-photos (avant la dernière page)")
            while (livre.numero + 1) % args.multiple:  # l'imprimeur veut un nombre de pages multiple de N
                livre.page_notes(sujet)
            livre.page_fin(sujet, periode, args.mot_fin)
    precedent_ref[0] = precedent


def composer_ambiance(args, c, cle, apercu):
    amb = AMBIANCES[cle]
    base, dossier, lignes, sujet, visages, periode = (c["base"], c["dossier"], c["lignes"], c["sujet"], c["visages"],
                                                     c["periode"])
    organisation = args.organisation or amb["organisation"]
    largeur_page = FORMATS[args.format][0] + 2 * args.fond_perdu
    ratio_page = largeur_page / (FORMATS[args.format][1] + 2 * args.fond_perdu)

    def dpi_pleine_page(ligne):
        v = visages[ligne["fichier"]]
        return fenetre(v, ratio_page)[2] * v["largeur"] / (largeur_page / 25.4)

    chapitres = construire_chapitres(c["souvenirs"], organisation, c["naissance"], sujet, c["maison"], amb["palette"])

    def dpi_panoramique(ligne):
        v = visages[ligne["fichier"]]
        largeur = 2 * FORMATS[args.format][0] + 2 * args.fond_perdu
        return fenetre(v, largeur / (FORMATS[args.format][1] + 2 * args.fond_perdu))[2] * v["largeur"] / (largeur / 25.4)

    pleine_ok = lambda l: dpi_pleine_page(l) >= DPI_ALERTE  # sinon trop agrandie : elle retourne en montage
    essais = []
    if amb.get("planches"):
        pano_ok = lambda l: args.reliure == "layflat" and dpi_panoramique(l) >= DPI_ALERTE
        niveaux = [{"par_page": cap} for cap in amb.get("caps", (4, 5, 6))]
        for densite, niveau in enumerate(niveaux if args.pages else niveaux[:1], 1):
            pages = planifier_planches(chapitres, niveau["par_page"], pleine_ok, pano_ok, organisation,
                                       amb.get("regle"))
            essais.append((nombre_de_pages(pages, args.multiple), densite, niveau, pages))
    else:
        niveaux = [n for n in NIVEAUX if n["par_page"] <= amb["max_par_page"]]  # jamais de page surchargée
        for densite, niveau in enumerate(niveaux if args.pages else niveaux[:1], 1):
            pages = planifier(chapitres, niveau, pleine_ok, c["naissance"], organisation)
            essais.append((nombre_de_pages(pages, args.multiple), densite, niveau, pages))
    tiennent = [e for e in essais if e[0] <= (args.pages or 10 ** 6)]
    # le plus aéré qui tient (le plus de pages sans dépasser), sinon le plus serré possible
    total, densite, niveau, pages = (max(tiennent, key=lambda e: (e[0], -e[1])) if tiennent
                                     else min(essais, key=lambda e: (e[0], e[1])))
    print(f"[{amb['nom']}] organisation {organisation} : {total} pages "
          f"(densité {densite}/{len(niveaux)}, jusqu'à {niveau['par_page']} photos par page)")
    alerte_pages = ""
    if args.pages and total > args.pages:
        surplus = (total - args.pages) * niveau["par_page"]
        alerte_pages = (f"ATTENTION : {total} pages au minimum sans surcharger les pages, pour {args.pages} demandées. "
                        f"Retirez environ {surplus} photos (garder = 0) dans selection_livre.csv, ou acceptez {total} pages.")
        print("  " + alerte_pages)

    couverture_ligne = next((l for l in lignes if l["vedette"] == "couverture"),
                            max(lignes, key=lambda l: float(l["score"] or 0)))
    livre = Livre(base, args.sortie, dossier, args.format, args.fond_perdu, visages, cle, apercu)
    if apercu:  # l'aperçu montre la couverture en tête, pour juger l'ensemble
        livre.page_couverture(couverture_ligne, sujet, periode)
        livre.numero = 0
    rendre_pages(livre, pages, sujet, periode, args)
    nom = af.nettoyer(sujet)
    if livre.coupees_origine:
        print(f"  {len(livre.coupees_origine)} photo(s) avec un visage déjà coupé sur l'original (étiquette rouge "
              "dans l'aperçu + liste en dernière page) : à remplacer si possible")
    if livre.controle:
        print(f"  Qualité : {len(livre.controle)} photo(s) réduite(s) pour rester nette(s) "
              + ("(étiquette orange + liste en dernière page de l'aperçu)" if apercu else "(voir rapport_impression.txt)"))
    if apercu:
        livre.page_controle()
        fichier = dossier / f"Apercu_{nom}_{cle}.pdf"
        livre.pdf.output(str(fichier))
        print(f"  {fichier}  ({livre.numero} pages + couverture)")
        return

    archiver_anciennes_sorties(dossier)
    sortie = dossier / f"imprimeur_{cle}"
    sortie.mkdir(exist_ok=True)
    interieur = sortie / f"Livre_{nom}_{cle}_interieur.pdf"
    livre.pdf.output(str(interieur))
    # couverture (page avant seule : l'imprimeur ajoute dos et 4e de couverture selon son gabarit)
    couverture = Livre(base, args.sortie, dossier, args.format, args.fond_perdu, visages, cle)
    couverture.page_couverture(couverture_ligne, sujet, periode)
    dpi_couverture = round(dpi_pleine_page(couverture_ligne))
    fichier_couverture = sortie / f"Livre_{nom}_{cle}_couverture.pdf"
    couverture.pdf.output(str(fichier_couverture))

    l, h = FORMATS[args.format]
    faibles = [p for p in livre.placements if p["dpi"] < DPI_ALERTE]
    rapport = [
        f"Livre de {sujet} - {periode} - ambiance {amb['nom']}",
        f"Format fini : {l} x {h} mm ; fond perdu : {args.fond_perdu} mm de chaque côté "
        f"(PDF : {l + 2 * args.fond_perdu} x {h + 2 * args.fond_perdu} mm)",
        f"Pages intérieures : {livre.numero} (multiple de {args.multiple}) ; photos : {len(livre.placements)} ; "
        f"couverture : {Path(couverture_ligne['fichier']).name} ({dpi_couverture} dpi"
        + (" : TROP FAIBLE, choisissez une autre photo « couverture » dans selection_livre.csv)"
           if dpi_couverture < DPI_ALERTE else ")"),
        f"Organisation : {organisation} ; densité {densite}/{len(niveaux)} (jusqu'à {niveau['par_page']} photos "
        "par page)" + (f" ; objectif : {args.pages} pages" if args.pages else ""),
        f"Images converties en sRGB (profil intégré ; sauf profils illisibles, listés plus bas), JPEG qualité 95, {DPI_CIBLE} dpi au maximum, accentuation "
        "légère après réduction ; textes et illustrations vectoriels.",
    ] + ([alerte_pages] if alerte_pages else []) + [
        "", f"Photos sous {DPI_ALERTE} dpi à l'impression (risque de flou) : {len(faibles)}",
    ] + [f"  page {p['page']} : {p['ligne']['fichier']} ({p['dpi']} dpi)" for p in faibles] + [
        "", f"Profils couleur non convertibles en sRGB (gardés tels quels, couleurs à vérifier sur épreuve) : "
        f"{len(CONVERSIONS_RATEES)}",
    ] + [f"  {c}" for c in sorted(set(CONVERSIONS_RATEES))] + [
        "", f"Photos réduites automatiquement pour cause de qualité : {len(livre.controle)}",
    ] + [f"  page {c['page']} : {c['fichier']} - {', '.join(c['motifs'])} - affichée à {c['taille']} %"
         for c in livre.controle] + [
        "", "À dire à l'imprimeur : couverture = page avant seule, il doit ajouter le dos (selon le nombre de pages "
        "et le papier) et la 4e de couverture selon son gabarit.",
    ]
    print("  Préparation du dossier pour l'imprimeur (photos numérotées, instructions, plan de montage)...")
    sortie, nb, faibles = exporter_imprimeur(base, dossier, cle, amb, sujet, periode, args, livre, couverture, rapport)
    if livre.entieres:
        print(f"  {livre.entieres} photo(s) montrée(s) entière(s) dans leur case pour ne couper aucun visage")
    if getattr(args, "pptx", False):
        print("  Version PowerPoint modifiable (décor + photos + textes)...")
        decor = Livre(base, args.sortie, dossier, args.format, args.fond_perdu, visages, cle)
        decor.decor_seul = True
        rendre_pages(decor, pages, sujet, periode, args)
        fichier_pptx = exporter_powerpoint(base, dossier, sortie, f"Livre_{nom}_{cle}_modifiable.pptx", livre, decor)
        print(f"    {fichier_pptx.name}")
    print(f"  {sortie}")
    print(f"    {interieur.name}  ({livre.numero} pages)  +  {fichier_couverture.name}")
    print(f"    photos_originales + photos_recadrees : {nb} photos + couverture, numérotées dans l'ordre du livre")
    print("    Instructions_imprimeur.xlsx, Plan_de_montage.pdf, LISEZ-MOI_imprimeur.txt, rapport_impression.txt")
    print(f"    {len(faibles)} photo(s) sous {DPI_ALERTE} dpi (en rouge dans l'Excel)")


# =========================================================================== ligne de commande

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sortie", type=Path, default=Path("albums_sortie"),
                        help="dossier de travail utilisé avec album_famille.py (défaut : albums_sortie)")
    sous = parser.add_subparsers(dest="commande", required=True)

    p = sous.add_parser("preparer", help="trouver et choisir les photos de la personne")
    p.add_argument("--personne", required=True, help="vedette du livre (nom de son dossier de référence)")
    p.add_argument("--avec", help="proches à mettre en avant, séparés par des virgules (ex. Hugo)")
    p.add_argument("--famille", required=True, help="dossier contenant un sous-dossier de photos par personne")
    p.add_argument("--naissance", help="date de naissance JJ/MM/AAAA : âges, anniversaires, naissance")
    p.add_argument("--pays-maison", help="pays « chez soi », ex. FR,PH (défaut : le plus fréquent) ; "
                                         "ailleurs = voyage")
    p.add_argument("--max", type=int, default=150, help="nombre maximum de photos (défaut 150)")
    p.add_argument("--seuil", type=float, default=af.SEUIL_VISAGE, help="exigence de ressemblance des visages")
    p.add_argument("--ecraser", action="store_true", help="refaire selection_livre.csv même s'il existe")
    p.set_defaults(fonction=cmd_preparer)

    p = sous.add_parser("proposer", help="proposer des améliorations à partir de la sélection déjà faite")
    p.add_argument("--personne", required=True, help="vedette du livre")
    p.add_argument("--famille", help="dossier des photos de référence (pour reconnaître les proches de --avec)")
    p.add_argument("--avec", help="proches à mettre en avant, séparés par des virgules")
    p.add_argument("--seuil", type=float, default=af.SEUIL_VISAGE, help="exigence de ressemblance des visages")
    p.add_argument("--recent", type=int, default=5, help="nombre d'années récentes à favoriser (défaut 5)")
    p.add_argument("--max-remplacements", type=int, default=40, help="nombre maximum de remplacements proposés")
    p.add_argument("--garder-total", action="store_true", help="ajouter sans retirer (le total augmente)")
    p.set_defaults(fonction=cmd_proposer)

    p = sous.add_parser("appliquer", help="appliquer les propositions acceptées à selection_livre.csv")
    p.add_argument("--personne", required=True, help="vedette du livre")
    p.set_defaults(fonction=cmd_appliquer)

    p = sous.add_parser("composer", help="mettre en page le livre et copier les photos retenues")
    p.add_argument("--personne", required=True, help="vedette du livre")
    p.add_argument("--naissance", help="date de naissance JJ/MM/AAAA (âge sur les pages de chapitre)")
    p.add_argument("--format", choices=sorted(FORMATS), default="carre30", help="format fini (défaut carre30 = 30x30 cm)")
    p.add_argument("--fond-perdu", type=float, default=3, help="fond perdu en mm (défaut 3 ; 0 si l'imprimeur n'en veut pas)")
    p.add_argument("--multiple", type=int, default=2, help="nombre de pages multiple de (défaut 2 ; 4 pour certains)")
    p.add_argument("--dedicace", help="texte de la page de titre")
    p.add_argument("--mot-fin", help="texte de la dernière page (défaut : « À suivre… »)")
    p.add_argument("--max", type=int, default=150, help="nombre maximum de photos (défaut 150)")
    p.add_argument("--pages", type=int, help="nombre de pages visé : la mise en page se densifie pour y tenir")
    p.add_argument("--organisation", choices=["chrono", "chrono-lieux", "themes", "lieux"],
                   help="chapitres par année, par thème (anniversaires, voyages, fêtes...) ou par lieu "
                        "(défaut : celle de l'ambiance)")
    p.add_argument("--ambiance", choices=list(AMBIANCES) + ["toutes"], default="toutes",
                   help="elegant, tendre, carnet, prestige ou magazine ; toutes (défaut) = aperçus légers pour choisir")
    p.add_argument("--pptx", action="store_true",
                   help="ajoute une version PowerPoint modifiable (photos déplaçables et recadrables)")
    p.add_argument("--reliure", choices=["classique", "layflat"], default="classique",
                   help="layflat = reliure à plat : autorise les photos panoramiques sur toute la double page")
    p.add_argument("--pays-maison", help="pays « chez soi », ex. FR,PH (organisation par lieux)")
    p.add_argument("--page-lettres", type=Path, help="image de la planche lettres-photos (planche_lettres.py "
                   "--page-livre) : remplace la page de titre")
    p.add_argument("--apercus", help="aperçus de ces ambiances seulement, séparées par des virgules "
                   "(ex. bd,bd-photo) ; les autres aperçus déjà faits restent tels quels")
    p.add_argument("--langue", choices=["fr", "en"], default="fr",
                   help="langue des textes du livre : fr (défaut) ou en (titres, dates, âges, pays, bulles traduits)")
    p.add_argument("--pied-de-page", help="texte en pied de page (toutes les pages après la première, ou seulement "
                   "les pages à photo unique avec --pied-pages photos-uniques)")
    p.add_argument("--pied-pages", choices=["toutes", "photos-uniques"], default="toutes",
                   help="pages qui reçoivent le pied de page")
    p.add_argument("--mot-fin-fichier", type=Path, help="texte de la dernière page lu dans ce fichier (plusieurs "
                   "lignes et paragraphes possibles)")
    p.add_argument("--symbole-fin", choices=["etoiles", "coeur", "coeurs", "fleur", "ornement", "colombe", "aucun"],
                   default="etoiles", help="petit motif au-dessus du texte de fin")
    p.add_argument("--couleur-bd", default="jaune", help="couleur des encadrés de légende en BD : jaune, bleu, "
                   "bleu-fonce, vert, vert-fonce, rose, orange, rouge, violet, turquoise, blanc, creme, gris... ou #RRGGBB")
    p.add_argument("--lettres-fin", action="store_true", help="remet la planche lettres avant la dernière page")
    p.set_defaults(fonction=cmd_composer)
    args = parser.parse_args()
    args.fonction(args)


if __name__ == "__main__":
    main()
