"""Lecture d'une sauvegarde Moodle / Éléa (.mbz) sans l'extraire sur le disque.

Produit un dictionnaire : sections, activités (liens, étiquettes, QCM) et
questions converties au format décrit dans CONTRATS.md §2.
"""
import json
import re
import tarfile
import xml.etree.ElementTree as ET

from nettoyage import nettoyer, texte_brut

NUL = "$@NULL@$"


class Sauvegarde:
    def __init__(self, chemin):
        self.tar = tarfile.open(chemin, "r:gz")
        self.noms = set(self.tar.getnames())

    def xml(self, nom):
        if nom not in self.noms:
            return None
        f = self.tar.extractfile(nom)
        return ET.parse(f).getroot() if f else None


def _t(el, chemin, defaut=""):
    if el is None:
        return defaut
    x = el.find(chemin)
    if x is None or x.text is None or x.text == NUL:
        return defaut
    return x.text


# ---------------------------------------------------------------- structure

def lire_structure(sv):
    racine = sv.xml("moodle_backup.xml")
    info = racine.find("information")
    cours = {
        "nom": _t(sv.xml("course/course.xml"), "fullname"),
        "nom_court": _t(sv.xml("course/course.xml"), "shortname"),
        "date": _t(info, "backup_date"),
    }
    sections = []
    for s in info.iter("section"):
        sid = _t(s, "sectionid")
        if not sid:
            continue
        sx = sv.xml("%s/section.xml" % _t(s, "directory"))
        sections.append({
            "id": sid,
            "titre": _t(s, "title"),
            "numero": int(_t(sx, "number", "0") or 0),
            "visible": _t(sx, "visible", "1") == "1",
            "sequence": [x for x in _t(sx, "sequence").split(",") if x],
        })
    activites = {}
    for a in info.iter("activity"):
        mid = _t(a, "moduleid")
        if not mid:
            continue
        d = _t(a, "directory")
        module = sv.xml("%s/module.xml" % d)
        activites[mid] = {
            "id": mid,
            "type": _t(a, "modulename"),
            "titre": _t(a, "title"),
            "section": _t(a, "sectionid"),
            "dossier": d,
            "visible": _t(module, "visible", "1") == "1",
        }
    for s in sections:
        s["sequence"] = [m for m in s["sequence"] if m in activites]
    sections.sort(key=lambda s: s["numero"])
    return cours, sections, activites


def detail_activite(sv, act):
    d, t = act["dossier"], act["type"]
    x = sv.xml("%s/%s.xml" % (d, t))
    el = x.find(t) if x is not None else None
    if t == "url":
        act["url"] = _t(el, "externalurl")
        act["nom"] = _t(el, "name") or act["titre"]
        act["intro"] = nettoyer(_t(el, "intro"))
    elif t == "label":
        act["html"] = nettoyer(_t(el, "intro"))
    elif t == "quiz":
        act["nom"] = _t(el, "name") or act["titre"]
        act["intro"] = nettoyer(_t(el, "intro"))
        act["emplacements"] = []
        for qi in el.iter("question_instance"):
            ref = qi.find("question_reference")
            jeu = qi.find("question_set_reference")
            if ref is not None:
                act["emplacements"].append({"entree": _t(ref, "questionbankentryid")})
            elif jeu is not None:
                fc = json.loads(_t(jeu, "filtercondition", "{}") or "{}")
                cat = (((fc.get("filter") or {}).get("category") or {}))
                vals = cat.get("values") or []
                sous = ((cat.get("filteroptions") or {}).get("includesubcategories", False))
                if not vals and fc.get("questioncategoryid"):
                    vals = [fc["questioncategoryid"]]
                    sous = bool(fc.get("includingsubcategories"))
                act["emplacements"].append({"categorie": str(vals[0]) if vals else "", "sous": bool(sous)})
    return act


# ---------------------------------------------------------------- questions

def lire_banque(sv):
    """Renvoie (categories, entrees) : entrees[id_entree] = élément <question> (dernière version)."""
    racine = sv.xml("questions.xml")
    categories, entrees, par_id = {}, {}, {}
    if racine is None:
        return categories, entrees, par_id
    for cat in racine.iter("question_category"):
        cid = cat.get("id")
        categories[cid] = {"id": cid, "nom": _t(cat, "name"), "parent": _t(cat, "parent"), "entrees": []}
        for be in cat.iter("question_bank_entry"):
            versions = []
            for qv in be.iter("question_versions"):
                q = qv.find("questions/question")
                if q is None:
                    continue
                versions.append((int(_t(qv, "version", "0") or 0), _t(qv, "status", "ready"), q))
            for qv in be.iter("question"):
                par_id[qv.get("id")] = qv
            if not versions:
                continue
            versions.sort(key=lambda v: v[0])
            _, statut, q = versions[-1]
            if statut == "hidden" or _t(q, "parent", "0") != "0":
                continue  # cachée, ou sous-question d'un texte à trous
            entrees[be.get("id")] = q
            categories[cid]["entrees"].append(be.get("id"))
    return categories, entrees, par_id


def _sous_categories(categories, cid):
    res = [cid]
    for c in categories.values():
        if c["parent"] == cid:
            res += _sous_categories(categories, c["id"])
    return res


def _fraction(x):
    try:
        return round(float(x), 4)
    except (TypeError, ValueError):
        return 0.0


