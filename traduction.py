#!/usr/bin/env python3
"""traduction.py - textes du livre en anglais (option --langue en), sans connexion Internet.

Traduit tout ce que l'outil écrit lui-même : titres automatiques (anniversaires, Noël, voyages...), dates, âges,
pays, bulles et pages fixes de la BD, page de fin... Les textes saisis à la main (légendes, titres modifiés,
dédicace) restent tels quels : ils ne passent pas par un traducteur en ligne.
La casse est respectée : un encadré en MAJUSCULES reste en majuscules.
"""
import re

MOIS = {"janvier": "January", "février": "February", "fevrier": "February", "mars": "March", "avril": "April",
        "mai": "May", "juin": "June", "juillet": "July", "août": "August", "aout": "August",
        "septembre": "September", "octobre": "October", "novembre": "November", "décembre": "December",
        "decembre": "December"}

PAYS = {"France": "France", "Philippines": "Philippines", "Italie": "Italy", "Espagne": "Spain",
        "Portugal": "Portugal", "Allemagne": "Germany", "Belgique": "Belgium", "Suisse": "Switzerland",
        "Luxembourg": "Luxembourg", "Pays-Bas": "Netherlands", "Royaume-Uni": "United Kingdom",
        "Irlande": "Ireland", "Autriche": "Austria", "Grèce": "Greece", "Croatie": "Croatia", "Monaco": "Monaco",
        "Maroc": "Morocco", "Tunisie": "Tunisia", "États-Unis": "United States", "Canada": "Canada",
        "Mexique": "Mexico", "Brésil": "Brazil", "Japon": "Japan", "Corée du Sud": "South Korea", "Chine": "China",
        "Hong Kong": "Hong Kong", "Singapour": "Singapore", "Thaïlande": "Thailand", "Vietnam": "Vietnam",
        "Indonésie": "Indonesia", "Malaisie": "Malaysia", "Cambodge": "Cambodia", "Australie": "Australia",
        "Nouvelle-Zélande": "New Zealand", "Inde": "India", "Émirats arabes unis": "United Arab Emirates",
        "Turquie": "Turkey", "Égypte": "Egypt", "La Réunion": "Réunion", "Maurice": "Mauritius",
        "Pologne": "Poland", "Hongrie": "Hungary", "Tchéquie": "Czechia", "Russie": "Russia", "Ukraine": "Ukraine",
        "Norvège": "Norway", "Suède": "Sweden", "Danemark": "Denmark", "Finlande": "Finland", "Islande": "Iceland",
        "Taïwan": "Taiwan"}

PHRASES = {  # textes fixes (bulles, chapitres par thème, pages fixes, étiquettes d'aperçu)
    "Joyeux anniversaire !": "Happy birthday!", "Joyeux Noël !": "Merry Christmas!", "Bonne année !": "Happy New Year!",
    "Vive les vacances !": "Holidays!", "Coucou le monde !": "Hello world!", "Vive les mariés !": "Congratulations!",
    "Quel beau jour !": "What a beautiful day!", "C'est la fête !": "Party time!",
    "Les premiers jours": "The first days", "Vacances": "Holidays", "Voyages": "Travels",
    "Fêtes et grands moments": "Celebrations and big moments", "Au fil des jours": "Day by day",
    "Ici et là": "Here and there", "Mes souvenirs à écrire": "My memories to write down",
    "À suivre…": "To be continued…", "LES AVENTURES DE": "THE ADVENTURES OF", "SOUVENIRS": "MEMORIES",
    "N°1": "No. 1", "Visage coupé sur la photo d'origine": "Face cut off in the original photo",
    "Contrôle qualité (cette page n'est pas dans le livre final)": "Quality check (this page is not in the final book)",
}
MOTS = {"peu nette": "blurry", "faible définition": "low resolution", "réduite": "reduced", "Qualité": "Quality",
        "naissance": "birth", "Naissance": "Birth", "Voyage": "Trip", "Noël": "Christmas", "Nouvel An": "New Year",
        "Bienvenue": "Welcome"}


def casse(modele, texte):
    """Applique la casse du texte d'origine (MAJUSCULES, Capitale, minuscules) à la traduction."""
    if modele.isupper():
        return texte.upper()
    if modele[:1].isupper():
        return texte[:1].upper() + texte[1:]
    return texte


def _mois(m):
    return casse(m.group(0), MOIS[m.group(0).lower()])


MOIS_RE = "|".join(MOIS)
MOIS_COURT = {"jan": "Jan", "fév": "Feb", "fev": "Feb", "mar": "Mar", "avr": "Apr", "mai": "May", "jun": "Jun",
              "jul": "Jul", "aoû": "Aug", "aou": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "déc": "Dec",
              "dec": "Dec"}
