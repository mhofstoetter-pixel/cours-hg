"""Restructure le HTML nettoyé d'une BEX (banque d'exercices) en page interactive.

Entrée : HTML déjà passé par nettoyage.nettoyer() (titres h2/h3).
Sortie : HTML balisé selon CONTRATS.md §7, ou None si le document ne ressemble
pas à une BEX (la page garde alors sa mise en forme simple).

Ce que fait le module :
- découpe en parties : Comprendre · La méthode · L'exemple corrigé · S'entraîner · Pour aller plus loin ;
- retire les blocs répétés (exemplaires à imprimer : le PDF les garde) ;
- range chaque corrigé, fermé, sous son exercice ;
- transforme les méthodes en lettres (C — Contexte…) en cartes, et les tableaux
  de critères en liste à cocher ;
- découpe le modelage corrigé en étapes.
"""
import re
import unicodedata
from html import escape
from html.parser import HTMLParser

VIDES = {"br", "img", "hr"}


# ------------------------------------------------------------------ mini-DOM

class N:
    __slots__ = ("tag", "attrs", "kids")

    def __init__(self, tag, attrs=None, kids=None):
        self.tag, self.attrs, self.kids = tag, list(attrs or []), list(kids or [])


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.racine = N("racine")
        self.pile = [self.racine]

    def handle_starttag(self, tag, attrs):
        n = N(tag, attrs)
        self.pile[-1].kids.append(n)
        if tag not in VIDES:
            self.pile.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.pile) - 1, 0, -1):
            if self.pile[i].tag == tag:
                del self.pile[i:]
                return

    def handle_data(self, d):
        self.pile[-1].kids.append(d)


def lire(html):
    p = _P()
    p.feed(html)
    p.close()
    return p.racine


def ser(n):
    if isinstance(n, str):
        return escape(n, quote=False)
    a = "".join(' %s="%s"' % (k, escape(v or "", quote=True)) for k, v in n.attrs)
    if n.tag in VIDES:
        return "<%s%s>" % (n.tag, a)
    inner = "".join(ser(k) for k in n.kids)
    return inner if n.tag == "racine" else "<%s%s>%s</%s>" % (n.tag, a, inner, n.tag)


BLOCS_TEXTE = {"p", "li", "td", "th", "tr", "div", "h2", "h3", "h4"}


def texte(n):
    if isinstance(n, str):
        return n
    if n.tag == "br":
        return " "
    t = "".join(texte(k) for k in n.kids)
    return t + " " if n.tag in BLOCS_TEXTE else t


def net(t):
    return re.sub(r"\s+", " ", t).strip()


