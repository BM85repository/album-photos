#!/usr/bin/env python3
"""choisir_photos.py - choisir les photos du livre directement sur les images, dans le navigateur.

Un petit serveur local (sur ce PC uniquement, rien ne part sur Internet) affiche toutes les photos
de la personne, souvenir par souvenir. Un clic garde ou retire une photo : selection_livre.csv est
enregistré aussitôt (une copie de sauvegarde est faite au démarrage). Les photos originales ne sont
que lues.

  python choisir_photos.py --sortie C:\\AlbumsFamille --personne Laura [--max 150]
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import secrets
import shutil
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageOps

try:
    import pillow_heif  # photos iPhone (.heic)

    pillow_heif.register_heif_opener()
except ImportError:
    pass

import numpy as np

import album_famille as af
import livre_photo as lp



class ServeurLocal(ThreadingHTTPServer):
    """Serveur de l'écran : un port qui n'est jamais partagé avec un autre écran encore ouvert (sous Windows,
    « allow_reuse_address » laisserait deux serveurs écouter le même port et les requêtes se perdre)."""
    allow_reuse_address = False
    daemon_threads = True

class Selection:
    """selection_livre.csv en mémoire, réécrit à chaque changement (protégé par un verrou)."""

    def __init__(self, fichier):
        self.fichier = fichier
        self.verrou = threading.Lock()
        with open(fichier, newline="", encoding="utf-8-sig") as f:
            lecteur = csv.DictReader(f, delimiter=";")
            self.colonnes = list(lecteur.fieldnames)
            self.lignes = list(lecteur)
        self.par_fichier = {l["fichier"]: l for l in self.lignes}

    def modifier(self, fichier, garder=None, vedette=None, remarque=None):
        with self.verrou:
            ligne = self.par_fichier[fichier]
            if remarque is not None and "remarque" in self.colonnes:
                ligne["remarque"] = remarque
            if garder is not None:
                ligne["garder"] = "1" if garder else "0"
            if vedette is not None:
                if vedette == "couverture":  # une seule couverture
                    for l in self.lignes:
                        if l.get("vedette", "").strip().lower() == "couverture":
                            l["vedette"] = ""
                    ligne["garder"] = "1"
                ligne["vedette"] = vedette
            temporaire = self.fichier.with_suffix(".tmp")
            with open(temporaire, "w", newline="", encoding="utf-8-sig") as f:
                ecrivain = csv.DictWriter(f, fieldnames=self.colonnes, delimiter=";")
                ecrivain.writeheader()
                ecrivain.writerows(self.lignes)
            temporaire.replace(self.fichier)  # écriture atomique : jamais de fichier à moitié écrit
            return sum(gardee(l) for l in self.lignes)


class Lettres:
    """Photos de la planche lettres-photos, dans leur propre fichier (lettres_photos.csv) : choisir les photos
    des lettres ne change jamais la sélection du livre (selection_livre.csv)."""

    def __init__(self, dossier, selection):
        self.fichier = dossier / "lettres_photos.csv"
        self.verrou = threading.Lock()
        self.dates = {l["fichier"]: l["date"] for l in selection.lignes}
        if self.fichier.exists():
            with open(self.fichier, newline="", encoding="utf-8-sig") as f:
                self.choisies = [l["fichier"] for l in csv.DictReader(f, delimiter=";") if l.get("fichier")]
        else:  # reprise des photos marquées avec l'ancienne version (colonne « lettres »)
            self.choisies = [l["fichier"] for l in selection.lignes
                             if (l.get("lettres") or "").strip() in ("1", "oui", "x")]

    def basculer(self, fichier, choisie):
        with self.verrou:
            if choisie and fichier not in self.choisies:
                self.choisies.append(fichier)
            elif not choisie and fichier in self.choisies:
                self.choisies.remove(fichier)
            temporaire = self.fichier.with_suffix(".tmp")
            with open(temporaire, "w", newline="", encoding="utf-8-sig") as f:
                ecrivain = csv.writer(f, delimiter=";")
                ecrivain.writerow(["fichier", "date"])
                ecrivain.writerows([c, self.dates.get(c, "")] for c in self.choisies)
            temporaire.replace(self.fichier)
            return len(self.choisies)


def gardee(ligne):
    return ligne["garder"].strip().lower() in ("1", "oui", "x")


def lire_propositions(dossier):
    """Suggestions de 3b_proposer_ameliorations (si elles existent), pour les afficher en badge."""
    fichier = dossier / "propositions.csv"
    badges = {}
    if fichier.exists():
        for p in af.lire_csv(fichier):
            if p["photo_proposee"]:
                badges[p["photo_proposee"]] = {"type": "suggeree", "raison": p["raison"]}
            if p["photo_actuelle"]:
                badges[p["photo_actuelle"]] = {"type": "a_retirer", "raison": p["raison"]}
    return badges


def aides_reduction(base, selection, maximum):
    """Mode « réduire » : signale, parmi les photos gardées, les meilleures candidates au retrait."""
    infos = {p["chemin"]: dict(p) for p in base.execute(
        "SELECT chemin, largeur_orig, hauteur_orig, nettete, dhash FROM photos")}
    gardees = [l for l in selection.lignes if gardee(l)]
    badges = {}
    par_souvenir = {}
    for l in gardees:
        par_souvenir.setdefault(l["souvenir"], []).append(l)
    score = lambda l: float(l.get("score") or 0)
    for groupe in par_souvenir.values():
        groupe.sort(key=score, reverse=True)
        # presque identique à une photo gardée plus belle du même souvenir : chaque photo est comparée d'un coup
        # (calcul vectoriel) à toutes les précédentes, rapide même pour un souvenir de milliers de photos
        empreintes = np.zeros(len(groupe), dtype=np.uint64)
        connues = np.zeros(len(groupe), dtype=bool)
        for i, l in enumerate(groupe):
            h = af.bits((infos.get(l["fichier"]) or {}).get("dhash"))
            if h is None:
                continue
            if i and connues[:i].any():
                proches = np.flatnonzero(connues[:i] & (af.bits_differents(empreintes[:i], h) <= 12))
                if proches.size:
                    badges[l["fichier"]] = {"type": "a_retirer", "raison": "presque identique à "
                                            + Path(groupe[proches[0]]["fichier"]).name}
            empreintes[i], connues[i] = h, True
        for l in groupe[6:]:  # souvenir très chargé : les moins fortes au-delà de 6
            badges.setdefault(l["fichier"], {"type": "a_retirer", "raison": f"souvenir chargé ({len(groupe)} photos)"})
    for l in gardees:
        p = infos.get(l["fichier"]) or {}
        cote = min(p.get("largeur_orig") or 9999, p.get("hauteur_orig") or 9999)
        if cote < 1200:
            badges.setdefault(l["fichier"], {"type": "a_retirer", "raison": f"faible définition ({cote} px)"})
        elif p.get("nettete") is not None and p["nettete"] < lp.SEUIL_PEU_NET:
            badges.setdefault(l["fichier"], {"type": "a_retirer", "raison": "peu nette"})
    return badges


def vignette(racine, cache, relatif, cote):
    """Vignette en cache ; le JPEG est décodé directement à petite taille (rapide sur un disque externe)."""
    etat = (racine / relatif).stat()  # taille et date : une autre photo au même chemin = une autre vignette
    cible = cache / f"{hashlib.md5(f'{relatif}|{cote}|{etat.st_size}|{etat.st_mtime}'.encode()).hexdigest()}.jpg"
    if not cible.exists():
        with Image.open(racine / relatif) as im:  # lecture seule de l'original
            im.draft("RGB", (cote * 2, cote * 2))
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((cote, cote))
            im.save(cible, quality=82)
    return cible.read_bytes()


PAGE_EN = [  # (français, anglais) : textes de l'écran de choix, remplacés quand l'application est en anglais
    ('<html lang="fr">', '<html lang="en">'), ("<title>Choisir les photos - __SUJET__", "<title>Choose the photos - __SUJET__"),
    ("Livre de __SUJET__ : choisir les photos", "__SUJET__'s book: choose the photos"),
    ('<span id="etat">chargement…', '<span id="etat">loading…'), (">Terminer</button>", ">Finish</button>"),
    (">Toutes</button>", ">All</button>"), (">Gardées</button>", ">Kept</button>"),
    (">Suggestions</button>", ">Suggestions</button>"), (">★ Spéciales</button>", ">★ Special</button>"),
    (">★ Pleine page</button>", ">★ Full page</button>"), (">Écartées</button>", ">Set aside</button>"),
    ('data-f="couverture">★ Couverture</button>', 'data-f="couverture">★ Cover</button>'),
    ('data-f="lettres">✉ Lettres</button>', 'data-f="lettres">✉ Letters</button>'),
    ('placeholder="Filtrer : lieu, titre, nom de fichier…"', 'placeholder="Filter: place, title, file name…"'),
    ("Clic = garder / retirer · 🔍 = voir en grand (← → pour naviguer, Espace = garder, C = couverture, N = la personne n'est pas sur la photo, "
     "L = photo pour la planche lettres, Échap = fermer)",
     "Click = keep / remove · 🔍 = enlarge (← → to browse, Space = keep, C = cover, N = the person is not in the photo, L = photo for the letters "
     "poster, Esc = close)"),
    ('<div class="vide">Chargement…</div>', '<div class="vide">Loading…</div>'),
    (">★ Couverture</button>", ">★ Cover</button>"), (">✉ Lettres</button>", ">✉ Letters</button>"),
    (">Fermer</button>", ">Close</button>"), ('PAS="✗ Pas __SUJET__"', 'PAS="✗ Not __SUJET__"'),
    (">✗ Pas __SUJET__</button>", ">✗ Not __SUJET__</button>"),
    ('MASTER_OK="◆ photo master de la mosaïque enregistrée"', 'MASTER_OK="◆ mosaic master photo saved"'),
    ('textContent="Gardées au départ"', 'textContent="Kept at the start"'),
    ('textContent="À retirer ?"', 'textContent="Remove?"'),
    ('textContent="Livre de "+D.sujet+" : réduire la sélection"', 'textContent=D.sujet+"\'s book: reduce the selection"'),
    ('textContent="Planche « "+MOT+" » : choisir "+LETTRES.length+" photos"',
     'textContent="Poster \u201c"+MOT+"\u201d: choose "+LETTRES.length+" photos"'),
    ('textContent="Choisies pour les lettres"', 'textContent="Chosen for the letters"'),
    ('textContent="Gardées pour le livre"', 'textContent="Kept for the book"'),
    ("Clic sur une photo = la choisir pour une lettre (ou l'enlever) · 🔍 = voir en grand · la sélection du livre "
     "n'est pas modifiée", "Click a photo = choose it for a letter (or remove it) · 🔍 = enlarge · the book selection "
     "is not changed"),
    ('d.title="Cliquer pour enlever cette photo"', 'd.title="Click to remove this photo"'),
    ('"Choisissez encore "+(LETTRES.length-n)+" photo(s). Elles sont placées par date : la plus ancienne sur la 1re '
     'lettre."', '"Choose "+(LETTRES.length-n)+" more photo(s). They are placed by date: the oldest on the first letter."'),
    ('"✓ Complet. Cliquez sur « Terminer », puis lancez 7_planche_lettres.bat."',
     '"✓ Complete. Click \u201cFinish\u201d, then \u201cCreate the letters poster\u201d."'),
    ('"Trop de photos : "+(n-LETTRES.length)+" en trop (les plus récentes ne seront pas utilisées)."',
     '"Too many photos: "+(n-LETTRES.length)+" too many (the most recent will not be used)."'),
    ('" photos pour les lettres"', '" photos for the letters"'),
    ('" · encore "+(n-D.max)+" à retirer"', '" · "+(n-D.max)+" more to remove"'),
    ("Aucune photo pour ce filtre.", "No photo for this filter."),
    ('"Toutes les années<small>"', '"All years<small>"'),
    ('esc(g[0].t||"Souvenir")', 'esc(g[0].t||"Memory")'),
    ('" photo(s)":" · "+n+" gardée(s) sur "+g.length', '" photo(s)":" · "+n+" kept out of "+g.length'),
    ('" photo(s) affichée(s)"', '" photo(s) shown"'),
    ('"suggérée":(REDUIRE?esc(p.b.raison):"à retirer ?")', '"suggested":(REDUIRE?esc(p.b.raison):"remove?")'),
    ("★ couverture</span>", "★ cover</span>"), ("✉ lettre '+lettreDe(p)", "✉ letter '+lettreDe(p)"),
    ('textContent="enregistrement…"', 'textContent="saving…"'), ('textContent="enregistré ✓"', 'textContent="saved ✓"'),
    ('"Retirer du livre":"Garder dans le livre"', '"Remove from the book":"Keep in the book"'),
    ('"Enlever des lettres":"Choisir pour une lettre"', '"Remove from the letters":"Choose for a letter"'),
    ('"✉ Retirer des lettres":"✉ Lettres ("', '"✉ Remove from the letters":"✉ Letters ("'),
    ("Sélection enregistrée. Vous pouvez fermer cet onglet.", "Selection saved. You can close this tab."),
]
RAISONS_EN = [("presque identique à", "almost identical to"), ("souvenir chargé", "crowded memory"),
              ("faible définition", "low resolution"), ("peu nette", "blurry")]


def creer_gestionnaire(selection, sujet, maximum, racine, cache, badges, arret, reduire=False, lettres=None, mot="",
                       langue="fr", fichier_base=None):
    page = (PAGE.replace("__SUJET__", sujet).replace("__REDUIRE__", "true" if reduire else "false")
            .replace("__MOT__", json.dumps(mot)))
    jeton = secrets.token_urlsafe(24)  # propre à cette session : une autre page web ne peut pas le deviner
    page = page.replace("__JETON__", jeton)
    if langue == "en":
        for fr, en in PAGE_EN:
            page = page.replace(fr.replace("__SUJET__", sujet), en.replace("__SUJET__", sujet))
        for b in badges.values():
            for fr, en in RAISONS_EN:
                b["raison"] = b["raison"].replace(fr, en)

    def remarque(ligne):  # pourquoi la photo avait été écartée (doublon, floue, petite)
        texte = (ligne.get("remarque") or "").strip()
        if langue == "en":
            for fr, en in (("doublon de", "duplicate of"), ("floue", "blurry"), ("petite", "small"), ("pas ", "not ")):
                texte = texte.replace(fr, en)
        return texte

    fichier_master = selection.fichier.parent / "mosaique_master.txt"
    master = [fichier_master.read_text(encoding="utf-8-sig").strip() if fichier_master.exists() else ""]

    class Gestionnaire(BaseHTTPRequestHandler):
        def log_message(self, *args):  # pas de journal à chaque vignette
            pass

        def envoyer(self, code, contenu, type_="application/json; charset=utf-8"):
            if isinstance(contenu, str):
                contenu = contenu.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", type_)
            self.send_header("Content-Length", str(len(contenu)))
            self.send_header("Cache-Control", "max-age=86400" if type_ == "image/jpeg" else "no-store")
            self.end_headers()
            self.wfile.write(contenu)

        def hote_local(self):
            """Seulement 127.0.0.1 / localhost (protège contre une page piégée qui se ferait passer pour l'écran)."""
            hote = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return hote in ("127.0.0.1", "localhost")

        def do_GET(self):
            if not self.hote_local():
                return self.envoyer(403, "{}")
            url = urlparse(self.path)
            if url.path == "/":
                return self.envoyer(200, page, "text/html; charset=utf-8")
            if url.path == "/api/donnees":
                photos = [{"f": l["fichier"], "d": l["date"], "h": l.get("heure", ""), "s": l["souvenir"],
                           "t": l["titre"], "ty": l.get("type", ""), "l": l["lieu"], "p": l.get("personnes", ""),
                           "sc": l.get("score", ""), "g": gardee(l), "v": l.get("vedette", "").strip().lower(),
                           "le": l["fichier"] in lettres.choisies,
                           "b": badges.get(l["fichier"]), "r": remarque(l)}
                          for l in selection.lignes]
                return self.envoyer(200, json.dumps({"sujet": sujet, "max": maximum, "photos": photos,
                                                     "master": master[0]}))
            if url.path in ("/vignette", "/grande"):
                relatif = parse_qs(url.query).get("f", [""])[0]
                if relatif not in selection.par_fichier:
                    return self.envoyer(404, "{}")
                try:
                    donnees = vignette(racine, cache, relatif, 300 if url.path == "/vignette" else 1400)
                except OSError:  # disque débranché ou fichier illisible
                    return self.envoyer(404, "{}")
                return self.envoyer(200, donnees, "image/jpeg")
            return self.envoyer(404, "{}")

        def do_POST(self):
            # toute modification exige le jeton de la page et une origine locale : une autre page ouverte dans le
            # navigateur ne peut ni changer la sélection ni arrêter l'écran
            origine = self.headers.get("Origin")
            if (not self.hote_local() or self.headers.get("X-Jeton") != jeton
                    or (origine and urlparse(origine).hostname not in ("127.0.0.1", "localhost"))):
                return self.envoyer(403, json.dumps({"erreur": "requête refusée"}))
            longueur = int(self.headers.get("Content-Length", 0))
            demande = json.loads(self.rfile.read(longueur) or b"{}")
            if self.path == "/api/lettres":
                if demande.get("f") not in selection.par_fichier:
                    return self.envoyer(404, "{}")
                try:
                    total = lettres.basculer(demande["f"], bool(demande.get("lettres")))
                except PermissionError:
                    return self.envoyer(409, json.dumps({"erreur": "lettres_photos.csv est ouvert dans Excel : "
                                                                   "fermez-le puis recommencez."}))
                return self.envoyer(200, json.dumps({"ok": True, "total": total}))
            if self.path == "/api/maj":
                if mot:  # écran des lettres : la sélection du livre n'est jamais modifiée
                    return self.envoyer(403, json.dumps({"erreur": "Écran des lettres : la sélection du livre "
                                                                   "n'est pas modifiable ici."}))
                try:
                    total = selection.modifier(demande["f"], demande.get("garder"), demande.get("vedette"))
                except PermissionError:
                    return self.envoyer(409, json.dumps({"erreur": "selection_livre.csv est ouvert dans Excel : "
                                                                   "fermez-le puis recommencez."}))
                return self.envoyer(200, json.dumps({"ok": True, "total": total}))
            if self.path == "/api/master":  # photo master de la mosaïque (fichier à part : la sélection ne change pas)
                if demande.get("f") not in selection.par_fichier:
                    return self.envoyer(404, "{}")
                fichier_master = selection.fichier.parent / "mosaique_master.txt"
                fichier_master.write_text(demande["f"] + "\n", encoding="utf-8")
                master[0] = demande["f"]
                return self.envoyer(200, json.dumps({"ok": True}))
            if self.path == "/api/absent":  # « la personne n'est pas sur cette photo » : retirée + reconnaissance corrigée
                if mot or demande.get("f") not in selection.par_fichier or fichier_base is None:
                    return self.envoyer(403, json.dumps({"erreur": "non disponible ici"}))
                try:
                    total = selection.modifier(demande["f"], False, remarque=f"pas {sujet}")
                except PermissionError:
                    return self.envoyer(409, json.dumps({"erreur": "selection_livre.csv est ouvert dans Excel : "
                                                                   "fermez-le puis recommencez."}))
                refuses = af.refuser_photo(fichier_base, demande["f"], sujet)
                return self.envoyer(200, json.dumps({"ok": True, "total": total, "visages": refuses}))
            if self.path == "/api/fin":
                self.envoyer(200, json.dumps({"ok": True}))
                threading.Thread(target=arret, daemon=True).start()
                return None
            return self.envoyer(404, "{}")

    return Gestionnaire


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sortie", type=Path, default=Path("albums_sortie"))
    parser.add_argument("--personne", required=True)
    parser.add_argument("--max", type=int, default=150)
    parser.add_argument("--reduire", action="store_true",
                        help="n'afficher que les photos gardées et signaler les meilleures candidates au retrait")
    parser.add_argument("--langue", choices=["fr", "en"], default="fr", help="langue de l'écran de choix")
    parser.add_argument("--lettres", metavar="MOT", default="",
                        help="choisir les photos de la planche lettres-photos (ne modifie pas la sélection du livre)")
    args = parser.parse_args()

    base = af.ouvrir_base(args.sortie)
    racine = Path(af.meta(base, "racine") or "")
    if not racine.exists():
        sys.exit(f"Disque de photos introuvable ({racine}) : branchez-le, puis relancez.")
    dossier = lp.dossier_livre(args.sortie, args.personne)
    fichier = dossier / "selection_livre.csv"
    if not fichier.exists():
        sys.exit("Lancez d'abord 3_preparer_selection.bat.")
    mot = " ".join(args.lettres.upper().split())
    if not mot:  # écran du livre : copie de sauvegarde de la sélection avant les clics
        shutil.copy2(fichier, dossier / f"selection_livre_avant_choix_{dt.datetime.now():%Y%m%d-%H%M}.csv")
    cache = args.sortie / "vignettes_choix"
    cache.mkdir(exist_ok=True)
    selection = Selection(fichier)
    lettres = Lettres(dossier, selection)
    serveur = None
    for port in range(8765, 8800):
        try:
            serveur = ServeurLocal(("127.0.0.1", port), BaseHTTPRequestHandler)
            break
        except OSError:
            continue
    if serveur is None:
        sys.exit("Impossible d'ouvrir le serveur local (ports 8765 à 8799 occupés).")
    badges = aides_reduction(base, selection, args.max) if args.reduire else lire_propositions(dossier)
    serveur.RequestHandlerClass = creer_gestionnaire(selection, dossier.name[len("livre_"):], args.max, racine,
                                                     cache, badges, serveur.shutdown, args.reduire, lettres, mot,
                                                     args.langue, args.sortie / "base.sqlite")
    if args.reduire:
        gardees = sum(gardee(l) for l in selection.lignes)
        print(f"Mode réduire : {gardees} photos gardées pour {args.max} au maximum"
              + (f" : {gardees - args.max} à retirer." if gardees > args.max else "."))
    adresse = f"http://127.0.0.1:{serveur.server_address[1]}/"
    print(f"Écran de sélection ouvert dans le navigateur : {adresse}")
    if mot:
        print(f"Planche « {mot} » : cliquez sur {len(mot.replace(' ', ''))} photos (une par lettre, placées par date).")
        print(f"Enregistré aussitôt dans {lettres.fichier.name} ; la sélection du livre n'est pas modifiée.")
    else:
        print("Chaque clic est enregistré aussitôt dans selection_livre.csv (sauvegarde faite au démarrage).")
    print("Pour finir : bouton « Terminer » dans la page (ou fermez cette fenêtre).", flush=True)
    webbrowser.open(adresse)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()  # libère le port tout de suite
    if mot:
        print(f"Photos des lettres enregistrées : {len(lettres.choisies)} (pour {len(mot.replace(' ', ''))} lettres).")
    else:
        print(f"Sélection enregistrée : {sum(gardee(l) for l in selection.lignes)} photos gardées.")


PAGE = r"""<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Choisir les photos - __SUJET__</title>
<style>
:root{--fond:#f6f3ee;--carte:#fff;--texte:#2f2b28;--doux:#8c847c;--vert:#2e9d4f;--orange:#e67e22;--or:#b8954f}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:var(--fond);color:var(--texte)}
header{position:sticky;top:0;z-index:5;background:#2f2b28;color:#fff;padding:10px 16px;display:flex;gap:16px;
align-items:center;flex-wrap:wrap}
header h1{font:600 18px Georgia,serif;margin:0}#total{font-weight:700;padding:3px 10px;border-radius:12px;background:var(--vert)}
#total.trop{background:#c0392b}#etat{font-size:12px;opacity:.8}header button{margin-left:auto}
button{font:inherit;border:0;border-radius:6px;padding:6px 12px;cursor:pointer;background:#e9e2d6;color:var(--texte)}
button.actif{background:var(--texte);color:#fff}
#annees{display:flex;gap:6px;flex-wrap:wrap;padding:10px 16px;background:#ece6dc;position:sticky;top:48px;z-index:4}
#annees button{font-size:13px}#annees small{display:block;font-size:10px;opacity:.75}
#outils{display:flex;gap:8px;padding:8px 16px;align-items:center;flex-wrap:wrap}
#outils input{padding:6px 10px;border:1px solid #ccc;border-radius:6px;min-width:220px}
main{padding:0 16px 40px}.souvenir{margin:18px 0}.souvenir h2{font:600 15px Georgia,serif;margin:0 0 2px}
.souvenir .info{font-size:12px;color:var(--doux);margin-bottom:6px}
.grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.carte{position:relative;background:var(--carte);border-radius:6px;overflow:hidden;cursor:pointer;
border:4px solid transparent;transition:transform .08s}
.carte:hover{transform:scale(1.02)}.carte img{width:100%;height:120px;object-fit:cover;display:block;background:#ddd}
.carte.g{border-color:var(--vert)}.carte:not(.g){opacity:.55}.carte.g::after{content:"✓";position:absolute;top:4px;left:6px;background:var(--vert);
color:#fff;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-weight:700}
.carte .loupe{position:absolute;top:4px;right:4px;background:rgba(0,0,0,.55);color:#fff;border-radius:4px;
padding:1px 6px;font-size:13px}.carte .legende{font-size:11px;padding:3px 5px;color:var(--doux);white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}.badge{position:absolute;left:4px;bottom:24px;font-size:10px;padding:1px 6px;
border-radius:8px;color:#fff;max-width:calc(100% - 8px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.badge.suggeree{background:var(--orange)}.badge.a_retirer{background:#7f8c8d}
.badge.couv{background:var(--or);bottom:auto;top:30px}
.carte .absent{position:absolute;right:4px;bottom:24px;background:rgba(192,57,43,.9);color:#fff;border-radius:4px;
padding:1px 6px;font-size:11px;display:none}.carte:hover .absent{display:block}body.ml .carte .absent{display:none!important}
.badge.lettres{background:#3A6EA5;bottom:auto;top:54px}
.badge.master{background:#6C3483;bottom:auto;top:78px}
.badge.ecartee{background:#7f8c8d;bottom:auto;top:4px;left:32px;max-width:calc(100% - 70px)}
body.ml .carte:not(.g){opacity:1}body.ml .carte.g{border-color:transparent}body.ml .carte.g::after{display:none}
body.ml .carte.le{border-color:#3A6EA5}.lettre{position:absolute;top:4px;left:4px;background:#3A6EA5;color:#fff;
font:900 26px/40px Arial Black,Arial,sans-serif;width:40px;height:40px;text-align:center;border-radius:6px}
#bandeau{display:none;position:sticky;top:52px;z-index:4;background:#fff;padding:8px 16px;gap:8px;align-items:center;
box-shadow:0 2px 6px rgba(0,0,0,.12);flex-wrap:wrap}body.ml #bandeau{display:flex}
.case{width:86px;height:104px;border:2px dashed #b9b2a9;border-radius:6px;position:relative;text-align:center;
font:900 22px Arial Black,Arial,sans-serif;color:#b9b2a9;overflow:hidden;cursor:pointer}
.case img{width:100%;height:76px;object-fit:cover;display:block}.case.pleine{border:2px solid #3A6EA5;color:#3A6EA5}
.case small{display:block;font:11px system-ui;color:var(--doux)}#bandeau .aide{font-size:13px;color:var(--doux);max-width:420px}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;z-index:10;color:#fff;align-items:center;
justify-content:center;flex-direction:column}#lb img{max-width:92vw;max-height:78vh}
#lb .barre{display:flex;gap:10px;margin-top:12px;align-items:center}#lb .txt{margin-top:8px;font-size:13px;opacity:.85}
#lb button.garder{background:var(--vert);color:#fff}#lb button.retirer{background:#c0392b;color:#fff}
.vide{padding:40px;text-align:center;color:var(--doux)}
</style>
<header><h1>Livre de __SUJET__ : choisir les photos</h1><span id="total">…</span><span id="etat">chargement…</span>
<button id="fin">Terminer</button></header>
<div id="bandeau"></div><div id="annees"></div>
<div id="outils"><button data-f="toutes" class="actif">Toutes</button><button data-f="gardees">Gardées</button>
<button data-f="suggestions">Suggestions</button>
<button data-f="speciales">★ Spéciales</button><button data-f="couverture">★ Couverture</button><button data-f="pleine">★ Pleine page</button>
<button data-f="lettres">✉ Lettres</button><button data-f="master">◆ Master</button><button data-f="ecartees">Écartées</button><input id="cherche" placeholder="Filtrer : lieu, titre, nom de fichier…">
<span style="font-size:12px;color:#8c847c">Clic = garder / retirer · 🔍 = voir en grand (← → pour naviguer, Espace = garder, C = couverture, N = la personne n'est pas sur la photo, L = photo pour la planche lettres, Échap = fermer)</span></div>
<main id="liste"><div class="vide">Chargement…</div></main>
<div id="lb"><img><div class="txt"></div><div class="barre"><button id="prec">←</button><button id="bascule"></button>
<button id="master">◆ Master</button><button id="absent">✗ Pas __SUJET__</button><button id="couv">★ Couverture</button><button id="let">✉ Lettres</button><button id="suiv">→</button><button id="ferme">Fermer</button></div></div>
<script>
const MASTER_OK="◆ photo master de la mosaïque enregistrée",PAS="✗ Pas __SUJET__",JETON="__JETON__",REDUIRE=__REDUIRE__,MOT=__MOT__,LETTRES=MOT.replace(/ /g,""),ML=LETTRES.length>0;
if(ML)document.body.classList.add("ml");
let D,annee=null,filtre=REDUIRE?"gardees":"toutes",texte="",visibles=[],courant=-1;
const $=s=>document.querySelector(s);
fetch("/api/donnees").then(r=>r.json()).then(d=>{D=d;D.photos.forEach(p=>p.an=p.d.slice(-4));
  if(REDUIRE){/* on n'affiche que les photos gardées au départ : une photo retirée reste visible (grisée) pour l'annuler */
    D.photos.forEach(p=>p.g0=p.g);document.querySelector('#outils button[data-f="gardees"]').textContent="Gardées au départ";
    document.querySelector('#outils button[data-f="suggestions"]').textContent="À retirer ?";
    document.querySelectorAll("#outils button").forEach(x=>x.classList.toggle("actif",x.dataset.f=="gardees"));
    document.querySelector("header h1").textContent="Livre de "+D.sujet+" : réduire la sélection"}
  if(ML){/* écran des lettres : un clic choisit la photo d'une lettre ; le livre n'est pas touché */
    document.querySelector("header h1").textContent="Planche « "+MOT+" » : choisir "+LETTRES.length+" photos";
    document.querySelector('#outils button[data-f="gardees"]').textContent="Choisies pour les lettres";
    document.querySelector('#outils button[data-f="suggestions"]').textContent="Gardées pour le livre";
    $("#couv").style.display="none";$("#let").style.display="none";
    ["couverture","pleine","master","speciales"].forEach(f=>{const b=document.querySelector('#outils button[data-f="'+f+'"]');if(b)b.style.display="none"});
    document.querySelector("#outils span").textContent="Clic sur une photo = la choisir pour une lettre (ou l'enlever) · 🔍 = voir en grand · la sélection du livre n'est pas modifiée"}
  const ans=[...new Set(D.photos.map(p=>p.an))].sort();annee=ans[0];barreAnnees();afficher();});
function cleDate(p){const d=p.d.split("/");return d[2]+d[1]+d[0]+(p.h||"")}
function choisies(){return D.photos.filter(p=>p.le).sort((a,b)=>cleDate(a)<cleDate(b)?-1:1)}
function lettreDe(p){const i=choisies().indexOf(p);return i>=0&&i<LETTRES.length?LETTRES[i]:"+"}
function bandeau(){if(!ML)return;const c=choisies(),b=$("#bandeau");b.innerHTML="";
  [...LETTRES].forEach((l,i)=>{const p=c[i],d=document.createElement("div");d.className="case"+(p?" pleine":"");
    d.innerHTML=p?'<img src="/vignette?f='+encodeURIComponent(p.f)+'"><small>'+l+" · "+p.d+"</small>":"<div style='line-height:100px'>"+l+"</div>";
    if(p){d.title="Cliquer pour enlever cette photo";d.onclick=()=>basculerLettre(p)}b.appendChild(d)});
  const a=document.createElement("div");a.className="aide";const n=c.length;
  a.textContent=n<LETTRES.length?"Choisissez encore "+(LETTRES.length-n)+" photo(s). Elles sont placées par date : la plus ancienne sur la 1re lettre."
    :n==LETTRES.length?"✓ Complet. Cliquez sur « Terminer », puis lancez 7_planche_lettres.bat.":"Trop de photos : "+(n-LETTRES.length)+" en trop (les plus récentes ne seront pas utilisées).";
  b.appendChild(a)}
function basculerLettre(p){const v=!p.le;fetch("/api/lettres",{method:"POST",headers:{"Content-Type":"application/json","X-Jeton":JETON},
  body:JSON.stringify({f:p.f,lettres:v})}).then(r=>r.json().then(j=>{if(!r.ok){alert(j.erreur);throw j}
  p.le=v;$("#etat").textContent="enregistré ✓";barreAnnees();if(courant>=0)ouvrir(courant);else afficher()}))}
function compte(){if(ML){const n=D.photos.filter(p=>p.le).length;const t=$("#total");
  t.textContent=n+" / "+LETTRES.length+" photos pour les lettres";t.classList.toggle("trop",n>LETTRES.length);bandeau();return}
  const n=D.photos.filter(p=>p.g).length;const t=$("#total");
  t.textContent=n+" / "+D.max+" photos"+(n>D.max?" · encore "+(n-D.max)+" à retirer":"");
  t.classList.toggle("trop",n>D.max);}
function compteFiltres(){/* nombre de photos de chaque rôle, sur les boutons de filtre */
  const n={couverture:D.photos.filter(p=>p.v=="couverture").length,pleine:D.photos.filter(p=>p.v=="1").length,
    lettres:D.photos.filter(p=>p.le).length,master:D.photos.filter(p=>D.master==p.f).length,
    ecartees:D.photos.filter(p=>p.r).length};
  n.speciales=D.photos.filter(p=>p.v=="couverture"||p.v=="1"||p.le||D.master==p.f).length;
  document.querySelectorAll("#outils button").forEach(b=>{if(n[b.dataset.f]===undefined)return;
    if(!b.dataset.t)b.dataset.t=b.textContent;b.textContent=b.dataset.t+" ("+n[b.dataset.f]+")"})}
function barreAnnees(){compteFiltres();const ans=[...new Set(D.photos.map(p=>p.an))].sort();$("#annees").innerHTML="";
  {const b=document.createElement("button");/* toutes les années d'un coup */
   b.innerHTML="Toutes les années<small>"+D.photos.filter(p=>ML?p.le:p.g).length+" / "+D.photos.length+"</small>";
   b.className=annee=="*"?"actif":"";b.onclick=()=>{annee="*";barreAnnees();afficher();scrollTo(0,0)};$("#annees").appendChild(b)}
  ans.forEach(a=>{const ps=D.photos.filter(p=>p.an==a);const b=document.createElement("button");
    b.innerHTML=a+"<small>"+ps.filter(p=>ML?p.le:p.g).length+" / "+ps.length+"</small>";b.className=a==annee?"actif":"";
    b.onclick=()=>{annee=a;barreAnnees();afficher();scrollTo(0,0)};$("#annees").appendChild(b)});compte();}
function correspond(p){if(ML){if(filtre=="gardees"&&!p.le)return false;if(filtre=="suggestions"&&!p.g)return false}
  else{if(filtre=="gardees"&&!(REDUIRE?p.g0:p.g))return false;if(filtre=="suggestions"&&!p.b)return false}
  /* photos à rôle particulier : couverture, pleine page, lettres, master de la mosaïque, ou écartées */
  if(filtre=="couverture"&&p.v!="couverture")return false;if(filtre=="pleine"&&p.v!="1")return false;
  if(filtre=="lettres"&&!p.le)return false;if(filtre=="master"&&D.master!=p.f)return false;
  if(filtre=="ecartees"&&!p.r)return false;
  if(filtre=="speciales"&&!(p.v=="couverture"||p.v=="1"||p.le||D.master==p.f))return false;
  if(texte){const t=(p.t+" "+p.l+" "+p.f+" "+p.p).toLowerCase();if(!t.includes(texte))return false}return true}
function afficher(){/* « Toutes » : l'année choisie ; un filtre ou une recherche : toutes les années */
  const liste=(filtre=="toutes"&&!texte&&annee!="*"?D.photos.filter(p=>p.an==annee):D.photos).filter(correspond);visibles=liste;
  const groupes={};liste.forEach(p=>{(groupes[p.s]=groupes[p.s]||[]).push(p)});const m=$("#liste");m.innerHTML="";
  if(!liste.length){m.innerHTML='<div class="vide">Aucune photo pour ce filtre.</div>';$("#etat").textContent="";return}
  Object.values(groupes).forEach(g=>{const s=document.createElement("section");s.className="souvenir";
    const n=g.filter(p=>p.g).length;s.innerHTML="<h2>"+esc(g[0].t||"Souvenir")+"</h2><div class='info'>"+g[0].d+
    (g[0].l?" · "+esc(g[0].l):"")+(ML?" · "+g.length+" photo(s)":" · "+n+" gardée(s) sur "+g.length)+"</div>";const gr=document.createElement("div");
    gr.className="grille";g.forEach(p=>gr.appendChild(carte(p)));s.appendChild(gr);m.appendChild(s)});
  $("#etat").textContent=liste.length+" photo(s) affichée(s)";}
function esc(t){return (t||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function carte(p){const c=document.createElement("div");c.className="carte"+(p.g?" g":"")+(p.le?" le":"");p.el=c;
  if(ML){c.innerHTML='<img loading="lazy" src="/vignette?f='+encodeURIComponent(p.f)+'" alt="">'+
    (p.le?'<span class="lettre">'+lettreDe(p)+"</span>":"")+'<span class="loupe">🔍</span><div class="legende">'+p.d+" "+(p.h||"")+"</div>";
    c.onclick=e=>{if(e.target.classList.contains("loupe"))ouvrir(visibles.indexOf(p));else basculerLettre(p)};return c}
  let b=p.b?'<span class="badge '+p.b.type+'" title="'+esc(p.b.raison)+'">'+(p.b.type=="suggeree"?"suggérée":(REDUIRE?esc(p.b.raison):"à retirer ?"))+"</span>":"";
  if(p.v=="couverture")b+='<span class="badge couv">★ couverture</span>';
  if(D.master==p.f)b+='<span class="badge master">◆ master</span>';
  if(p.r)b+='<span class="badge ecartee" title="'+esc(p.r)+'">'+esc(p.r)+'</span>';
  if(p.le)b+='<span class="badge lettres">✉ lettre '+lettreDe(p)+'</span>';
  c.innerHTML='<img loading="lazy" src="/vignette?f='+encodeURIComponent(p.f)+'" alt="">'+b+
    '<span class="loupe">🔍</span><span class="absent" title="'+esc(PAS)+'">'+esc(PAS)+'</span><div class="legende">'+p.d+" "+(p.h||"")+"</div>";
  c.onclick=e=>{if(e.target.classList.contains("loupe")){ouvrir(visibles.indexOf(p))}
    else if(e.target.classList.contains("absent"))absent(p);else basculer(p)};return c}
function absent(p){/* la personne n'est pas sur la photo : retirée du livre ET plus jamais reconnue sur cette photo */
  $("#etat").textContent="enregistrement…";fetch("/api/absent",{method:"POST",headers:{"Content-Type":"application/json","X-Jeton":JETON},
  body:JSON.stringify({f:p.f})}).then(r=>r.json().then(j=>{if(!r.ok){alert(j.erreur);throw j}
  p.g=false;p.r=PAS;$("#etat").textContent="enregistré ✓";barreAnnees();
  if(courant>=0)ouvrir(courant);else afficher()}))}
function maj(p,corps){$("#etat").textContent="enregistrement…";
  return fetch("/api/maj",{method:"POST",headers:{"Content-Type":"application/json","X-Jeton":JETON},body:JSON.stringify(Object.assign({f:p.f},corps))})
  .then(r=>r.json().then(j=>{if(!r.ok){alert(j.erreur);throw j}$("#etat").textContent="enregistré ✓";return j}))}
function basculer(p){const v=!p.g;maj(p,{garder:v}).then(()=>{p.g=v;if(p.el)p.el.classList.toggle("g",v);barreAnnees();
  if(courant>=0)ouvrir(courant)})}
function ouvrir(i){if(i<0||i>=visibles.length)return;courant=i;const p=visibles[i];$("#lb").style.display="flex";
  $("#lb img").src="/grande?f="+encodeURIComponent(p.f);$("#lb .txt").textContent=p.d+" "+(p.h||"")+" · "+(p.t||"")+
  (p.l?" · "+p.l:"")+" · "+p.f+(p.b?" · "+p.b.raison:"");const b=$("#bascule");b.textContent=p.g?"Retirer du livre":"Garder dans le livre";
  b.className=p.g?"retirer":"garder";
  if(ML){b.textContent=p.le?"Enlever des lettres":"Choisir pour une lettre";b.className=p.le?"retirer":"garder"}
  $("#master").textContent=D.master==p.f?"◆ Master ✓":"◆ Master";
  $("#let").textContent=p.le?"✉ Retirer des lettres":"✉ Lettres ("+nLettres()+")"}
function nLettres(){return D.photos.filter(x=>x.le).length}
function fermer(){$("#lb").style.display="none";courant=-1;afficher()}
$("#prec").onclick=()=>ouvrir(courant-1);$("#suiv").onclick=()=>ouvrir(courant+1);$("#ferme").onclick=fermer;
$("#bascule").onclick=()=>ML?basculerLettre(visibles[courant]):basculer(visibles[courant]);
$("#couv").onclick=()=>{const p=visibles[courant];maj(p,{vedette:"couverture"}).then(()=>{D.photos.forEach(x=>{if(x.v=="couverture")x.v=""});
  p.v="couverture";p.g=true;barreAnnees();ouvrir(courant)})};
$("#let").onclick=()=>basculerLettre(visibles[courant]);
$("#absent").onclick=()=>absent(visibles[courant]);if(ML)$("#absent").style.display="none";
$("#master").onclick=()=>{const p=visibles[courant];fetch("/api/master",{method:"POST",headers:{"Content-Type":"application/json","X-Jeton":JETON},
  body:JSON.stringify({f:p.f})}).then(r=>{if(!r.ok)throw r;D.master=p.f;$("#etat").textContent=MASTER_OK;barreAnnees();ouvrir(courant)})};
if(ML)$("#master").style.display="none";
document.addEventListener("keydown",e=>{if(courant<0)return;if(e.key=="ArrowRight")ouvrir(courant+1);
  else if(e.key=="ArrowLeft")ouvrir(courant-1);else if(e.key==" "){e.preventDefault();ML?basculerLettre(visibles[courant]):basculer(visibles[courant])}
  else if(e.key.toLowerCase()=="c"&&!ML)$("#couv").click();
  else if(e.key.toLowerCase()=="n"&&!ML)absent(visibles[courant]);
  else if(e.key.toLowerCase()=="l")basculerLettre(visibles[courant]);else if(e.key=="Escape")fermer()});
document.querySelectorAll("#outils button").forEach(b=>b.onclick=()=>{filtre=b.dataset.f;
  document.querySelectorAll("#outils button").forEach(x=>x.classList.toggle("actif",x==b));afficher()});
let minuterie;$("#cherche").oninput=e=>{clearTimeout(minuterie);minuterie=setTimeout(()=>{texte=e.target.value.trim().toLowerCase();afficher()},250)};
$("#fin").onclick=()=>fetch("/api/fin",{method:"POST",headers:{"X-Jeton":JETON}}).then(()=>{document.body.innerHTML=
  '<div class="vide" style="font-size:18px">Sélection enregistrée. Vous pouvez fermer cet onglet.</div>'});
</script></html>"""


if __name__ == "__main__":
    main()
    # sortie immédiate : des vignettes encore en cours de lecture sur le disque externe (navigateur) ne doivent
    # pas retarder le retour à l'application (tout est déjà enregistré à ce stade)
    sys.stdout.flush()
    os._exit(0)
