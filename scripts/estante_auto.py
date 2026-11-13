# -*- coding: utf-8 -*-
"""Roda no GitHub, antes do KoShelf: coloca na estante os livros lidos que ainda nao estao em livros/,
usando o banco de capas privado do Koofr (KoShelf/capas). Nao altera nada no repositorio."""
import os, re, sys, time, base64, sqlite3, urllib.request

URL = os.environ.get("BANCO_URL", "https://app.koofr.net/dav/Koofr/KoShelf/capas/")
BANCO = os.path.join("privacidade", "banco.txt")
META = os.path.join("privacidade", "meta.json")
VAZIO = ("", "N/A", "n/a", None)

def corrige_metadados():
    """autor/serie/volume vindos do banco (ComicInfo.xml dos .cbz e OPF dos EPUB) onde o KOReader deixou "N/A" """
    import json
    if not os.path.exists(META): return {}
    try: meta = json.load(open(META, encoding="utf-8"))
    except Exception: return {}
    c = sqlite3.connect("statistics.sqlite3"); n = 0
    for i, md5, t, a, s in c.execute("select id, md5, title, authors, series from book").fetchall():
        m = meta.get(md5)
        if not m: continue
        nt = m.get("t") if t in VAZIO and m.get("t") else t
        na = m.get("a") if a in VAZIO and m.get("a") else a
        ns = (m.get("s") + (" #" + m["n"] if m.get("n") else "")) if s in VAZIO and m.get("s") else s
        if (nt, na, ns) != (t, a, s):
            if c.execute("select 1 from book where title = ? and authors = ? and md5 = ? and id != ?", (nt, na, md5, i)).fetchone(): continue
            c.execute("update book set title = ?, authors = ?, series = ? where id = ?", (nt, na, ns, i)); n += 1
    c.commit(); c.close()
    # pastas ja publicadas pelo PC (livros/<md5>.sdr): completa autor e serie se estiverem vazios
    for d in os.listdir("livros") if os.path.isdir("livros") else []:
        m = meta.get(d[:-4]); f = os.path.join("livros", d, "metadata.epub.lua")
        if not m or not os.path.exists(f): continue
        txt = open(f, encoding="utf-8").read(); novo = txt
        if m.get("a") and re.search(r'\["authors"\] = "(N/A|)"', novo):
            novo = re.sub(r'\["authors"\] = "(N/A|)"', lambda _: '["authors"] = ' + lua(m["a"]), novo)
        if m.get("s") and '["series"]' not in novo:
            novo = novo.replace('    ["doc_props"] = {\n', '    ["doc_props"] = {\n        ["series"] = %s,\n%s' % (lua(m["s"]), ('        ["series_index"] = %s,\n' % m["n"]) if re.fullmatch(r"\d+(\.\d+)?", m.get("n") or "") else ""), 1)
        if novo != txt: open(f, "w", encoding="utf-8").write(novo)
    print("metadados completados pelo banco:", n)
    return meta

def lua(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "") + '"'

def chave(t, a):
    return re.sub(r"\W+", "", (t or "").lower()) + "|" + re.sub(r"\W+", "", (a or "").lower())

def main():
    if not os.path.exists(BANCO): print("sem banco de capas"); return 0
    banco = {}
    for l in open(BANCO, encoding="utf-8"):
        p = l.split()
        if len(p) == 2: banco[p[0]] = p[1] == "c"
    meta = corrige_metadados()
    auth = "Basic " + base64.b64encode(("%s:%s" % (os.environ.get("KOOFR_EMAIL", ""), os.environ.get("KOOFR_SENHA", ""))).encode()).decode()
    ja = set(); ja_chave = set()
    for d in os.listdir("livros") if os.path.isdir("livros") else []:
        ja.add(d[:-4])
        try:
            t = open(os.path.join("livros", d, "metadata.epub.lua"), encoding="utf-8").read()
            ti = re.search(r'\["title"\] = "((?:[^"\\]|\\.)*)"', t); au = re.search(r'\["authors"\] = "((?:[^"\\]|\\.)*)"', t)
            ja_chave.add(chave(ti and ti.group(1), au and au.group(1)))
        except OSError: pass
    con = sqlite3.connect("statistics.sqlite3")
    livros = con.execute("""select title, authors, md5, pages,
            (select 1.0 * count(distinct d.page) from page_stat d join book b2 on b2.id = d.id_book where b2.md5 = book.md5),
            (select coalesce(sum(d.duration), 0) from page_stat_data d join book b3 on b3.id = d.id_book where b3.md5 = book.md5),
            last_open, series, language,
            (select 1.0 * d.page / d.total_pages from page_stat_data d join book b4 on b4.id = d.id_book
             where b4.md5 = book.md5 and d.total_pages > 0 order by d.start_time desc limit 1) from book where md5 is not null and md5 != '' order by last_open desc""").fetchall()
    vistos = set(); vmd5 = set(); novos = 0
    for title, authors, md5, pages, prog, tempo, last_open, series, language, pos in livros:
        k = chave(title, authors)
        if k in vistos or md5 in vmd5 or (title or "").startswith("KOReader Quickstart"): continue
        if tempo < 300: continue
        vistos.add(k); vmd5.add(md5)
        if md5 in ja or k in ja_chave or md5 not in banco: continue
        pasta = os.path.join("livros", md5 + ".sdr"); os.makedirs(pasta, exist_ok=True)
        if banco[md5]:
            try:
                r = urllib.request.urlopen(urllib.request.Request(URL + md5 + ".jpg", headers={"Authorization": auth}), timeout=60)
                open(os.path.join(pasta, "cover.jpg"), "wb").write(r.read())
            except Exception as e:
                print("  sem capa para", md5, e)
        lido = min(1.0, (prog or 0) / pages) if pages else 0
        pct = min(1.0, pos or 0)  # onde parou na ultima sessao
        if pct >= 0.98 or lido >= 0.9: status = "complete"; pct = 1.0
        elif last_open and time.time() - last_open > 60 * 86400: status = "abandoned"
        else: status = "reading"
        m = meta.get(md5, {})
        if title in VAZIO and m.get("t"): title = m["t"]
        if authors in VAZIO and m.get("a"): authors = m["a"]
        language = language if language not in VAZIO else m.get("l")
        props = ['        ["title"] = %s,' % lua(title or "?"), '        ["authors"] = %s,' % lua(authors or "")]
        if language: props.append('        ["language"] = %s,' % lua(language))
        if m.get("s"):
            props.append('        ["series"] = %s,' % lua(m["s"]))
            if re.fullmatch(r"\d+(\.\d+)?", m.get("n") or ""): props.append('        ["series_index"] = %s,' % m["n"])
        elif series and series != "N/A": props.append('        ["series"] = %s,' % lua(series))
        open(os.path.join(pasta, "metadata.epub.lua"), "w", encoding="utf-8").write(
            "-- gerado no GitHub a partir do banco de capas\nreturn {\n"
            '    ["partial_md5_checksum"] = %s,\n    ["doc_props"] = {\n%s\n    },\n    ["doc_pages"] = %d,\n'
            '    ["percent_finished"] = %.4f,\n    ["summary"] = {\n        ["status"] = %s,\n    },\n}\n'
            % (lua(md5), "\n".join(props), pages or 0, pct, lua(status)))
        novos += 1; print("  + estante:", title)
    print("livros colocados na estante automaticamente:", novos)
    return 0

if __name__ == "__main__":
    sys.exit(main())
