# Réf. 20261101-Photos-33 : guide de l'application Album Photos

Version du 01/11/2026. L'application regroupe en une seule fenêtre toutes les étapes du livre photo et de la planche lettres-photos. Chaque bouton fait exactement ce que faisait le fichier `.bat` du même nom, qui reste utilisable.

**Règle de sécurité :** l'application ne fait que **lire** tes photos. Elle ne modifie, ne déplace et ne supprime jamais rien sur le disque de backup. Tout ce qu'elle crée va dans le dossier de travail, par exemple `C:\AlbumsFamille`.

## 1. Installer l'application (une seule fois)

| Étape | Ce qu'il faut faire |
|---|---|
| 1. Python | Si Python n'est pas encore installé : https://www.python.org/downloads/. Sur le premier écran, coche **« Add python.exe to PATH »**, puis redémarre le PC. |
| 2. L'outil | Décompresse le zip reçu (par exemple dans Documents). L'auteur de l'outil, lui, utilise sa copie Git `%USERPROFILE%\AlbumPhotos\outils\albums-famille`. |
| 3. Installer | Dans ce dossier, double-clique sur **`Installer_application.bat`**. Il installe les bibliothèques (quelques minutes la première fois), crée l'icône **Album Photos** sur le Bureau et dans le menu Démarrer, puis ouvre l'application. |
| 4. Ensuite | Ouvre simplement **Album Photos** depuis le Bureau. |

Si le raccourci n'a pas pu être créé, `Lancer_application.bat` ouvre aussi l'application.

### Vérifier l'outil (tests automatiques)

Le bouton **🔧 Maintenance** > **Vérifier l'outil (tests)** (ou `9_tests_automatiques.bat`) lance 39 tests en 1 à 3 minutes, sur un petit disque de **photos de synthèse** créé dans un dossier temporaire : tes photos, tes réglages et tes livres ne sont pas utilisés. Les tests couvrent l'analyse, la sélection, les aperçus, le livre final avec le PowerPoint, la planche lettres, les écrans du navigateur (jeton de sécurité), les propositions, la traduction, les paramètres (lettre sur plusieurs lignes, écriture sûre) et surtout le fait que **les photos d'origine ne sont jamais modifiées**. À la fin, « OK » et « Tous les tests sont passés » s'affichent en vert. Sinon, envoie `journal.txt` à Claude.

## 2. L'écran

| Zone | Rôle |
|---|---|
| Bandeau du haut | Le nom de la personne du livre, les dossiers utilisés et la date de la version. À droite : l'étape en cours, une barre d'activité et le bouton **■ Arrêter l'étape**. |
| Colonne de gauche | Les boutons des étapes, dans l'ordre (1 à 5 ; l'installation et la mise à jour sont dans **🔧 Maintenance**) : **boutons bleus ▶**, qui s'éclaircissent au survol. **Le bouton conseillé est vert.** Pendant une étape, les autres sont grisés. En bas, les boutons blancs « Ouvrir » donnent accès aux dossiers. |
| Onglet **Journal** | Ce que fait l'étape, en direct. La ligne verte en haut indique la prochaine étape conseillée. Les erreurs sont en rouge. |
| Onglet **Paramètres** | Tous les réglages, en trois pages : Photos et personnes, Livre, Planche lettres. **Chaque réglage est dans un cadre blanc** : un titre en gras, la zone à remplir (bordure bleue quand on écrit dedans, flèche ▼ pour une liste de choix) et une aide en gris. Le bouton vert **✔ Enregistrer les paramètres** est en haut. |
| Onglet **Aide** | Ce guide. Le bouton « Ouvrir le guide complet » l'affiche dans le navigateur. |

Les paramètres sont enregistrés automatiquement avant chaque étape. Il n'est donc pas nécessaire de cliquer sur « Enregistrer » avant de lancer un bouton.

## 3. Faire le livre pas à pas

