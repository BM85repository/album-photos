"""Lance tous les tests et affiche à la fin un récapitulatif lisible (un test par ligne, ce qu'il vérifie,
le résultat), puis le verdict. Code de sortie 0 si tout va bien.

  python tests/lancer_tests.py
"""
import sys
import time
import unittest
import warnings
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))

DESCRIPTIONS = {  # nom du test : ce qu'il garantit, en clair
    "test_1_analyse": "Analyse du disque : toutes les photos trouvées, corbeille ignorée, visages détectés",
    "test_2_apercu_et_livre_final": "Aperçus + livre final (PDF, couverture, Excel, plan, PowerPoint), lettre de fin "
                                    "non traduite",
    "test_3_planche_lettres": "Planche lettres-photos (modèles choisis, fond noir, comparaison)",
    "test_4_ecran_de_choix_protege": "Écran de choix des photos : fonctionne et refuse les requêtes sans jeton",
    "test_5_propositions_cliquables": "Écran des propositions : tout refuser puis appliquer ne change rien",
    "test_6_photo_disparue_du_disque": "Photo déplacée/supprimée après l'analyse : ignorée sans arrêter l'outil",
    "test_7_verifier_la_reconnaissance": "Vérifier la reconnaissance : un visage refusé n'est plus attribué",
    "test_8_pas_la_personne_et_repartir_de_zero": "« Pas Laura » dans l'écran de choix + effacer les corrections",
    "test_refus_appris_et_petits_visages": "Reconnaissance : sosies des visages refusés et petits visages écartés",
    "test_seuil_marge_et_refus": "Reconnaissance : seuil, personnes trop proches, inconnus, refus manuels",
    "test_autre_photo_au_meme_chemin": "« Reliquat » : autre photo au même chemin -> nouvelle vignette, pas l'ancienne",
    "test_references_douteuses_ecartees": "Photos de référence douteuses (plusieurs visages, autre personne) : écartées",
    "test_8b_mosaique": "Mosaïque : master à l'écran, poster + PDF, texte hors du visage, autre dossier, A0 à 150 dpi",
    "test_9_photos_originales_intactes": "PHOTOS D'ORIGINE INTACTES (aucune modifiée, ajoutée ni supprimée)",
    "test_doublons_rafale": "Doublons d'une rafale repérés",
    "test_inventaire_ignore_corbeille_et_miniatures": "Inventaire : corbeille, miniatures et non-photos ignorées",
    "test_sortie_dans_photos_refusee": "Dossier de travail dans le dossier des photos : refusé",
    "test_libelles_des_listes": "Application : listes traduites (FR/EN), codes inchangés",
    "test_texte_multiligne_et_reecriture_sans_orphelins": "Application : lettre sur plusieurs lignes bien enregistrée",
    "test_legende_courte_sans_repetition": "Légendes : « Oct 2010 », jour seulement pour Noël / anniversaire",
    "test_legende_photo_seule": "Photo seule sur sa page : légende date + lieu",
    "test_zip_a_partager_sans_donnees_ni_github": "Zip à partager : sans réglages, données ni lien GitHub",
    "test_boutons_de_l_application_connus_du_lanceur": "Application : chaque bouton (dont Maintenance) lance une étape connue",
    "test_placement_par_blocs_memoire_bornee": "Mosaïque : mémoire bornée (calcul par blocs), sans répétition voisine",
    "test_couleurs_bd": "Couleurs des encadrés BD",
    "test_recadrage_garde_les_visages": "Recadrage : les visages ne sont pas coupés",
    "test_recouvrement": "Bulles et encadrés BD : calcul de ce qu'ils cachent",
    "test_visage_au_bord": "Visage déjà coupé sur l'original : repéré",
    "test_dossiers_melanges": "Dossiers photos / travail qui se recouvrent : repérés",
    "test_ecriture_sure_et_sauvegardes": "Paramètres : écriture sûre + 10 sauvegardes au plus",
    "test_fichier_abime_par_windows": "Paramètres abîmés sous Windows (lignes vides fantômes) : réparés",
    "test_lettre_coupee_recollee": "Lettre de fin coupée par une ancienne version : recollée",
    "test_lettre_gardee_apres_plusieurs_enregistrements": "Lettre de fin : jamais effacée par un 2e enregistrement",
    "test_lettre_sur_plusieurs_lignes_lue_en_entier": "Lettre de fin sur plusieurs lignes : lue en entier",
    "test_sortie_dans_les_photos_refusee": "Lanceur : dossier de travail dans les photos refusé",
    "test_creux_du_A_rempli_et_visage_sur_le_plein": "Planche lettres : creux du A rempli, visage sur le plein",
    "test_francais_inchange": "Livre en français : rien n'est traduit",
    "test_texte_ecrit_a_la_main_jamais_traduit": "Textes écrits à la main : jamais traduits",
    "test_textes_de_l_outil_traduits": "Textes de l'outil traduits en anglais (dates, âges, pays, titres)",
}


