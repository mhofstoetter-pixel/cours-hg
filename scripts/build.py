#!/usr/bin/env python3
"""Construit le site public à partir d'une sauvegarde Éléa (.mbz).

    python3 scripts/build.py <sauvegarde.mbz> --niveau 4e     # lit la sauvegarde, met à jour data/4e.json, régénère docs/
    python3 scripts/build.py --pages                          # régénère docs/ à partir de data/*.json seulement

Rien de nominatif n'est publié : voir « exclusions » dans scripts/config.json
et le contrôle final, qui bloque la construction en cas de doute.
"""
import argparse
import datetime
import json
import re
import shutil
import string
import sys
import unicodedata
from html import escape
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))

import bex  # noqa: E402
import elea  # noqa: E402
from nettoyage import nettoyer  # noqa: E402

RACINE = ICI.parent
DATA = RACINE / "data"
DOCS = RACINE / "docs"
SOURCES = RACINE / "sources"
TEMPLATES = RACINE / "templates"
CONFIG = json.loads((ICI / "config.json").read_text(encoding="utf-8"))

DISCIPLINES = {"H": "histoire", "G": "geographie", "E": "emc"}
TYPES_RUBRIQUES = {"cours": "Cours", "bex": "BEX", "methode": "Méthodologie", "qcm": "QCM", "enquetes": "Enquête"}
NOMS_DISCIPLINES = {"histoire": "Histoire", "geographie": "Géographie", "emc": "EMC", "methode": "Méthode"}


# ------------------------------------------------------------------ outils

def slug(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:60].strip("-") or "sans-titre"


def bas(t):
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def contient(texte, motifs):
    b = bas(texte)
    return any(bas(m) in b for m in motifs)


def code_de(titre):
    m = re.search(r"\b([HGE]\d{1,2}[a-z]?)\b", titre)
    if m:
        return m.group(1)
    m = re.search(r"\bBEX\s*(\d+)\b", titre, re.I)
    if m:
        return "BEX %s" % m.group(1)
    return ""


def discipline_de(code, rubrique):
    if code and code[0] in DISCIPLINES and code[1:2].isdigit():
        return DISCIPLINES[code[0]]
    if rubrique in ("bex", "methode"):
        return "methode"
    return None


def titre_propre(titre):
    """« Cours H1 : Bourgeoisie… » → « Bourgeoisie… » ; « BEX 2 - Présenter… » → « Présenter… »."""
    t = re.sub(r"^(cours|qcm|bex)?\s*([HGE]\d{1,2}[a-z]?|\d+)?\s*[-:–]\s*", "", titre, flags=re.I).strip()
    t = re.sub(r"^([HGE]\d{1,2}[a-z]?)\s*[-:–]\s*", "", t).strip()
    return t[:1].upper() + t[1:] if t else titre


def lien_public(url):
    """Lien Google sans paramètres (ouid = identifiant du compte Google du professeur)."""
    m = re.match(r"(https://docs\.google\.com/(?:document|presentation|spreadsheets)/d/[A-Za-z0-9_-]+)", url or "")
    return (m.group(1) + "/edit?usp=sharing") if m else (url or "")


def id_gdoc(url):
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})", url or "")
    return m.group(1) if m else ""


# ------------------------------------------------------------------ lecture de la sauvegarde

def rubrique_de(section_titre):
    for r in CONFIG["rubriques"]:
        if contient(section_titre, r["sections"]):
            return r["id"]
    return None


