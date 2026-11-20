"""Mode parent : pages pour les parents d'élèves, en plusieurs langues.

Pages écrites dans docs/parents/<langue>/ :
  index.html                    accueil parents (comment utiliser, niveaux, questions pratiques)
  <niveau>/index.html           en ce moment en classe + chapitres de l'année
  <niveau>/<code>/index.html    un chapitre (H1, G1…) : résumé, mots, repères, questions, évaluation
  <niveau>/outils/index.html    les outils expliqués + les méthodes des BEX

Textes : contenus/parents/<langue>.json (format décrit dans CONTRATS.md §8),
libellés : contenus/parents/interface.json. Une langue ou un texte manquant
retombe sur le français, avec une mention « pas encore traduit ».
"""
import json
import re
from html import escape
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CONTENUS = RACINE / "contenus" / "parents"
LANGUES = ["fr", "ar", "tr", "en", "es", "pt"]
RUB_ELEVE = {"cours": "cours", "qcm": "qcm", "enquetes": "enquete", "bex": "bex", "methode": "bex"}


def _lire(nom):
    f = CONTENUS / nom
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


INTERFACE = _lire("interface.json")
TEXTES = {l: _lire("%s.json" % l) for l in LANGUES}


def t(lang, cle):
    return INTERFACE.get(lang, {}).get(cle) or INTERFACE["fr"].get(cle, cle)


def texte(lang, *chemin):
    """Renvoie (valeur, traduit) : la valeur dans la langue, sinon en français (traduit = False)."""
    def chercher(d):
        for c in chemin:
            if not isinstance(d, dict) or c not in d:
                return None
            d = d[c]
        return d
    v = chercher(TEXTES.get(lang, {}))
    if v not in (None, "", [], {}):
        return v, True
    return chercher(TEXTES["fr"]), lang == "fr"


# ------------------------------------------------------------------ chapitres d'un niveau

def est_chapitre(code):
    """H1, G2, E3, H3a… (pas « 5e » : QCM de révision de l'année précédente)."""
    return bool(re.match(r"^[HGE]\d", code or ""))


def chapitres(nd, niveau):
    """Codes de chapitre dans l'ordre d'Éléa : d'abord ceux des cours, puis les autres."""
    ordre, titres = [], {}
    items = nd.get("items", [])
    for it in [i for i in items if i["rubrique"] == "cours"] + items:
        c = it.get("code") or ""
        if not est_chapitre(c) or it["rubrique"] in ("bex", "methode"):
            continue
        if c not in ordre:
            ordre.append(c)
        if it["rubrique"] == "cours" and c not in titres:
            titres[c] = it["titre"]
    cours = [i.get("code") for i in items if i["rubrique"] == "cours" and est_chapitre(i.get("code"))]
    actuel = cours[-1] if cours else (ordre[-1] if ordre else None)
    return ordre, titres, actuel


def lien_eleve(it, racine):
    if it["rubrique"] == "qcm":
        return "%s%s/qcm/%s/index.html" % (racine, it["_niveau"], it["slug"])
    return "%s%s/%s/index.html" % (racine, it["_niveau"], it["slug"])


def page_parent_de(it, niveau):
    """Chemin (depuis docs/parents/<langue>/) de la page parent qui correspond à une ressource élève."""
    if it["rubrique"] in ("bex", "methode"):
        return "%s/outils/index.html#%s" % (niveau, it["slug"])
    code = it.get("code") or ""
    if est_chapitre(code):
        return "%s/%s/index.html" % (niveau, code.lower())
    return "%s/index.html" % niveau


# ------------------------------------------------------------------ bascule élève / parent

def bascule(lang, mode, lien_eleve_, lien_parent_):
    def a(m, lien, cle):
        cur = ' aria-current="true"' if m == mode else ""
        return '<a href="%s" data-mode="%s"%s>%s</a>' % (lien, m, cur, escape(t(lang, cle)))
    return ('<nav class="hg-bascule" aria-label="%s">%s%s</nav>'
            % (escape(t(lang, "mode")), a("eleve", lien_eleve_, "eleve"), a("parent", lien_parent_, "parent")))


def bascule_eleve(racine, chemin_parent):
    """Bascule placée sur les pages élèves (toujours en français)."""
    return bascule("fr", "eleve", "#", "%sparents/fr/%s" % (racine, chemin_parent)).replace('href="#"', 'href="#contenu"')


def selecteur_langues(lang, racine, chemin):
    li = []
    for l in LANGUES:
        cur = ' aria-current="true"' if l == lang else ""
        li.append('<li><a href="%sparents/%s/%sindex.html" lang="%s" hreflang="%s"%s>%s</a></li>'
                  % (racine, l, chemin, l, l, cur, escape(INTERFACE["_langues"][l]["nom"])))
    return ('<nav class="hg-langues" aria-label="%s"><div class="hg-conteneur"><ul>%s</ul></div></nav>'
            % (escape(t(lang, "langue")), "".join(li)))


