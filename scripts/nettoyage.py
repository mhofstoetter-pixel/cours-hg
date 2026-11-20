"""Nettoyage HTML par liste blanche (bibliothèque standard uniquement).

Garde la structure (titres, paragraphes, listes, tableaux, images, liens) et
retire styles, classes, scripts et attributs inconnus. Sert aux énoncés de QCM
et aux pages tirées des Google Docs.
"""
from html import escape
from html.parser import HTMLParser
import re

BALISES = {
    "p", "br", "strong", "b", "em", "i", "u", "sup", "sub", "ul", "ol", "li",
    "span", "a", "img", "table", "thead", "tbody", "tr", "th", "td",
    "h2", "h3", "h4", "blockquote", "hr", "figure", "figcaption",
}
VIDES = {"br", "img", "hr"}
ATTRIBUTS = {
    "a": {"href"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
RENOMMER = {"b": "strong", "i": "em", "h1": "h2", "h5": "h4", "h6": "h4"}
SUPPRIMER_CONTENU = {"script", "style", "head", "title", "noscript", "iframe", "object"}


def _url_sure(url):
    u = (url or "").strip()
    if re.match(r"(?i)^(https?:|mailto:|#|\.{0,2}/|[\w./-]+$)", u):
        return u
    if re.match(r"(?i)^data:image/(png|jpe?g|gif|webp);", u):
        return u
    return None


class _Nettoyeur(HTMLParser):
    def __init__(self, h_decalage=0):
        super().__init__(convert_charrefs=True)
        self.sortie = []
        self.pile = []
        self.ignorer = 0
        self.h_decalage = h_decalage

    def _nom(self, tag):
        tag = RENOMMER.get(tag, tag)
        m = re.match(r"h([1-6])$", tag)
        if m:
            n = min(4, max(2, int(m.group(1)) + self.h_decalage))
            tag = "h%d" % n
        return tag

    def handle_starttag(self, tag, attrs):
        if tag in SUPPRIMER_CONTENU:
            self.ignorer += 1
            return
        if self.ignorer:
            return
        tag = self._nom(tag)
        if tag not in BALISES:
            return
        gardes = []
        for k, v in attrs:
            if k in ATTRIBUTS.get(tag, ()):
                if k in ("href", "src"):
                    v = _url_sure(v)
                    if v is None:
                        continue
                gardes.append(' %s="%s"' % (k, escape(v or "", quote=True)))
        if tag == "a":
            gardes.append(' rel="noopener"')
        if tag == "img" and not any(a.startswith(" alt=") for a in gardes):
            gardes.append(' alt=""')
        self.sortie.append("<%s%s>" % (tag, "".join(gardes)))
        if tag not in VIDES:
            self.pile.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        tag2 = self._nom(tag)
        if tag2 in BALISES and tag2 not in VIDES and self.pile and self.pile[-1] == tag2:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in SUPPRIMER_CONTENU:
            self.ignorer = max(0, self.ignorer - 1)
            return
        if self.ignorer:
            return
        tag = self._nom(tag)
        if tag in VIDES or tag not in self.pile:
            return
        while self.pile:
            t = self.pile.pop()
            self.sortie.append("</%s>" % t)
            if t == tag:
                break

    def handle_data(self, data):
        if not self.ignorer:
            self.sortie.append(escape(data, quote=False))

    def resultat(self):
        while self.pile:
            self.sortie.append("</%s>" % self.pile.pop())
        html = "".join(self.sortie)
        html = re.sub(r"<span>(.*?)</span>", r"\1", html, flags=re.S)
        html = re.sub(r"<(p|li|h[2-4])>\s*</\1>", "", html)
        return html.strip()


def nettoyer(html, h_decalage=0):
    """Renvoie un HTML sûr et sans mise en forme d'origine."""
    if not html:
        return ""
    n = _Nettoyeur(h_decalage)
    n.feed(html)
    n.close()
    return n.resultat()


def texte_brut(html):
    """Texte sans balise (pour les menus déroulants)."""
    t = re.sub(r"<[^>]+>", "", nettoyer(html))
    from html import unescape
    return re.sub(r"\s+", " ", unescape(t)).strip()
