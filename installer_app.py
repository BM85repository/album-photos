#!/usr/bin/env python3
"""installer_app.py - installe l'application « Album Photos » sur le PC (Windows).

1. installe les bibliothèques Python (requirements.txt) ;
2. crée parametres_livre.txt s'il n'existe pas ;
3. crée l'icône et les raccourcis « Album Photos » sur le Bureau et dans le menu Démarrer ;
4. lance l'application.

  python installer_app.py               installation complète
  python installer_app.py --raccourcis  raccourcis seulement (après un déplacement de l'outil), puis lancement
Bibliothèque standard uniquement (Pillow, s'il est là, sert à dessiner l'icône).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
APPLI = ICI / "album_photos_app.pyw"
NOM = "Album Photos"


def afficher(texte=""):
    print(texte, flush=True)
    with open(ICI / "journal.txt", "a", encoding="utf-8") as f:
        f.write(texte + "\n")


def pythonw():
    exe = Path(sys.executable)
    candidat = exe.with_name("pythonw.exe")
    return candidat if candidat.exists() else exe


def creer_icone():
    """Icône (appareil photo + cœur) en .ico pour Windows et .png pour la fenêtre ; ignorée sans Pillow."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    taille = 256
    im = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 8, 248, 248), radius=48, fill="#2F2B28")
    d.rounded_rectangle((40, 84, 216, 204), radius=22, fill="#F6F3EE")
    d.rounded_rectangle((88, 60, 150, 92), radius=10, fill="#F6F3EE")
    d.ellipse((88, 104, 168, 184), fill="#2F2B28")
    d.ellipse((100, 116, 156, 172), fill="#C8A96A")
    cx, cy, r = 186, 72, 30  # petit cœur rouge
    d.ellipse((cx - r, cy - r // 2 - 6, cx, cy + r // 2 - 6), fill="#D7263D")
    d.ellipse((cx, cy - r // 2 - 6, cx + r, cy + r // 2 - 6), fill="#D7263D")
    d.polygon([(cx - r + 2, cy + 2), (cx + r - 2, cy + 2), (cx, cy + r + 8)], fill="#D7263D")
    im.save(ICI / "album_photos.png")
    im.save(ICI / "album_photos.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
                                             (256, 256)])
    return ICI / "album_photos.ico"


def ps(chemin):
    """Chemin entre apostrophes pour PowerShell (une apostrophe dans le chemin est doublée)."""
    return "'" + str(chemin).replace("'", "''") + "'"


def creer_raccourcis(icone):
    if os.name != "nt":
        afficher("(Raccourcis : seulement sous Windows.)")
        return
    script = (
        "$w = New-Object -ComObject WScript.Shell; "
        "foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { "
        f"$s = $w.CreateShortcut((Join-Path $d '{NOM}.lnk')); "
        f"$s.TargetPath = {ps(pythonw())}; "
        f"$s.Arguments = {ps(chr(34) + str(APPLI) + chr(34))}; "
        f"$s.WorkingDirectory = {ps(ICI)}; "
        "$s.Description = 'Livre photo et planche lettres'; "
        + (f"$s.IconLocation = {ps(icone)}; " if icone else "")
        + "$s.Save(); Write-Output (Join-Path $d '" + NOM + ".lnk') }"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True)
    if r.returncode:
        afficher("Les raccourcis n'ont pas pu être créés : " + (r.stderr or r.stdout).strip())
        afficher(f"Vous pouvez lancer l'application avec Lancer_application.bat (dans {ICI}).")
    else:
        for ligne in r.stdout.split():
            if ligne.strip():
                afficher(f"Raccourci créé : {ligne.strip()}")


def lancer_appli():
    options = {"creationflags": subprocess.DETACHED_PROCESS} if os.name == "nt" else {}
    subprocess.Popen([str(pythonw()), str(APPLI)], cwd=ICI, **options)


def main():
    raccourcis_seulement = "--raccourcis" in sys.argv
    afficher(f"===== Installation de l'application {NOM} =====")
    if sys.version_info < (3, 9):
        afficher(f"Python {sys.version.split()[0]} est trop ancien : installez Python 3.11 ou plus récent.")
        sys.exit(1)
    afficher(f"Python {sys.version.split()[0]} : {sys.executable}")
    afficher(f"Dossier de l'outil : {ICI}")
    if not raccourcis_seulement:
        afficher("Installation des bibliothèques (quelques minutes la première fois)...")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r",
                            str(ICI / "requirements.txt")])
        if r.returncode == 0:
            import hashlib
            (ICI / ".bibliotheques_installees").write_text(hashlib.md5(
                (ICI / "requirements.txt").read_bytes() + sys.version.encode()).hexdigest())
        if r.returncode:
            afficher("L'installation des bibliothèques a échoué (voir ci-dessus). Vérifiez la connexion Internet "
                     "et relancez Installer_application.bat.")
            sys.exit(1)
    if not (ICI / "parametres_livre.txt").exists() and (ICI / "parametres_livre.modele.txt").exists():
        shutil.copy(ICI / "parametres_livre.modele.txt", ICI / "parametres_livre.txt")
        afficher("parametres_livre.txt créé (à remplir dans l'onglet Paramètres de l'application).")
    icone = creer_icone()
    creer_raccourcis(icone)
    afficher("")
    afficher(f"C'est installé. Ouvrez « {NOM} » depuis le Bureau ou le menu Démarrer.")
    lancer_appli()


if __name__ == "__main__":
    main()
