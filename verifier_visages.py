#!/usr/bin/env python3
"""verifier_visages.py - écran pour corriger la reconnaissance des visages d'une personne.

Montre les visages que l'outil attribue à la personne (les moins sûrs d'abord) et ceux qu'il a presque attribués.
Un clic « C'est bien X » en fait une référence de plus (à l'âge exact de la photo) ; « Pas X » l'interdit pour
toujours. Ensuite, « Préparer la sélection » tient compte de ces corrections. Les photos ne sont que lues.

  python verifier_visages.py --sortie C:\\AlbumsFamille --personne Laura --famille C:\\AlbumsFamille\\famille
"""
import argparse
import hashlib
import json
import secrets
import sqlite3
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
from PIL import Image, ImageOps

import album_famille as af
from choisir_photos import ServeurLocal

TEXTES_EN = [
    ('<html lang="fr">', '<html lang="en">'), ("Vérifier la reconnaissance", "Check the recognition"),
    ("Un clic sur ✓ ou ✗ corrige l'outil", "One click on ✓ or ✗ corrects the tool"),
    ("Reconnus comme ", "Recognised as "), (" (les moins sûrs d'abord)", " (least sure first)"),
    ("Peut-être ", "Maybe "), (" (non retenus)", " (not kept)"), ('"✓ C\'est "', '"✓ It\'s "'), ('"✗ Pas "', '"✗ Not "'),
    (">Terminer<", ">Finish<"), ("Aucun visage dans cette liste.", "No face in this list."),
    ("corrections enregistrées", "corrections saved"),
    (">Effacer toutes mes corrections<", ">Erase all my corrections<"),
    ('"Effacer toutes les confirmations et tous les refus pour "+NOM+" ? La reconnaissance repartira des seules '
     'photos de référence."', '"Erase every confirmation and refusal for "+NOM+"? Recognition will start again from '
     'the reference photos only."'),
    ("Corrections enregistrées. Relancez « Préparer la sélection » pour en tenir compte. Vous pouvez fermer cet onglet.",
     "Corrections saved. Run \"Prepare the selection\" again to use them. You can close this tab."),
    ("puis relancez « Préparer la sélection » : vos corrections servent de références.",
     "then run \"Prepare the selection\" again: your corrections are used as references."),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sortie", type=Path, default=Path("albums_sortie"))
    parser.add_argument("--personne", required=True)
    parser.add_argument("--famille", type=Path, required=True)
    parser.add_argument("--seuil", type=float, default=af.SEUIL_VISAGE)
    parser.add_argument("--nombre", type=int, default=150, help="visages montrés par liste")
    parser.add_argument("--langue", choices=["fr", "en"], default="fr")
    args = parser.parse_args()

    base = af.ouvrir_base(args.sortie)
    racine = Path(af.meta(base, "racine") or "")
    detecteur, reco = af.modeles(args.sortie)
    refs, exclusions = af.charger_references(base, args.famille, detecteur, reco)
    nom = next((n for n in refs if n.lower() == args.personne.lower()), None)
    if nom is None:
        sys.exit(f"Pas de photos de référence pour {args.personne} dans {args.famille}.")
    deja = {(c["visage_id"]): c["ok"] for c in base.execute("SELECT visage_id, ok FROM confirmations WHERE nom = ?",
                                                             (nom,))}
    attribues = af.identifier(base, refs, exclusions, args.seuil)
    lignes = list(base.execute("SELECT v.id, v.photo_id, v.x, v.y, v.l, v.h, v.emb, p.chemin, p.date "
                               "FROM visages v JOIN photos p ON p.id = v.photo_id"))
    embs = np.stack([np.frombuffer(v["emb"], dtype=np.float32) for v in lignes]) if lignes else np.zeros((0, 128))
    noms, sims = af.ressemblances(refs, embs) if lignes else (sorted(refs), np.zeros((0, len(refs))))
    colonne = noms.index(nom)
    visages = {v["id"]: v for v in lignes}
    reconnus, peut_etre = [], []
    for i, v in enumerate(lignes):
        s = float(sims[i, colonne])
        if v["id"] in attribues and attribues[v["id"]][2] == nom:
            reconnus.append((s, v["id"]))
        elif s >= args.seuil - 0.12 and (v["id"], nom) not in exclusions:
            autre = attribues.get(v["id"], (None, None, "", 0))[2]
            peut_etre.append((s, v["id"], autre))
    reconnus.sort()  # les moins sûrs d'abord : c'est là que se cachent les erreurs
    peut_etre.sort(reverse=True)

    def element(s, vid, autre=""):
        v = visages[vid]
        return {"id": vid, "s": round(s * 100), "date": str(v["date"])[:10], "fichier": Path(v["chemin"]).name,
                "autre": autre, "etat": deja.get(vid)}

    donnees = {"nom": nom, "reconnus": [element(s, vid) for s, vid in reconnus[:args.nombre]],
               "total_reconnus": len(reconnus),
               "peut_etre": [element(s, vid, autre) for s, vid, autre in peut_etre[:args.nombre]]}
    empreintes = {v["id"]: hashlib.md5(f"{v['chemin']}|{af.empreinte_fichier(base, v['chemin'])}".encode())
                  .hexdigest()[:12] for v in lignes}
    cache = args.sortie / "vignettes_visages"
    cache.mkdir(exist_ok=True)
    jeton = secrets.token_urlsafe(24)
    verrou = threading.Lock()
    compte = {"ok": 0, "non": 0}
    page = PAGE.replace("__JETON__", jeton).replace("__NOM__", nom)
    if args.langue == "en":
        for fr, en in TEXTES_EN:
            page = page.replace(fr, en)

    def vignette_visage(vid):
        """Le visage et un peu autour (cheveux, épaules), recadré dans l'original (lecture seule)."""
        v = visages[vid]  # le n° de visage et la photo : jamais l'image d'un ancien visage
        cible = cache / f"{vid}_{empreintes[vid]}.jpg"
        if not cible.exists():
            v = visages[vid]
            with Image.open(racine / v["chemin"]) as im:
                im = ImageOps.exif_transpose(im)
                im.draft("RGB", (1600, 1600))
                im = im.convert("RGB")
                L, H = im.size
                cx, cy = (v["x"] + v["l"] / 2) * L, (v["y"] + v["h"] / 2) * H
                demi = max(v["l"] * L, v["h"] * H) * 0.9
                boite = (max(0, cx - demi), max(0, cy - demi), min(L, cx + demi), min(H, cy + demi))
                im = im.crop(tuple(map(round, boite)))
                im.thumbnail((220, 220))
                im.save(cible, quality=85)
        return cible.read_bytes()

    serveur = None
    for port in range(8765, 8800):
        try:
            serveur = ServeurLocal(("127.0.0.1", port), BaseHTTPRequestHandler)
            break
        except OSError:
            continue
    if serveur is None:
        sys.exit("Impossible d'ouvrir le serveur local (ports 8765 à 8799 occupés).")

    class Gestionnaire(BaseHTTPRequestHandler):
        def log_message(self, *a):
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

        def local(self):
            return (self.headers.get("Host") or "").rsplit(":", 1)[0] in ("127.0.0.1", "localhost")

        def do_GET(self):
            if not self.local():
                return self.envoyer(403, "{}")
            url = urlparse(self.path)
            if url.path == "/":
                return self.envoyer(200, page, "text/html; charset=utf-8")
            if url.path == "/api/visages":
                return self.envoyer(200, json.dumps(donnees))
            if url.path == "/visage":
                try:
                    vid = int(parse_qs(url.query).get("id", ["0"])[0])
                    if vid not in visages:
                        return self.envoyer(404, "{}")
                    return self.envoyer(200, vignette_visage(vid), "image/jpeg")
                except (OSError, ValueError):
                    return self.envoyer(404, "{}")
            return self.envoyer(404, "{}")

        def do_POST(self):
            if not self.local() or self.headers.get("X-Jeton") != jeton:
                return self.envoyer(403, json.dumps({"erreur": "requête refusée"}))
            demande = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/corriger":
                vid, ok = int(demande["id"]), demande.get("ok")
                if vid not in visages:
                    return self.envoyer(404, "{}")
                with verrou, sqlite3.connect(args.sortie / "base.sqlite") as connexion:  # connexion propre à ce fil
                    if ok is None:  # deuxième clic : on annule la correction
                        connexion.execute("DELETE FROM confirmations WHERE visage_id = ? AND nom = ?", (vid, nom))
                    else:
                        connexion.execute("REPLACE INTO confirmations VALUES (?, ?, ?)", (vid, nom, 1 if ok else 0))
                        compte["ok" if ok else "non"] += 1
                return self.envoyer(200, json.dumps({"ok": True}))
            if self.path == "/api/effacer":  # repartir de zéro : toutes les corrections de cette personne
                with verrou, sqlite3.connect(args.sortie / "base.sqlite") as connexion:
                    n = connexion.execute("DELETE FROM confirmations WHERE nom = ?", (nom,)).rowcount
                print(f"Corrections effacées pour {nom} : {n}.", flush=True)
                return self.envoyer(200, json.dumps({"ok": True, "effacees": n}))
            if self.path == "/api/fin":
                self.envoyer(200, json.dumps({"ok": True}))
                threading.Thread(target=serveur.shutdown, daemon=True).start()
                return None
            return self.envoyer(404, "{}")

    serveur.RequestHandlerClass = Gestionnaire
    adresse = f"http://127.0.0.1:{serveur.server_address[1]}/"
    print(f"{nom} : {len(reconnus)} visage(s) reconnu(s), {len(peut_etre)} « peut-être ».")
    print(f"Écran de vérification ouvert dans le navigateur : {adresse}", flush=True)
    webbrowser.open(adresse)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
    print(f"Corrections : {compte['ok']} confirmé(s), {compte['non']} refusé(s). Relancez « Préparer la sélection » "
          "pour en tenir compte.")


PAGE = r"""<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Vérifier la reconnaissance - __NOM__</title>
<style>
:root{--fond:#f6f3ee;--texte:#2f2b28;--doux:#8c847c;--vert:#2e9d4f;--rouge:#c0392b}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:var(--fond);color:var(--texte)}
header{position:sticky;top:0;z-index:5;background:#2f2b28;color:#fff;padding:10px 16px;display:flex;gap:14px;align-items:center}
header h1{font-size:18px;margin:0}#compte{color:#ffe9a8;font-size:13px}#effacer{margin-left:auto;background:#5d554e;color:#fff;border:0;border-radius:6px;padding:8px 12px;font:inherit;cursor:pointer}
#fin{background:var(--vert);color:#fff;
border:0;border-radius:6px;padding:8px 16px;font:inherit;font-weight:700;cursor:pointer}
.aide{padding:10px 16px;color:var(--doux);font-size:13px}h2{margin:18px 16px 8px;font-size:17px}
.grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;padding:0 16px}
.carte{background:#fff;border-radius:8px;overflow:hidden;border:3px solid transparent}
.carte.ok{border-color:var(--vert)}.carte.non{border-color:var(--rouge);opacity:.6}
.carte img{width:100%;height:170px;object-fit:cover;display:block;background:#ddd}
.info{font-size:11px;color:var(--doux);padding:4px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.boutons{display:flex}.boutons button{flex:1;border:0;padding:8px 4px;font:inherit;font-size:12px;cursor:pointer;background:#eee}
.boutons .oui.actif{background:var(--vert);color:#fff}.boutons .non.actif{background:var(--rouge);color:#fff}
.vide{padding:16px;color:var(--doux)}#merci{padding:40px;text-align:center;font-size:18px}
</style>
<header><h1>Vérifier la reconnaissance : __NOM__</h1><span id="compte"></span><button id="effacer">Effacer toutes mes corrections</button><button id="fin">Terminer</button></header>
<div class="aide">Un clic sur ✓ ou ✗ corrige l'outil (un 2e clic annule), puis relancez « Préparer la sélection » : vos corrections servent de références.</div>
<main id="liste"></main>
<script>
const JETON="__JETON__",NOM="__NOM__",EFFACER="Effacer toutes les confirmations et tous les refus pour "+NOM+" ? La reconnaissance repartira des seules photos de référence.";let D,faits=0;const $=s=>document.querySelector(s);
function carte(v){const c=document.createElement("div");c.className="carte"+(v.etat===1?" ok":v.etat===0?" non":"");
  c.innerHTML='<img loading="lazy" src="/visage?id='+v.id+'"><div class="info">'+v.date+" · "+v.s+" %"+
    (v.autre?" · "+v.autre:"")+'</div><div class="boutons"><button class="oui'+(v.etat===1?" actif":"")+'">'+"✓ C'est "+NOM+
    '</button><button class="non'+(v.etat===0?" actif":"")+'">'+"✗ Pas "+NOM+"</button></div>";
  const [oui,non]=c.querySelectorAll("button");
  const corriger=ok=>{const valeur=(v.etat===(ok?1:0))?null:ok;fetch("/api/corriger",{method:"POST",
    headers:{"Content-Type":"application/json","X-Jeton":JETON},body:JSON.stringify({id:v.id,ok:valeur})}).then(()=>{
    v.etat=valeur===null?null:(valeur?1:0);faits++;$("#compte").textContent=faits+" corrections enregistrées";
    c.replaceWith(carte(v))})};
  oui.onclick=()=>corriger(true);non.onclick=()=>corriger(false);return c}
function section(titre,liste){const h=document.createElement("h2");h.textContent=titre;$("#liste").appendChild(h);
  const g=document.createElement("div");g.className="grille";
  if(!liste.length)g.innerHTML='<div class="vide">Aucun visage dans cette liste.</div>';
  liste.forEach(v=>g.appendChild(carte(v)));$("#liste").appendChild(g)}
fetch("/api/visages").then(r=>r.json()).then(d=>{D=d;
  section("Reconnus comme "+NOM+" ("+d.total_reconnus+") (les moins sûrs d'abord)",d.reconnus);
  section("Peut-être "+NOM+" (non retenus)",d.peut_etre)});
$("#effacer").onclick=()=>{if(!confirm(EFFACER))return;fetch("/api/effacer",{method:"POST",headers:{"X-Jeton":JETON}})
  .then(r=>r.json()).then(()=>location.reload())};
$("#fin").onclick=()=>fetch("/api/fin",{method:"POST",headers:{"X-Jeton":JETON}}).then(()=>{document.body.innerHTML=
  '<div id="merci">Corrections enregistrées. Relancez « Préparer la sélection » pour en tenir compte. Vous pouvez fermer cet onglet.</div>'});
</script></html>"""


if __name__ == "__main__":
    main()
    # sortie immédiate : des vignettes encore en cours de lecture sur le disque externe (navigateur) ne doivent
    # pas retarder le retour à l'application (tout est déjà enregistré à ce stade)
    sys.stdout.flush()
    os._exit(0)
