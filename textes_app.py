"""textes_app.py - textes de l'application Album Photos en anglais (bouton FR / EN).

T("texte français") renvoie la traduction anglaise quand la langue est « en » (sinon le texte tel quel).
Les modèles avec {nom} se complètent ensuite avec .format(...).
"""
import os
LANGUE = ["fr"]

EN = {
    # sections et étapes
    "1. Analyse des photos": "1. Photo analysis",
    "2. Sélection des photos": "2. Photo selection",
    "3. Livre": "3. Book",
    "4. Planche lettres-photos": "4. Photo-letters poster",
    "Mettre à jour l'outil": "Update the tool",
    "Récupère la dernière version (vos réglages et livres sont gardés)":
        "Gets the latest version (your settings and books are kept)",
    "Installer / réparer": "Install / repair",
    "Vérifier l'outil (tests)": "Check the tool (tests)",
    "Tests automatiques sur des photos de synthèse (1 à 3 min) ; vos photos et réglages ne sont pas utilisés":
        "Automatic tests on synthetic photos (1 to 3 min); your photos and settings are not used",
    "Installe les bibliothèques et crée les dossiers de photos de référence":
        "Installs the libraries and creates the reference photo folders",
    "Analyser le disque": "Analyse the drive",
    "Une seule fois pour toutes les personnes (lecture seule, des heures la 1re fois) ; à relancer seulement si vous ajoutez des photos au disque":
        "Once for everybody (read-only, hours the first time); rerun only if you add photos to the drive",
    "Préparer la sélection": "Prepare the selection",
    "Reconnaît la personne du livre et propose ses photos, puis ouvre l'écran de choix ; à faire pour chaque nouvelle personne":
        "Recognises the book's person, suggests their photos, then opens the selection screen; do it for each new person",
    "Livre de {personne} : prochaine étape « Préparer la sélection » (l'analyse du disque est déjà faite et sert pour toutes les personnes).":
        "{personne}'s book: next step \"Prepare the selection\" (the drive analysis is already done and serves everybody).",
    "Ajoutez 3 à 10 photos nettes du visage de {personne} dans {dossier} (bouton « Photos de référence »), puis « Préparer la sélection ». L'analyse du disque est déjà faite : inutile de la refaire.":
        "Add 3 to 10 sharp photos of {personne}'s face to {dossier} (\"Reference photos\" button), then \"Prepare the selection\". The drive analysis is already done: no need to redo it.",
    "L'analyse est déjà faite ({nombre} photos). Elle sert pour toutes les personnes : pour faire le livre d'une autre personne, il suffit de changer « Personne du livre » puis de cliquer sur « Préparer la sélection ».\n\nLa relancer ne sert que si vous avez ajouté des photos sur le disque (seules les nouvelles seront analysées).\n\nRelancer l'analyse ?":
        "The analysis is already done ({nombre} photos). It serves everybody: for another person's book, just change \"Person of the book\" and click \"Prepare the selection\".\n\nRerunning it is only useful if you added photos to the drive (only the new ones are analysed).\n\nRerun the analysis?",
    "nom de son dossier de photos de référence ; changer de personne = un autre livre (dossier livre_<Prénom>), sans refaire l'analyse du disque":
        "name of their reference photo folder; another person = another book (folder livre_<Name>), no need to redo the drive analysis",
    "Choisir les photos": "Choose the photos",
    "Écran de choix dans le navigateur : un clic = garder / retirer":
        "Selection screen in the browser: one click = keep / remove",
    "Réduire la sélection": "Reduce the selection",
    "Seules les photos gardées, avec les candidates au retrait": "Kept photos only, with candidates for removal",
    "Proposer des améliorations": "Suggest improvements",
    "Propositions à accepter ou refuser d'un clic, puis appliquer": "Suggestions to accept or refuse with a click, then apply",
    "Revoir les propositions": "Review the suggestions",
    "Rouvre l'écran des propositions déjà faites (sans les recalculer)": "Reopens the suggestions already made (without recomputing)",
    "Aperçus des ambiances": "Style previews",
    "Un PDF d'aperçu par ambiance ; vous cochez celles à (re)faire": "One preview PDF per style; tick the ones to (re)do",
    "Livre final": "Final book",
    "Le livre dans l'ambiance choisie + le dossier pour l'imprimeur":
        "The book in the chosen style + the folder for the printer",
    "Livre + PowerPoint modifiable": "Book + editable PowerPoint",
    "Comme le livre final, avec une version .pptx à retoucher": "Like the final book, plus a .pptx version to edit",
    "Choisir les photos des lettres": "Choose the letter photos",
    "Une photo par lettre ; le livre n'est pas modifié": "One photo per letter; the book is not changed",
    "Créer la planche lettres": "Create the letters poster",
    "5. Mosaïque de photos": "5. Photo mosaic",
    "Maintenance": "Maintenance", "🔧  Maintenance": "🔧  Maintenance", "Maintenance de l'outil": "Tool maintenance",
    "Mode administrateur": "Administrator mode", "Fermer": "Close",
    "Copie partagée : la mise à jour est réservée à l'auteur de l'outil":
        "Shared copy: updates are reserved for the tool's author",
    "Fabriquer le zip à partager": "Make the zip to share",
    "Copie propre de l'outil, sans vos réglages, vos données ni le lien vers votre dépôt GitHub":
        "Clean copy of the tool, without your settings, your data or the link to your GitHub repository", "Créer la mosaïque": "Create the mosaic",
    "Aperçu de la mosaïque": "Mosaic preview", "Pas encore d'aperçu": "No preview yet",
    "↻  Actualiser l'aperçu": "↻  Refresh the preview",
    "Rendu rapide (quelques secondes) avec les réglages actuels, affiché dans Paramètres > Mosaïque":
        "Quick render (a few seconds) with the current settings, shown in Settings > Mosaic",
    "Quelques secondes, avec les réglages de gauche (enregistrés d'abord).\nLe poster pour l'imprimeur : « Créer la "
    "mosaïque ».": "A few seconds, with the settings on the left (saved first).\nThe poster for the printer: "
                  "\"Create the mosaic\".",
    "La photo master reconstituée avec les photos de l'album (A4 à A0) ; choix de la master : « ◆ Master » dans "
    "l'écran de choix ou Paramètres":
        "The master photo rebuilt from the album photos (A4 to A0); pick the master with \"◆ Master\" in the "
        "choice screen or in Settings",
    "Mosaïque": "Mosaic", "Photo master": "Master photo",
    "la photo à reconstituer ; vide = celle marquée « ◆ Master » dans l'écran de choix, sinon la couverture":
        "the photo to rebuild; empty = the one marked \"◆ Master\" in the choice screen, otherwise the cover",
    "Format du poster": "Poster format", "Petites photos en largeur": "Small photos across",
    "plus = visage plus net de loin, petites photos plus petites ; A0 : 80 à 120":
        "more = sharper face from afar, smaller photos; A0: 80 to 120",
    "Visage fondu par-dessus": "Master photo blended on top",
    "0.25 discret, 0.35 conseillé, 0.50 visage très marqué": "0.25 subtle, 0.35 recommended, 0.50 very visible face",
    "Petites photos utilisées": "Small photos used",
    "sans dossier de miniatures : gardées = celles du livre, toutes = toutes les photos de la personne ; "
    "« + dossier » = l'album ET le dossier de miniatures":
        "without a thumbnail folder: kept = the book's photos, all = every photo of the person; "
        "\"+ folder\" = the album AND the thumbnail folder",
    "Dossier des photos en miniature (option)": "Thumbnail photos folder (optional)",
    "rempli = les petites photos viennent de ce dossier (sous-dossiers compris, lu sans être modifié) ; "
    "vide = les photos sélectionnées de l'album":
        "filled = the small photos come from this folder (subfolders included, never changed); "
        "empty = the album's selected photos",
    "gardées = celles du livre ; toutes = toutes les photos de la personne (plus de variété)":
        "kept = the book's photos; all = every photo of the person (more variety)",
    "Résolution d'impression": "Print resolution",
    "auto = 300 dpi jusqu'au A2, 200 en A1, 150 en A0 (norme des posters, vus à distance)":
        "auto = 300 dpi up to A2, 200 for A1, 150 for A0 (poster standard, seen from a distance)",
    "Photos": "Photos", "Tous les fichiers": "All files",
    "Rendu du visage": "Face rendering",
    "adaptatif = conseillé (yeux, bouche, contours plus détaillés) ; lumière = les photos gardent leurs couleurs":
        "adaptive = recommended (eyes, mouth, outlines more detailed); light = photos keep their colours",
    "Teinte des petites photos": "Small photos tint",
    "photos teintées vers la couleur de leur case : 0 = couleurs d'origine, 0.6 = harmonie forte":
        "photos tinted towards their cell colour: 0 = original colours, 0.6 = strong harmony",
    "Liseré entre les photos": "Line between photos", "effet « carreaux » discret": "subtle \"tiles\" effect",
    "Écart entre deux mêmes photos": "Gap between two identical photos",
    "nombre de cases minimum ; plus = plus de variété apparente": "minimum number of cells; more = more visible variety",
    "Fond perdu (mm)": "Bleed (mm)",
    "marge rognée par l'imprimeur (3 mm en général) ; le texte reste à l'intérieur":
        "margin trimmed by the printer (usually 3 mm); the text stays inside",
    "Texte sur la photo": "Text on the photo",
    "vide = aucun ; « | » = nouvelle ligne, ex. Laura | 2003 - 2026": "empty = none; \"|\" = new line, e.g. Laura | 2003 - 2026",
    "Position du texte": "Text position", "auto = là où il n'y a pas de visage": "auto = where there is no face",
    "Police du texte": "Text font", "Couleur du texte": "Text colour", "ou #RRGGBB": "or #RRGGBB",
    "Taille du texte": "Text size", "ou un % de la largeur, ex. 7": "or a % of the width, e.g. 7",
    "Style du texte": "Text style",
    "ombre = lisible partout ; bandeau = bande translucide derrière le texte":
        "shadow = readable everywhere; band = translucent strip behind the text",
    "Les modèles en JPEG 300 dpi + PDF, et une planche de comparaison":
        "The designs as 300 dpi JPEG + PDF, and a comparison sheet",
    "Ouvrir": "Open",
    "Dossier de travail": "Work folder",
    "Dossier du livre": "Book folder",
    "Photos de référence": "Reference photos",
    "Planches lettres": "Letter posters",
    "Dossier de l'outil": "Tool folder",
    # bandeau, onglets, boutons
    "Prêt": "Ready",
    "■  Arrêter l'étape": "■  Stop the step",
    "  Journal  ": "  Log  ",
    "  Paramètres  ": "  Settings  ",
    "  Aide  ": "  Help  ",
    "Effacer l'affichage": "Clear the display",
    "Copier le journal": "Copy the log",
    "En cas de problème : envoyez journal.txt (bouton « journal.txt » à gauche) à Claude.":
        "If there is a problem: send journal.txt (\"journal.txt\" button on the left) to Claude.",
    "✔  Enregistrer les paramètres": "✔  Save the settings",
    "Annuler les modifications": "Undo the changes",
    "liste ou saisie libre": "list or free text",
    "📁  Parcourir…": "📁  Browse…",
    "Ouvrir le guide complet (navigateur)": "Open the full guide (browser)",
    "{nom} · livre de {personne}": "{nom} · {personne}'s book",
    "Photos : {photos}   ·   Travail : {travail}   ·   {version}": "Photos: {photos}   ·   Work: {travail}   ·   {version}",
    "version du {date}": "version of {date}",
    "Fichier : {fichier}": "File: {fichier}",
    "Modifié : pensez à enregistrer (fait aussi automatiquement avant chaque étape).":
        "Changed: remember to save (also done automatically before each step).",
    "Enregistré à {heure} dans {fichier}": "Saved at {heure} in {fichier}",
    # sections et champs des paramètres
    "Photos et personnes": "Photos and people",
    "Livre": "Book",
    "Planche lettres": "Letters poster",
    "Dossier des photos": "Photo folder",
    "disque de backup : il n'est jamais modifié": "backup drive: it is never modified",
    "sur le PC (ni sur le disque de backup, ni dans OneDrive)": "on the PC (not on the backup drive, not in OneDrive)",
    "Personne du livre": "Person of the book",
    "nom de son dossier de photos de référence": "name of their reference photo folder",
    "Proches à mettre en avant": "Close relatives to feature",
    "séparés par des virgules (ex. son frère)": "separated by commas (e.g. her brother)",
    "Date de naissance": "Date of birth",
    "JJ/MM/AAAA (vide si inconnue)": "DD/MM/YYYY (empty if unknown)",
    "Pays « chez soi »": "\"Home\" countries",
    "codes à 2 lettres, ex. FR,PH : ailleurs = voyage": "2-letter codes, e.g. FR,PH: elsewhere = trip",
    "Format du livre": "Book format",
    "Nombre maximum de photos": "Maximum number of photos",
    "ex. 150": "e.g. 150",
    "Nombre de pages visé": "Target number of pages",
    "vide = mise en page aérée": "empty = airy layout",
    "Organisation des chapitres": "Chapter organisation",
    "vide = celle de chaque ambiance": "empty = each style's own",
    "Ambiance du livre final": "Style of the final book",
    "choisie après les aperçus": "chosen after the previews",
    "Reliure": "Binding",
    "layflat = reliure à plat (panoramiques)": "layflat = lay-flat binding (panoramas)",
    "Couleur des encadrés de légende (ambiances BD)": "Caption box colour (comic styles)",
    "jaune par défaut ; ou un code #RRGGBB ; texte blanc sur les couleurs foncées":
        "yellow by default; or a #RRGGBB code; white text on dark colours",
    "Langue du livre et de la planche lettres": "Language of the book and letters poster",
    "titres, dates, âges, pays et bulles traduits ; les légendes saisies à la main restent telles quelles":
        "titles, dates, ages, countries and bubbles translated; hand-typed captions stay as typed",
    "Dédicace (page de titre)": "Dedication (title page)",
    "Pied de page": "Footer",
    "Aperçu schématique": "Schematic preview",
    "dernière page (vide = « À suivre… ») ; retours à la ligne et paragraphes gardés ; la taille s'adapte":
        "last page (empty = \"To be continued…\"); line breaks and paragraphs kept; size adapts",
    "Symbole au-dessus du texte de fin": "Symbol above the end text",
    "Modèles à fabriquer :": "Designs to make:",
    "tous (les 6 modèles, pour comparer)": "all (the 6 designs, to compare)",
    "Aperçus": "Previews",
    "Les lettres colorées représentent les photos.\nRendu exact : « Créer la planche lettres ».":
        "Coloured letters stand for the photos.\nExact result: \"Create the letters poster\".",
    "petit texte en bas des pages, ex. Laura · 2012-2024 (vide = aucun)":
        "small text at the bottom of pages, e.g. Laura · 2012-2024 (empty = none)",
    "Pages avec le pied de page": "Pages with the footer",
    "toutes = toutes les pages après la première ; pages à photo unique = seulement celles-là":
        "all = every page after the first; single-photo pages = only those",
    "Texte de la fin de l'album": "Text at the end of the album",
    "dernière page (vide = « À suivre… ») ; un texte long passe à la ligne":
        "last page (empty = \"To be continued…\"); a long text wraps",
    "vide = aucune": "empty = none",
    "Mot écrit": "Word written",
    "vide = le prénom ; un espace = nouvelle ligne": "empty = the first name; a space = new line",
    "Texte au-dessus": "Text above",
    "ex. On t'aime": "e.g. We love you",
    "Texte au-dessous": "Text below",
    "ex. De la part de Papa (suivi d'un cœur)": "e.g. From Dad (followed by a heart)",
    "Format": "Format",
    "Modèles à fabriquer": "Designs to make",
    "tous, ou des numéros": "tous (all), or numbers",
    "Police des lettres": "Letter font",
    "toutes = celle de chaque modèle": "all = each design's own",
    "Taille des lettres (%)": "Letter size (%)",
    "100 = maximum": "100 = maximum",
    "Creux des lettres (A, R, O)": "Letter holes (A, R, O)",
    "non = la photo remplit tout": "no = the photo fills everything",
    "Couleur du fond": "Background colour",
    "vide = celle du modèle, ou #RRGGBB": "empty = the design's own, or #RRGGBB",
    "Couleur du contour": "Outline colour",
    "vide = celle du modèle": "empty = the design's own",
    "Couleur des textes": "Text colour",
    "vide = automatique": "empty = automatic",
    "Photos": "Photos",
    "Mettre la planche dans le livre photo": "Put the poster in the photo book",
    "première page = à la place de la page de titre ; première et dernière page = aussi avant la dernière page":
        "first page = instead of the title page; first and last page = also before the last page",
    "Modèle de planche pour le livre": "Poster design for the book",
    "voir Comparaison_modeles.jpg ; mis au format du livre automatiquement":
        "see Comparaison_modeles.jpg; resized to the book format automatically",
    # messages
    "« Personne du livre » : une seule personne. Mettez les autres dans « Proches à mettre en avant ».":
        "\"Person of the book\": one person only. Put the others in \"Close relatives to feature\".",
    "Date de naissance : format JJ/MM/AAAA (ex. 10/11/2003).": "Date of birth: DD/MM/YYYY format (e.g. 10/11/2003).",
    "{fichier} est ouvert dans un autre programme : fermez-le.": "{fichier} is open in another program: close it.",
    "Ce dossier n'existe pas encore :\n{dossier}\n\nIl sera créé par l'étape correspondante.":
        "This folder does not exist yet:\n{dossier}\n\nIt will be created by the matching step.",
    "Bibliothèques à installer ({liste}) : bouton « 🔧 Maintenance » puis « Installer / réparer ».":
        "Libraries to install ({liste}): \"🔧 Maintenance\" button, then \"Install / repair\".",
    "Ajoutez 3 à 10 photos nettes du visage de {personne} dans {dossier} (bouton « Photos de référence »), puis « Analyser le disque ».":
        "Add 3 to 10 sharp photos of {personne}'s face to {dossier} (\"Reference photos\" button), then \"Analyse the drive\".",
    "Prochaine étape : « Analyser le disque ».": "Next step: \"Analyse the drive\".",
    "Prochaine étape : « Préparer la sélection ».": "Next step: \"Prepare the selection\".",
    "Prochaine étape : « Choisir les photos », puis « Aperçus des ambiances ».":
        "Next step: \"Choose the photos\", then \"Style previews\".",
    "Regardez les aperçus (bouton « Dossier du livre »), choisissez l'ambiance dans Paramètres > Livre, puis « Livre final ».":
        "Look at the previews (\"Book folder\" button), choose the style in Settings > Book, then \"Final book\".",
    "Ambiance choisie : {ambiance}. Prochaine étape : « Livre final ».": "Chosen style: {ambiance}. Next step: \"Final book\".",
    "Une étape est déjà en cours. Attendez la fin ou cliquez sur « Arrêter l'étape ».":
        "A step is already running. Wait for it to finish or click \"Stop the step\".",
    "Dossier des photos (disque de backup)": "Photo folder (backup drive)",
    "Une sélection existe déjà pour {personne}.\n\nOui = la refaire (vos choix seront perdus ; une copie est gardée)\nNon = garder la sélection actuelle et l'afficher":
        "A selection already exists for {personne}.\n\nYes = redo it (your choices will be lost; a copy is kept)\nNo = keep the current selection and show it",
    "Choisissez d'abord l'ambiance du livre dans Paramètres > Livre (après avoir regardé les aperçus).":
        "First choose the book style in Settings > Book (after looking at the previews).",
    "Impossible de lancer Python : {erreur}": "Cannot start Python: {erreur}",
    "L'écran de choix s'ouvre dans le navigateur. Quand c'est fini, cliquez sur « Terminer » dans la page.\n":
        "The selection screen opens in the browser. When you are done, click \"Terminer\" (Finish) on the page.\n",
    "En cours : {etape}": "Running: {etape}",
    "Quels aperçus faire ou refaire ?": "Which previews should be made or redone?",
    "Les aperçus non cochés restent tels quels.": "Unticked previews stay as they are.",
    "déjà fait le {date}": "done on {date}",
    "pas encore fait": "not done yet",
    "Cochez au moins une ambiance.": "Tick at least one style.",
    "Tout cocher": "Tick all",
    "Tout décocher": "Untick all",
    "✔  Lancer": "✔  Start",
    "Annuler": "Cancel",
    "Vérifier la reconnaissance": "Check the recognition",
    "Visages mal reconnus : un clic confirme ou refuse ; puis relancez « Préparer la sélection »":
        "Wrongly recognised faces: one click confirms or refuses; then run \"Prepare the selection\" again",
    "Exigence de ressemblance des visages": "Face likeness requirement",
    "vide = 0.40 ; plus haut = moins de photos sans la personne, mais quelques oublis":
        "empty = 0.40; higher = fewer photos without the person, but a few missed",
    "fichiers parcourus": "files scanned",
    "reste ≈ {duree}": "about {duree} left",
    "Inventaire du disque": "Scanning the drive",
    "Analyse des photos": "Analysing photos",
    "Reconnaissance des visages": "Recognising faces",
    "Mise en page du livre": "Laying out the book",
    "Dossier de l'imprimeur": "Printer folder",
    "Planche lettres": "Letters poster",
    "Redémarrage…": "Restarting…",
    "Le dossier de travail doit être en dehors du dossier des photos (l'outil n'écrit jamais sur le disque de backup).":
        "The work folder must be outside the photo folder (the tool never writes to the backup drive).",
    "Vos paramètres semblent vides (fichier abîmé lors d'une fermeture forcée ?).\n\nRestaurer les derniers réglages connus ({origine}) ?\n\nPersonne : {personne}\nPhotos : {photos}\nTravail : {travail}":
        "Your settings look empty (file damaged by a forced close?).\n\nRestore the last known settings ({origine})?\n\nPerson: {personne}\nPhotos: {photos}\nWork: {travail}",
    "Erreur inattendue (notée dans journal.txt) : {erreur}": "Unexpected error (written to journal.txt): {erreur}",
    "Terminé ✓": "Done ✓",
    "✓ Étape terminée.\n": "✓ Step finished.\n",
    "Arrêté / erreur": "Stopped / error",
    "✗ L'étape s'est arrêtée (voir les messages ci-dessus).\n": "✗ The step stopped (see the messages above).\n",
    "L'outil a été copié dans :\n{dossier}\n\nMettre les raccourcis « Album Photos » sur cette nouvelle copie et la lancer ?":
        "The tool was copied to:\n{dossier}\n\nPoint the \"Album Photos\" shortcuts to this new copy and start it?",
    "Mise à jour terminée. Redémarrer l'application pour utiliser la nouvelle version ?":
        "Update finished. Restart the application to use the new version?",
    "Arrêter l'étape en cours ? (Le travail déjà fait est conservé : l'analyse reprendra où elle s'est arrêtée.)":
        "Stop the running step? (Work already done is kept: the analysis will resume where it stopped.)",
    "Journal copié": "Log copied",
    "Une étape est en cours. Quitter quand même ? (elle sera arrêtée)": "A step is running. Quit anyway? (it will be stopped)",
    "Enregistrer les paramètres modifiés ?": "Save the changed settings?",
    "Attendez la fin de l'étape en cours pour changer de langue.": "Wait for the running step to finish before changing language.",
    "Les messages détaillés du journal restent en français.": "Detailed log messages stay in French.",
}