def cle(t):
    t = re.sub(r"[‐-―−]", "-", net(t).lower())
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[’']", "'", t)


def enfants(n, tag=None):
    return [k for k in n.kids if isinstance(k, N) and (tag is None or k.tag == tag)]


def rangees(table):
    rs = []
    for k in enfants(table):
        if k.tag == "tr":
            rs.append(k)
        elif k.tag in ("tbody", "thead"):
            rs += enfants(k, "tr")
    return rs


def cellules(tr):
    return [k for k in enfants(tr) if k.tag in ("td", "th")]


def tout_gras(n):
    """Vrai si tout le texte du bloc est dans du <strong>."""
    hors = []

    def parcours(x, gras):
        if isinstance(x, str):
            if not gras and x.strip():
                hors.append(x)
            return
        for k in x.kids:
            parcours(k, gras or x.tag == "strong")
    parcours(n, False)
    return not hors and bool(net(texte(n)))


# ------------------------------------------------------------------ reconnaissance

MARQUEURS = [
    (r"^exemplaires? (a|pour) imprimer", "imprimer"),
    (r"^pour aller plus loin", "plus-loin"),
    (r"^corrections?\s*:?$", "corrections"),
    (r"^exercice non corrige", "non-corrige"),
    (r"^exercice modele", "exemple"),
    (r"^modelage", "modelage"),
    (r"^(banque d'exercices|exercices d'entra[iî]nement|exercices d'entrainement|je m'entraine)", "entrainement"),
    (r"^(les )?criteres de reussite", "criteres"),
    (r"^(le processus|la methode|comment cette banque|la demarche)", "methode"),
]
RE_EXERCICE = re.compile(r"^(?:bex\s*\d+\s*[-–—]\s*)?exercice\s+(\d+|[a-z]\.\d+)\b")
RE_CORRIGE = re.compile(r"^(?:correction\s*(?:[-–—:]\s*)?(?:de l'|du |de la )?(?:exercice\s*(\d+)|bloc\s+([a-z])\b)"
                        r"|exercice\s+(\d+)\s*[-–—])")


def est_titre(b):
    if b.tag in ("h2", "h3", "h4"):
        return True
    return b.tag == "p" and len(net(texte(b))) <= 90 and tout_gras(b)


def marqueur(b):
    t = cle(texte(b))
    if not (est_titre(b) or (b.tag == "p" and len(t) <= 45)):
        return None
    if re.match(r"^correction\s*:?$", t) and b.tag not in ("h2", "h3", "h4"):
        return None
    for motif, nom in MARQUEURS:
        if re.search(motif, t):
            return nom
    return None


def etiquette_exercice(b):
    t = cle(texte(b))
    if b.tag == "table":
        r = rangees(b)
        t = cle(texte(cellules(r[0])[0])) if r and cellules(r[0]) else ""
    elif not (est_titre(b) or (b.tag == "p" and len(t) <= 90)):
        return None
    m = RE_EXERCICE.match(t)
    return m.group(1) if m else None


def etiquette_corrige(b):
    if not (est_titre(b) or b.tag == "p"):
        return None
    t = cle(texte(b))
    if len(t) > 120:
        return None
    m = RE_CORRIGE.match(t)
    if not m:
        return None
    if m.group(1) or m.group(3):
        return "n:" + (m.group(1) or m.group(3))
    return "bloc:" + m.group(2)


def debut_corrige_interne(b):
    """« Correction : » ou « Correction » seul, dans un exercice."""
    return b.tag in ("p", "h3", "h4") and re.match(r"^(correction|corrige)\s*:?$", cle(texte(b))) is not None


# ------------------------------------------------------------------ transformations de blocs

RE_LETTRE = re.compile(r"^([A-Z])\s*[—–-]\s*(.+)$", re.S)


def cartes_depuis_liste(ul):
    items = enfants(ul, "li")
    cartes = []
    for li in items:
        t = net(texte(li))
        m = RE_LETTRE.match(t)
        if not m:
            return None
        reste = m.group(2)
        nom, _, expl = reste.partition(".")
        if len(nom) > 40:
            nom, expl = reste.split(" ", 1)[0], reste
        cartes.append((m.group(1), nom.strip(), expl.strip(), ""))
    return cartes if len(cartes) >= 3 else None


def cartes_depuis_table(table):
    rs = rangees(table)
    cartes = []
    for tr in rs:
        cs = cellules(tr)
        if not cs:
            continue
        m = RE_LETTRE.match(net(texte(cs[0])))
        if not m:
            continue
        nom = m.group(2).strip()
        expl = net(texte(cs[1])) if len(cs) > 1 else ""
        verif = net(texte(cs[2])) if len(cs) > 2 else ""
        cartes.append((m.group(1), nom, expl, verif))
    return cartes if len(cartes) >= 3 else None


def html_cartes(cartes, n):
    sigle = " · ".join(c[0] for c in cartes)
    out = ['<div class="bex-cartes" data-sigle="%s">' % escape("".join(c[0] for c in cartes)),
           '<p class="bex-cartes__consigne">Pour chaque lettre, dites ce qu\'elle veut dire, puis retournez la carte.</p>',
           '<ul class="bex-cartes__liste" aria-label="Méthode %s">' % escape(sigle)]
    for i, (lettre, nom, expl, verif) in enumerate(cartes):
        cid = "carte-%d-%d" % (n, i)
        dos = "<p>%s</p>" % escape(expl) if expl else ""
        if verif:
            dos += '<p class="bex-carte__verif"><strong>On vérifie :</strong> %s</p>' % escape(verif)
        out.append(
            '<li class="bex-carte">'
            '<button type="button" class="bex-carte__face" aria-expanded="true" aria-controls="%s">'
            '<span class="bex-carte__lettre" aria-hidden="true">%s</span><span class="bex-carte__nom">%s — %s</span>'
            '<span class="bex-carte__invite">Que veut dire %s ?</span></button>'
            '<div class="bex-carte__dos" id="%s">%s</div></li>'
            % (cid, escape(lettre), escape(lettre), escape(nom), escape(lettre), cid, dos))
    out.append("</ul>")
    out.append('<button type="button" class="bex-lien bex-cartes__tout" hidden>Retourner toutes les cartes</button></div>')
    return "".join(out)


def est_table_criteres(table):
    rs = rangees(table)
    if len(rs) < 2:
        return False
    tete = [cle(texte(c)) for c in cellules(rs[0])]
    return bool(tete) and tete[0].startswith("critere") and len(tete) >= 2


def html_criteres(table, n):
    rs = rangees(table)
    out = ['<fieldset class="bex-criteres" data-criteres="%d">' % n,
           '<legend>Je relis ma réponse et je coche ce qui est réussi</legend><ul>']
    for i, tr in enumerate(rs[1:]):
        cs = cellules(tr)
        if not cs:
            continue
        crit = net(texte(cs[0]))
        detail = net(" ".join(texte(c) for c in cs[1:]))
        iid = "critere-%d-%d" % (n, i)
        out.append('<li><input type="checkbox" id="%s"><label for="%s"><strong>%s</strong>%s</label></li>'
                   % (iid, iid, escape(crit), ("<span>%s</span>" % escape(detail)) if detail else ""))
    out.append('</ul><p class="bex-criteres__bilan" aria-live="polite"></p>'
               '<button type="button" class="bex-lien bex-criteres__effacer" hidden>Tout décocher</button></fieldset>')
    return "".join(out)


def html_criteres_liste(ul, n):
    out = ['<fieldset class="bex-criteres" data-criteres="%d">' % n,
           '<legend>Je relis ma réponse et je coche ce qui est réussi</legend><ul>']
    for i, li in enumerate(enfants(ul, "li")):
        iid = "critere-%d-%d" % (n, i)
        out.append('<li><input type="checkbox" id="%s"><label for="%s"><strong>%s</strong></label></li>'
                   % (iid, iid, escape(net(texte(li)))))
    out.append('</ul><p class="bex-criteres__bilan" aria-live="polite"></p>'
               '<button type="button" class="bex-lien bex-criteres__effacer" hidden>Tout décocher</button></fieldset>')
    return "".join(out)


def preparer_table(table):
    """Encadré pour un document seul ; étiquettes de colonnes pour l'empilement sur téléphone."""
    rs = rangees(table)
    if not rs:
        return
    if len(rs) == 1 and len(cellules(rs[0])) == 1:
        table.attrs.append(("class", "bex-encadre"))
        return
    tete = cellules(rs[0])
    if 2 <= len(tete) <= 3 and all(tout_gras(c) for c in tete):
        noms = [net(texte(c)) for c in tete]
        table.attrs.append(("class", "bex-pile"))
        for c in tete:
            c.tag = "th"
            c.attrs.append(("scope", "col"))
        for tr in rs[1:]:
            for c, nom in zip(cellules(tr), noms):
                c.attrs.append(("data-colonne", nom))


def abaisser_titres(n):
    if isinstance(n, str):
        return
    if n.tag in ("h2", "h3"):
        n.tag = "h3" if n.tag == "h2" else "h4"
    for k in n.kids:
        abaisser_titres(k)


# ------------------------------------------------------------------ programme principal

PARTIES = [("comprendre", "Comprendre"), ("methode", "La méthode"), ("exemple", "L'exemple corrigé"),
           ("entrainement", "S'entraîner"), ("corrections", "Les corrections"), ("plus-loin", "Pour aller plus loin")]


def structurer(html):
    racine = lire(html)
    blocs = [k for k in racine.kids if isinstance(k, N)]

    # 1. Doublons (exemplaires à imprimer) : on garde la première occurrence.
    vus, uniques = set(), []
    for b in blocs:
        t = cle(texte(b))
        if len(t) > 80 and b.tag in ("table", "ul", "ol", "p"):
            if t in vus:
                continue
            vus.add(t)
        uniques.append(b)

    # 2. Répartition en zones.
    zones = {p: [] for p, _ in PARTIES}
    zone, vus_marqueurs = "comprendre", set()
    modelage_debut = None
    cles_vues, saut = set(), False
    pleins = [x for x in uniques if net(texte(x)) or "<img" in ser(x)]
    suivant = {id(x): (pleins[i + 1] if i + 1 < len(pleins) else None) for i, x in enumerate(pleins)}
    for b in uniques:
        m = marqueur(b)
        if m is None and debut_corrige_interne(b):
            nb = suivant.get(id(b))
            if nb is not None and etiquette_exercice(nb) and zone in ("entrainement", "corrections"):
                m = "corrections"
        if m:
            vus_marqueurs.add(m)
            saut = False
            if m == "imprimer":
                break
            if m == "entrainement" and cles_vues:
                saut = True  # deuxième « Exercices d'entraînement » : exemplaires à imprimer
                continue
            elif m in ("methode", "criteres"):
                zone = "methode" if zone in ("comprendre", "methode") else zone
                if zone != "methode":
                    zones[zone].append(b)
            elif m == "exemple":
                zone = "exemple"
            elif m == "modelage":
                zone = "exemple"
                modelage_debut = len(zones["exemple"])
            elif m == "entrainement":
                zone = "entrainement"
            elif m == "non-corrige":
                zone = "entrainement"
                if "libre" in cles_vues:
                    saut = True
                    continue
                cles_vues.add("libre")
                b.kids = ["Exercice non corrigé"]
                b.tag, b.attrs = "p", [("data-exercice", "libre")]
                zones[zone].append(b)
            elif m == "corrections":
                zone = "corrections"
            elif m == "plus-loin":
                zone = "plus-loin"
            continue
        k = etiquette_exercice(b)
        if zone in ("comprendre", "methode", "exemple") and k:
            zone = "entrainement"
        if zone == "entrainement" and k:
            saut = k in cles_vues
            cles_vues.add(k)
        if saut:
            continue
        if zone == "corrections" and k and not etiquette_corrige(b):
            b.attrs.append(("data-corrige", "n:%s" % k if k.isdigit() else "bloc:%s" % k[0]))
        zones[zone].append(b)

    if len(vus_marqueurs - {"criteres", "methode"}) < 1 or not (zones["entrainement"] or zones["exemple"]):
        return None

    compteur = [0]

    def rendre(bs, cartes=False):
        out, precedent = [], ""
        for b in bs:
            compteur[0] += 1
            avant, precedent = precedent, cle(texte(b))
            if b.tag == "ul" and re.match(r"^criteres( de reussite)?\s*:?$", avant):
                out.append(html_criteres_liste(b, compteur[0]))
                continue
            if b.tag == "ul" and cartes:
                c = cartes_depuis_liste(b)
                if c:
                    out.append(html_cartes(c, compteur[0]))
                    continue
            if b.tag == "table":
                if est_table_criteres(b):
                    out.append(html_criteres(b, compteur[0]))
                    continue
                c = cartes_depuis_table(b) if cartes else None
                if c:
                    out.append(html_cartes(c, compteur[0]))
                    continue
                preparer_table(b)
            abaisser_titres(b)
            out.append(ser(b))
        return "".join(out)

    def avec_corrige_interne(bs):
        for i, b in enumerate(bs):
            if debut_corrige_interne(b) and i < len(bs) - 1:
                j = next((j for j in range(i + 1, len(bs)) if est_titre(bs[j]) and net(texte(bs[j]))), len(bs))
                return rendre(bs[:i]) + corrige(rendre(bs[i + 1:j])) + rendre(bs[j:])
        return rendre(bs)

    # 3. Corrections regroupées : par exercice ou par bloc.
    corriges, prelude, orphelins = [], [], []
    for b in zones["corrections"]:
        k = etiquette_corrige(b) or dict(b.attrs).get("data-corrige")
        if k:
            corriges.append([k, prelude + [b]])
            prelude = []
        elif re.match(r"^bloc [a-z]\b", cle(texte(b))) and len(texte(b)) < 80:
            prelude = [b]
        elif corriges:
            corriges[-1][1] += prelude + [b]
            prelude = []
        else:
            orphelins.append(b)

    # 4. Exercices.
    exercices, intro_ent = [], []
    for b in zones["entrainement"]:
        k = etiquette_exercice(b)
        libre = dict(b.attrs).get("data-exercice") == "libre"
        if k or libre:
            exercices.append({"cle": "libre" if libre else k, "blocs": [b]})
        elif exercices:
            exercices[-1]["blocs"].append(b)
        else:
            intro_ent.append(b)
    if not exercices:
        # Pas d'étiquette « Exercice N » : un exercice = un document suivi de son vocabulaire.
        courant = None
        for i, b in enumerate(intro_ent):
            suivant = intro_ent[i + 1] if i + 1 < len(intro_ent) else None
            debut = (b.tag == "table" and suivant is not None and suivant.tag == "table"
                     and cle(texte(suivant)).startswith("vocabulaire"))
            if debut:
                courant = {"cle": str(len(exercices) + 1), "blocs": [b]}
                exercices.append(courant)
            elif courant:
                courant["blocs"].append(b)
        intro_ent = intro_ent[:next((i for i, b in enumerate(intro_ent) if exercices and b is exercices[0]["blocs"][0]),
                                    len(intro_ent))]

    def numero(k):
        m = re.search(r"(\d+)$", k or "")
        return m.group(1) if m else None

    restants = []
    for k, bs in corriges:
        cible = None
        if k.startswith("n:"):
            cible = next((e for e in exercices if e["cle"] == k[2:]), None)
            if cible is None:
                idx = int(k[2:]) - 1
                numerotes = [e for e in exercices if e["cle"] != "libre"]
                cible = numerotes[idx] if 0 <= idx < len(numerotes) else None
        else:
            lettre = k[5:]
            du_bloc = [e for e in exercices if (e["cle"] or "").startswith(lettre + ".")]
            cible = du_bloc[-1] if du_bloc else None
        if cible is not None and "corrige" not in cible:
            cible["corrige"] = bs
        else:
            restants.append(bs)

    # 5. Assemblage.
    def corrige(contenu):
        return ('<details class="bex-corrige"><summary><span class="bex-corrige__ouvrir">Voir la correction</span>'
                '<span class="bex-corrige__fermer">Masquer la correction</span></summary>'
                '<div class="bex-corrige__corps">%s</div></details>' % contenu)

    sections = []

    def section(pid, titre, corps):
        if corps.strip():
            sections.append((pid, titre, '<section class="bex-partie" id="%s" aria-labelledby="%s-titre">'
                             '<h2 class="bex-partie__titre" id="%s-titre">%s</h2>%s</section>'
                             % (pid, pid, pid, escape(titre), corps)))

    titres = dict(PARTIES)
    comprendre = rendre(zones["comprendre"], cartes=True)
    if len(net(re.sub(r"<[^>]+>", " ", comprendre))) < 60:
        comprendre = ""  # seulement un bandeau-titre en image : rien à comprendre ici
    section("comprendre", titres["comprendre"], comprendre)
    section("methode", titres["methode"], rendre(zones["methode"], cartes=True))

    ex = zones["exemple"]
    if modelage_debut is not None and modelage_debut < len(ex):
        enonce, modelage = ex[:modelage_debut], ex[modelage_debut:]
        pas, avant = [], []
        for b in modelage:
            if b.tag in ("h2", "h3", "h4") or (est_titre(b) and b.tag == "p"):
                pas.append([b])
            elif pas:
                pas[-1].append(b)
            else:
                avant.append(b)
        corps = rendre(enonce)
        corps += '<div class="bex-modelage"><h3 class="bex-modelage__titre">Le corrigé, étape par étape</h3>' + rendre(avant)
        corps += '<ol class="bex-pas">%s</ol>' % "".join(
            '<li class="bex-pas__etape" data-etape="%d">%s</li>' % (i + 1, rendre(p)) for i, p in enumerate(pas))
        corps += "</div>"
        section("exemple", titres["exemple"], corps)
    else:
        section("exemple", titres["exemple"], avec_corrige_interne(ex))

    corps = rendre(intro_ent)
    for i, e in enumerate(exercices):
        bs = e["blocs"]
        tete = bs[0]
        titre = net(texte(tete))
        if tete.tag == "table":
            titre_html = '<h3 class="bex-exercice__titre">Exercice %s</h3>' % escape(e["cle"] or str(i + 1))
            contenu = avec_corrige_interne(bs)
        elif e["cle"] in (None, "libre") or not RE_EXERCICE.match(cle(titre)):
            titre_html = '<h3 class="bex-exercice__titre">%s</h3>' % escape(
                "Exercice non corrigé" if e["cle"] == "libre" else "Exercice %s" % (e["cle"] or i + 1))
            contenu = avec_corrige_interne(bs if e["cle"] != "libre" else bs[1:])
        else:
            titre_html = '<h3 class="bex-exercice__titre">%s</h3>' % escape(titre)
            contenu = avec_corrige_interne(bs[1:])
        if "corrige" in e:
            contenu += corrige(rendre(e["corrige"]))
        eid = "exercice-%d" % (i + 1)
        corps += ('<article class="bex-exercice" id="%s" aria-labelledby="%s-t">%s%s'
                  '<p class="bex-fait"><input type="checkbox" id="%s-fait"><label for="%s-fait">J\'ai fait cet exercice</label></p>'
                  '</article>') % (eid, eid, titre_html.replace("<h3 ", '<h3 id="%s-t" ' % eid, 1), contenu, eid, eid)
    section("entrainement", titres["entrainement"], corps)

    reste = orphelins + [b for bs in restants for b in bs]
    if reste:
        section("corrections", titres["corrections"], corrige(rendre(reste)))
    section("plus-loin", titres["plus-loin"], rendre(zones["plus-loin"]))

    sommaire = "".join('<li><a href="#%s">%s</a></li>' % (pid, escape(t)) for pid, t, _ in sections)
    nb = len(exercices)
    entete = ('<nav class="bex-sommaire" aria-label="Parties de la BEX"><ol>%s</ol>'
              '<p class="bex-progression" data-total="%d" aria-live="polite"></p></nav>' % (sommaire, nb))
    return '<div class="bex" data-exercices="%d">%s%s</div>' % (nb, entete, "".join(s for _, _, s in sections))
