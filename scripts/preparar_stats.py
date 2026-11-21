# -*- coding: utf-8 -*-
"""Roda no GitHub, logo depois de baixar as estatisticas do Koofr e antes de tudo o mais.
Deixa a copia das estatisticas usada pelo site coerente com a estante (pasta livros/), para que
estante, calendario, estatisticas e imagens de compartilhar mostrem sempre o mesmo titulo e a mesma capa:
 1. junta as versoes antigas de livros revisados na versao de hoje (privacidade/apelidos.txt);
 2. tira os livros privados e esconde o titulo dos ainda nao catalogados -- olhando o codigo de hoje
    do livro, e nao so o da versao antiga que o aparelho conhece;
 3. copia titulo, autor e serie das fichas da estante (livros/<md5>.sdr) para as estatisticas.
Mexe so nesta copia das estatisticas (nunca nos aparelhos nem no Koofr)."""
import os, re, sys, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import juntar_versoes

DB = "statistics.sqlite3"

def lista(n):
    p = os.path.join("privacidade", n)
    return set(open(p, encoding="utf-8").read().split()) if os.path.exists(p) else set()

def lua_campo(t, k):
    m = re.search(r'\["%s"\]\s*=\s*"((?:[^"\\]|\\.)*)"' % k, t)
    if not m: return None
    return re.sub(r'\\(.)', lambda x: "\n" if x.group(1) == "n" else x.group(1), m.group(1))

def fichas():
    res = {}
    if not os.path.isdir("livros"): return res
    for d in os.listdir("livros"):
        f = os.path.join("livros", d, "metadata.epub.lua")
        if not d.endswith(".sdr") or not os.path.exists(f): continue
        t = open(f, encoding="utf-8").read()
        res[d[:-4]] = {k: lua_campo(t, k) for k in ("title", "authors", "series", "series_index")}
    return res

def main():
    ap = juntar_versoes.carrega(os.path.join("privacidade", "apelidos.txt"))
    ocultos, conhecidos = lista("ocultos.txt"), lista("conhecidos.txt")
    conhecidos |= {l.split()[0] for l in open(os.path.join("privacidade", "banco.txt"), encoding="utf-8") if l.strip()} \
        if os.path.exists(os.path.join("privacidade", "banco.txt")) else set()
    # versao antiga de um livro privado tambem e privada; versao antiga de um livro conhecido tambem e conhecida
    ocultos |= {a for a, b in ap.items() if b in ocultos}
    conhecidos |= {a for a, b in ap.items() if b in conhecidos}
    conhecidos -= ocultos
    c = sqlite3.connect(DB)
    # 1. privados: fora antes de qualquer outra coisa
    tirados = 0
    for i, md5 in c.execute("select id, md5 from book").fetchall():
        if md5 in ocultos or ap.get(md5) in ocultos:
            c.execute("delete from page_stat_data where id_book = ?", (i,))
            c.execute("delete from book where id = ?", (i,)); tirados += 1
    c.commit()
    # 2. versoes revisadas juntadas na de hoje
    juntados = juntar_versoes.junta(c, ap)
    # 3. sem titulo so o que continua desconhecido depois de juntar
    anonimos = 0
    for i, md5 in c.execute("select id, md5 from book").fetchall():
        if md5 not in conhecidos:
            try:
                c.execute("update book set title = ?, authors = '', series = NULL where id = ?", ("Livro ainda não catalogado", i)); anonimos += 1
            except sqlite3.IntegrityError: pass
    # 4. titulo, autor e serie iguais aos da estante
    fx = fichas(); iguais = 0
    for i, md5, t, a, s in c.execute("select id, md5, title, authors, series from book").fetchall():
        f = fx.get(md5)
        if not f or not f.get("title"): continue
        nt = f["title"]; na = f.get("authors") or a or ""
        ns = s
        if f.get("series"): ns = f["series"] + (" #" + f["series_index"] if f.get("series_index") else "")
        if (nt, na, ns) != (t, a, s):
            try:
                c.execute("update book set title = ?, authors = ?, series = ? where id = ?", (nt, na, ns, i)); iguais += 1
            except sqlite3.IntegrityError: pass
    c.commit(); c.execute("vacuum"); c.close()
    print("privados removidos:", tirados, "| versoes juntadas:", juntados, "| sem titulo:", anonimos,
          "| titulos acertados pela estante:", iguais)
    return 0

if __name__ == "__main__":
    sys.exit(main())
