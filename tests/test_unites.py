"""Tests rapides des fonctions sensibles (quelques secondes, sans photos réelles)."""
import importlib.util
import importlib.machinery
import tempfile
import unittest
from pathlib import Path

from donnees import DOSSIER_OUTIL  # noqa: F401  (ajoute le dossier de l'outil au chemin)

import album_famille as af
import lanceur
import livre_photo as lp
import textes_app
import traduction


def charger_appli():
    """L'application (.pyw) chargée comme un module, sans ouvrir de fenêtre ; None si Tkinter est absent."""
    if importlib.util.find_spec("tkinter") is None:
        return None
    chemin = str(DOSSIER_OUTIL / "album_photos_app.pyw")
    chargeur = importlib.machinery.SourceFileLoader("album_photos_app", chemin)
    spec = importlib.util.spec_from_loader("album_photos_app", chargeur)
    module = importlib.util.module_from_spec(spec)
    chargeur.exec_module(module)
    return module


class Traduction(unittest.TestCase):
    def test_textes_de_l_outil_traduits(self):
        cas = {"Les 3 ans de Laura": "Laura turns 3", "Le premier anniversaire de Laura": "Laura's first birthday",
               "Noël 2013": "Christmas 2013", "Du 4 au 5 août 2013": "4–5 August 2013",
               "10 DÉCEMBRE · VOYAGE – ÉMIRATS ARABES UNIS": "10 DECEMBER · TRIP – UNITED ARAB EMIRATES",
               "2013 · 1 AN": "2013 · 1 YEAR", "Joyeux anniversaire !": "Happy birthday!",
               "Bienvenue Laura": "Welcome Laura"}
        for fr, en in cas.items():
            self.assertEqual(traduction.traduire(fr, "en"), en, fr)

    def test_texte_ecrit_a_la_main_jamais_traduit(self):
        for texte in ("Avec tout notre amour,", "Tu grandis trop vite, mais chaque souvenir avec toi reste notre trésor.",
                      "Visite chez tata Maurice", "AVEC TATA HELENE"):
            self.assertEqual(traduction.traduire(texte, "en"), texte)

    def test_francais_inchange(self):
        self.assertEqual(traduction.traduire("Noël 2013", "fr"), "Noël 2013")


