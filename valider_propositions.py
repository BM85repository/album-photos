#!/usr/bin/env python3
"""valider_propositions.py - écran cliquable pour accepter ou refuser les propositions d'amélioration du livre.

Remplace l'aller-retour par Excel : chaque proposition (remplacer / ajouter / retirer) s'affiche avec ses photos ;
un clic l'accepte ou la refuse, puis « Appliquer » met à jour selection_livre.csv (copie de sauvegarde faite).
Les photos originales ne sont que lues (vignettes en cache dans le dossier de travail).

  python valider_propositions.py --sortie C:\\AlbumsFamille --personne Laura [--langue en]
"""
import argparse
import csv
import json
import secrets
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import album_famille as af
import choisir_photos as cp
import livre_photo as lp


class ServeurLocal(ThreadingHTTPServer):
    """Serveur de l'écran : un port qui n'est jamais partagé avec un autre écran encore ouvert (sous Windows,
    « allow_reuse_address » laisserait deux serveurs écouter le même port et les requêtes se perdre)."""
    allow_reuse_address = False
    daemon_threads = True

TEXTES_EN = [
    ('<html lang="fr">', '<html lang="en">'), ("Propositions d'amélioration", "Suggested improvements"),
    ("Un clic sur une proposition l'accepte ou la refuse. Rien n'est changé avant « Appliquer ».",
     "Click a suggestion to accept or refuse it. Nothing changes before \"Apply\"."),
    (">Tout accepter<", ">Accept all<"), (">Tout refuser<", ">Refuse all<"),
    (">Appliquer les choix<", ">Apply the choices<"),
    ('"Remplacements proposés"', '"Suggested replacements"'), ('"Ajouts proposés"', '"Suggested additions"'),
    ('"Retraits proposés"', '"Suggested removals"'),
    ('"✓ Acceptée"', '"✓ Accepted"'), ('"✗ Refusée"', '"✗ Refused"'),
    (" acceptée(s) sur ", " accepted out of "), ('"actuelle"', '"current"'), ('"proposée"', '"suggested"'),
    ('"Application…"', '"Applying…"'), ("Choix appliqués. Vous pouvez fermer cet onglet.",
                                        "Choices applied. You can close this tab."),
    (">(aucune)<", ">(none)<"), ("chargement…", "loading…"),
]
RAISONS_EN = [("plus belle photo du même souvenir", "nicer photo of the same memory"), ("avec un proche", "with a relative"),
              ("meilleure qualité", "better quality"), ("petit côté", "short side"), ("souvenir", "memory"),
              ("récente", "recent"), ("absent", "missing"), ("doublon", "duplicate")]


def lire_propositions(fichier):
    with open(fichier, newline="", encoding="utf-8-sig") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        return lecteur.fieldnames, list(lecteur)