def extraire(mbz, niveau):
    d = elea.lire(mbz)
    ex = CONFIG["exclusions"]
    items, ecartes = [], []
    for s in d["sections"]:
        if contient(s["titre"], ex["sections"]) and not rubrique_de(s["titre"]):
            for m in s["sequence"]:
                ecartes.append((d["activites"][m]["titre"], "section « %s »" % s["titre"]))
            continue
        rub = rubrique_de(s["titre"])
        for m in s["sequence"]:
            a = d["activites"][m]
            raison = None
            if not s["visible"] or not a["visible"]:
                raison = "caché sur Éléa"
            elif a["type"] in ex["types"]:
                raison = "type « %s »" % a["type"]
            elif contient(a["titre"], ex["titres"]):
                raison = "titre"
            elif a["type"] == "url" and contient(a.get("url", ""), ex["urls"]):
                raison = "lien vers un tableur ou formulaire"
            elif rub is None:
                raison = "section « %s » non reconnue" % s["titre"]
            elif a["type"] not in ("url", "quiz"):
                raison = "type « %s » non pris en charge" % a["type"]
            if raison:
                ecartes.append((a["titre"], raison))
                continue
            titre = a.get("nom") or a["titre"]
            code = CONFIG["chapitres"].get(titre) or code_de(titre)
            item = {
                "id": a["id"],
                "rubrique": "qcm" if a["type"] == "quiz" else rub,
                "titre": titre_propre(titre) if a["type"] == "url" else titre,
                "titre_eléa": titre,
                "code": code if code != niveau else "",
                "discipline": CONFIG.get("disciplines", {}).get(titre) or discipline_de(code, rub),
                "slug": slug(titre),
            }
            if a["type"] == "url":
                item["lien"] = lien_public(a["url"])
                item["gdoc"] = id_gdoc(a["url"])
                item["intro"] = a.get("intro", "")
            else:
                item["intro"] = a.get("intro", "")
                item["tirage"] = a["tirage"]
                item["questions"] = a["questions"]
                item["questions_ignorees"] = a["ignorees"]
            items.append(item)
    return {"niveau": niveau, "cours": d["cours"]["nom"], "date_sauvegarde": d["cours"]["date"],
            "items": items, "ecartes": [{"titre": t, "raison": r} for t, r in ecartes]}


# ------------------------------------------------------------------ pages

def gabarit(nom):
    return string.Template((TEMPLATES / nom).read_text(encoding="utf-8"))


def _versions():
    import hashlib
    v = {}
    for f in (DOCS / "assets").glob("*.*"):
        v[f.name] = hashlib.sha1(f.read_bytes()).hexdigest()[:8]
    return v


def ecrire(chemin, texte):
    """Écrit un fichier ; dans les pages, ajoute ?v=<empreinte> aux CSS/JS du site
    pour que les navigateurs reprennent la nouvelle version après une mise à jour."""
    if chemin.suffix == ".html":
        v = _versions()
        texte = re.sub(r'(assets/)([\w.-]+\.(?:css|js))"',
                       lambda m: '%s%s?v=%s"' % (m.group(1), m.group(2), v.get(m.group(2), "0")), texte)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")


def ariane(morceaux):
    """morceaux : liste de (texte, lien ou None)."""
    li = []
    for t, l in morceaux:
        li.append('<li><a href="%s">%s</a></li>' % (l, escape(t)) if l else '<li aria-current="page">%s</li>' % escape(t))
    return "<ol>%s</ol>" % "".join(li)


def commun(racine, titre_page, fil):
    return {"racine": racine, "titre_page": escape(titre_page), "fil_ariane": fil,
            "annee": str(datetime.date.today().year)}


def carte(item, lien):
    disc = item.get("discipline") or "methode"
    code = '<span class="hg-carte__code">%s</span>' % escape(item["code"]) if item["code"] else ""
    typ = TYPES_RUBRIQUES.get(item["rubrique"], "")
    if item["rubrique"] == "qcm":
        n = item["tirage"] or len(item["questions"])
        typ = "QCM · %d questions" % n
    return ('<a class="hg-carte hg-pastille--%s" href="%s">%s<span class="hg-carte__titre">%s</span>'
            '<span class="hg-carte__type">%s</span></a>') % (disc, lien, code, escape(item["titre"]), escape(typ))