MOIS_COURT_RE = "|".join(MOIS_COURT)
SEGMENTS = [  # un morceau ENTIER (entre « · », « – »...) qui correspond exactement à un texte fabriqué par l'outil
    (rf"Le premier anniversaire de (.+)", lambda m: f"{m.group(1)}'s first birthday"),
    (rf"Les (\d+) ans de (.+)", lambda m: f"{m.group(2)} turns {m.group(1)}"),
    (rf"(\S+) a (\d+) ans?", lambda m: f"{m.group(1)}, age {m.group(2)}"),
    (rf"Bienvenue (\S+)", lambda m: f"Welcome {m.group(1)}"),
    (rf"Anniversaire de (.+)", lambda m: f"{m.group(1)}'s birthday"),
    (rf"Noël( \d{{4}})?", lambda m: f"Christmas{m.group(1) or ''}"),
    (rf"Nouvel An( \d{{4}})?", lambda m: f"New Year{m.group(1) or ''}"),
    (rf"Du (\d+) au (\d+) ({MOIS_RE})( \d{{4}})?",
     lambda m: f"{m.group(1)}–{m.group(2)} {MOIS[m.group(3).lower()]}{m.group(4) or ''}"),
    (rf"Du (\d+) ({MOIS_RE}) au (\d+) ({MOIS_RE})( \d{{4}})?",
     lambda m: f"{m.group(1)} {MOIS[m.group(2).lower()]} – {m.group(3)} {MOIS[m.group(4).lower()]}{m.group(5) or ''}"),
    (rf"(\d+ )?({MOIS_RE})( \d{{4}})?", lambda m: f"{m.group(1) or ''}{MOIS[m.group(2).lower()]}{m.group(3) or ''}"),
    (rf"(\d+ )?({MOIS_COURT_RE}) (\d{{4}})",  # légende courte « 31 Oct 2010 », « Déc 2013 »
     lambda m: f"{m.group(1) or ''}{MOIS_COURT[m.group(2).lower()]} {m.group(3)}"),
    (rf"1 an", lambda m: "1 year"),
    (rf"(\d+) ans", lambda m: f"{m.group(1)} years"),
]
SEPARATEURS = re.compile(r"( · | – | - |: |, )")


def traduire_segment(segment):
    nu = segment.strip()
    if not nu:
        return segment
    for fr, en in {**PHRASES, **MOTS, **PAYS}.items():  # morceau qui est exactement un texte connu
        if nu.lower() == fr.lower():
            return segment.replace(nu, casse(nu, en))
    for motif, remplacement in SEGMENTS:
        m = re.fullmatch(motif, nu, flags=re.IGNORECASE)
        if m:
            return segment.replace(nu, casse(nu, remplacement(m)))
    return segment  # texte libre (légende, lettre...) : jamais traduit mot à mot


def traduire(texte, langue="fr"):
    """Texte fabriqué par l'outil dans la langue demandée (fr : inchangé). Seuls les morceaux qui sont en entier
    un texte de l'outil (date, âge, pays, titre automatique, bulle...) sont traduits : une phrase écrite à la main
    garde ses mots (« avec » reste « avec »)."""
    if langue != "en" or not texte or not texte.strip():
        return texte
    majuscules = texte.isupper()
    morceaux = SEPARATEURS.split(texte)
    resultat = "".join(m if i % 2 else traduire_segment(m) for i, m in enumerate(morceaux))
    return resultat.upper() if majuscules else resultat


if __name__ == "__main__":
    for t in ["Les 3 ans de Laura", "LES 3 ANS DE LAURA", "Le premier anniversaire de Laura", "Noël 2013",
              "12 AVRIL · PHÚ QUỐC · PHU QUOC - VIETNAM", "Du 4 au 5 août 2013", "Du 30 juin au 2 juillet 2015",
              "Voyage – Émirats arabes unis", "10 DÉCEMBRE · VOYAGE – ÉMIRATS ARABES UNIS", "2013 · 1 AN",
              "Laura a 12 ans", "Joyeux anniversaire !", "Mars 2014", "Bienvenue Laura", "AVEC TATA HELENE",
              "Qualité : peu nette - réduite", "Nouvel An 2016", "2012 · naissance",
              "Avec tout notre amour,", "Tu grandis trop vite, mais chaque souvenir avec toi reste notre trésor.",
              "Visite chez tata Maurice", "Maurice", "12 août · La Roche-sur-Yon, Vendée (FR)"]:
        print(f"{t!r:55} -> {traduire(t, 'en')!r}")
