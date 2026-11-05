#!/usr/bin/env python3
"""lanceur.py - lance les étapes du livre photo à partir de parametres_livre.txt (utilisé par les .bat).

N'utilise que la bibliothèque standard : il fonctionne avant l'installation des dépendances.
Tout ce qui s'affiche est aussi écrit dans journal.txt, à envoyer en cas de problème.

  python lanceur.py installer | analyser | preparer | composer
"""
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
PARAMETRES = ICI / "parametres_livre.txt"
JOURNAL = ICI / "journal.txt"
ETAPES = ("installer", "analyser", "preparer", "choisir", "reduire", "proposer", "appliquer", "apercu", "composer",
          "powerpoint", "choisir_lettres", "lettres", "mosaique", "mosaique_apercu", "tests", "partager", "verifier_visages", "mettre_a_jour")
MODELE = ICI / "parametres_livre.modele.txt"
DEPOT = ""  # copie partagee : pas de mise a jour
BRANCHE = "ccr-5689f376-wfm33a"
DOSSIER_GIT = Path.home() / "AlbumPhotos"  # copie mise à jour automatiquement (pas de droits administrateur)


def journal(texte=""):
    print(texte)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(texte + "\n")


def echec(texte):
    journal("")
    journal("ERREUR : " + texte)
    journal(f"En cas de doute, envoyez le fichier {JOURNAL} à Claude.")
    sys.exit(1)


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


def dossiers_melanges(photos, sortie):
    """Vrai si le dossier de travail est le dossier des photos, dedans, ou le contient."""
    try:
        a, b = Path(photos).resolve(), Path(sortie).resolve()
    except OSError:
        return False
    return a == b or a in b.parents or b in a.parents


def demander(question):
    """Question au clavier ; depuis l'application (fenêtre sans clavier), la réponse est donnée d'avance
    par la variable LANCEUR_REPONSE (vide = abandonner / non)."""
    if os.environ.get("LANCEUR_APP"):
        reponse = os.environ.get("LANCEUR_REPONSE", "")
        journal(f"{question}{reponse}")
        return reponse
    return input(question)


def ouvrir(chemin):
    if hasattr(os, "startfile"):  # Windows : ouvre dans l'Explorateur, le navigateur...
        os.startfile(str(chemin))
    else:
        journal(f"À ouvrir : {chemin}")


def lire_texte_parametres():
    brut = PARAMETRES.read_bytes()
    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:  # Bloc-notes ancien : enregistré en ANSI
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



def lire_parametres():
    if not PARAMETRES.exists():  # première utilisation : on part du modèle (vos réglages ne sont jamais écrasés)
        if not MODELE.exists():
            echec(f"fichier {PARAMETRES.name} introuvable à côté de lanceur.py.")
        shutil.copy(MODELE, PARAMETRES)
        ouvrir(PARAMETRES)
        echec(f"{PARAMETRES.name} vient d'être créé et s'ouvre : remplissez-le, enregistrez, puis relancez.")
    valeurs, lignes_par_cle = {}, {}
    multiligne = None  # TEXTE_FIN / DEDICACE : les lignes suivantes (sans « = ») font partie du texte
    for numero, ligne in enumerate(lire_texte_parametres().splitlines(), 1):
        brute = ligne.strip()
        if multiligne and not brute.startswith("#") and not re.match(r"^[A-Za-z_]{3,}\s*=", brute):
            valeurs[multiligne] += "\n" + ligne.rstrip()
            continue
        multiligne = None
        if brute and not brute.startswith("#") and "=" in brute:
            cle, valeur = brute.split("=", 1)
            cle, valeur = cle.strip().upper(), valeur.strip().strip('"')
            lignes_par_cle.setdefault(cle, []).append(f"ligne {numero} : {valeur}")
            valeurs[cle] = valeur
            if cle in ("TEXTE_FIN", "DEDICACE"):
                multiligne = cle
    for cle in ("TEXTE_FIN", "DEDICACE"):
        if cle in valeurs:
            valeurs[cle] = valeurs[cle].strip()
    doublons = {c: l for c, l in lignes_par_cle.items() if len(l) > 1}
    if doublons:
        echec(f"dans {PARAMETRES}, ces réglages apparaissent plusieurs fois : "
              + " ; ".join(f"{c} ({', '.join(l)})" for c, l in doublons.items())
              + ". Gardez une seule ligne pour chacun, puis enregistrez.")
    journal(f"Paramètres lus dans : {PARAMETRES}")
    for cle, valeur in valeurs.items():  # tous les réglages (sauf les textes longs) : ils servent aussi à les
        if cle not in ("TEXTE_FIN", "DEDICACE"):  # restaurer si parametres_livre.txt était perdu
            journal(f"  {cle} = {valeur}")
    for cle in ("SORTIE", "PERSONNE"):
        if not valeurs.get(cle):
            echec(f"la ligne {cle} = ... est vide dans {PARAMETRES.name}.")
    if valeurs.get("PHOTOS") and dossiers_melanges(valeurs["PHOTOS"], valeurs["SORTIE"]):
        echec(f"SORTIE ({valeurs['SORTIE']}) et PHOTOS ({valeurs['PHOTOS']}) se recouvrent : le dossier de travail "
              "doit être en dehors du dossier des photos (l'outil n'écrit jamais sur le disque de backup). "
              f"Corrigez {PARAMETRES.name}.")
    if "," in valeurs["PERSONNE"]:
        noms = [n.strip() for n in valeurs["PERSONNE"].split(",") if n.strip()]
        echec(f"PERSONNE = une seule personne (celle du livre). Par exemple : PERSONNE = {noms[0]} et "
              f"AVEC = {', '.join(noms[1:])} (les proches à mettre en avant). Corrigez {PARAMETRES.name}.")
    return valeurs