| N° | Bouton | Ce qui se passe | Durée |
|---|---|---|---|
| 0 | Onglet **Paramètres** | Remplis au minimum : dossier des photos (bouton « Parcourir… »), dossier de travail, personne du livre (Laura), proches (son frère), date de naissance, pays « chez soi » (FR,PH). | 2 min |
| 1 | **🔧 Maintenance** > **Installer / réparer** | Vérifie les bibliothèques et crée un dossier de photos de référence par personne. | 2 à 10 min |
| — | **Photos de référence** (Ouvrir) | Mets 3 à 10 photos nettes du visage de chaque personne dans son dossier, à des âges différents, bébé compris. | 10 min |
| 2 | **Analyser le disque** | Lit toutes les photos : dates, lieux, visages, netteté. On peut l'arrêter et la relancer : le travail déjà fait est conservé. | plusieurs heures la 1re fois |
| 3 | **Préparer la sélection** | Propose les photos du livre, regroupées en souvenirs. Si une sélection existe déjà, l'application demande s'il faut la refaire. Elle garde une copie de l'ancienne. | quelques min |
| 3a | **Choisir les photos** | Le navigateur s'ouvre : un clic garde ou retire une photo, 🔍 l'agrandit. Boutons de filtre : **★ Spéciales** (toutes les photos à rôle), **★ Couverture**, **★ Pleine page**, **✉ Lettres**, **◆ Master**, **Écartées** (doublons, floues, « pas Laura »), avec leur nombre. Termine avec le bouton **Terminer** de la page. | à ton rythme |
| 3b | **Réduire la sélection** *(facultatif)* | Affiche seulement les photos gardées et signale celles à retirer en priorité : doublons, photos floues, faible définition. | à ton rythme |
| 3c | **Proposer des améliorations** *(facultatif)* | Un écran s'ouvre : chaque proposition (remplacer, ajouter, retirer) avec ses photos ; **un clic l'accepte ou la refuse**, « Tout accepter » / « Tout refuser », puis **« Appliquer les choix »** met à jour la sélection (copie de sauvegarde faite). Plus besoin d'Excel. « Revoir les propositions » rouvre cet écran sans tout recalculer. | quelques min |
| 4 | **Aperçus des 10 ambiances** | Crée un PDF d'aperçu par style dans le dossier du livre. | 10 à 30 min |
| — | Onglet Paramètres > Livre | Choisis l'**ambiance**. Selon ton besoin, règle aussi le nombre de pages, l'organisation et la dédicace. | 2 min |
| 5 | **Livre final** | Crée le livre et le dossier pour l'imprimeur : PDF, photos numérotées dans l'ordre, fichier Excel d'instructions, plan de montage. | 10 à 30 min |
| 5b | **Livre + PowerPoint modifiable** *(facultatif)* | Même chose, avec en plus un fichier `.pptx` pour retoucher une planche à la main. | 10 à 30 min |

### Améliorer la reconnaissance des visages

| Problème | Que faire |
|---|---|
| Photos retenues **sans la personne** | Bouton **Vérifier la reconnaissance** : les visages attribués à la personne, **les moins sûrs d'abord**. Un clic **✗ Pas Laura** les interdit pour toujours, et **✓ C'est Laura** en fait une référence de plus, à l'âge exact. Ensuite, relance **Préparer la sélection**. |
| Une photo **sans la personne** dans l'écran de choix | Survole la photo et clique sur **✗ Pas Laura** (ou touche **N** en grand) : elle est retirée du livre **et** cette photo ne sera plus jamais proposée. Chaque refus apprend aussi à l'outil à écarter les visages qui lui ressemblent. |
| **Repartir de zéro** | Écran **Vérifier la reconnaissance** > **Effacer toutes mes corrections**, puis **Préparer la sélection** (répondre « o » : la sélection est entièrement refaite, rien n'est gardé de l'ancienne). |
| Photos **oubliées** | Même écran, liste « Peut-être Laura » : un clic ✓ les fait reconnaître. |
| Beaucoup d'erreurs | Paramètres > « Exigence de ressemblance des visages » : 0.45 ou 0.50 (moins de photos sans la personne, quelques oublis). |
| Photos de référence | 10 à 20 par personne, **une par période** (bébé, 3 ans, 6 ans… pour un enfant), visage grand, net, de face, **seul ou nettement au premier plan**. Les photos à plusieurs visages de même taille et celles qui ne ressemblent pas aux autres sont écartées automatiquement (voir le journal). |

Depuis le 01/11/2026 : un visage n'est attribué que s'il ressemble nettement plus à la personne qu'aux autres membres de la famille. Les inconnus et les frères et sœurs très ressemblants ne sont plus attribués au hasard. Les petits visages (arrière-plan, foule) doivent ressembler nettement plus, et un visage qui ressemble davantage à un visage que tu as refusé n'est plus attribué.

### Faire le livre d'une autre personne (Bo, Hugo…)

**L'analyse du disque se fait une seule fois pour toute la famille.** Elle détecte les visages et calcule leurs empreintes, mais ne sait pas encore qui est qui. La reconnaissance de la personne se fait à « Préparer la sélection », en comparant les visages aux photos de référence.

