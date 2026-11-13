# -*- coding: utf-8 -*-
"""Imagens de compartilhar (retrospectiva) em JPG e PNG, alem do WebP/SVG do KoShelf.
Roda no GitHub depois do "koshelf export site":
- cria <ano>_share_<formato>.jpg e .png ao lado de cada .webp
- o botao principal (Baixar/Compartilhar) passa a entregar o JPG, e o botao "SVG" vira "PNG".
Se uma versao nova do KoShelf mudar o codigo da pagina, so cria os arquivos e nao mexe na pagina."""
import glob, os, re, sys
from PIL import Image

SITE = sys.argv[1] if len(sys.argv) > 1 else "site"
webps = glob.glob(os.path.join(SITE, "assets", "recap", "*_share_*.webp"))
for w in webps:
    base = w[:-5]
    im = Image.open(w)
    im.save(base + ".png", "PNG", optimize=True)
    im.convert("RGB").save(base + ".jpg", "JPEG", quality=93, optimize=True, progressive=True)
print("imagens convertidas:", len(webps))

js = glob.glob(os.path.join(SITE, "core", "js", "RecapRoute-*.js"))
TROCAS = [
    (r"\.replace\(/\\\.webp\(\$\|\\\?\)/,`\.svg\$1`\)", ".replace(/\\.jpg($|\\?)/,`.png$1`)", 1),
    (r",`svg`\)", ",`png`)", 1),
    (r",`webp`\)", ",`jpg`)", 2),
    (r"type:`image/webp`", "type:`image/jpeg`", 1),
    (r"children:`SVG`", "children:`PNG`", 1),
]
ok = False
if len(js) == 1:
    s = open(js[0], encoding="utf-8").read()
    if all(len(re.findall(p, s)) == n for p, _, n in TROCAS):
        for p, r, _ in TROCAS:
            s = re.sub(p, lambda m, r=r: r, s)
        open(js[0], "w", encoding="utf-8").write(s)
        ok = True
if not ok:
    print("AVISO: o codigo da pagina mudou; deixei os botoes como estao (JPG/PNG continuam disponiveis por link).")
    sys.exit(0)
n = 0
for j in glob.glob(os.path.join(SITE, "data", "reading", "completions", "*", "*.json")):
    t = open(j, encoding="utf-8").read()
    t2 = re.sub(r"(/assets/recap/[^\"?]*_share_[a-z]+)\.webp", r"\1.jpg", t)
    if t2 != t:
        open(j, "w", encoding="utf-8").write(t2); n += 1
print("botoes ajustados (JPG + PNG); arquivos de dados:", n)