def T(texte):
    """Texte dans la langue de l'application."""
    return EN.get(texte, texte) if LANGUE[0] == "en" else texte


# --------------------------------------------------------------------------- valeurs des listes de choix
# Le fichier de paramètres garde toujours le code (colonne de gauche) ; l'application affiche un libellé lisible.
VALEURS = {  # code : (libellé français, libellé anglais)
    "": ("(vide)", "(empty)"),
    "oui": ("oui", "yes"), "non": ("non", "no"),
    "tous": ("tous", "all"), "toutes": ("toutes", "all"),
    "fr": ("français", "French"), "en": ("anglais", "English"),
    # couleurs
    "noir": ("noir", "black"), "blanc": ("blanc", "white"), "creme": ("crème", "cream"), "gris": ("gris", "grey"),
    "gris-clair": ("gris clair", "light grey"), "anthracite": ("anthracite", "charcoal"),
    "bleu-nuit": ("bleu nuit", "midnight blue"), "marine": ("bleu marine", "navy"), "bleu": ("bleu", "blue"),
    "bleu-ciel": ("bleu ciel", "sky blue"), "bleu-fonce": ("bleu foncé", "dark blue"), "rose": ("rose", "pink"),
    "rose-poudre": ("rose poudré", "powder pink"), "fuchsia": ("fuchsia", "fuchsia"), "rouge": ("rouge", "red"),
    "bordeaux": ("bordeaux", "burgundy"), "vert": ("vert", "green"), "vert-fonce": ("vert foncé", "dark green"),
    "vert-sauge": ("vert sauge", "sage green"), "beige": ("beige", "beige"), "kraft": ("kraft", "kraft"),
    "or": ("or", "gold"), "argent": ("argent", "silver"), "lavande": ("lavande", "lavender"),
    "violet": ("violet", "purple"), "jaune": ("jaune", "yellow"), "orange": ("orange", "orange"),
    "turquoise": ("turquoise", "turquoise"), "aucun": ("aucun", "none"),
    # photos, planche, livre
    "couleur": ("couleur", "colour"), "noir-et-blanc": ("noir et blanc", "black and white"),
    "sepia": ("sépia", "sepia"),
    "premiere-page": ("première page", "first page"),
    "gardees": ("gardées pour le livre", "kept for the book"),
    "dossier": ("un autre dossier seulement", "another folder only"),
    "gardees+dossier": ("gardées + dossier de miniatures", "kept + thumbnail folder"),
    "toutes+dossier": ("toutes + dossier de miniatures", "all + thumbnail folder"),
    "auto": ("automatique", "automatic"),
    "adaptatif": ("adaptatif (conseillé)", "adaptive (recommended)"), "naturel": ("naturel", "natural"),
    "lumiere": ("lumière seulement", "light only"), "blanc-fin": ("blanc fin", "thin white"),
    "noir-fin": ("noir fin", "thin black"), "bas": ("bas", "bottom"), "haut": ("haut", "top"),
    "centre": ("centre", "centre"), "bas-gauche": ("bas gauche", "bottom left"), "bas-droite": ("bas droite", "bottom right"),
    "haut-gauche": ("haut gauche", "top left"), "haut-droite": ("haut droite", "top right"),
    "ombre": ("ombre", "shadow"), "contour": ("contour", "outline"), "bandeau": ("bandeau", "band"),
    "petit": ("petit", "small"), "moyen": ("moyen", "medium"), "grand": ("grand", "large"),
    "tres-grand": ("très grand", "very large"), "script": ("manuscrite", "handwriting"), "texte": ("texte", "text"),
    "a2-portrait": ("A2 portrait", "A2 portrait"), "a1-portrait": ("A1 portrait", "A1 portrait"),
    "a0-portrait": ("A0 portrait (84 x 119 cm)", "A0 portrait (84 x 119 cm)"),
    "a2-paysage": ("A2 paysage", "A2 landscape"), "a1-paysage": ("A1 paysage", "A1 landscape"),
    "a0-paysage": ("A0 paysage (119 x 84 cm)", "A0 landscape (119 x 84 cm)"),
    "a3-portrait": ("A3 portrait", "A3 portrait"), "carre50": ("carré 50 cm", "50 cm square"),
    "premiere-et-derniere": ("première et dernière page", "first and last page"),
    "photos-uniques": ("pages à photo unique", "single-photo pages"),
    "chrono-lieux": ("chronologique + lieux", "chronological + places"), "chrono": ("chronologique", "chronological"),
    "themes": ("par thèmes", "by theme"), "lieux": ("par lieux", "by place"),
    "classique": ("classique", "classic"), "layflat": ("à plat (layflat)", "lay-flat"),
    "carre30": ("carré 30 x 30 cm", "square 30 x 30 cm"), "carre20": ("carré 20 x 20 cm", "square 20 x 20 cm"),
    "a4-paysage": ("A4 paysage", "A4 landscape"), "a4-portrait": ("A4 portrait", "A4 portrait"),
    "a3-paysage": ("A3 paysage", "A3 landscape"), "30x20": ("30 x 20 cm", "30 x 20 cm"),
    "40x30": ("40 x 30 cm", "40 x 30 cm"),
    "arial-black": ("Arial Black", "Arial Black"), "impact": ("Impact", "Impact"), "georgia": ("Georgia", "Georgia"),
    "segoe-black": ("Segoe Black", "Segoe Black"),
    # symboles de fin
    "coeurs": ("cœurs", "hearts"), "coeur": ("cœur", "heart"), "fleur": ("fleur", "flower"),
    "ornement": ("ornement", "ornament"), "colombe": ("colombe", "dove"), "etoiles": ("étoiles", "stars"),
    # ambiances
    "elegant": ("élégant", "elegant"), "tendre": ("tendre", "tender"), "carnet": ("carnet", "notebook"),
    "prestige": ("prestige", "prestige"), "prestige-compact": ("prestige compact", "prestige compact"),
    "prestige-mosaique": ("prestige mosaïque", "prestige mosaic"),
    "prestige-mosaique-bd": ("prestige mosaïque BD", "prestige mosaic comic"),
    "magazine": ("magazine", "magazine"), "bd": ("BD dessinée", "comic (drawn)"), "bd-photo": ("BD photo", "comic (photo)"),
}
MODELES_NOMS = ["classique", "aquarelle", "impact", "deux-lignes", "elegant", "prestige-noir"]
MODELES_LIBELLES = {"classique": ("classique", "classic"), "aquarelle": ("aquarelle", "watercolour"),
                    "impact": ("impact", "impact"), "deux-lignes": ("deux lignes", "two lines"),
                    "elegant": ("élégant", "elegant"), "prestige-noir": ("prestige noir", "black prestige")}