def ecrire_propositions(fichier, colonnes, lignes):
    temporaire = fichier.with_suffix(".tmp")
    with open(temporaire, "w", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    temporaire.replace(fichier)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sortie", type=Path, default=Path("albums_sortie"))
    parser.add_argument("--personne", required=True)
    parser.add_argument("--langue", choices=["fr", "en"], default="fr")
    args = parser.parse_args()

    base = af.ouvrir_base(args.sortie)
    racine = Path(af.meta(base, "racine") or "")
    dossier = lp.dossier_livre(args.sortie, args.personne)
    fichier = dossier / "propositions.csv"
    if not fichier.exists():
        sys.exit("Aucune proposition : lancez d'abord « Proposer des améliorations ».")
    colonnes, propositions = lire_propositions(fichier)
    cache = args.sortie / "vignettes_choix"
    cache.mkdir(exist_ok=True)
    autorisees = {p[c] for p in propositions for c in ("photo_actuelle", "photo_proposee") if p.get(c)}
    jeton = secrets.token_urlsafe(24)
    verrou = threading.Lock()
    resultat = {}

    page = PAGE.replace("__JETON__", jeton).replace("__SUJET__", dossier.name[len("livre_"):])
    if args.langue == "en":
        for fr, en in TEXTES_EN:
            page = page.replace(fr, en)

    def raison(texte):
        if args.langue == "en":
            for fr, en in RAISONS_EN:
                texte = texte.replace(fr, en)
        return texte

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
            if url.path == "/api/propositions":
                return self.envoyer(200, json.dumps([
                    {"i": i, "action": p["action"], "raison": raison(p["raison"]), "titre": p.get("titre", ""),
                     "annee": p.get("annee", ""), "avant": p.get("photo_actuelle", ""),
                     "apres": p.get("photo_proposee", ""),
                     "ok": p["accepter"].strip().lower() in ("1", "oui", "x")} for i, p in enumerate(propositions)]))
            if url.path == "/vignette":
                relatif = parse_qs(url.query).get("f", [""])[0]
                if relatif not in autorisees:
                    return self.envoyer(404, "{}")
                try:
                    return self.envoyer(200, cp.vignette(racine, cache, relatif, 300), "image/jpeg")
                except OSError:
                    return self.envoyer(404, "{}")
            return self.envoyer(404, "{}")

        def do_POST(self):
            if not self.local() or self.headers.get("X-Jeton") != jeton:
                return self.envoyer(403, json.dumps({"erreur": "requête refusée"}))
            demande = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/choix":  # accepter / refuser (une ou toutes)
                with verrou:
                    indices = range(len(propositions)) if demande.get("tous") else [int(demande["i"])]
                    for i in indices:
                        propositions[i]["accepter"] = "1" if demande.get("ok") else "0"
                    try:
                        ecrire_propositions(fichier, colonnes, propositions)
                    except PermissionError:
                        return self.envoyer(409, json.dumps({"erreur": "propositions.csv est ouvert dans Excel : "
                                                                       "fermez-le puis recommencez."}))
                return self.envoyer(200, json.dumps({"ok": True}))
            if self.path == "/api/appliquer":
                with verrou:
                    try:
                        lp.cmd_appliquer(argparse.Namespace(sortie=args.sortie, personne=args.personne))
                    except PermissionError:
                        return self.envoyer(409, json.dumps({"erreur": "selection_livre.csv est ouvert dans Excel : "
                                                                       "fermez-le puis recommencez."}))
                    resultat["applique"] = sum(p["accepter"].strip() == "1" for p in propositions)
                self.envoyer(200, json.dumps({"ok": True, "acceptees": resultat["applique"]}))
                threading.Thread(target=serveur.shutdown, daemon=True).start()
                return None
            return self.envoyer(404, "{}")

    serveur.RequestHandlerClass = Gestionnaire
    adresse = f"http://127.0.0.1:{serveur.server_address[1]}/"
    print(f"Écran des propositions ouvert dans le navigateur : {adresse}")
    print("Cliquez pour accepter ou refuser, puis « Appliquer les choix » (rien n'est changé avant).", flush=True)
    webbrowser.open(adresse)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()  # libère le port tout de suite
    if "applique" in resultat:
        print(f"{resultat['applique']} proposition(s) appliquée(s) à selection_livre.csv (ancienne version sauvegardée).")
    else:
        print("Fermé sans appliquer : la sélection du livre n'a pas changé (vos choix sont gardés dans propositions.csv).")


PAGE = r"""<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Propositions d'amélioration - __SUJET__</title>
<style>
:root{--fond:#f6f3ee;--texte:#2f2b28;--doux:#8c847c;--vert:#2e9d4f;--rouge:#c0392b}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:var(--fond);color:var(--texte)}
header{position:sticky;top:0;z-index:5;background:#2f2b28;color:#fff;padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:18px;margin:0 12px 0 0}#compte{background:#ffe9a8;color:#2f2b28;border-radius:12px;padding:3px 10px;font-weight:700}
button{font:inherit;border:0;border-radius:6px;padding:8px 14px;cursor:pointer}
.secondaire{background:#fff;color:#2f2b28}.principal{background:var(--vert);color:#fff;font-weight:700;margin-left:auto}
.aide{padding:10px 16px;color:var(--doux);font-size:13px}h2{margin:18px 16px 8px;font-size:18px}
.prop{display:flex;align-items:center;gap:14px;background:#fff;margin:8px 16px;padding:10px 14px;border-radius:8px;
border:3px solid var(--vert);cursor:pointer;transition:opacity .1s}.prop.non{border-color:#d9d4cc;opacity:.55}
.prop img{width:170px;height:120px;object-fit:cover;border-radius:4px;background:#ddd;display:block}
.photo small{display:block;font-size:11px;color:var(--doux);margin-top:3px;max-width:170px;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}.vide{width:170px;height:120px;border:2px dashed #ccc;border-radius:4px;
display:flex;align-items:center;justify-content:center;color:#aaa;font-size:12px}
.fleche{font-size:26px;color:var(--doux)}.texte{flex:1}.texte b{display:block;margin-bottom:4px}
.etat{min-width:110px;text-align:center;font-weight:700;border-radius:6px;padding:8px}
.prop:not(.non) .etat{background:var(--vert);color:#fff}.prop.non .etat{background:#eee;color:#888}
#fin{padding:40px;text-align:center;font-size:18px}
</style>
<header><h1>Propositions d'amélioration</h1><span id="compte">chargement…</span>
<button class="secondaire" id="tous">Tout accepter</button><button class="secondaire" id="aucun">Tout refuser</button>
<button class="principal" id="appliquer">Appliquer les choix</button></header>
<div class="aide">Un clic sur une proposition l'accepte ou la refuse. Rien n'est changé avant « Appliquer ».</div>
<main id="liste"></main>
<script>
const JETON="__JETON__";let P=[];const $=s=>document.querySelector(s);
const TITRES={REMPLACER:"Remplacements proposés",AJOUTER:"Ajouts proposés",RETIRER:"Retraits proposés"};
function esc(t){return (t||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function poster(url,corps){return fetch(url,{method:"POST",headers:{"Content-Type":"application/json","X-Jeton":JETON},
  body:JSON.stringify(corps)}).then(r=>r.json().then(j=>{if(!r.ok){alert(j.erreur);throw j}return j}))}
function photo(f,libelle){return f?'<div class="photo"><img loading="lazy" src="/vignette?f='+encodeURIComponent(f)+'"><small>'+
  libelle+" · "+esc(f.split("/").pop())+"</small></div>":'<div class="vide">(aucune)</div>'}
function compte(){$("#compte").textContent=P.filter(p=>p.ok).length+" acceptée(s) sur "+P.length}
function afficher(){const m=$("#liste");m.innerHTML="";["REMPLACER","AJOUTER","RETIRER"].forEach(a=>{
  const ps=P.filter(p=>p.action==a);if(!ps.length)return;const h=document.createElement("h2");
  h.textContent=(TITRES[a]||a)+" ("+ps.length+")";m.appendChild(h);
  ps.forEach(p=>{const d=document.createElement("div");d.className="prop"+(p.ok?"":" non");
    d.innerHTML=photo(p.avant,"actuelle")+'<div class="fleche">→</div>'+photo(p.apres,"proposée")+
      '<div class="texte"><b>'+esc(p.titre)+(p.titre.includes(p.annee)?"":" "+esc(p.annee))+"</b>"+esc(p.raison)+'</div><div class="etat">'+
      (p.ok?"✓ Acceptée":"✗ Refusée")+"</div>";
    d.onclick=()=>poster("/api/choix",{i:p.i,ok:!p.ok}).then(()=>{p.ok=!p.ok;afficher()});m.appendChild(d)})});compte()}
fetch("/api/propositions").then(r=>r.json()).then(d=>{P=d;afficher()});
$("#tous").onclick=()=>poster("/api/choix",{tous:true,ok:true}).then(()=>{P.forEach(p=>p.ok=true);afficher()});
$("#aucun").onclick=()=>poster("/api/choix",{tous:true,ok:false}).then(()=>{P.forEach(p=>p.ok=false);afficher()});
$("#appliquer").onclick=()=>{$("#compte").textContent="Application…";poster("/api/appliquer",{}).then(j=>{
  document.body.innerHTML='<div id="fin">✓ '+j.acceptees+" acceptée(s) sur "+P.length+". Choix appliqués. Vous pouvez fermer cet onglet.</div>"})};
</script></html>"""


if __name__ == "__main__":
    main()
    # sortie immédiate : des vignettes encore en cours de lecture sur le disque externe (navigateur) ne doivent
    # pas retarder le retour à l'application (tout est déjà enregistré à ce stade)
    sys.stdout.flush()
    os._exit(0)