def google_vers_html(html):
    """Traduit la mise en forme par classes CSS de Google Docs en balises :
    gras / italique / souligné → strong / em / u ; paragraphe court tout en gras
    marqué « garder avec le suivant » → titre (h1 si ≥ 12 pt, sinon h2 ; décalés d'un cran ensuite)."""
    css = {}
    for noms, decl in re.findall(r"((?:\.c\d+\s*,?\s*)+)\{([^}]*)\}", html):
        for n in re.findall(r"c\d+", noms):
            css[n] = css.get(n, "") + ";" + decl.replace(" ", "")

    def props(classes):
        return ";".join(css.get(c, "") for c in classes.split())

    def taille(p):
        m = re.findall(r"font-size:([\d.]+)pt", p)
        return float(m[-1]) if m else 11.0

    def span(m):
        p, txt = props(m.group(1)), m.group(2)
        if not re.sub(r"<[^>]+>|&nbsp;|\s", "", txt):
            return txt
        if "text-decoration:underline" in p and "<a " not in txt:
            txt = "<u>%s</u>" % txt
        if "font-style:italic" in p:
            txt = "<em>%s</em>" % txt
        if "font-weight:700" in p or "font-weight:bold" in p:
            txt = '<strong data-pt="%s">%s</strong>' % (taille(p), txt)
        return txt

    html = re.sub(r'<span class="([^"]*)"[^>]*>(.*?)</span>', span, html, flags=re.S)

    def para(m):
        p, inner = props(m.group(1)), m.group(2)
        texte = re.sub(r"<[^>]+>", "", inner).strip()
        hors_gras = re.sub(r"<strong[^>]*>.*?</strong>", "", inner, flags=re.S)
        hors_gras = re.sub(r"<[^>]+>|&nbsp;|\s", "", hors_gras)
        if "page-break-after:avoid" in p and texte and not hors_gras and len(texte) <= 140:
            tailles = [float(x) for x in re.findall(r'data-pt="([\d.]+)"', inner)] or [11.0]
            niveau = "h1" if max(tailles) >= 12 else "h2"
            inner = re.sub(r"</?strong[^>]*>", "", inner)
            return "<%s>%s</%s>" % (niveau, inner, niveau)
        return "<p>%s</p>" % inner

    html = re.sub(r'<p class="([^"]*)"[^>]*>(.*?)</p>', para, html, flags=re.S)
    return html


def contenu_ressource(niveau, item):
    """HTML de la page : export HTML du Google Doc s'il existe dans sources/."""
    src = SOURCES / niveau / ("%s.html" % item["slug"])
    if src.exists():
        html = src.read_text(encoding="utf-8", errors="replace")
        # Commentaires Google (peuvent contenir des noms) : renvois et blocs de fin de document
        html = re.sub(r'<div[^>]*>\s*<p[^>]*>\s*<a[^>]*href="#cmnt_ref\d+".*?</div>', "", html, flags=re.S)
        html = re.sub(r'<sup>\s*<a[^>]*href="#cmnt\d+"[^>]*>.*?</a>\s*</sup>', "", html, flags=re.S)
        html = google_vers_html(html)
        m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
        corps = nettoyer(m.group(1) if m else html, h_decalage=1)
        corps = re.sub(r'(<img[^>]*src=")(?!https?:|data:)', r'\1./', corps)
        if item["rubrique"] in ("bex", "methode"):
            interactif = bex.structurer(corps)
            if interactif:
                return interactif, True
        corps = corps.replace("<table>", '<table tabindex="0">')
        return corps, True
    return ("<p>La version web de ce document arrive bientôt. "
            "Vous pouvez déjà l'ouvrir en PDF ou sur Google Docs.</p>"), False


def copier_medias(niveau, item, dest):
    """Copie le PDF et les images de l'export HTML (dossier sources/<niveau>/<slug>_images/)."""
    pdf = SOURCES / niveau / ("%s.pdf" % item["slug"])
    lien_pdf = ""
    if pdf.exists():
        shutil.copy2(pdf, dest / pdf.name)
        lien_pdf = pdf.name
    images = SOURCES / niveau / ("%s_images" % item["slug"])
    if images.is_dir():
        shutil.copytree(images, dest / "images", dirs_exist_ok=True)
    return lien_pdf


def boutons(lien_pdf, lien_gdoc):
    b = []
    if lien_pdf:
        b.append('<a class="hg-bouton hg-bouton--pdf" href="%s" download>Télécharger le PDF</a>' % escape(lien_pdf))
    if lien_gdoc:
        b.append('<a class="hg-bouton hg-bouton--gdoc" href="%s" target="_blank" rel="noopener">Ouvrir le Google Doc</a>'
                 % escape(lien_gdoc, quote=True))
    return "".join(b)