| Pour un nouveau livre | À faire |
|---|---|
| 1 | Paramètres > « Personne du livre » : le nouveau prénom (et ses proches) |
| 2 | **Photos de référence** : 3 à 10 photos nettes de son visage dans `famille\<Prénom>` |
| 3 | **Préparer la sélection**, puis la suite habituelle (choisir, aperçus, livre final) |
| ✗ | **Pas besoin de relancer « Analyser le disque »** : à refaire seulement si tu ajoutes des photos sur le disque (seules les nouvelles sont analysées). L'application le rappelle si tu cliques dessus. |

Chaque personne a son propre dossier `livre_<Prénom>` : les livres ne se mélangent pas.

## 4. Faire la planche lettres-photos

| N° | Où | Ce qu'il faut faire |
|---|---|---|
| 1 | Paramètres > Planche lettres | Mot (vide = le prénom), textes au-dessus et au-dessous, format, modèles, couleurs. |
| 2 | **Choisir les photos des lettres** | Le navigateur s'ouvre. Clique sur une photo par lettre : le bandeau L A U R A se remplit, dans l'ordre des dates. Cet écran ne modifie pas la sélection du livre. |
| 3 | **Créer la planche lettres** | Crée les modèles en JPEG 300 dpi et en PDF, plus `Comparaison_modeles.jpg`, qui s'ouvre tout seul. |
| 4 | **Planches lettres** (Ouvrir) | Choisis le modèle à donner à l'imprimeur. |

Les réglages utiles de la planche lettres :

| Réglage | Exemple | Effet |
|---|---|---|
| Modèles à fabriquer | `3 - impact` | Liste au-dessus de l'aperçu schématique : ce qui est montré est ce qui sera fabriqué. « tous » montre et fabrique les 6 modèles pour comparer. |
| Couleur du fond | `noir` | Fond noir pour tous les modèles choisis. Un code `#1C2B44` est aussi accepté. |
| Couleur du contour | `or` | Contour doré autour des lettres. `aucun` = pas de contour. |
| Couleur des textes | vide | Choisie automatiquement : claire sur fond sombre. |
| Photos | `sepia` | Photos en couleur, en noir et blanc ou en sépia. |
| Creux des lettres | `non` | La photo remplit aussi le triangle du A et la boucle du R. |
| Mettre la planche dans le livre photo | `premiere-page` | **Optionnel.** La planche remplace la page de titre du livre. `premiere-et-derniere` la remet aussi juste avant la dernière page. `non` = livre classique. |
| Modèle de planche pour le livre | `6` | Le modèle (1 à 6) utilisé dans le livre. Il est mis automatiquement au format du livre (30x30 par exemple). |
| Taille des lettres | `85` | Lettres un peu plus petites, avec plus d'air autour. |

Chaque photo est cadrée pour que le visage de Laura tombe sur une partie pleine de la lettre.

**Aperçu schématique :** dans Paramètres > Planche lettres, la planche est dessinée en direct à droite des réglages (format, fond, police, contour, couleurs, une ou deux lignes, textes ; les lettres colorées représentent les photos). La liste « Modèles à fabriquer », juste au-dessus, choisit à la fois ce qui est montré et ce qui sera fabriqué : un modèle, ou « tous » (les 6 en vignettes).

**Langue :** en anglais, toutes les listes de choix (couleurs, formats, ambiances, symboles…) et les écrans de choix des photos dans le navigateur sont aussi en anglais. Le fichier de paramètres garde toujours les mêmes codes, quelle que soit la langue.

Pour la mettre dans le livre : choisis `premiere-page` dans « Mettre la planche dans le livre photo », puis relance **Aperçus** ou **Livre final**. La planche est fabriquée au format du livre et placée en première page.

### Options du livre (Paramètres > Livre)

| Réglage | Exemple | Effet |
|---|---|---|
| Langue du livre | `en` | Titres, dates, âges, pays, bulles et pages fixes en anglais. Les légendes et titres saisis à la main restent tels quels. |
| Pied de page | `Laura · 2012-2024` | Petit texte en bas des pages, côté extérieur. |
| Pages avec le pied de page | `photos-uniques` | `toutes` = toutes les pages après la première ; `photos-uniques` = seulement les pages à une seule photo. |
| Texte de la fin de l'album | une lettre sur plusieurs paragraphes | Grande zone de texte dans l'application, enregistrée dans `texte_fin.txt`. Les retours à la ligne et les paragraphes sont gardés, la taille s'adapte pour que tout tienne (jamais tronqué), et une 1re ligne courte (« Ma chérie, ») sert d'en-tête. Un ❤️ devient un cœur dessiné. |
| Symbole au-dessus du texte de fin | `coeurs` | coeurs, coeur, fleur, ornement, colombe, etoiles ou aucun : dessinés dans l'application, un clic sur un dessin le choisit. |