class Resultat(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.lignes = []
        self.debuts = {}

    def startTest(self, test):
        self.debuts[test.id()] = time.perf_counter()
        super().startTest(test)

    def _noter(self, test, etat, detail=""):
        duree = time.perf_counter() - self.debuts.get(test.id(), time.perf_counter())
        nom = test.id().split(".")[-1]
        self.lignes.append((etat, DESCRIPTIONS.get(nom, nom), duree, detail))

    def addSuccess(self, test):
        super().addSuccess(test)
        self._noter(test, "OK")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._noter(test, "ÉCHEC", str(err[1]).splitlines()[0] if str(err[1]) else "")

    def addError(self, test, err):
        super().addError(test, err)
        self._noter(test, "ERREUR", f"{err[0].__name__}: {str(err[1]).splitlines()[0] if str(err[1]) else ''}")

    def addSkip(self, test, raison):
        super().addSkip(test, raison)
        self._noter(test, "sauté", raison)


def main():
    warnings.simplefilter("ignore", ResourceWarning)
    debut = time.perf_counter()
    suite = unittest.defaultTestLoader.discover(str(ICI))
    executeur = unittest.TextTestRunner(verbosity=2, resultclass=Resultat, warnings="ignore")
    resultat = executeur.run(suite)
    duree = time.perf_counter() - debut
    symboles = {"OK": "✓", "ÉCHEC": "✗", "ERREUR": "✗", "sauté": "–"}
    print("\n" + "=" * 78)
    print("RÉCAPITULATIF DES TESTS")
    print("=" * 78)
    ordre = {"ÉCHEC": 0, "ERREUR": 0, "OK": 1, "sauté": 2}
    for etat, description, d, detail in sorted(resultat.lignes, key=lambda l: ordre[l[0]]):
        print(f" {symboles[etat]} {etat:<7} {description}" + (f"  ({d:.1f} s)" if d >= 1 else ""))
        if detail and etat != "OK":
            print(f"            -> {detail}")
    compte = {e: sum(1 for l in resultat.lignes if l[0] == e) for e in ("OK", "ÉCHEC", "ERREUR", "sauté")}
    print("-" * 78)
    print(f" {len(resultat.lignes)} tests en {duree:.0f} s : {compte['OK']} réussis, "
          f"{compte['ÉCHEC'] + compte['ERREUR']} en échec, {compte['sauté']} sautés")
    if compte["sauté"]:
        print(" (sauté = sans objet sur ce PC, par exemple Tkinter absent de ce Python : ce n'est pas une erreur)")
    if resultat.wasSuccessful():
        print(" VERDICT : tout fonctionne. Les photos d'origine n'ont pas été modifiées.")
    else:
        print(" VERDICT : un ou plusieurs tests ont échoué. Envoyez journal.txt à Claude.")
    print("=" * 78)
    sys.exit(0 if resultat.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