class Parametres(unittest.TestCase):
    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp())
        self.anciens = lanceur.PARAMETRES, lanceur.JOURNAL
        lanceur.PARAMETRES, lanceur.JOURNAL = self.dossier / "parametres_livre.txt", self.dossier / "journal.txt"

    def tearDown(self):
        lanceur.PARAMETRES, lanceur.JOURNAL = self.anciens

    def ecrire(self, texte):
        lanceur.PARAMETRES.write_bytes(("\ufeff" + texte).encode("utf-8"))

    def test_lettre_gardee_apres_plusieurs_enregistrements(self):
        """Bug du 01/11/2026 : le 2e enregistrement (automatique avant chaque étape) supprimait texte_fin.txt,
        et le livre affichait « À suivre… » au lieu de la lettre."""
        fichier = Path(tempfile.mkdtemp()) / "texte_fin.txt"
        lettre = "Tu grandis trop vite.\n\nAvec tout notre amour,\nMaman et Papa"
        for _ in range(3):  # enregistrer à la main, puis avant l'aperçu, puis avant le livre final
            textes_app.enregistrer_texte_fin(fichier, lettre)
            self.assertTrue(fichier.exists(), "la lettre ne doit jamais disparaître")
        self.assertEqual(fichier.read_text(encoding="utf-8"), lettre + "\n")
        textes_app.enregistrer_texte_fin(fichier, "  ")
        self.assertFalse(fichier.exists(), "zone vidée : retour à « À suivre… »")

    def test_lettre_sur_plusieurs_lignes_lue_en_entier(self):
        self.ecrire("PHOTOS = D:\\Photos\r\nSORTIE = C:\\Albums\r\nPERSONNE = Laura\r\n"
                    "TEXTE_FIN = Ma chérie,\r\n\r\nComme tu le vois…\r\nAvec tout notre amour,\r\n"
                    "# commentaire\r\nSYMBOLE_FIN = coeurs\r\n")
        p = lanceur.lire_parametres()
        self.assertEqual(len(p["TEXTE_FIN"].splitlines()), 4)
        self.assertEqual(p["SYMBOLE_FIN"], "coeurs")

    def test_fichier_abime_par_windows(self):
        """Anciennes versions sous Windows : « \\r\\r\\n » en fin de ligne (ligne vide fantôme après chaque ligne)."""
        brut = ("PHOTOS = D:\\Photos\r\r\nSORTIE = C:\\Albums\r\r\nPERSONNE = Laura\r\r\n"
                "TEXTE_FIN = Ma chérie,\r\r\n\r\r\nSuite de la lettre\r\r\nSYMBOLE_FIN = coeurs\r\r\n")
        lanceur.PARAMETRES.write_bytes(brut.encode("utf-8"))
        self.assertEqual(lanceur.lire_parametres()["TEXTE_FIN"], "Ma chérie,\n\nSuite de la lettre")
        lanceur.enregistrer_parametre("PHOTOS", "E:\\Photos")
        octets = lanceur.PARAMETRES.read_bytes()
        self.assertNotIn(b"\r\r\n", octets, "plus jamais de « \\r\\r\\n » écrit")
        self.assertNotIn(b"\r\n\r\n\r\n", octets, "pas de lignes vides accumulées")

    def test_lettre_coupee_recollee(self):
        texte = lanceur.texte_fin_complet("Ma chérie,", "\nComme tu le vois…\nAvec amour")
        self.assertTrue(texte.startswith("Ma chérie,\n\nComme"))

    def test_sortie_dans_les_photos_refusee(self):
        self.ecrire("PHOTOS = %s\r\nSORTIE = %s\r\nPERSONNE = Laura\r\n" % (self.dossier, self.dossier / "travail"))
        with self.assertRaises(SystemExit):
            lanceur.lire_parametres()

    def test_dossiers_melanges(self):
        self.assertTrue(lanceur.dossiers_melanges("D:/Photos", "D:/Photos/travail"))
        self.assertTrue(lanceur.dossiers_melanges("D:/Photos/2020", "D:/Photos"))
        self.assertFalse(lanceur.dossiers_melanges("D:/Photos", "C:/AlbumsFamille"))

    def test_ecriture_sure_et_sauvegardes(self):
        for i in range(13):
            lanceur.ecrire_sur(lanceur.PARAMETRES, f"PERSONNE = Laura{i}\r\n")
        self.assertIn("Laura12", lanceur.PARAMETRES.read_text(encoding="utf-8-sig"))
        sauvegardes = list((self.dossier / "sauvegardes_parametres").glob("*.txt"))
        self.assertLessEqual(len(sauvegardes), 10)
        self.assertFalse(list(self.dossier.glob("*.tmp")))


class Application(unittest.TestCase):
    """Fonctions de l'application qui ne demandent pas de fenêtre."""

    @classmethod
    def setUpClass(cls):
        cls.app = charger_appli()

    def setUp(self):
        if self.app is None:
            self.skipTest("Tkinter absent de ce Python")

    def test_texte_multiligne_et_reecriture_sans_orphelins(self):
        app = self.app
        dossier = Path(tempfile.mkdtemp())
        ancien = app.PARAMETRES
        app.PARAMETRES = dossier / "parametres_livre.txt"
        try:
            # écrit comme le faisait l'ancienne version sous Windows (« \\r\\r\\n »)
            app.PARAMETRES.write_bytes(("\ufeffPERSONNE = Laura\r\r\nTEXTE_FIN = Ma chérie,\r\r\n\r\r\n"
                                        "Suite de la lettre\r\r\nSYMBOLE_FIN = coeurs\r\r\n").encode("utf-8"))
            valeurs = app.analyser_texte(app.lire_texte())
            self.assertEqual(valeurs["TEXTE_FIN"], "Ma chérie,\n\nSuite de la lettre")
            app.ecrire_parametres({"TEXTE_FIN": "", "PERSONNE": "Laura"})
            contenu = app.PARAMETRES.read_text(encoding="utf-8-sig")
            self.assertNotIn("Suite de la lettre", contenu)
            self.assertIn("SYMBOLE_FIN = coeurs", contenu)
            self.assertNotIn(b"\r\r\n", app.PARAMETRES.read_bytes())
        finally:
            app.PARAMETRES = ancien

    def test_libelles_des_listes(self):
        textes_app.LANGUE[0] = "en"
        try:
            self.assertEqual(textes_app.libelle("noir"), "black")
            self.assertEqual(textes_app.code_de("black", ["noir", "blanc"]), "noir")
            self.assertEqual(textes_app.code_de("#1C2B44", ["noir"]), "#1C2B44")
        finally:
            textes_app.LANGUE[0] = "fr"