def _reponses_choix(q):
    out = []
    for a in q.iter("answer"):
        out.append({
            "texteHtml": nettoyer(_t(a, "answertext")),
            "fraction": _fraction(_t(a, "fraction", "0")),
            "feedbackHtml": nettoyer(_t(a, "feedback")),
        })
    return out


CLOZE = re.compile(r"\{(\d*):([A-Z_]+):(.*)\}\s*$", re.S)


def _decouper(s, sep):
    """Découpe en ignorant les séparateurs échappés par une barre oblique inverse."""
    morceaux, cur, i = [], "", 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            cur += s[i + 1]
            i += 2
            continue
        if c == sep:
            morceaux.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    morceaux.append(cur)
    return morceaux


def _lire_cloze(code):
    m = CLOZE.match(code.strip())
    if not m:
        return None
    _, typ, corps = m.groups()
    if typ in ("MULTICHOICE", "MULTICHOICE_S", "MC", "MCS"):
        mode = "liste"
    elif typ in ("MULTICHOICE_V", "MULTICHOICE_H", "MULTICHOICE_VS", "MULTICHOICE_HS",
                 "MCV", "MCH", "MCVS", "MCHS"):
        mode = "boutons"
    elif typ.startswith("SHORTANSWER") or typ in ("SA", "MW", "SAC", "MWC"):
        mode = "texte"
    elif typ.startswith("NUMERICAL") or typ == "NM":
        mode = "texte"
    else:
        return None
    options = []
    for brut in _decouper(corps, "~"):
        brut = brut.strip()
        if not brut:
            continue
        txt, _, fb = brut.partition("#") if "#" in brut else (brut, "", "")
        frac = 0.0
        if txt.startswith("="):
            frac, txt = 1.0, txt[1:]
        else:
            mm = re.match(r"%(-?[\d.]+)%(.*)", txt, re.S)
            if mm:
                frac, txt = float(mm.group(1)) / 100, mm.group(2)
        if mode == "texte" and frac <= 0:
            continue
        options.append({"texte": texte_brut(txt), "fraction": round(frac, 4), "feedback": texte_brut(fb)})
    return {"mode": mode, "options": options}


def convertir_question(q, par_id):
    typ = _t(q, "qtype")
    base = {
        "id": q.get("id"),
        "enonceHtml": nettoyer(_t(q, "questiontext")),
        "feedbackHtml": nettoyer(_t(q, "generalfeedback")),
    }
    if typ == "multichoice":
        mc = q.find(".//plugin_qtype_multichoice_question/multichoice")
        base.update({
            "type": "choix",
            "multiple": _t(mc, "single", "1") != "1",
            "melanger": _t(mc, "shuffleanswers", "1") == "1",
            "reponses": _reponses_choix(q),
        })
        return base
    if typ == "truefalse":
        reps = _reponses_choix(q)
        base.update({"type": "choix", "multiple": False, "melanger": False, "reponses": reps})
        return base
    if typ == "match":
        paires, distracteurs = [], []
        for m in q.iter("match"):
            g = nettoyer(_t(m, "questiontext"))
            d = texte_brut(_t(m, "answertext"))
            if g:
                paires.append({"gaucheHtml": g, "droite": d})
            elif d:
                distracteurs.append(d)
        base.update({"type": "association", "paires": paires, "distracteurs": distracteurs})
        return base
    if typ == "multianswer":
        ma = q.find(".//multianswer")
        seq = [x for x in _t(ma, "sequence").split(",") if x]
        trous = {}
        for i, sid in enumerate(seq, 1):
            sq = par_id.get(sid)
            if sq is None:
                return None
            t = _lire_cloze(_t(sq, "questiontext"))
            if t is None:
                return None
            trous[str(i)] = t
        enonce = re.sub(r"\{#(\d+)\}", r"{{\1}}", _t(q, "questiontext"))
        base["enonceHtml"] = nettoyer(enonce)
        base.update({"type": "trous", "trous": trous})
        return base
    return None  # type non pris en charge (rapporté par build.py)


def questions_du_quiz(act, categories, entrees, par_id):
    """Renvoie (questions, tirage, ignorees)."""
    vues, questions, ignorees = set(), [], []
    aleatoire = 0
    for emp in act.get("emplacements", []):
        ids = []
        if "entree" in emp:
            ids = [emp["entree"]]
        else:
            aleatoire += 1
            cats = _sous_categories(categories, emp["categorie"]) if emp["sous"] else [emp["categorie"]]
            for c in cats:
                ids += categories.get(c, {}).get("entrees", [])
        for e in ids:
            if e in vues or e not in entrees:
                continue
            vues.add(e)
            q = entrees[e]
            conv = convertir_question(q, par_id)
            if conv is None:
                ignorees.append("%s (%s)" % (_t(q, "name"), _t(q, "qtype")))
            else:
                questions.append(conv)
    tirage = len(act.get("emplacements", [])) if aleatoire else None
    if tirage is not None and tirage >= len(questions):
        tirage = None
    return questions, tirage, ignorees


def lire(chemin):
    sv = Sauvegarde(chemin)
    cours, sections, activites = lire_structure(sv)
    for a in activites.values():
        detail_activite(sv, a)
    categories, entrees, par_id = lire_banque(sv)
    for a in activites.values():
        if a["type"] == "quiz":
            a["questions"], a["tirage"], a["ignorees"] = questions_du_quiz(a, categories, entrees, par_id)
    return {"cours": cours, "sections": sections, "activites": activites}