def alternates(racine, chemin):
    return "\n".join('<link rel="alternate" hreflang="%s" href="%sparents/%s/%sindex.html">' % (l, racine, l, chemin)
                     for l in LANGUES)


# ------------------------------------------------------------------ morceaux de page

def non_traduit(lang, traduit):
    return "" if traduit else '<p class="hg-non-traduit">%s</p>' % escape(t(lang, "pas_traduit"))


def en_francais(html):
    """Texte resté en français sur une page traduite : bon sens de lecture, même en arabe."""
    return '<div lang="fr" dir="ltr">%s</div>' % html


def section(id_, titre, corps, lang=None, traduit=True, classe=""):
    if not corps:
        return ""
    if lang and not traduit:
        corps = en_francais(corps)
    return ('<section class="hg-bloc-parent %s" id="%s" aria-labelledby="t-%s">\n<h2 id="t-%s">%s</h2>\n%s\n</section>'
            % (classe, id_, id_, id_, escape(titre), corps))


def paragraphes(liste):
    return "".join("<p>%s</p>" % escape(p) for p in (liste or []))


def questions_html(lang, qs):
    out = []
    for q in qs or []:
        out.append('<details class="hg-question"><summary><span>%s</span><span class="hg-question__ouvrir">%s</span></summary>'
                   '<p>%s</p></details>' % (escape(q.get("question", "")), escape(t(lang, "voir_reponse")),
                                             escape(q.get("reponse", ""))))
    return "\n".join(out)


def cartes_ressources(items, racine):
    out = []
    for it in items:
        disc = it.get("discipline") or "methode"
        code = '<span class="hg-carte__code">%s</span>' % escape(it["code"]) if it.get("code") else ""
        out.append('<a class="hg-carte hg-pastille--%s" href="%s" lang="fr">%s<span class="hg-carte__titre">%s</span></a>'
                   % (disc, lien_eleve(it, racine), code, escape(it["titre"])))
    return '<div class="hg-cartes-parent">%s</div>' % "".join(out) if out else ""


# ------------------------------------------------------------------ génération