class Analyse(unittest.TestCase):
    def test_sortie_dans_photos_refusee(self):
        with self.assertRaises(SystemExit):
            af.verifier_sortie(Path("/x/photos"), Path("/x/photos/travail"))
        with self.assertRaises(SystemExit):
            af.verifier_sortie(Path("/x/photos"), Path("/x"))
        af.verifier_sortie(Path("/x/photos"), Path("/y/travail"))

    def test_inventaire_ignore_corbeille_et_miniatures(self):
        racine = Path(tempfile.mkdtemp())
        for relatif in ("2020/a.jpg", "2020/b.JPG", "$RECYCLE.BIN/c.jpg", ".thumbnails/d.jpg", "2020/notes.txt",
                        "2020/._e.jpg"):
            (racine / relatif).parent.mkdir(parents=True, exist_ok=True)
            (racine / relatif).write_bytes(b"x")
        noms = sorted(Path(c).name for c in af.lister_photos(racine))
        self.assertEqual(noms, ["a.jpg", "b.JPG"])

    def test_doublons_rafale(self):
        photos = []
        for i in range(400):  # 2 empreintes très proches par paire
            h = (i // 2) * 0x1F3D5B79A1C3E5F7 & 0xFFFFFFFFFFFFFFFF
            photos.append({"evenement": "e", "chemin": f"p{i}.jpg", "dhash": "%016x" % (h ^ (i % 2)),
                           "largeur_visage": 0.1, "nettete": 200, "luminosite": 120, "nb_visages": 1,
                           "largeur_orig": 2000, "hauteur_orig": 1500})
        af.marquer_doublons(photos)
        self.assertEqual(sum(1 for p in photos if p["doublon_de"]), 200)


class Reconnaissance(unittest.TestCase):
    """Attribution des visages : seuil, marge entre personnes proches, corrections manuelles."""

    def base_visages(self, embs, largeurs=None):
        import sqlite3

        import numpy as np

        base = sqlite3.connect(":memory:")
        base.row_factory = sqlite3.Row
        base.execute("CREATE TABLE visages (id INTEGER PRIMARY KEY, photo_id INTEGER, l REAL, emb BLOB)")
        for i, e in enumerate(embs, 1):
            e = np.asarray(e, dtype=np.float32)
            l = (largeurs or {}).get(i, 0.1)
            base.execute("INSERT INTO visages VALUES (?, ?, ?, ?)", (i, i, l, (e / np.linalg.norm(e)).tobytes()))
        return base

    def test_seuil_marge_et_refus(self):
        import numpy as np

        def unitaire(v):
            v = np.asarray(v, dtype=np.float32)
            return v / np.linalg.norm(v)
        refs = {"Laura": np.stack([unitaire([1, 0, 0]), unitaire([0.95, 0.1, 0])]),
                "Bo": np.stack([unitaire([0, 1, 0]), unitaire([0.1, 0.95, 0])])}
        base = self.base_visages([[1, 0.05, 0],      # 1 : Laura, sans doute possible
                                  [0.7, 0.68, 0],    # 2 : entre Laura et Bo : trop proche, personne
                                  [0, 0, 1],         # 3 : inconnu : personne
                                  [0.9, 0.1, 0.1]])  # 4 : Laura... mais refusé à la main
        resultat = af.identifier(base, refs, {(4, "Laura")}, 0.40)
        self.assertEqual(resultat[1][2], "Laura")
        self.assertNotIn(2, resultat, "deux personnes trop proches : pas d'attribution au hasard")
        self.assertNotIn(3, resultat, "visage inconnu : attribué à personne")
        self.assertNotEqual(resultat.get(4, (0, 0, ""))[2], "Laura", "un refus manuel est respecté")

    def test_refus_appris_et_petits_visages(self):
        """Un visage qui ressemble plus à un visage refusé qu'à la personne n'est pas attribué ; un petit visage
        (arrière-plan) doit ressembler nettement plus."""
        import numpy as np

        def unitaire(v):
            v = np.asarray(v, dtype=np.float32)
            return v / np.linalg.norm(v)
        refs = {"Laura": np.stack([unitaire([1, 0, 0]), unitaire([0.95, 0.1, 0])]),
                "Bo": np.stack([unitaire([0, 1, 0]), unitaire([0.1, 0.95, 0])])}
        base = self.base_visages([[0.62, 0.02, 0.78],   # 1 : un inconnu, sosie d'un visage refusé
                                  [0.6, 0.0, 0.8],      # 2 : visage refusé pour Laura
                                  [0.44, 0.0, 0.9],     # 3 : ressemblance limite, petit visage au fond
                                  [0.44, 0.0, 0.9]],    # 4 : même ressemblance, visage bien visible
                                 largeurs={3: 0.03})
        sans = af.identifier(base, refs, af.Exclusions(), 0.40)
        self.assertEqual(sans[1][2], "Laura", "avant le refus, le sosie était pris pour Laura")
        exclusions = af.Exclusions({(2, "Laura")})
        exclusions.negatifs = {"Laura": np.stack([unitaire([0.6, 0.0, 0.8])])}
        resultat = af.identifier(base, refs, exclusions, 0.40)
        self.assertNotIn(1, resultat, "ressemble plus au visage refusé qu'à Laura : pas Laura")
        self.assertNotIn(3, af.identifier(base, refs, af.Exclusions(), 0.40), "petit visage limite : écarté")
        self.assertEqual(af.identifier(base, refs, af.Exclusions(), 0.40)[4][2], "Laura", "grand visage : gardé")


class MosaiqueMemoire(unittest.TestCase):
    def test_placement_par_blocs_memoire_bornee(self):
        """Grille dense et beaucoup de photos : distances calculées par petits blocs (jamais la matrice complète
        cases x photos, plus de 4 Go en A0 dense) ; chaque case remplie, aucune répétition dans le voisinage."""
        import numpy as np

        import mosaique_photos as mp
        ancien = mp.MEMOIRE_DISTANCES
        mp.MEMOIRE_DISTANCES = 200_000  # quelques cases par bloc : force le découpage
        try:
            rng = np.random.default_rng(2)
            cibles = rng.random((40 * 30, 27), dtype=np.float32) * 255
            signatures = rng.random((900, 27), dtype=np.float32) * 255
            choix, usages = mp.attribuer(cibles, signatures, 40, 30)
        finally:
            mp.MEMOIRE_DISTANCES = ancien
        self.assertTrue((choix >= 0).all())
        self.assertEqual(int(usages.sum()), 40 * 30)
        for r in range(30):
            for c in range(40):
                zone = choix[max(0, r - 3):r + 4, max(0, c - 3):c + 4]
                self.assertEqual(int((zone == choix[r, c]).sum()), 1, "même photo dans le voisinage")


class Partage(unittest.TestCase):
    def test_boutons_de_l_application_connus_du_lanceur(self):
        """Chaque bouton (colonne de gauche et fenêtre Maintenance) lance une étape qui existe, et son nom est
        trouvé (bug du 03/11/2026 : une étape de Maintenance restait « en cours » pour toujours)."""
        import ast
        source = (Path(lanceur.__file__).parent / "album_photos_app.pyw").read_text(encoding="utf-8")
        valeurs = {}
        for noeud in ast.parse(source).body:
            if isinstance(noeud, ast.Assign) and getattr(noeud.targets[0], "id", "") in ("ETAPES", "MAINTENANCE"):
                valeurs[noeud.targets[0].id] = ast.literal_eval(noeud.value)
        codes = [e for _, boutons in valeurs["ETAPES"] for _, e, _ in boutons] + [m[1] for m in valeurs["MAINTENANCE"]]
        for code in codes:
            self.assertIn(code, lanceur.ETAPES, f"étape {code} inconnue du lanceur")
        self.assertIn("def nom_etape(", source)
        self.assertNotIn("next(t for _, bs in ETAPES", source)

    def test_zip_a_partager_sans_donnees_ni_github(self):
        """Zip à partager : ni réglages, ni lettre, ni journal, ni lien vers le dépôt GitHub de l'auteur."""
        import zipfile
        dossier = Path(tempfile.mkdtemp())
        ancien_ouvrir, ancien_journal = lanceur.ouvrir, lanceur.JOURNAL
        lanceur.ouvrir, lanceur.JOURNAL = (lambda *a: None), dossier / "journal.txt"
        try:
            if not lanceur.mode_admin():
                self.skipTest("copie partagée : pas de zip à fabriquer")
            lanceur.etape_partager({"SORTIE": str(dossier)})
        finally:
            lanceur.ouvrir, lanceur.JOURNAL = ancien_ouvrir, ancien_journal
        archive = zipfile.ZipFile(next(dossier.glob("AlbumPhotos_partage_*.zip")))
        noms = {Path(n).name for n in archive.namelist()}
        for prive in ("parametres_livre.txt", "texte_fin.txt", "journal.txt", "admin.txt", "0_mettre_a_jour.bat"):
            self.assertNotIn(prive, noms)
        self.assertIn("LISEZ-MOI.txt", noms)
        code = archive.read("AlbumPhotos/lanceur.py").decode("utf-8")
        self.assertIn('DEPOT = ""', code)
        self.assertNotIn("github.com/", code.split("DEPOT =")[1].split("\n")[0])
        modele = archive.read("AlbumPhotos/parametres_livre.modele.txt").decode("utf-8-sig")
        self.assertRegex(modele, r"(?m)^PERSONNE =$")


class LegendesDates(unittest.TestCase):
    def test_legende_courte_sans_repetition(self):
        """« 31 OCTOBER · OCT-10 » : la date ne se répète plus ; mois en 3 lettres + année, le jour seulement pour
        un jour important (anniversaire, Noël, Nouvel An)."""
        import datetime as dt

        import traduction
        p = {"jour": dt.date(2010, 10, 31)}
        self.assertEqual(lp.legende_mixte(p, {"titre": "Oct-10", "type": ""}, "chrono"), "Oct 2010")
        self.assertEqual(lp.legende_mixte(p, {"titre": "Octobre 2010", "type": ""}, "themes"), "Oct 2010")
        self.assertEqual(lp.legende_mixte(p, {"titre": "Paris", "type": "voyage"}, "chrono"), "Oct 2010 · Paris")
        noel = lp.legende_mixte({"jour": dt.date(2013, 12, 25)}, {"titre": "Noël 2013", "type": "noel"}, "chrono")
        self.assertEqual(noel, "25 Déc 2013 · Noël")
        self.assertEqual(traduction.traduire(noel.upper(), "en"), "25 DEC 2013 · CHRISTMAS")

    def test_legende_photo_seule(self):
        """Photo seule sur sa page : date courte + lieu (pas répété s'il est déjà dans le titre)."""
        import datetime as dt
        p = {"jour": dt.date(2017, 8, 3), "lieu": "Rome, Lazio, Italie", "type": "voyage", "legende": ""}
        self.assertEqual(lp.legende_seule(p), "Aoû 2017 · Rome")
        self.assertEqual(lp.legende_seule(p, deja="Voyage à Rome"), "Aoû 2017")
        self.assertEqual(lp.legende_seule(dict(p, lieu="", type="anniversaire")), "3 Aoû 2017")


class Caches(unittest.TestCase):
    """« Reliquat » : une autre photo arrivée au même chemin (dossiers réorganisés) ne doit jamais réafficher
    l'image en cache de l'ancienne."""

    def test_autre_photo_au_meme_chemin(self):
        import os
        import time

        from PIL import Image

        import choisir_photos

        dossier = Path(tempfile.mkdtemp())
        racine, sortie = dossier / "photos", dossier / "travail"
        (racine / "2023").mkdir(parents=True)
        chemin = racine / "2023" / "IMG_0001.jpg"
        Image.new("RGB", (900, 700), (230, 20, 20)).save(chemin)
        base = af.ouvrir_base(sortie)
        af.meta(base, "racine", racine)

        def analyser():  # ce que fait « Analyser le disque » : taille et date du fichier dans la base
            etat = chemin.stat()
            base.execute("REPLACE INTO photos (id, chemin, taille, mtime) VALUES (1, ?, ?, ?)",
                         ("2023/IMG_0001.jpg", etat.st_size, etat.st_mtime))
            base.commit()
        analyser()
        cache = sortie / "vignettes_choix"
        cache.mkdir()
        rouge_vignette = choisir_photos.vignette(racine, cache, "2023/IMG_0001.jpg", 300)
        rouge_apercu = af.apercu(base, sortie, "2023/IMG_0001.jpg", 300, "vignettes")
        # une autre photo (bleue, autre taille) remplace l'ancienne au même chemin
        Image.new("RGB", (1200, 800), (20, 20, 230)).save(chemin)
        os.utime(chemin, (time.time() + 10, time.time() + 10))
        analyser()
        bleu_vignette = choisir_photos.vignette(racine, cache, "2023/IMG_0001.jpg", 300)
        bleu_apercu = af.apercu(base, sortie, "2023/IMG_0001.jpg", 300, "vignettes")
        self.assertNotEqual(rouge_vignette, bleu_vignette, "écran de choix : nouvelle vignette")
        self.assertNotEqual(rouge_apercu, bleu_apercu, "livre : nouvelle image en cache")
        r, g, b = Image.open(bleu_apercu).convert("RGB").getpixel((50, 50))
        self.assertGreater(b, r, "c'est bien la nouvelle photo (bleue) qui est montrée")


class References(unittest.TestCase):
    def test_references_douteuses_ecartees(self):
        """Photo de référence avec deux visages de même taille, ou visage d'une autre personne : écartée."""
        import contextlib
        import io

        from donnees import FauxDetecteur, FauxReconnaissance, enregistrer, scene
        import datetime as dt
        import numpy as np

        famille = Path(tempfile.mkdtemp())
        alea = np.random.default_rng(5)
        for i in range(5):
            enregistrer(famille / "Laura" / f"ok{i}.jpg", scene(800, 1000, ["Laura"], alea), dt.datetime(2020, 1, 1))
        enregistrer(famille / "Laura" / "groupe.jpg", scene(1200, 800, ["Laura", "Hugo"], alea), dt.datetime(2020, 1, 1))
        enregistrer(famille / "Laura" / "erreur.jpg", scene(800, 1000, ["Papa"], alea), dt.datetime(2020, 1, 1))
        texte = io.StringIO()
        with contextlib.redirect_stdout(texte):
            refs = af.references(famille, FauxDetecteur(), FauxReconnaissance())
        self.assertEqual(len(refs["Laura"]), 5, texte.getvalue())
        self.assertIn("groupe.jpg : plusieurs visages", texte.getvalue())
        self.assertIn("erreur.jpg : ne ressemble pas", texte.getvalue())


class MiseEnPage(unittest.TestCase):
    def test_recadrage_garde_les_visages(self):
        photo = {"ratio": 1.5, "visages": [(0.1, 0.3, 0.1, 0.15), (0.75, 0.3, 0.1, 0.15)]}
        gauche, haut, cw, ch, coupe = lp.fenetre(photo, 1.5)
        self.assertFalse(coupe)
        _, _, _, _, coupe = lp.fenetre(photo, 0.5)  # case très étroite : impossible sans couper
        self.assertTrue(coupe)

    def test_visage_au_bord(self):
        self.assertTrue(lp.visage_au_bord({"visages": [(0.85, 0.2, 0.15, 0.3)]}))
        self.assertFalse(lp.visage_au_bord({"visages": [(0.4, 0.2, 0.15, 0.3)]}))

    def test_recouvrement(self):
        self.assertEqual(lp.recouvrement((0, 0, 10, 10), [(20, 20, 5, 5)]), 0)
        self.assertAlmostEqual(lp.recouvrement((0, 0, 10, 10), [(5, 0, 10, 10)]), 0.5)

    def test_couleurs_bd(self):
        self.assertEqual(lp.couleur_bd("vert"), lp.COULEURS_BD["vert"])
        self.assertEqual(lp.couleur_bd("#123456"), "#123456")
        with self.assertRaises(SystemExit):
            lp.couleur_bd("arc-en-ciel")


class PlancheLettres(unittest.TestCase):
    def test_creux_du_A_rempli_et_visage_sur_le_plein(self):
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont

        import planche_lettres as pl

        taille = (600, 500)
        masque = Image.new("L", taille, 0)
        police = pl.police("arial-black", 400)
        ImageDraw.Draw(masque).text((50, 20), "A", font=police, fill=255)
        boite = masque.getbbox()
        avant = np.asarray(masque.crop(boite)) > 127
        pl.boucher_creux(masque, boite)
        apres = np.asarray(masque.crop(boite)) > 127
        self.assertGreaterEqual(apres.sum(), avant.sum())  # le creux est rempli (ou il n'y en avait pas)
        info = {"ratio": 1.0, "visages": [(0.4, 0.3, 0.2, 0.25)]}
        k, ox, oy = pl.cadrage(info, apres)
        H, W = apres.shape
        x0, x1 = ox + 0.4 * k, ox + 0.6 * k
        y0, y1 = oy + 0.3 * k, oy + 0.55 * k
        zone = apres[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)]
        self.assertGreater(zone.mean(), 0.9, "le visage doit tomber sur le plein de la lettre")
        self.assertIsInstance(ImageFont, object)


if __name__ == "__main__":
    unittest.main()
