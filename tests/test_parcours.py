"""Parcours complet sur un petit disque de synthèse (1 à 3 minutes) : analyse, sélection, aperçu, livre final,
planche lettres, écrans du navigateur. Vérifie surtout que les photos d'origine ne sont JAMAIS modifiées."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from donnees import creer_disque, installer_faux_modeles, lancer

import album_famille as af
import choisir_photos
import livre_photo as lp
import planche_lettres as pl


def empreintes(dossier):
    return {str(f.relative_to(dossier)): (hashlib.md5(f.read_bytes()).hexdigest(), f.stat().st_mtime)
            for f in sorted(dossier.rglob("*")) if f.is_file()}


class Parcours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = Path(tempfile.mkdtemp(prefix="albumphotos_test_"))
        cls.sortie = cls.temp / "AlbumsFamille"
        cls.photos, cls.nombre = creer_disque(cls.temp, cls.sortie)
        cls.avant = empreintes(cls.photos)
        installer_faux_modeles()
        lancer(af, "--sortie", cls.sortie, "analyser", cls.photos)
        lancer(af, "--sortie", cls.sortie, "trier")
        lancer(lp, "--sortie", cls.sortie, "preparer", "--personne", "Laura", "--avec", "Hugo",
               "--famille", cls.sortie / "famille", "--naissance", "12/03/2012", "--pays-maison", "FR")
        cls.livre = cls.sortie / "livre_Laura"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp, ignore_errors=True)

    def test_1_analyse(self):
        base = af.ouvrir_base(self.sortie)
        n = base.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
        self.assertEqual(n, self.nombre, "toutes les photos trouvées, corbeille ignorée")
        self.assertGreater(base.execute("SELECT COUNT(*) FROM visages").fetchone()[0], n)
        self.assertTrue((self.livre / "selection_livre.csv").exists())

    def test_2_apercu_et_livre_final(self):
        lancer(lp, "--sortie", self.sortie, "composer", "--personne", "Laura", "--apercus", "elegant,bd-photo",
               "--naissance", "12/03/2012", "--langue", "en", "--pied-de-page", "Avec amour")
        for amb in ("elegant", "bd-photo"):
            self.assertTrue((self.livre / f"Apercu_Laura_{amb}.pdf").exists(), amb)
        fin = self.temp / "texte_fin.txt"
        fin.write_text("Ma chérie,\n\nAvec tout notre amour,\nMaman et Papa ❤️\n", encoding="utf-8")
        lancer(lp, "--sortie", self.sortie, "composer", "--personne", "Laura", "--ambiance", "prestige-mosaique-bd",
               "--naissance", "12/03/2012", "--mot-fin-fichier", fin, "--langue", "en", "--pptx")
        imprimeur = self.livre / "imprimeur_prestige-mosaique-bd"
        for nom in ("Livre_Laura_prestige-mosaique-bd_interieur.pdf", "Livre_Laura_prestige-mosaique-bd_couverture.pdf",
                    "Instructions_imprimeur.xlsx", "Plan_de_montage.pdf", "rapport_impression.txt",
                    "Livre_Laura_prestige-mosaique-bd_modifiable.pptx"):
            self.assertTrue((imprimeur / nom).exists(), nom)
        import pypdfium2

        pdf = pypdfium2.PdfDocument(str(imprimeur / "Livre_Laura_prestige-mosaique-bd_interieur.pdf"))
        self.assertEqual(len(pdf) % 2, 0, "nombre de pages pair pour l'imprimeur")
        texte = "".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
        self.assertIn("Avec tout notre amour", texte, "la lettre de fin reste dans sa langue")
        self.assertNotIn("With tout notre", texte)

    def test_3_planche_lettres(self):
        lancer(pl, "--sortie", self.sortie, "--personne", "Laura", "--modeles", "1,3", "--fond", "noir",
               "--haut", "On t'aime")
        lettres = self.livre / "lettres"
        self.assertTrue((lettres / "Lettres_LAURA_1-classique_fond-noir.jpg").exists())
        self.assertTrue((lettres / "Comparaison_modeles.jpg").exists())

    def test_4_ecran_de_choix_protege(self):
        adresse = self.demarrer(choisir_photos, "--sortie", self.sortie, "--personne", "Laura")
        page = urllib.request.urlopen(adresse, timeout=30).read().decode("utf-8")
        jeton = re.search(r'JETON="([^"]+)"', page).group(1)
        donnees = json.loads(urllib.request.urlopen(adresse + "api/donnees", timeout=30).read())
        self.assertGreater(len(donnees["photos"]), 0)
        for filtre in ("couverture", "pleine", "lettres", "master", "speciales", "ecartees"):
            self.assertIn(f'data-f="{filtre}"', page, f"bouton de filtre {filtre}")
        for entetes in ({}, {"X-Jeton": "faux"}):  # sans jeton, ou faux jeton : refusé
            with self.assertRaises(urllib.error.HTTPError) as erreur:
                self.poster(adresse + "api/fin", {}, entetes)
            self.assertEqual(erreur.exception.code, 403)
            erreur.exception.close()
        self.poster(adresse + "api/fin", {}, {"X-Jeton": jeton})
        self.attendre_fin()

    def test_5_propositions_cliquables(self):
        lancer(lp, "--sortie", self.sortie, "proposer", "--personne", "Laura")
        import valider_propositions as vp

        selection = (self.livre / "selection_livre.csv").read_text(encoding="utf-8-sig")
        adresse = self.demarrer(vp, "--sortie", self.sortie, "--personne", "Laura")
        page = urllib.request.urlopen(adresse, timeout=30).read().decode("utf-8")
        jeton = re.search(r'JETON="([^"]+)"', page).group(1)
        propositions = json.loads(urllib.request.urlopen(adresse + "api/propositions", timeout=30).read())
        if propositions:
            self.poster(adresse + "api/choix", {"tous": True, "ok": False}, {"X-Jeton": jeton})
        self.poster(adresse + "api/appliquer", {}, {"X-Jeton": jeton})
        self.attendre_fin()
        self.assertEqual((self.livre / "selection_livre.csv").read_text(encoding="utf-8-sig"), selection,
                         "tout refusé : la sélection ne change pas")

    def test_7_verifier_la_reconnaissance(self):
        """Écran de vérification : un visage refusé n'est plus attribué à la personne."""
        import sqlite3

        import verifier_visages as vv

        adresse = self.demarrer(vv, "--sortie", self.sortie, "--personne", "Laura", "--famille", self.sortie / "famille")
        page = urllib.request.urlopen(adresse, timeout=30).read().decode("utf-8")
        jeton = re.search(r'JETON="([^"]+)"', page).group(1)
        donnees = json.loads(urllib.request.urlopen(adresse + "api/visages", timeout=30).read())
        self.assertGreater(len(donnees["reconnus"]), 0)
        refuse = donnees["reconnus"][0]["id"]
        vignette = urllib.request.urlopen(adresse + f"visage?id={refuse}", timeout=30).read()
        self.assertGreater(len(vignette), 500, "la vignette du visage s'affiche")
        self.poster(adresse + "api/corriger", {"id": refuse, "ok": False}, {"X-Jeton": jeton})
        self.poster(adresse + "api/fin", {}, {"X-Jeton": jeton})
        self.attendre_fin()
        base = af.ouvrir_base(self.sortie)
        self.assertEqual(base.execute("SELECT ok FROM confirmations WHERE visage_id = ?", (refuse,)).fetchone()[0], 0)
        refs, exclusions = af.charger_references(base, self.sortie / "famille", *af.modeles(self.sortie))
        self.assertNotEqual(af.identifier(base, refs, exclusions).get(refuse, (0, 0, ""))[2], "Laura")
        base.execute("DELETE FROM confirmations")
        base.commit()

    def test_8_pas_la_personne_et_repartir_de_zero(self):
        """« ✗ Pas Laura » dans l'écran de choix : photo retirée, plus jamais proposée ; « Effacer toutes mes
        corrections » dans l'écran de vérification : on repart des seules photos de référence."""
        lancer(lp, "--sortie", self.sortie, "preparer", "--personne", "Laura", "--famille", self.sortie / "famille",
               "--naissance", "12/03/2012", "--ecraser")
        fichier = self.livre / "selection_livre.csv"
        lignes = af.lire_csv(fichier)
        cible = next(l["fichier"] for l in lignes if l["garder"] == "1")
        adresse = self.demarrer(choisir_photos, "--sortie", self.sortie, "--personne", "Laura")
        jeton = re.search(r'JETON="([^"]+)"', urllib.request.urlopen(adresse, timeout=30).read().decode()).group(1)
        reponse = json.loads(self.poster(adresse + "api/absent", {"f": cible}, {"X-Jeton": jeton}))
        self.assertGreater(reponse["visages"], 0)
        self.poster(adresse + "api/fin", {}, {"X-Jeton": jeton})
        self.attendre_fin()
        ligne = next(l for l in af.lire_csv(fichier) if l["fichier"] == cible)
        self.assertEqual((ligne["garder"], ligne["remarque"]), ("0", "pas Laura"))
        lancer(lp, "--sortie", self.sortie, "preparer", "--personne", "Laura", "--famille", self.sortie / "famille",
               "--naissance", "12/03/2012", "--ecraser")
        self.assertNotIn(cible, {l["fichier"] for l in af.lire_csv(fichier)}, "plus jamais proposée")

        import verifier_visages as vv
        adresse = self.demarrer(vv, "--sortie", self.sortie, "--personne", "Laura", "--famille", self.sortie / "famille")
        jeton = re.search(r'JETON="([^"]+)"', urllib.request.urlopen(adresse, timeout=30).read().decode()).group(1)
        self.assertGreater(json.loads(self.poster(adresse + "api/effacer", {}, {"X-Jeton": jeton}))["effacees"], 0)
        self.poster(adresse + "api/fin", {}, {"X-Jeton": jeton})
        self.attendre_fin()
        base = af.ouvrir_base(self.sortie)
        self.assertEqual(base.execute("SELECT COUNT(*) FROM confirmations").fetchone()[0], 0)
        lancer(lp, "--sortie", self.sortie, "preparer", "--personne", "Laura", "--famille", self.sortie / "famille",
               "--naissance", "12/03/2012", "--ecraser")
        self.assertIn(cible, {l["fichier"] for l in af.lire_csv(fichier)}, "corrections effacées : de nouveau proposée")

    def test_6_photo_disparue_du_disque(self):
        """Une photo déplacée ou supprimée après l'analyse ne doit pas arrêter la préparation ni le livre."""
        import contextlib
        import io

        photo = next(f for f in sorted(self.photos.rglob("*.jpg")) if "RECYCLE" not in str(f))
        cachee = self.temp / "cachee.jpg"
        shutil.move(photo, cachee)  # sortie du « disque » le temps du test, puis remise à l'identique
        try:
            sortie_texte = io.StringIO()
            with contextlib.redirect_stdout(sortie_texte):
                lancer(lp, "--sortie", self.sortie, "preparer", "--personne", "Laura", "--famille",
                       self.sortie / "famille", "--naissance", "12/03/2012", "--ecraser")
                lancer(lp, "--sortie", self.sortie, "composer", "--personne", "Laura", "--apercus", "elegant",
                       "--naissance", "12/03/2012")
            self.assertIn("introuvable", sortie_texte.getvalue())
            self.assertTrue((self.livre / "Apercu_Laura_elegant.pdf").exists())
        finally:
            shutil.move(cachee, photo)

    def test_8b_mosaique(self):
        """Mosaïque : la photo master choisie dans l'écran de choix, reconstituée avec les photos de l'album ;
        format A0 calculé à 150 dpi (sans le fabriquer : trop long pour un test)."""
        import mosaique_photos as mp
        lignes = af.lire_csv(self.livre / "selection_livre.csv")
        master = lignes[0]["fichier"]
        adresse = self.demarrer(choisir_photos, "--sortie", self.sortie, "--personne", "Laura")
        jeton = re.search(r'JETON="([^"]+)"', urllib.request.urlopen(adresse, timeout=30).read().decode()).group(1)
        self.poster(adresse + "api/master", {"f": master}, {"X-Jeton": jeton})
        self.poster(adresse + "api/fin", {}, {"X-Jeton": jeton})
        self.attendre_fin()
        self.assertEqual((self.livre / "mosaique_master.txt").read_text(encoding="utf-8").strip(), master)
        lancer(mp, "--sortie", self.sortie, "--personne", "Laura", "--photos", "toutes", "--colonnes", "16",
               "--format", "a4-portrait", "--dpi", "100", "--fond-perdu", "0", "--joint", "blanc-fin",
               "--texte", "Laura | 2012 - 2026", "--texte-position", "bas", "--texte-style", "bandeau")
        self.assertTrue((self.livre / "mosaique" / "Mosaique_Laura.pdf").exists())
        from PIL import Image
        with Image.open(self.livre / "mosaique" / "Mosaique_Laura.jpg") as im:
            self.assertEqual(im.width, 16 * (827 // 16))
            self.assertAlmostEqual(im.width / im.info["dpi"][0] * 25.4, 210, delta=1)  # 21 cm de large
        self.assertTrue((self.livre / "mosaique" / "Mosaique_Laura_photos.csv").exists())
        lancer(mp, "--sortie", self.sortie, "--personne", "Laura", "--photos", "toutes", "--colonnes", "100",
               "--format", "a0-portrait", "--apercu")  # aperçu rapide, même en A0
        with Image.open(self.livre / "mosaique" / "Mosaique_Laura_apercu_rapide.jpg") as im:
            self.assertLessEqual(max(im.size), 2400, "aperçu : petite image")
        self.assertTrue((self.livre / "mosaique" / "apercu_application.png").exists())
        # photos d'un autre dossier (hors album), lues sans être modifiées
        autre = self.temp / "autres_photos" / "vacances"
        autre.mkdir(parents=True)
        import random as alea
        hasard = alea.Random(3)
        for i in range(24):
            Image.effect_noise((300, 300), 60).convert("RGB").resize((600, 450)).point(
                lambda v, d=hasard.randint(-80, 80): max(0, min(255, v + d))).save(autre / f"IMG_{i:03d}.jpg", quality=92)
        avant = {f: f.read_bytes() for f in autre.iterdir()}
        lancer(mp, "--sortie", self.sortie, "--personne", "Laura", "--dossier",  # rempli : miniatures du dossier
               str(self.temp / "autres_photos"), "--colonnes", "12", "--format", "a4-portrait", "--dpi", "72",
               "--apercu")
        self.assertEqual({f: f.read_bytes() for f in autre.iterdir()}, avant, "autre dossier : rien de modifié")
        lignes_csv = (self.livre / "mosaique" / "Mosaique_Laura_apercu_rapide.jpg").exists()
        self.assertTrue(lignes_csv)
        # texte : posé dans la zone choisie, jamais sur le visage en « auto »
        fond = Image.new("RGB", (1000, 1400), "#777777")
        bas = mp.poser_texte(fond.copy(), "LAURA", "bas", couleur="blanc", style="aucun")
        zone_bas = sum(bas.crop((0, 1000, 1000, 1400)).convert("L").histogram()[200:])
        self.assertGreater(zone_bas, 500, "texte blanc dans le bas")
        auto = mp.poser_texte(fond.copy(), "LAURA", "auto", couleur="blanc", style="aucun",
                              visages=(200, 900, 800, 1400))  # visage en bas : le texte va en haut
        self.assertGreater(sum(auto.crop((0, 0, 1000, 400)).convert("L").histogram()[200:]), 500)
        self.assertEqual(sum(auto.crop((0, 900, 1000, 1400)).convert("L").histogram()[200:]), 0)
        self.assertEqual(mp.dpi_auto(841, 1189), 150)
        self.assertEqual(mp.dpi_auto(297, 420), 300)

    def test_9_photos_originales_intactes(self):
        self.assertEqual(empreintes(self.photos), self.avant, "aucune photo d'origine modifiée, ajoutée ou supprimée")

    # ---------------------------------------------------------------- outils
    def demarrer(self, module, *arguments):
        """Lance un écran du navigateur dans un fil (sans ouvrir de navigateur) et renvoie son adresse."""
        import webbrowser

        adresses = []
        ancien = webbrowser.open
        webbrowser.open = lambda url, *a, **k: adresses.append(url)
        fil = threading.Thread(target=lancer, args=(module, *arguments), daemon=True)
        fil.start()
        self.fil = fil
        for _ in range(100):
            if adresses:
                break
            time.sleep(0.1)
        webbrowser.open = ancien
        self.assertTrue(adresses, "l'écran ne s'est pas ouvert")
        return adresses[0]

    def attendre_fin(self):
        """L'écran doit se fermer et libérer son port après « Terminer » / « Appliquer »."""
        self.fil.join(timeout=30)
        self.assertFalse(self.fil.is_alive(), "l'écran ne s'est pas fermé")

    @staticmethod
    def poster(url, corps, entetes):
        requete = urllib.request.Request(url, data=json.dumps(corps).encode(), method="POST",
                                         headers={"Content-Type": "application/json", **entetes})
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            return reponse.read()


if __name__ == "__main__":
    unittest.main()