def generer(niveaux_data):
    if not (TEMPLATES / "accueil.html").exists():
        print("! templates/ absent : pages non générées (données à jour dans data/).")
        return []
    rapport = []
    # Accueil
    cartes_niv = []
    for niv in CONFIG["niveaux"]:
        nd = niveaux_data.get(niv)
        n = len(nd["items"]) if nd else 0
        sous = "Cours, BEX, QCM et enquêtes" if n else "Bientôt disponible"
        cartes_niv.append('<a class="hg-carte" href="%s/index.html"><span class="hg-carte__code">%s</span>'
                          '<span class="hg-carte__titre">Classe de %s</span><span class="hg-carte__type">%s</span></a>'
                          % (niv, niv, niv, sous))
    v = commun("", "Cours d'Histoire-Géo-EMC", "")
    v.update(niveaux="".join(cartes_niv), lien_bex=CONFIG["lien_bex"])
    ecrire(DOCS / "index.html", gabarit("accueil.html").safe_substitute(v))

    for niv in CONFIG["niveaux"]:
        nd = niveaux_data.get(niv) or {"items": []}
        base = DOCS / niv
        rubs = []
        for r in CONFIG["rubriques"]:
            its = [i for i in nd["items"] if i["rubrique"] == r["id"]]
            if its:
                corps = "\n".join(carte(i, ("qcm/%s/index.html" % i["slug"]) if r["id"] == "qcm"
                                         else ("%s/index.html" % i["slug"])) for i in its)
            else:
                corps = '<p class="hg-vide">Bientôt disponible.</p>'
            rubs.append('<section class="hg-rubrique" id="%s">\n<h2 class="hg-rubrique__titre">%s</h2>\n%s\n</section>'
                        % (r["id"], escape(r["titre"]), corps))
        v = commun("../", "%s · Cours d'Histoire-Géo-EMC" % niv, ariane([("Accueil", "../index.html"), (niv, None)]))
        v.update(niveau=niv, rubriques="".join(rubs))
        ecrire(base / "index.html", gabarit("niveau.html").safe_substitute(v))

        for it in nd["items"]:
            if it["rubrique"] == "qcm":
                dest = base / "qcm" / it["slug"]
                dest.mkdir(parents=True, exist_ok=True)
                q = {"id": it["slug"], "titre": it["titre"], "niveau": niv, "chapitre": it["code"] or None,
                     "discipline": it["discipline"] if it["discipline"] != "methode" else None,
                     "intro": it["intro"], "tirage": it["tirage"], "questions": it["questions"]}
                ecrire(dest / "qcm.json", json.dumps(q, ensure_ascii=False))
                v = commun("../../../", "%s · %s" % (it["titre"], niv),
                           ariane([("Accueil", "../../../index.html"), (niv, "../../index.html"), ("Les QCM", "../../index.html#qcm"), (it["titre"], None)]))
                v.update(titre=escape(it["titre"]), code=escape(it["code"]), discipline=it["discipline"] or "methode",
                         intro=it["intro"], retour="../../index.html#qcm")
                ecrire(dest / "index.html", gabarit("qcm.html").safe_substitute(v))
                rapport.append(("QCM", niv, it["titre"], "%d questions" % len(it["questions"])))
            else:
                dest = base / it["slug"]
                dest.mkdir(parents=True, exist_ok=True)
                html, web = contenu_ressource(niv, it)
                extra = ""
                if html.startswith('<div class="bex"'):
                    extra = ('<link rel="stylesheet" href="../../assets/bex.css">\n'
                             '<script src="../../assets/bex.js" defer></script>')
                lien_pdf = copier_medias(niv, it, dest)
                rub_titre = next(r["titre"] for r in CONFIG["rubriques"] if r["id"] == it["rubrique"])
                v = commun("../../", "%s · %s" % (it["titre"], niv),
                           ariane([("Accueil", "../../index.html"), (niv, "../index.html"), (rub_titre, "../index.html#%s" % it["rubrique"]), (it["titre"], None)]))
                v.update(titre=escape(it["titre"]), code=escape(it["code"]), discipline=it["discipline"] or "methode",
                         contenu=html, extra_head=extra, lien_pdf=escape(lien_pdf), lien_gdoc=escape(it["lien"], quote=True),
                         boutons=boutons(lien_pdf, it["lien"]), retour="../index.html#%s" % it["rubrique"])
                ecrire(dest / "index.html", gabarit("ressource.html").safe_substitute(v))
                etat = ", ".join(x for x in ["page web" if web else "page web EN ATTENTE", "PDF" if lien_pdf else "PDF EN ATTENTE", "Google Doc"])
                rapport.append((rub_titre, niv, it["titre"], etat))
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    return rapport