def enregistrer_parametre(cle, valeur):
    """Remplace la ligne CLE = ... du fichier de paramètres (ou l'ajoute)."""
    lignes, remplacee = [], False
    for ligne in lire_texte_parametres().splitlines():
        brute = ligne.strip()
        if not brute.startswith("#") and "=" in brute and brute.split("=", 1)[0].strip().upper() == cle:
            if not remplacee:
                lignes.append(f"{cle} = {valeur}")
                remplacee = True
            continue
        lignes.append(ligne)
    if not remplacee:
        lignes.append(f"{cle} = {valeur}")
    ecrire_sur(PARAMETRES, "\r\n".join(sans_lignes_vides_en_double(lignes)) + "\r\n")
    journal(f"{cle} enregistré dans {PARAMETRES.name} : {valeur}")


def executer(*arguments):
    """Lance un script de l'outil, affiche et journalise sa sortie au fil de l'eau."""
    commande = [sys.executable, "-u", *map(str, arguments)]
    journal("> " + " ".join(f'"{a}"' if " " in str(a) else str(a) for a in commande[2:]))
    environnement = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    processus = subprocess.Popen(commande, cwd=ICI, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", env=environnement)
    dernieres = []
    dernier_palier = {}
    for ligne in processus.stdout:
        if ligne.startswith("PROGRESSION "):  # avancement : pour la barre de l'application, pas pour le journal
            if os.environ.get("LANCEUR_APP"):
                print(ligne.rstrip(), flush=True)
            else:  # fenêtre noire (.bat) : une ligne lisible tous les 5 %
                compte, _, etape = ligne[12:].strip().partition(" ")
                fait, _, total = compte.partition("/")
                if total.isdigit() and int(total):
                    palier = int(fait) * 20 // int(total)
                    if dernier_palier.get(etape) != palier:
                        dernier_palier[etape] = palier
                        print(f"  {etape} : {fait} / {total} ({int(fait) * 100 // int(total)} %)", flush=True)
                elif fait.isdigit() and int(fait) % 5000 == 0:
                    print(f"  {etape} : {fait}...", flush=True)
            continue
        journal(ligne.rstrip())
        dernieres = (dernieres + [ligne])[-30:]
    processus.wait()
    if processus.returncode:
        if any("ModuleNotFoundError" in l for l in dernieres):
            echec("une bibliothèque manque : relancez 1_installer.bat.")
        if any("urlopen error" in l or "HTTP Error" in l for l in dernieres):
            echec("le téléchargement des modèles de visages a échoué : vérifiez la connexion Internet.")
        echec("l'étape s'est arrêtée (voir le message juste au-dessus).")


def personnes(p):
    noms = [n for n in [(p.get("PERSONNE") or "").strip()] if n] + [n.strip() for n in p.get("AVEC", "").split(",")
                                                                   if n.strip()]
    return noms


def etape_installer(p):
    if sys.version_info < (3, 9):
        echec(f"Python {sys.version.split()[0]} est trop ancien : installez Python 3.11 ou plus récent.")
    journal(f"Python {sys.version.split()[0]} trouvé : {sys.executable}")
    executer("-m", "pip", "install", "-r", ICI / "requirements.txt")
    import hashlib
    (ICI / ".bibliotheques_installees").write_text(
        hashlib.md5((ICI / "requirements.txt").read_bytes() + sys.version.encode()).hexdigest())
    famille = Path(p["SORTIE"]) / "famille"
    for nom in personnes(p):
        (famille / nom).mkdir(parents=True, exist_ok=True)
    journal("")
    journal("Installation terminée.")
    journal(f"Étape suivante : mettez 3 à 10 photos nettes du visage de chaque personne dans {famille}\\<Prénom>")
    journal("(à des âges différents, bébé compris), puis lancez 2_analyser_disque.bat.")
    ouvrir(famille)


def etape_analyser(p):
    photos = Path(p.get("PHOTOS", ""))
    while not p.get("PHOTOS") or not photos.is_dir():
        journal(f"Dossier de photos introuvable : « {p.get('PHOTOS', '')} ».")
        journal("Astuce : dans l'Explorateur, clic droit sur le dossier > « Copier en tant que chemin d'accès »,")
        journal("puis clic droit dans cette fenêtre pour coller.")
        saisie = demander("Chemin du dossier de photos (Entrée seule pour abandonner) : ").strip().strip('"')
        if not saisie:
            echec("aucun dossier de photos.")
        p["PHOTOS"], photos = saisie, Path(saisie)
        if photos.is_dir():
            enregistrer_parametre("PHOTOS", saisie)
    journal("Analyse en lecture seule : peut durer plusieurs heures. Vous pouvez fermer la fenêtre et relancer,")
    journal("le travail déjà fait est conservé.")
    executer("album_famille.py", "--sortie", p["SORTIE"], "analyser", photos)
    executer("album_famille.py", "--sortie", p["SORTIE"], "trier")
    journal("")
    journal("Analyse terminée. Étape suivante : 3_preparer_selection.bat")


def etape_preparer(p):
    famille = Path(p["SORTIE"]) / "famille"
    for nom in personnes(p):
        dossier = next((d for d in famille.glob("*") if d.is_dir() and d.name.lower() == nom.lower()), None)
        if dossier is None or not any(f.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic") for f in dossier.iterdir()):
            echec(f"aucune photo de référence pour {nom} : ajoutez-en dans {famille / nom}.")
    arguments = ["livre_photo.py", "--sortie", p["SORTIE"], "preparer", "--personne", p["PERSONNE"],
                 "--famille", famille, "--max", p.get("MAX") or "150", *seuil(p)]
    if p.get("AVEC"):
        arguments += ["--avec", p["AVEC"]]
    if p.get("NAISSANCE"):
        arguments += ["--naissance", p["NAISSANCE"]]
    if p.get("PAYS"):
        arguments += ["--pays-maison", p["PAYS"]]
    selection = Path(p["SORTIE"]) / f"livre_{p['PERSONNE']}" / "selection_livre.csv"
    if selection.exists():
        reponse = demander(f"Une sélection existe déjà pour {p['PERSONNE']}. La refaire ? "
                           "Vos choix actuels seront remplacés (o/N) : ").strip().lower()
        if reponse not in ("o", "oui"):
            journal("Sélection actuelle gardée : l'écran de choix des photos s'ouvre.")
            etape_choisir(p)
            return
        arguments.append("--ecraser")
    executer(*arguments)
    journal("")
    journal("Sélection proposée. L'écran de choix s'ouvre dans le navigateur : un clic garde ou retire une photo")
    journal("(vert = gardée), puis « Terminer » dans la page. La planche figée planche_livre.html reste disponible")
    journal(f"dans {selection.parent} pour une vue d'ensemble.")
    etape_choisir(p)


def langue_ecran(p):
    """Écrans de choix dans le navigateur : dans la langue de l'application (LANGUE = fr ou en)."""
    return ["--langue", "en"] if (p.get("LANGUE") or "fr").lower() == "en" else []


def seuil(p):
    """Exigence de ressemblance des visages (SEUIL_VISAGE), si elle est réglée."""
    valeur = (p.get("SEUIL_VISAGE") or "").replace(",", ".").strip()
    try:
        return ["--seuil", str(float(valeur))] if valeur else []
    except ValueError:
        echec(f"SEUIL_VISAGE = {valeur} : un nombre entre 0.30 et 0.60 est attendu (ex. 0.45).")


def etape_verifier_visages(p):
    """Écran pour corriger la reconnaissance de la personne du livre (visages confirmés ou refusés)."""
    journal("Vérification de la reconnaissance : un clic confirme (c'est bien la personne) ou refuse chaque visage.")
    journal("Commencez par les moins sûrs (en haut). Ensuite, relancez « Préparer la sélection ».")
    executer("verifier_visages.py", *langue_ecran(p), "--sortie", p["SORTIE"], "--personne", p["PERSONNE"],
             "--famille", Path(p["SORTIE"]) / "famille", *seuil(p))
    journal("")
    journal("Étape suivante : « Préparer la sélection » (vos corrections servent désormais de références).")


def etape_choisir(p):
    journal("L'écran de sélection s'ouvre dans le navigateur. Un clic garde ou retire une photo (enregistré aussitôt).")
    journal("Laissez cette fenêtre ouverte pendant la sélection ; cliquez sur « Terminer » dans la page pour finir.")
    executer("choisir_photos.py", *langue_ecran(p), "--sortie", p["SORTIE"], "--personne", p["PERSONNE"], "--max", p.get("MAX") or "150")
    journal("")
    journal("Étape suivante : 4_apercu_3_ambiances.bat")


def etape_reduire(p):
    journal("Réduire la sélection : seules les photos gardées s'affichent, avec les meilleures candidates au retrait")
    journal("(presque identiques, faible définition, peu nettes, souvenirs trop chargés). Clic = retirer / remettre.")
    executer("choisir_photos.py", *langue_ecran(p), "--sortie", p["SORTIE"], "--personne", p["PERSONNE"], "--max", p.get("MAX") or "150",
             "--reduire")
    journal("")
    journal("Étape suivante : 4_apercu_3_ambiances.bat")


def etape_proposer(p):
    arguments = ["livre_photo.py", "--sortie", p["SORTIE"], "proposer", "--personne", p["PERSONNE"], *seuil(p)]
    if p.get("AVEC"):
        arguments += ["--avec", p["AVEC"], "--famille", Path(p["SORTIE"]) / "famille"]
    executer(*arguments)
    journal("")
    journal("Rien n'est encore changé. L'écran des propositions s'ouvre dans le navigateur : un clic accepte ou")
    journal("refuse chaque proposition, puis « Appliquer les choix » met à jour la sélection du livre.")
    etape_appliquer(p)


def etape_appliquer(p):
    """Écran cliquable des propositions (plus besoin d'Excel) ; applique les choix à la sélection du livre."""
    executer("valider_propositions.py", *langue_ecran(p), "--sortie", p["SORTIE"], "--personne", p["PERSONNE"])
    journal("")
    journal("Étape suivante : « Aperçus des ambiances » (4_apercu_3_ambiances.bat).")


def etape_powerpoint(p):
    etape_composer(p, pptx=True)


def etape_apercu(p):
    etape_composer(p, ambiance="toutes", apercus=os.environ.get("LANCEUR_APERCUS") or p.get("APERCUS", ""))


def etape_composer(p, ambiance=None, pptx=False, apercus=""):
    ambiance = ambiance or (p.get("AMBIANCE") or "").lower()
    ambiances = ("elegant", "tendre", "carnet", "prestige", "prestige-compact", "prestige-mosaique",
                 "prestige-mosaique-bd", "magazine", "bd", "bd-photo")
    if ambiance not in ambiances + ("toutes",):
        echec(f"choisissez une ambiance dans {PARAMETRES.name} : AMBIANCE = {', '.join(ambiances)} "
              "(regardez d'abord les aperçus avec 4_apercu_3_ambiances.bat).")
    arguments = ["livre_photo.py", "--sortie", p["SORTIE"], "composer", "--personne", p["PERSONNE"],
                 "--ambiance", ambiance,
                 "--format", p.get("FORMAT") or "carre30", "--max", p.get("MAX") or "150"]
    if p.get("NAISSANCE"):
        arguments += ["--naissance", p["NAISSANCE"]]
    if p.get("DEDICACE"):
        arguments += ["--dedicace", p["DEDICACE"]]
    if p.get("PAGES"):
        arguments += ["--pages", p["PAGES"]]
    if p.get("ORGANISATION"):
        arguments += ["--organisation", p["ORGANISATION"].lower()]
    if p.get("PAYS"):
        arguments += ["--pays-maison", p["PAYS"]]
    if p.get("RELIURE"):
        arguments += ["--reliure", p["RELIURE"].lower()]
    if apercus:  # seulement certains aperçus (les autres restent tels quels)
        arguments += ["--apercus", apercus.replace(" ", "")]
    if (p.get("LANGUE_LIVRE") or "fr").lower() == "en":
        arguments += ["--langue", "en"]
    if p.get("PIED_DE_PAGE"):
        arguments += ["--pied-de-page", p["PIED_DE_PAGE"],
                      "--pied-pages", (p.get("PIED_PAGES") or "toutes").lower()]
    texte_fin = ICI / "texte_fin.txt"  # texte de fin sur plusieurs lignes (écrit par l'application)
    actuel = texte_fin.read_text(encoding="utf-8-sig") if texte_fin.exists() else ""
    complet = texte_fin_complet(actuel, p.get("TEXTE_FIN", ""))
    if complet and complet != actuel.strip():
        texte_fin.write_text(complet + "\n", encoding="utf-8")
    if texte_fin.exists() and texte_fin.read_text(encoding="utf-8-sig").strip():
        contenu = texte_fin.read_text(encoding="utf-8-sig").strip()
        journal(f"Texte de fin : {len(contenu.splitlines())} ligne(s), {len(contenu)} caractères ({texte_fin.name}).")
        arguments += ["--mot-fin-fichier", texte_fin]
    if p.get("SYMBOLE_FIN"):
        arguments += ["--symbole-fin", p["SYMBOLE_FIN"].lower()]
    if p.get("BD_COULEUR"):
        arguments += ["--couleur-bd", p["BD_COULEUR"]]
    if pptx:
        arguments.append("--pptx")
    arguments += page_lettres_du_livre(p)
    executer(*arguments)
    journal("")
    if ambiance == "toutes":
        journal("Les 10 aperçus (Apercu_..._elegant, _tendre, _carnet, _prestige, _prestige-compact, _prestige-mosaique, "
                "_prestige-mosaique-bd, _magazine, _bd, _bd-photo.pdf) sont dans le dossier du livre.")
        journal(f"Choisissez, écrivez AMBIANCE = ... dans {PARAMETRES.name}, puis lancez 5_livre_final.bat.")
    else:
        journal(f"Livre terminé. Tout ce qu'il faut remettre à l'imprimeur est dans le dossier imprimeur_{ambiance} :")
        journal("PDF à imprimer, photos numérotées dans l'ordre du livre, Instructions_imprimeur.xlsx, Plan_de_montage.pdf.")
        journal("Lisez rapport_impression.txt avant l'envoi.")
    dossier = Path(p["SORTIE"]) / f"livre_{p['PERSONNE']}"
    ouvrir(dossier / f"imprimeur_{ambiance}" if ambiance != "toutes" else dossier)


def git(*arguments, cwd=ICI):
    """git sans jamais attendre une saisie au clavier invisible (depuis l'application, il n'y a pas de console) :
    s'il faut se connecter à GitHub, c'est la fenêtre de connexion de Git qui s'ouvre ; sinon erreur claire."""
    environnement = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        return subprocess.run(["git", *arguments], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=environnement, timeout=600, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        echec("GitHub ne répond pas (plus de 10 minutes) : vérifiez la connexion Internet, puis relancez.")


def est_depot_outil(dossier):
    """Vrai seulement si ce dossier est la copie Git de l'outil lui-même (et pas un autre dépôt Git
    qui contiendrait le dossier, par exemple un dossier de documents suivi par Git)."""
    haut = git("rev-parse", "--show-toplevel", cwd=dossier)
    if haut.returncode:
        return False
    origine = git("remote", "get-url", "origin", cwd=dossier).stdout
    racine = Path(haut.stdout.strip())
    try:
        meme = os.path.samefile(racine / "outils" / "albums-famille", dossier)
    except OSError:
        meme = False
    return meme and "ClaudeCamera" in origine


def mettre_de_cote_modifications():
    """Fichiers de l'outil modifiés à la main (souvent : réglages saisis dans parametres_livre.modele.txt) :
    on les copie dans le dossier modifications_locales_<date> avant de remettre la version d'origine, pour que la mise
    à jour passe. Rien n'est perdu ; si parametres_livre.txt n'existe pas, le modèle modifié le devient."""
    racine = Path(git("rev-parse", "--show-toplevel").stdout.strip())
    modifies = [l[3:].strip().strip('"') for l in git("status", "--porcelain").stdout.splitlines()
                if l[:2].strip() and not l.startswith("??")]
    if not modifies:
        return
    sauvegarde = ICI / f"modifications_locales_{dt.datetime.now():%Y%m%d-%H%M}"
    sauvegarde.mkdir(exist_ok=True)
    for relatif in modifies:
        fichier = racine / relatif
        if fichier.is_file():
            shutil.copy2(fichier, sauvegarde / fichier.name)
            if fichier.name == MODELE.name and not PARAMETRES.exists():
                shutil.copy2(fichier, PARAMETRES)  # vos réglages étaient dans le modèle : ils deviennent les vôtres
                journal(f"Vos réglages saisis dans {MODELE.name} sont repris dans {PARAMETRES.name}.")
    git("checkout", "--", *modifies, cwd=racine)
    journal(f"Fichiers de l'outil modifiés à la main, copiés dans {sauvegarde.name} puis remis d'origine : "
            + ", ".join(Path(m).name for m in modifies))
    if MODELE.name in [Path(m).name for m in modifies]:
        journal(f"Rappel : vos réglages vont dans {PARAMETRES.name} (le modèle est remplacé à chaque mise à jour).")


BLOC_LETTRES = """
# ---------------- Planche lettres-photos (7_planche_lettres.bat) ----------------
# Mot écrit en lettres-photos (vide = le prénom de PERSONNE). Une photo par lettre, de petite à maintenant.
# Pour choisir les photos vous-même : 7a_choisir_photos_lettres.bat (un clic par photo).
LETTRES_MOT =
# Texte libre au-dessus et au-dessous (vides = aucun)
LETTRES_HAUT = On t'aime
LETTRES_BAS = De la part de Papa
# Format : a4-paysage, a3-paysage, 30x20, 40x30, a4-portrait
LETTRES_FORMAT = a4-paysage
# Police des lettres : toutes (chaque modèle a la sienne), arial-black, impact, georgia, segoe-black
LETTRES_POLICE = toutes
# Taille des lettres en % de la plus grande possible (100 = maximum, 80 = plus d'air)
LETTRES_TAILLE = 100
# Creux des lettres (triangle du A, boucle du R, du O) : non = lettres pleines, la photo se voit en entier
LETTRES_CREUX = non
# Modèles à fabriquer : tous, ou des numéros (ex. 3 pour seulement le modèle 3, ou 1,3)
LETTRES_MODELES = tous
# Couleur du fond (vide = celle de chaque modèle) : noir, blanc, creme, gris-clair, anthracite, bleu-nuit,
# marine, bleu-ciel, rose, rose-poudre, lavande, vert-sauge, beige, kraft, bordeaux... ou un code #RRGGBB
LETTRES_FOND =
# Couleur du contour des lettres (vide = celle du modèle ; aucun = sans contour) : or, argent, blanc, noir...
LETTRES_CONTOUR =
# Couleur des textes (vide = automatique : clair sur fond sombre, foncé sur fond clair)
LETTRES_TEXTE =
# Photos : couleur, noir-et-blanc ou sepia
LETTRES_TEINTE = couleur
# Planche lettres dans le livre photo : non, premiere-page (à la place de la page de titre),
# ou premiere-et-derniere (aussi juste avant la dernière page)
LETTRES_DANS_LIVRE = non
# Modèle de planche utilisé dans le livre (1 à 6, voir Comparaison_modeles.jpg)
LETTRES_MODELE_LIVRE = 1
"""


def morceaux_manquants(p):
    """Les réglages LETTRES_... (avec leurs lignes d'explication) absents du fichier de paramètres."""
    morceaux, courant = [], ""
    for ligne in BLOC_LETTRES.strip("\n").split("\n"):
        courant += ligne + "\n"
        if not ligne.startswith("#"):
            cle = ligne.split("=", 1)[0].strip()
            if cle not in p:
                morceaux.append(courant)
            courant = ""
    return morceaux


def etape_mosaique_apercu(p):
    etape_mosaique(p, apercu=True)


def etape_mosaique(p, apercu=False):
    """Mosaïque : la photo master reconstituée avec les petites photos de l'album."""
    arguments = ["mosaique_photos.py", "--sortie", p["SORTIE"], "--personne", p["PERSONNE"],
                 "--format", (p.get("MOSAIQUE_FORMAT") or "a3-portrait").lower(),
                 "--colonnes", p.get("MOSAIQUE_COLONNES") or "60",
                 "--melange", (p.get("MOSAIQUE_MELANGE") or "0.35").replace(",", "."),
                 "--photos", (p.get("MOSAIQUE_PHOTOS") or "gardees").lower(),
                 "--dpi", p.get("MOSAIQUE_DPI") or "auto"]
    if p.get("MOSAIQUE_MASTER"):
        arguments += ["--master", p["MOSAIQUE_MASTER"].strip().strip('"')]
    if p.get("MOSAIQUE_DOSSIER"):
        arguments += ["--dossier", p["MOSAIQUE_DOSSIER"].strip().strip('"')]
    for cle, option in (("MOSAIQUE_FONDU", "--fondu"), ("MOSAIQUE_TEINTE", "--teinte"), ("MOSAIQUE_JOINT", "--joint"),
                        ("MOSAIQUE_ECART", "--ecart"), ("MOSAIQUE_FOND_PERDU", "--fond-perdu"),
                        ("MOSAIQUE_TEXTE", "--texte"), ("MOSAIQUE_TEXTE_POSITION", "--texte-position"),
                        ("MOSAIQUE_TEXTE_POLICE", "--texte-police"), ("MOSAIQUE_TEXTE_COULEUR", "--texte-couleur"),
                        ("MOSAIQUE_TEXTE_TAILLE", "--texte-taille"), ("MOSAIQUE_TEXTE_STYLE", "--texte-style")):
        valeur = (p.get(cle) or "").strip()
        if valeur:
            arguments += [option, valeur.replace(",", ".") if cle in ("MOSAIQUE_TEINTE", "MOSAIQUE_FOND_PERDU")
                          else valeur if cle == "MOSAIQUE_TEXTE" else valeur.lower()]
    if apercu:
        arguments.append("--apercu")
    executer(*arguments)
    if apercu:
        if not os.environ.get("LANCEUR_APP"):  # dans l'application, l'aperçu s'affiche dans l'onglet Mosaïque
            dossier = Path(p["SORTIE"]) / f"livre_{p['PERSONNE']}" / "mosaique"
            ouvrir(next(dossier.glob("Mosaique_*_apercu_rapide.jpg"), dossier))
        return
    dossier = Path(p["SORTIE"]) / f"livre_{p['PERSONNE']}" / "mosaique"
    journal("")
    journal(f"Mosaïque dans : {dossier} (le grand JPEG est pour l'imprimeur ; _detail.jpg montre le rendu de près).")
    ouvrir(next(dossier.glob("Mosaique_*_apercu.jpg"), dossier))


def etape_choisir_lettres(p):
    mot = p.get("LETTRES_MOT") or p["PERSONNE"]
    journal(f"Choix des photos de la planche « {mot.upper()} » : un clic sur une photo la choisit pour une lettre.")
    journal("Elles sont placées par date (la plus ancienne sur la 1re lettre). La sélection du livre n'est pas modifiée.")
    journal("Laissez cette fenêtre ouverte ; cliquez sur « Terminer » dans la page pour finir.")
    executer("choisir_photos.py", *langue_ecran(p), "--sortie", p["SORTIE"], "--personne", p["PERSONNE"], "--lettres", mot)
    journal("")
    journal("Étape suivante : 7_planche_lettres.bat")


def arguments_lettres(p, modeles=None):
    arguments = ["planche_lettres.py", "--sortie", p["SORTIE"], "--personne", p["PERSONNE"],
                 "--haut", p.get("LETTRES_HAUT", ""), "--bas", p.get("LETTRES_BAS", ""),
                 "--format", p.get("LETTRES_FORMAT") or "a4-paysage", "--police", p.get("LETTRES_POLICE") or "toutes",
                 "--taille", p.get("LETTRES_TAILLE") or "100"]
    if (p.get("LETTRES_CREUX") or "non").lower() in ("oui", "1", "x"):
        arguments.append("--evider")
    for cle, option in (("LETTRES_FOND", "--fond"), ("LETTRES_CONTOUR", "--contour"), ("LETTRES_TEXTE", "--texte"),
                        ("LETTRES_TEINTE", "--teinte")):
        if p.get(cle):
            arguments += [option, p[cle]]
    if modeles or p.get("LETTRES_MODELES"):
        arguments += ["--modeles", modeles or p["LETTRES_MODELES"]]
    if p.get("LETTRES_MOT"):
        arguments += ["--mot", p["LETTRES_MOT"]]
    if (p.get("LANGUE_LIVRE") or "fr").lower() == "en":
        arguments += ["--langue", "en"]
    if p.get("NAISSANCE"):
        arguments += ["--naissance", p["NAISSANCE"]]
    return arguments


def page_lettres_du_livre(p):
    """Option LETTRES_DANS_LIVRE : fabrique la planche lettres au format du livre ; renvoie les options pour
    livre_photo.py composer (rien si l'option est à non)."""
    choix = (p.get("LETTRES_DANS_LIVRE") or "non").strip().lower()
    if choix in ("", "non", "0"):
        return []
    if choix not in ("premiere-page", "premiere-et-derniere"):
        echec(f"LETTRES_DANS_LIVRE = non, premiere-page ou premiere-et-derniere (et pas « {choix} »).")
    image = Path(p["SORTIE"]) / f"livre_{p['PERSONNE']}" / "lettres" / "Page_lettres_livre.jpg"
    arguments = [*arguments_lettres(p, modeles=p.get("LETTRES_MODELE_LIVRE") or "1"), "--page-livre", image,
                 "--format-livre", p.get("FORMAT") or "carre30"]
    # déjà faite avec les mêmes réglages et les mêmes photos : on la réutilise (gain de 20 s à 1 min)
    dossier = image.parent.parent
    sources = [dossier / "lettres_photos.csv", dossier / "selection_livre.csv", ICI / "planche_lettres.py"]
    signature = " | ".join(map(str, arguments)) + " | " + " ".join(
        str(int(f.stat().st_mtime)) for f in sources if f.exists())
    repere = image.with_suffix(".reglages.txt")
    if image.exists() and repere.exists() and repere.read_text(encoding="utf-8") == signature:
        journal(f"Planche lettres de la première page : inchangée, réutilisée ({image.name}).")
    else:
        journal("Planche lettres-photos pour la première page du livre :")
        executer(*arguments)
        repere.write_text(signature, encoding="utf-8")
    return ["--page-lettres", image] + (["--lettres-fin"] if choix == "premiere-et-derniere" else [])


def etape_lettres(p):
    manquants = morceaux_manquants(p)
    if manquants:  # fichier de paramètres plus ancien que ces réglages : on les ajoute à la fin
        with open(PARAMETRES, "a", encoding="utf-8", newline="") as f:
            f.write(("\n" + "".join(manquants)).replace("\n", "\r\n"))
        journal(f"Nouveaux réglages de la planche lettres ajoutés à la fin de {PARAMETRES.name} (modifiables).")
        p = lire_parametres()
    executer(*arguments_lettres(p))
    dossier = Path(p["SORTIE"]) / f"livre_{p['PERSONNE']}" / "lettres"
    journal("")
    journal(f"6 modèles (JPEG 300 dpi + PDF) dans : {dossier}")
    journal("Comparaison_modeles.jpg s'ouvre : choisissez, puis donnez le JPEG ou le PDF du modèle à l'imprimeur.")
    ouvrir(dossier / "Comparaison_modeles.jpg")


def bibliotheques(dossier):
    """pip seulement si la liste des bibliothèques a changé depuis la dernière installation réussie (pip met
    30 s à 1 min à tout vérifier, même quand il n'y a rien à faire)."""
    import hashlib

    liste = dossier / "requirements.txt"
    empreinte = hashlib.md5(liste.read_bytes() + sys.version.encode()).hexdigest()
    repere = dossier / ".bibliotheques_installees"
    if repere.exists() and repere.read_text().strip() == empreinte:
        journal("Bibliothèques : déjà à jour.")
        return
    journal("Installation ou mise à jour des bibliothèques (1 à 3 minutes)...")
    executer("-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", liste)
    repere.write_text(empreinte)


def verifier_disque_analyse(p):
    """Avertit si PHOTOS ne désigne pas le disque réellement analysé (les étapes utilisent toujours le disque
    analysé, noté dans la base) ou si ce disque n'est pas branché."""
    import sqlite3

    base = Path(p["SORTIE"]) / "base.sqlite"
    if not base.exists():
        return
    try:
        with sqlite3.connect(f"file:{base}?mode=ro", uri=True) as connexion:
            ligne = connexion.execute("SELECT valeur FROM meta WHERE cle = 'racine'").fetchone()
    except sqlite3.Error:
        return
    racine = ligne[0] if ligne else ""
    if not racine:
        return
    if p.get("PHOTOS") and Path(p["PHOTOS"]).resolve() != Path(racine).resolve():
        if not Path(p["PHOTOS"]).exists() and Path(racine).exists():  # simple réglage périmé : rien de grave
            journal(f"Info : le réglage PHOTOS ({p['PHOTOS']}) n'existe pas sur ce PC ; l'outil utilise le dossier "
                    f"analysé, {racine}. Pour ne plus voir ce message : Paramètres > Photos = {racine}.")
        else:
            journal(f"ATTENTION : PHOTOS = {p['PHOTOS']}, mais le disque analysé est {racine} : c'est lui qui est "
                    "utilisé. Si vos photos ont changé de place, corrigez PHOTOS puis relancez « Analyser le disque ».")
    if not Path(racine).exists():
        journal(f"ATTENTION : le disque des photos ({racine}) n'est pas branché ou a changé de lettre.")


def etape_tests(p):
    """Tests automatiques de l'outil sur un petit disque de photos de synthèse créé dans un dossier temporaire :
    vos photos, vos réglages et vos livres ne sont pas utilisés."""
    journal("Tests automatiques (1 à 3 minutes) : photos de synthèse dans un dossier temporaire, vos photos ne sont")
    journal("pas utilisées. Chaque test affiche « ok » ; à la fin : « OK » si tout va bien.")
    executer("-W", "ignore::ResourceWarning", ICI / "tests" / "lancer_tests.py")  # récapitulatif à la fin
    journal("")
    journal("Tous les tests sont passés : l'outil fonctionne sur ce PC.")


def mode_admin():
    """Administrateur = copie Git de l'outil (celle de l'auteur) ou fichier admin.txt à côté du lanceur.
    Une copie partagée (zip) n'a ni l'un ni l'autre : ni mise à jour depuis GitHub, ni zip à partager."""
    return bool(DEPOT) and ((ICI / "admin.txt").exists() or (ICI.parent.parent / ".git").exists())


FICHIERS_PRIVES = {"parametres_livre.txt", "texte_fin.txt", "journal.txt", ".bibliotheques_installees", "admin.txt",
                   "0_mettre_a_jour.bat"}
DOSSIERS_PRIVES = {"__pycache__", "sauvegardes_parametres", ".git"}

LISEZ_MOI = """ALBUM PHOTOS - livres photo de famille, automatiques
=====================================================

L'outil parcourt un disque de photos en LECTURE SEULE (vos photos ne sont jamais modifiées, déplacées ni
supprimées), reconnaît les visages de la famille, choisit les plus belles photos d'une personne et fabrique un
livre photo prêt pour l'imprimeur (10 styles), une planche lettres-photos et une mosaïque de photos (A4 à A0).
Tout ce qu'il crée va dans un dossier de travail, par exemple C:\\AlbumsFamille.

INSTALLATION (Windows, une seule fois)
1. Installez Python : https://www.python.org/downloads/
   Sur le premier écran, cochez « Add python.exe to PATH ». Redémarrez le PC.
2. Décompressez ce zip (par exemple dans Documents).
3. Double-cliquez sur Installer_application.bat : bibliothèques (quelques minutes la 1re fois), icône
   « Album Photos » sur le Bureau, puis l'application s'ouvre.
4. Bouton « 🔧 Maintenance » > « Vérifier l'outil (tests) » : contrôle que tout fonctionne (1 à 3 min).

PREMIER LIVRE
1. Onglet Paramètres : dossier des photos, dossier de travail, personne du livre, proches, date de naissance.
2. « 🔧 Maintenance » > « Installer / réparer » crée un dossier par personne dans <dossier de travail>\\famille :
   mettez-y 10 à 20 photos nettes du visage de chaque personne (une par âge, seule sur la photo).
3. « Analyser le disque » (plusieurs heures la 1re fois, une seule fois pour toute la famille).
4. « Préparer la sélection », « Choisir les photos », « Aperçus des ambiances », puis « Livre final ».
Le guide complet est dans l'onglet Aide (et Guide_application.html / .pdf ; en anglais : Guide_application_EN).

À SAVOIR
- Les modèles de reconnaissance des visages se téléchargent automatiquement à la 1re analyse (Internet une fois).
- Cette copie ne se met pas à jour toute seule : demandez une nouvelle version à la personne qui vous l'a donnée.
"""


def etape_partager(p):
    """Zip à partager : copie propre de l'outil, sans réglages ni données personnelles, sans lien vers le dépôt
    GitHub (la copie partagée ne peut pas se mettre à jour depuis votre dépôt). Réservé à l'administrateur."""
    import re
    import zipfile
    if not mode_admin():
        echec("fabrication du zip réservée à l'auteur de l'outil.")
    sortie = Path(p.get("SORTIE") or Path.home())
    sortie.mkdir(parents=True, exist_ok=True)
    cible = sortie / f"AlbumPhotos_partage_{dt.datetime.now():%Y%m%d}.zip"
    nombre = 0
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as archive:
        for dossier, sous, fichiers in os.walk(ICI):
            sous[:] = sorted(d for d in sous if d not in DOSSIERS_PRIVES and not d.startswith("modifications_locales_"))
            for nom in sorted(fichiers):
                chemin = Path(dossier) / nom
                relatif = chemin.relative_to(ICI)
                if (nom in FICHIERS_PRIVES or nom.endswith((".tmp", ".pyc")) or re.match(r"\d{8}-Photos-\d+_(Guide|Guide-livre|Demarrage)\.md$", nom)
                        and "application" not in nom):
                    continue
                contenu = chemin.read_bytes()
                if nom == "lanceur.py":  # plus de lien vers votre dépôt GitHub
                    contenu = re.sub(rb'^DEPOT = ".*"$', b'DEPOT = ""  # copie partagee : pas de mise a jour',
                                     contenu, flags=re.M)
                if nom == MODELE.name:  # modèle de réglages vierge
                    texte = contenu.decode("utf-8-sig")
                    for cle, valeur in (("PHOTOS", ""), ("PERSONNE", ""), ("AVEC", ""), ("NAISSANCE", ""),
                                        ("PAYS", "FR"), ("MOSAIQUE_MASTER", ""), ("MOSAIQUE_TEXTE", ""),
                                        ("MOSAIQUE_DOSSIER", "")):
                        texte = re.sub(rf"^{cle} = .*$", f"{cle} = {valeur}".rstrip(), texte, flags=re.M)
                    contenu = ("\ufeff" + texte).encode("utf-8")
                archive.writestr(f"AlbumPhotos/{relatif.as_posix()}", contenu)
                nombre += 1
        archive.writestr("AlbumPhotos/LISEZ-MOI.txt", ("\ufeff" + LISEZ_MOI.replace("\n", "\r\n")).encode("utf-8"))
    journal(f"Zip à partager : {cible} ({nombre + 1} fichiers, {cible.stat().st_size // 1024} Ko).")
    journal("Sans vos réglages, votre lettre de fin, votre base de visages, vos photos ni le lien vers votre dépôt "
            "GitHub ; la mise à jour y est désactivée.")
    ouvrir(sortie)


def etape_mettre_a_jour():
    """Récupère la dernière version de l'outil depuis GitHub, sans toucher à parametres_livre.txt
    ni aux livres (dans SORTIE). La première fois, crée une copie Git dans %USERPROFILE%\\AlbumPhotos."""
    if not DEPOT:
        echec("cette copie de l'outil a été partagée : elle ne se met pas à jour toute seule. Demandez une nouvelle "
              "version à la personne qui vous l'a donnée.")
    if not shutil.which("git"):
        journal("Git n'est pas installé : installation (une seule fois)...")
        if shutil.which("winget"):
            subprocess.run(["winget", "install", "--id", "Git.Git", "-e", "--source", "winget",
                            "--accept-package-agreements", "--accept-source-agreements"])
            echec("Git vient d'être installé : fermez cette fenêtre, puis relancez 0_mettre_a_jour.bat.")
        ouvrir("https://git-scm.com/download/win")
        echec("installez Git depuis la page qui s'ouvre (options par défaut), puis relancez 0_mettre_a_jour.bat.")
    if est_depot_outil(ICI):
        mettre_de_cote_modifications()
        journal("Récupération de la nouvelle version sur GitHub...")
        recuperation = git("pull", "--ff-only", "origin", BRANCHE)
        journal((recuperation.stdout + recuperation.stderr).strip())
        if recuperation.returncode:
            echec("la mise à jour a échoué (voir le message ci-dessus).")
        bibliotheques(ICI)
        journal("")
        journal("Outil à jour. Vos paramètres et vos livres n'ont pas été touchés.")
        return
    # dossier issu d'un ZIP : on crée une fois pour toutes une copie Git, mise à jour ensuite en un clic
    destination = DOSSIER_GIT
    if not (destination / ".git").exists():
        journal(f"Première mise à jour : copie de l'outil dans {destination}")
        journal("(une fenêtre GitHub peut s'ouvrir pour vous connecter : le dépôt est privé).")
        clone = git("clone", "--branch", BRANCHE, DEPOT, str(destination), cwd=Path.home())
        journal((clone.stdout + clone.stderr).strip())
        if clone.returncode:
            echec("la copie depuis GitHub a échoué (voir le message ci-dessus).")
    else:
        mise_a_jour = git("pull", "--ff-only", "origin", BRANCHE, cwd=destination)
        journal((mise_a_jour.stdout + mise_a_jour.stderr).strip())
    nouveau = destination / "outils" / "albums-famille"
    if PARAMETRES.exists() and not (nouveau / PARAMETRES.name).exists():
        shutil.copy(PARAMETRES, nouveau / PARAMETRES.name)  # vos réglages suivent
    bibliotheques(nouveau)
    journal("")
    journal(f"C'est fait. Désormais, utilisez le dossier : {nouveau}")
    journal("(vous pouvez supprimer l'ancien dossier dézippé). Pour les prochaines versions :")
    journal("double-cliquez simplement sur 0_mettre_a_jour.bat dans ce nouveau dossier.")
    ouvrir(nouveau)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ETAPES:
        sys.exit(f"Usage : python lanceur.py {' | '.join(ETAPES)}")
    etape = sys.argv[1]
    journal("")
    journal(f"===== {dt.datetime.now():%d/%m/%Y %H:%M} - étape {etape} =====")
    if etape == "mettre_a_jour":
        etape_mettre_a_jour()
        return
    if etape == "tests":  # n'a pas besoin de vos réglages
        etape_tests({})
        return
    if etape == "partager":
        etape_partager(lire_parametres() if PARAMETRES.exists() else {})
        return
    parametres = lire_parametres()
    if etape not in ("installer", "analyser") and not (parametres.get("PERSONNE") or "").strip():
        echec("indiquez d'abord la personne du livre (Paramètres > « Personne du livre », ou PERSONNE = ... dans "
              f"{PARAMETRES.name}).")
    if etape not in ("installer", "analyser"):
        verifier_disque_analyse(parametres)
    globals()[f"etape_{etape}"](parametres)


if __name__ == "__main__":
    main()