**Aperçus :** le bouton « Aperçus des ambiances » ouvre une fenêtre où tu **coches les ambiances à faire ou refaire**. Les autres aperçus restent tels quels. Dans les aperçus seulement : une étiquette rouge signale un visage déjà coupé sur la photo d'origine (aucun recadrage ne peut le rattraper : remplace la photo si possible). Elle est aussi listée en dernière page.

**Langue de l'application :** le bouton **🌐 EN / FR**, en haut à droite, passe toute l'application en anglais ou en français. Les messages détaillés du journal restent en français.

## 4 bis. La mosaïque de photos

Une photo « master » (un portrait, par exemple) reconstituée avec des centaines de petites photos de l'album : de loin on voit le visage, de près chaque souvenir.

| N° | Où | Que faire |
|---|---|---|
| 1 | **Choisir les photos** | Ouvre la photo en grand (🔍) puis **◆ Master** : elle devient la photo à reconstituer (la sélection du livre ne change pas). Ou : Paramètres > Mosaïque > « Photo master » > Parcourir… (n'importe quelle photo). Sans choix : la couverture. |
| 2 | Paramètres > Mosaïque | Format **A4 à A0**, nombre de petites photos en largeur (60 ; 80 à 120 en A0), part du visage fondu par-dessus (0.35), petites photos « gardées » ou « toutes » (plus de variété), ou un **dossier des photos en miniature** (Paramètres > Mosaïque, option ; lu sans être modifié). Vide = les photos sélectionnées de l'album ; rempli = les miniatures viennent de ce dossier ; « gardées + dossier » = les deux. |
| 2 bis | **Aperçu de la mosaïque** (ou « ↻ Actualiser l'aperçu » dans Paramètres > Mosaïque) | Rendu rapide en quelques secondes avec les réglages actuels, affiché à droite des réglages : essaie plusieurs formats, nombres de photos et mélanges avant de fabriquer le poster. |
| 3 | **Créer la mosaïque** | `livre_<Prénom>\mosaique` : le grand JPEG pour l'imprimeur, un aperçu, un détail vu de près et la liste des photos utilisées. |

### Réglages avancés (rendu professionnel)

| Réglage | Conseil | Effet |
|---|---|---|
| Rendu du visage | adaptatif | Plus de photo master sur les détails (yeux, bouche, contours), moins dans les aplats : visage net de loin, souvenirs visibles de près. « lumière » : les petites photos gardent leurs vraies couleurs. |
| Teinte des petites photos | 0.45 | 0 = couleurs d'origine ; plus haut = harmonie plus forte avec la photo master. |
| Liseré entre les photos | aucun ou blanc-fin | Effet « carreaux » discret. |
| Écart entre deux mêmes photos | 3 | Une photo n'est jamais reprise à moins de 3 cases. |
| Fond perdu | 3 mm | Marge rognée par l'imprimeur ; le texte reste toujours à l'intérieur. |
| Texte sur la photo | `Laura \| 2003 - 2026` | « \| » = nouvelle ligne. Position (auto = hors du visage, ou haut, bas, centre, un coin), police, couleur, taille, style (ombre, contour, bandeau translucide). |

Fichiers pour l'imprimeur : JPEG qualité maximale avec profil couleur sRGB, et PDF au format exact (fond perdu compris).

Qualité : 300 dpi jusqu'au A2, 200 dpi en A1, 150 dpi en A0 (norme des posters, regardés à plus d'un mètre). Chaque petite photo est fabriquée à partir de l'original, donc nette. Au moins 150 photos conseillées ; sinon les mêmes reviennent souvent (le journal le signale).

## 5. Ambiances BD : les bulles

Dans les ambiances `bd`, `bd-photo` et `prestige-mosaique-bd`, la bulle (« Joyeux anniversaire ! ») se place là où il n'y a pas de visage : en haut à droite, en haut à gauche, au centre ou en bas. Sa pointe est tournée vers la personne. Si aucun endroit libre n'existe, la case n'a pas de bulle : une bulle ne cache jamais un visage. L'encadré jaune (date, lieu, titre) se met dans le coin de la case où il ne cache aucun visage. Au besoin, il devient plus étroit ou plus large, et sa police descend jusqu'à 9 pt. Seules les fêtes ont une bulle (anniversaire, Noël, nouvel an, naissance, mariage, baptême, vacances, fête) ; il n'y a plus de bulle « En route ! » sur les voyages.

**Couleur des encadrés** : Paramètres > Livre > « Couleur des encadrés de légende (ambiances BD) ». Les choix sont jaune (par défaut), bleu, bleu-fonce, vert, vert-fonce, rose, orange, rouge, violet, turquoise, blanc, creme, gris, ou un code `#RRGGBB`. Le texte passe en blanc sur les couleurs foncées.

**Visages coupés** : le recadrage protège la tête entière (cheveux et menton). Si une photo ne peut pas être recadrée sans couper quelqu'un, elle est montrée entière dans sa case. Quand une photo est réduite (qualité insuffisante), l'encadré se place dans l'espace libre à côté d'elle.

## 6. Maintenance, mise à jour et partage

Le bouton **🔧 Maintenance** (en haut à droite) ouvre une fenêtre :

| Bouton | Pour qui | Rôle |
|---|---|---|
| Installer / réparer | tout le monde | Bibliothèques et dossiers de photos de référence |
| Vérifier l'outil (tests) | tout le monde | Tests automatiques sur des photos de synthèse |
| Mettre à jour l'outil | **administrateur seulement** | Dernière version depuis GitHub ; paramètres, sélections et livres jamais touchés |
| Fabriquer le zip à partager | **administrateur seulement** | `AlbumPhotos_partage_AAAAMMJJ.zip` dans le dossier de travail : sans tes réglages, ta lettre, ta base de visages, tes photos ni le lien vers ton dépôt GitHub |

**Mode administrateur** : automatique sur ta copie Git (`%USERPROFILE%\AlbumPhotos`), ou en créant un fichier vide `admin.txt` à côté de l'application. Une copie partagée n'a aucun bouton lié à GitHub, et sa mise à jour est désactivée : pour une nouvelle version, refais un zip et renvoie-le.

## 7. Où sont les fichiers

| Fichier | Emplacement |
|---|---|
| Réglages | `parametres_livre.txt`, dans le dossier de l'outil |
| Livre, aperçus, sélection | `C:\AlbumsFamille\livre_Laura\` |
| Dossier pour l'imprimeur | `C:\AlbumsFamille\livre_Laura\imprimeur_<ambiance>\` |
| Planches lettres | `C:\AlbumsFamille\livre_Laura\lettres\` |
| Photos de référence | `C:\AlbumsFamille\famille\<Prénom>\` |
| Journal de toutes les étapes | `journal.txt`, dans le dossier de l'outil |

## 8. En cas de problème

| Problème | Solution |
|---|---|
| L'icône ne fait rien | Double-clique sur `Lancer_application.bat`. Si Python est introuvable, réinstalle-le en cochant « Add python.exe to PATH », puis relance `Installer_application.bat`. |
| « Bibliothèques à installer » | **🔧 Maintenance** > **Installer / réparer**. |
| Le dossier de photos est introuvable | Branche le disque de backup. Si sa lettre a changé (D:, E:…), corrige le chemin dans Paramètres. Rien ne sera recalculé. |
| Une étape semble bloquée | La barre bouge tant que l'étape travaille. Pour les écrans de choix, termine avec **Terminer** dans le navigateur. Sinon, utilise **■ Arrêter l'étape**. |
| « … est ouvert dans Excel » | Ferme le fichier dans Excel, puis recommence. |
| Une erreur en rouge | Clique sur **journal.txt** (Ouvrir) et envoie ce fichier à Claude. |

## 9. Correspondance avec les fichiers .bat

| Bouton | Fichier .bat équivalent |
|---|---|
| Mettre à jour l'outil (administrateur) | `0_mettre_a_jour.bat` |
| Installer / réparer | `1_installer.bat` |
| Analyser le disque | `2_analyser_disque.bat` |
| Préparer la sélection | `3_preparer_selection.bat` |
| Choisir les photos | `3a_choisir_photos.bat` |
| Proposer des améliorations | `3b_proposer_ameliorations.bat` |
| Appliquer les propositions | `3c_appliquer_propositions.bat` |
| Réduire la sélection | `3d_reduire_selection.bat` |
| Aperçus des 10 ambiances | `4_apercu_3_ambiances.bat` |
| Livre final | `5_livre_final.bat` |
| Livre + PowerPoint modifiable | `6_livre_powerpoint.bat` |
| Choisir les photos des lettres | `7a_choisir_photos_lettres.bat` |
| Créer la planche lettres | `7_planche_lettres.bat` |
| Aperçu de la mosaïque | `8a_apercu_mosaique.bat` |
| Créer la mosaïque | `8_mosaique_photos.bat` |
| Vérifier l'outil (tests) | `9_tests_automatiques.bat` |
