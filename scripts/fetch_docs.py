#!/usr/bin/env python3
"""Télécharge les Google Docs d'un niveau en PDF et en HTML (avec images).

    python3 scripts/fetch_docs.py 4e

Lit data/<niveau>.json et remplit sources/<niveau>/ :
    <slug>.pdf, <slug>.html, <slug>_images/
Fonctionne pour les documents partagés « Tous les utilisateurs disposant du lien ».
"""
import io
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
EXPORT = "https://docs.google.com/document/d/%s/export?format=%s"
IMAGE_OK = re.compile(r"^images/[A-Za-z0-9_.-]+\.(png|jpe?g|gif|webp)$", re.I)


def telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": "cours-hg-build/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.headers.get("Content-Type", ""), r.read()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    niv = sys.argv[1]
    data = json.loads((RACINE / "data" / ("%s.json" % niv)).read_text(encoding="utf-8"))
    dest = RACINE / "sources" / niv
    dest.mkdir(parents=True, exist_ok=True)
    echecs = []
    for it in data["items"]:
        if not it.get("gdoc"):
            continue
        s = it["slug"]
        try:
            typ, pdf = telecharger(EXPORT % (it["gdoc"], "pdf"))
            if "pdf" not in typ:
                raise ValueError("pas un PDF (%s) : document non partagé par lien ?" % typ)
            (dest / ("%s.pdf" % s)).write_bytes(pdf)
            typ, z = telecharger(EXPORT % (it["gdoc"], "zip"))
            if "zip" not in typ:
                raise ValueError("pas une archive HTML (%s)" % typ)
            imgs = dest / ("%s_images" % s)
            shutil.rmtree(imgs, ignore_errors=True)
            with zipfile.ZipFile(io.BytesIO(z)) as zf:
                html_noms = [n for n in zf.namelist() if n.endswith(".html") and "/" not in n]
                if not html_noms:
                    raise ValueError("archive sans page HTML")
                html = zf.read(html_noms[0]).decode("utf-8", "replace")
                (dest / ("%s.html" % s)).write_text(html, encoding="utf-8")
                n_img = 0
                for n in zf.namelist():
                    if IMAGE_OK.match(n):
                        imgs.mkdir(exist_ok=True)
                        (imgs / Path(n).name).write_bytes(zf.read(n))
                        n_img += 1
            print("  ok  %-55s PDF %4d Ko, %d images" % (it["titre"][:55], len(pdf) // 1024, n_img))
        except (urllib.error.URLError, ValueError, zipfile.BadZipFile) as e:
            echecs.append(it["titre"])
            print("  !!  %-55s %s" % (it["titre"][:55], e))
    if echecs:
        print("\nÀ télécharger à la main dans sources/%s/ (Fichier › Télécharger › PDF) : %s" % (niv, ", ".join(echecs)))
        sys.exit(1)


if __name__ == "__main__":
    main()
