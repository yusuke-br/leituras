# -*- coding: utf-8 -*-
"""Atualiza o progresso de cada livro da estante com as estatisticas mais recentes (roda no GitHub de hora em hora).
Progresso = onde voce parou na ultima sessao, juntando todos os aparelhos.
Livro marcado como terminado continua terminado. Nota, resenha, sinopse etc. nao sao tocados."""
import glob, os, re, sqlite3, time

def main():
    if not os.path.exists("statistics.sqlite3"):
        print("sem estatisticas"); return 0
    c = sqlite3.connect("statistics.sqlite3")
    mudou = 0
    for f in glob.glob(os.path.join("livros", "*.sdr", "metadata.*.lua")):
        t = open(f, encoding="utf-8").read()
        m = re.search(r'\["partial_md5_checksum"\]\s*=\s*"([0-9a-f]{32})"', t)
        if not m: continue
        md5 = m.group(1)
        r = c.execute("""select max(b.pages), max(b.last_open),
                (select 1.0 * count(distinct d.page) from page_stat d join book b2 on b2.id = d.id_book where b2.md5 = ?),
                (select 1.0 * d.page / d.total_pages from page_stat_data d join book b4 on b4.id = d.id_book
                 where b4.md5 = ? and d.total_pages > 0 order by d.start_time desc limit 1)
                from book b where b.md5 = ?""", (md5, md5, md5)).fetchone()
        if not r or r[3] is None: continue
        pages, last_open, prog, pos = r
        lido = min(1.0, (prog or 0) / pages) if pages else 0
        pct = min(1.0, pos)
        st = re.search(r'\["status"\]\s*=\s*"([a-z_]+)"', t)
        atual = st.group(1) if st else None
        if atual == "complete": continue  # terminado continua terminado
        if pct >= 0.98 or lido >= 0.9: status = "complete"; pct = 1.0
        elif last_open and time.time() - last_open > 60 * 86400: status = "abandoned"
        else: status = "reading"
        novo = re.sub(r'(\["percent_finished"\]\s*=\s*)[-0-9.eE+]+', lambda x: x.group(1) + "%.4f" % pct, t, count=1)
        novo = re.sub(r'(\["status"\]\s*=\s*)"[a-z_]+"', lambda x: x.group(1) + '"%s"' % status, novo, count=1)
        if novo != t:
            open(f, "w", encoding="utf-8").write(novo); mudou += 1
    print("progresso atualizado em", mudou, "livros")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
