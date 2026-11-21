# -*- coding: utf-8 -*-
"""Junta nas estatisticas as versoes antigas e novas do mesmo livro.
Quando um livro e trocado por uma versao revisada, o arquivo muda e o KOReader passa a conta-lo com outro
codigo (partial md5). O PC grava em privacidade/apelidos.txt as linhas "md5_antigo md5_novo"; aqui o tempo
de leitura da versao antiga passa para a nova, e o livro aparece uma vez so, com capa.
Mexe so na copia das estatisticas usada para gerar o site (nunca nos aparelhos nem no Koofr).
Uso: python3 juntar_versoes.py statistics.sqlite3 privacidade/apelidos.txt"""
import os, sys, sqlite3

def carrega(p):
    ap = {}
    if not os.path.exists(p): return ap
    for l in open(p, encoding="utf-8"):
        a = l.split()
        if len(a) == 2 and a[0] != a[1]: ap[a[0]] = a[1]
    for k in list(ap):  # versao revisada mais de uma vez: vai direto para a mais nova
        v = ap[k]; vistos = {k}
        while v in ap and v not in vistos: vistos.add(v); v = ap[v]
        ap[k] = v
    return ap

def junta(con, ap):
    n = 0; alvos = set()
    for i, md5 in con.execute("select id, md5 from book").fetchall():
        novo = ap.get(md5)
        if not novo: continue
        alvo = con.execute("select id from book where md5 = ? and id != ? order by last_open desc", (novo, i)).fetchone()
        if alvo:
            a = alvo[0]
            con.execute("insert or ignore into page_stat_data (id_book, page, start_time, duration, total_pages) "
                        "select ?, page, start_time, duration, total_pages from page_stat_data where id_book = ?", (a, i))
            con.execute("delete from page_stat_data where id_book = ?", (i,))
            con.execute("update book set last_open = max(coalesce(last_open, 0), (select coalesce(last_open, 0) from book where id = ?)), "
                        "notes = max(coalesce(notes, 0), (select coalesce(notes, 0) from book where id = ?)), "
                        "highlights = max(coalesce(highlights, 0), (select coalesce(highlights, 0) from book where id = ?)) where id = ?", (i, i, i, a))
            con.execute("delete from book where id = ?", (i,))
            alvos.add(a)
        else:
            try: con.execute("update book set md5 = ? where id = ?", (novo, i))
            except sqlite3.IntegrityError: continue
        n += 1
    for a in alvos:
        con.execute("update book set total_read_time = (select coalesce(sum(duration), 0) from page_stat_data where id_book = ?), "
                    "total_read_pages = (select count(distinct page) from page_stat_data where id_book = ?) where id = ?", (a, a, a))
    con.commit()
    return n

if __name__ == "__main__":
    db, ap = sys.argv[1], carrega(sys.argv[2])
    con = sqlite3.connect(db); n = junta(con, ap); con.close()
    print("versoes revisadas juntadas as originais:", n)