def libelle(code):
    """Libellé affiché pour un code de liste (dans la langue de l'application)."""
    if code in VALEURS:
        return VALEURS[code][1 if LANGUE[0] == "en" else 0]
    return code


def code_de(texte, choix):
    """Code correspondant à un libellé affiché (ou au texte saisi tel quel : code, couleur #RRGGBB...)."""
    texte = texte.strip()
    for c in choix:
        if libelle(c) == texte or c == texte:
            return c
    for c, (fr, en) in VALEURS.items():  # libellé d'une autre liste ou de l'autre langue
        if texte.lower() in (fr.lower(), en.lower()):
            return c
    return texte


def enregistrer_texte_fin(fichier, texte):
    """Écrit le texte de fin dans texte_fin.txt (sans tk : testable). Texte vide = fichier supprimé ; texte
    inchangé = rien à faire. (Bug corrigé le 01/11/2026 : un texte inchangé supprimait le fichier, donc le
    2e enregistrement - automatique avant chaque étape - effaçait la lettre et le livre affichait « À suivre… ».)"""
    texte = (texte or "").replace("\r\n", "\n").strip()
    if not texte:
        if fichier.exists():
            fichier.unlink()
        return
    if fichier.exists() and fichier.read_text(encoding="utf-8-sig").replace("\r\n", "\n") == texte + "\n":
        return
    temporaire = fichier.with_suffix(".tmp")
    with open(temporaire, "w", encoding="utf-8", newline="") as sortie:
        sortie.write(texte + "\n")
    os.replace(temporaire, fichier)