def generer(niveaux_data, ecrire, gabarit, docs, config, annee):
    rapport, manques = [], set()
    gab = gabarit("parent.html")

    def page(lang, chemin, titre, contenu, fil, eleve, code="", chapeau="", discipline="methode"):
        prof = chemin.count("/")
        racine = "../" * (prof + 2)
        v = {
            "lang": lang, "dir": INTERFACE["_langues"][lang]["dir"],
            "police": "&family=Noto+Sans+Arabic:wght@400;600;700" if lang == "ar" else "",
            "titre_page": escape("%s · %s" % (titre, t(lang, "espace"))), "racine": racine,
            "alternates": alternates(racine, chemin), "aller_contenu": escape({"fr": "Aller au contenu", "ar": "الذهاب إلى المحتوى",
                "tr": "İçeriğe geç", "en": "Skip to content", "es": "Ir al contenido", "pt": "Ir para o conteúdo"}[lang]),
            "accueil": "%sparents/%s/index.html" % (racine, lang), "site": escape(t(lang, "site")),
            "bascule": bascule(lang, "parent", racine + eleve, "#contenu"),
            "langues": selecteur_langues(lang, racine, chemin),
            "aria_ariane": escape(t(lang, "accueil")), "fil_ariane": fil(racine),
            "avertissement": ('<p class="hg-traduction-auto">%s</p>' % escape(t(lang, "traduction_auto"))) if lang != "fr" else "",
            "code": '<span class="hg-code">%s</span>' % escape(code) if code else "",
            "titre": escape(titre), "chapeau": '<p class="hg-chapeau">%s</p>' % escape(chapeau) if chapeau else "",
            "contenu": contenu, "annee": annee, "pied": escape(t(lang, "pied")), "discipline": discipline,
        }
        ecrire(docs / "parents" / lang / chemin / "index.html", gab.safe_substitute(v))

    def ariane(lang, morceaux):
        def f(racine):
            li = []
            for txt, lien in morceaux:
                if lien is None:
                    li.append('<li aria-current="page">%s</li>' % escape(txt))
                else:
                    li.append('<li><a href="%sparents/%s/%s">%s</a></li>' % (racine, lang, lien, escape(txt)))
            return "<ol>%s</ol>" % "".join(li)
        return f

    for lang in LANGUES:
        # ---------------- accueil parents
        acc, tr1 = texte(lang, "accueil")
        acc = acc or {}
        prat, tr2 = texte(lang, "pratique")
        corps = paragraphes(acc.get("intro")) if tr1 else en_francais(paragraphes(acc.get("intro")))
        if acc.get("comment_utiliser"):
            corps += section("comment", t(lang, "comment_utiliser"),
                             "<ol class=\"hg-etapes\">%s</ol>" % "".join("<li>%s</li>" % escape(x) for x in acc["comment_utiliser"]),
                             lang, tr1)
        niv_cartes = []
        for niv in config["niveaux"]:
            nd = niveaux_data.get(niv) or {"items": []}
            sous = "" if nd["items"] else '<span class="hg-carte__type">%s</span>' % escape(t(lang, "vide_niveau"))
            niv_cartes.append('<a class="hg-carte" href="%s/index.html"><span class="hg-carte__code">%s</span>'
                              '<span class="hg-carte__titre">%s</span>%s</a>' % (niv, niv, escape(t(lang, "classe") % niv), sous))
        corps += section("niveaux", t(lang, "choisir_niveau"), '<nav class="hg-niveaux">%s</nav>' % "".join(niv_cartes))
        if prat:
            corps += section("pratique", t(lang, "pratique"), questions_html(lang, prat), lang, tr2)
        if (acc and not tr1) or (prat and not tr2):
            corps = non_traduit(lang, False) + corps
        page(lang, "", acc.get("titre") or t(lang, "espace"), corps,
             ariane(lang, [(t(lang, "espace"), None)]), "index.html")
        if not acc:
            manques.add("accueil")

        for niv in config["niveaux"]:
            nd = niveaux_data.get(niv) or {"items": []}
            items = [dict(i, _niveau=niv) for i in nd["items"]]
            ordre, titres, actuel = chapitres(nd, niv)
            fil_niv = [(t(lang, "espace"), "index.html"), (t(lang, "classe") % niv, None)]

            def titre_chap(c):
                v, _ = texte(lang, "chapitres", niv, c, "titre")
                return v or titres.get(c) or c

            # ---------------- page du niveau
            corps = ""
            if actuel:
                resume, trr = texte(lang, "chapitres", niv, actuel, "resume")
                corps += section("en-ce-moment", t(lang, "en_ce_moment"),
                                 '<a class="hg-carte hg-carte--actuel" href="%s/index.html"><span class="hg-carte__code">%s</span>'
                                 '<span class="hg-carte__titre">%s</span>%s</a>'
                                 % (actuel.lower(), escape(actuel), escape(titre_chap(actuel)),
                                    ('<span class="hg-carte__type"%s>%s</span>' % ("" if trr else ' lang="fr" dir="ltr"', escape(resume[0]))) if resume else ""),
                                 classe="hg-bloc-parent--actuel")
            if ordre:
                corps += section("chapitres", t(lang, "chapitres"), '<div class="hg-cartes-parent">%s</div>' % "".join(
                    '<a class="hg-carte" href="%s/index.html"><span class="hg-carte__code">%s</span><span class="hg-carte__titre">%s</span></a>'
                    % (c.lower(), escape(c), escape(titre_chap(c))) for c in ordre))
            if items:
                corps += section("outils-lien", t(lang, "outils"),
                                 '<a class="hg-bouton" href="outils/index.html">%s</a>' % escape(t(lang, "outils_court")))
                aide, tra = texte(lang, "aide_generale")
                if aide:
                    corps += section("aider", t(lang, "aide_generale"),
                                     "<ul>%s</ul>" % "".join("<li>%s</li>" % escape(x) for x in aide), lang, tra)
            else:
                corps = '<p class="hg-vide">%s</p>' % escape(t(lang, "vide_niveau"))
            page(lang, "%s/" % niv, t(lang, "classe") % niv, corps, ariane(lang, fil_niv), "%s/index.html" % niv)
            if not items:
                continue

            # ---------------- pages des chapitres
            for c in ordre:
                ch, trc = texte(lang, "chapitres", niv, c)
                ch = ch or {}
                lies = [i for i in items if i.get("code") == c and i["rubrique"] in ("cours", "qcm", "enquetes")]
                corps = ""
                if ch:
                    if not trc:
                        corps += non_traduit(lang, False)
                    corps += section("apprend", t(lang, "apprend"), paragraphes(ch.get("resume")), lang, trc)
                    if ch.get("mots"):
                        corps += section("mots", t(lang, "mots"), '<dl class="hg-mots">%s</dl>' % "".join(
                            "<div><dt>%s</dt><dd>%s</dd></div>" % (escape(m.get("mot", "")), escape(m.get("definition", "")))
                            for m in ch["mots"]), lang, trc)
                    if ch.get("reperes"):
                        corps += section("reperes", t(lang, "reperes"),
                                         '<ul class="hg-reperes">%s</ul>' % "".join("<li>%s</li>" % escape(r) for r in ch["reperes"]), lang, trc)
                    if ch.get("questions"):
                        corps += section("aider", t(lang, "aider"), '<p>%s</p>%s' % (escape(t(lang, "aider_chapeau")),
                                                                                    (questions_html(lang, ch["questions"]) if trc else en_francais(questions_html(lang, ch["questions"])))))
                    if ch.get("evalue"):
                        corps += section("evalue", t(lang, "evalue"), "<p>%s</p>" % escape(ch["evalue"]), lang, trc)
                else:
                    manques.add("chapitres.%s.%s" % (niv, c))
                    aide, _ = texte(lang, "aide_generale")
                    corps += '<p class="hg-a-venir">%s</p>' % escape(t(lang, "a_venir"))
                    if aide:
                        corps += section("aider", t(lang, "aide_generale"),
                                         "<ul>%s</ul>" % "".join("<li>%s</li>" % escape(x) for x in aide))
                corps += section("ressources", t(lang, "ressources"), cartes_ressources(lies, "../" * 4))
                cours = next((i for i in lies if i["rubrique"] == "cours"), None)
                eleve = ("%s/%s/index.html" % (niv, cours["slug"])) if cours else "%s/index.html" % niv
                disc = (cours or (lies[0] if lies else {})).get("discipline") or "methode"
                page(lang, "%s/%s/" % (niv, c.lower()), titre_chap(c), corps,
                     ariane(lang, fil_niv[:1] + [(t(lang, "classe") % niv, "%s/index.html" % niv), (titre_chap(c), None)]),
                     eleve, code=c, discipline=disc)

            # ---------------- outils expliqués + méthodes des BEX
            outils, tro = texte(lang, "outils")
            corps = non_traduit(lang, False) if (outils and not tro) else ""
            for o in outils or []:
                bouton = ""
                if o.get("cle") == "suivi-bex":
                    bouton = '<a class="hg-bouton hg-bouton--bex" href="%s">%s</a>' % (
                        escape(config["lien_bex"], quote=True), escape(t(lang, "suivi_bex")))
                corps += section(o.get("cle", "outil"), o.get("titre", ""), paragraphes(o.get("texte")) + bouton, lang, tro)
            bex = [i for i in items if i["rubrique"] in ("bex", "methode")]
            meth = ""
            for b in bex:
                m, trm = texte(lang, "methodes", niv, b["slug"])
                m = m or {}
                lettres = "".join('<div><dt><span class="hg-lettre">%s</span> %s</dt><dd>%s</dd></div>'
                                  % (escape(str(x.get("lettre", ""))), escape(x.get("mot", "")), escape(x.get("explication", "")))
                                  for x in m.get("lettres", []))
                bloc = ""
                if m.get("nom"):
                    bloc += '<p class="hg-methode__nom">%s</p>' % escape(m["nom"])
                if lettres:
                    bloc += '<dl class="hg-methode">%s</dl>' % lettres
                if m.get("faire_reciter"):
                    bloc += '<h4>%s</h4><p>%s</p>' % (escape(t(lang, "faire_reciter")), escape(m["faire_reciter"]))
                if not m:
                    manques.add("methodes.%s.%s" % (niv, b["slug"]))
                bloc += cartes_ressources([b], "../" * 4)
                titre_m = escape(m.get("savoir_faire") or b["titre"])
                if m and not trm:
                    bloc, titre_m = non_traduit(lang, False) + en_francais(bloc), '<span lang="fr" dir="ltr">%s</span>' % titre_m
                meth += ('<article class="hg-methode-bex" id="%s"><h3>%s</h3>%s</article>' % (b["slug"], titre_m, bloc))
            if meth:
                corps += section("methodes", t(lang, "methodes"), meth)
            if not outils:
                manques.add("outils")
            page(lang, "%s/outils/" % niv, t(lang, "outils"), corps,
                 ariane(lang, fil_niv[:1] + [(t(lang, "classe") % niv, "%s/index.html" % niv), (t(lang, "outils"), None)]),
                 "%s/index.html#bex" % niv)

        n = sum(1 for _ in (docs / "parents" / lang).rglob("index.html"))
        manque_trad = lang != "fr" and not TEXTES.get(lang)
        rapport.append((lang, n, "à traduire" if manque_trad else ""))

    a_confirmer = []

    def chercher(d, chemin):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == "a_confirmer" and v:
                    a_confirmer.append("%s : %s" % (chemin, v))
                else:
                    chercher(v, "%s.%s" % (chemin, k) if chemin else k)
        elif isinstance(d, list):
            for i, v in enumerate(d):
                chercher(v, "%s[%d]" % (chemin, i))
    chercher(TEXTES["fr"], "")
    return rapport, sorted(manques), a_confirmer