# ------------------------------------------------------------------ contrôle de vie privée

INTERDITS = [r"docs\.google\.com/spreadsheets", r"suivi des notes", r"groupe de travail", r"groupes de travail",
             r"\.mbz\b", r"createdby", r"ouid=", r"#cmnt", r"@ac-[a-z]+\.fr", r"elea\.apps\.education\.fr/user"]


def controle():
    problemes = []
    for f in DOCS.rglob("*"):
        if f.suffix.lower() not in (".html", ".json", ".js", ".css"):
            continue
        t = f.read_text(encoding="utf-8", errors="replace").lower()
        for motif in INTERDITS:
            if re.search(motif, t):
                problemes.append("%s : « %s »" % (f.relative_to(RACINE), motif))
    return problemes


# ------------------------------------------------------------------ programme

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mbz", nargs="?", help="sauvegarde Éléa .mbz")
    p.add_argument("--niveau", help="niveau de la sauvegarde (4e, 5e…)")
    p.add_argument("--pages", action="store_true", help="régénérer les pages sans lire de sauvegarde")
    a = p.parse_args()

    DATA.mkdir(exist_ok=True)
    if a.mbz:
        if not a.niveau:
            p.error("préciser --niveau (ex. --niveau 4e)")
        nd = extraire(a.mbz, a.niveau)
        ecrire(DATA / ("%s.json" % a.niveau), json.dumps(nd, ensure_ascii=False, indent=1))
        print("Sauvegarde « %s » → data/%s.json" % (nd["cours"], a.niveau))
        print("  Publié : %d éléments" % len(nd["items"]))
        for it in nd["items"]:
            extra = ""
            if it["rubrique"] == "qcm":
                extra = " (%d questions%s%s)" % (len(it["questions"]), ", tirage de %d" % it["tirage"] if it["tirage"] else "",
                                                ", ignorées : %s" % it["questions_ignorees"] if it["questions_ignorees"] else "")
            print("    + [%s] %s%s" % (it["rubrique"], it["titre_eléa"], extra))
        print("  Écarté : %d éléments" % len(nd["ecartes"]))
        for e in nd["ecartes"]:
            print("    - %s (%s)" % (e["titre"], e["raison"]))
    elif not a.pages:
        p.error("donner une sauvegarde .mbz ou --pages")

    niveaux_data = {}
    for f in sorted(DATA.glob("*.json")):
        if f.stem in CONFIG["niveaux"]:
            nd = json.loads(f.read_text(encoding="utf-8"))
            for it in nd.get("items", []):  # titres corrigés (coquilles d'Éléa), cf. config « titres »
                it["titre"] = CONFIG.get("titres", {}).get(it.get("titre_eléa"), it["titre"])
            niveaux_data[f.stem] = nd

    if DOCS.exists():
        for niv in CONFIG["niveaux"]:
            shutil.rmtree(DOCS / niv, ignore_errors=True)
    rapport = generer(niveaux_data)
    if rapport:
        print("Pages générées dans docs/ :")
        for r in rapport:
            print("    %-14s %-3s %-55s %s" % r)

    pb = controle()
    if pb:
        print("\n!!! CONTRÔLE DE VIE PRIVÉE : ÉCHEC — ne pas publier !!!")
        for x in pb:
            print("    " + x)
        sys.exit(1)
    print("Contrôle de vie privée : OK")


if __name__ == "__main__":
    main()
