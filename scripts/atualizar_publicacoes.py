"""Atualiza a lista de publicações do site a partir do perfil público do ORCID.

Uso (na pasta do site):
    python scripts/atualizar_publicacoes.py

O script:
  1. baixa os trabalhos do ORCID (API pública, sem login);
  2. junta os trabalhos cadastrados à mão em data/publicacoes_extras.json
     (por exemplo, anais locais de eventos que não estão no ORCID);
  3. classifica cada trabalho em "indexada", "não indexada" ou "preprint";
  4. salva os dados em data/publicacoes.json;
  5. reescreve o trecho entre os marcadores PUBLICACOES:INICIO e PUBLICACOES:FIM
     em publicacoes.html.

Classificação automática:
  - preprint: tipo "preprint" no ORCID ou DOI de servidor de preprints (SSRN, Preprints.org,
    Research Square, arXiv);
  - indexada: o ORCID tem o identificador do Scopus (eid) ou do Web of Science (wosuid), ou o DOI
    é da SciELO (10.1590), do IEEE (10.1109) ou da ACM (10.1145);
  - não indexada: todos os demais.
Para corrigir um caso, acrescente-o em data/classificacao_manual.json, usando o DOI (ou o
título exato) como chave e "indexada", "nao_indexada" ou "preprint" como valor.

Depende só da biblioteca padrão do Python (3.8+).
"""

import datetime
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ORCID = "0000-0001-9945-0367"
API = f"https://pub.orcid.org/v3.0/{ORCID}"
SITE = Path(__file__).resolve().parent.parent
PAGE = SITE / "publicacoes.html"
DATA = SITE / "data" / "publicacoes.json"
EXTRAS = SITE / "data" / "publicacoes_extras.json"
MANUAL = SITE / "data" / "classificacao_manual.json"
MAX_AUTHORS = 12

# Tipo ORCID -> (grupo do filtro, rótulo PT, rótulo EN)
TYPES = {
    "journal-article": ("journal", "Artigo em periódico", "Journal article"),
    "conference-paper": ("conference", "Trabalho em evento", "Conference paper"),
    "conference-output": ("conference", "Trabalho em evento", "Conference paper"),
    "conference-abstract": ("conference", "Resumo em evento", "Conference abstract"),
    "book-chapter": ("chapter", "Capítulo de livro", "Book chapter"),
    "book": ("chapter", "Livro", "Book"),
    "edited-book": ("chapter", "Livro (organizador)", "Edited book"),
    "preprint": ("other", "Preprint", "Preprint"),
    "dissertation-thesis": ("other", "Tese / dissertação", "Thesis"),
}
OTHER = ("other", "Outro", "Other")

# Categorias, na ordem em que aparecem na página
CATS = [
    ("indexada", "indexadas", "Publicações indexadas", "Indexed publications",
     "Trabalhos indexados no Scopus, Web of Science, SciELO, IEEE Xplore ou ACM Digital Library.",
     "Works indexed in Scopus, Web of Science, SciELO, IEEE Xplore or the ACM Digital Library."),
    ("nao_indexada", "nao-indexadas", "Publicações não indexadas", "Non-indexed publications",
     "Principalmente anais de eventos e periódicos não cobertos por essas bases.",
     "Mostly conference proceedings and journals not covered by those databases."),
    ("preprint", "preprints", "Preprints", "Preprints",
     "Versões ainda não revisadas por pares.", "Versions not yet peer reviewed."),
]
PREPRINT_DOI = ("10.2139/ssrn", "10.20944/preprints", "10.21203/rs", "10.48550/arxiv")
INDEXER_DOI = {"10.1590/": "SciELO", "10.1109/": "IEEE", "10.1145/": "ACM"}


def get(path):
    req = urllib.request.Request(
        API + path,
        headers={"Accept": "application/json", "User-Agent": "personal-site-builder"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def val(d, *keys):
    """Acessa d[k1][k2]... devolvendo None se algo faltar."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def fetch_works():
    groups = get("/works")["group"]
    summaries = [g["work-summary"][0] for g in groups]
    codes = [str(s["put-code"]) for s in summaries]

    details = {}
    for i in range(0, len(codes), 100):  # a API aceita até 100 por chamada
        for item in get("/works/" + ",".join(codes[i:i + 100]))["bulk"]:
            w = item.get("work")
            if w:
                details[w["put-code"]] = w

    works = []
    for g, s in zip(groups, summaries):
        d = details.get(s["put-code"], {})
        # identificadores de todas as versões do trabalho (Scopus, WoS, Crossref...)
        id_types = set()
        for ws in g["work-summary"]:
            for e in val(ws, "external-ids", "external-id") or []:
                id_types.add(e.get("external-id-type"))
        ids = val(s, "external-ids", "external-id") or []
        doi = next((e["external-id-value"] for e in ids
                    if e.get("external-id-type") == "doi"), None)
        authors = [val(c, "credit-name", "value")
                   for c in (val(d, "contributors", "contributor") or [])]
        year = val(s, "publication-date", "year", "value")
        works.append({
            "title": (val(s, "title", "title", "value") or "").strip(),
            "venue": val(s, "journal-title", "value") or val(d, "journal-title", "value"),
            "year": int(year) if year else None,
            "type": s.get("type"),
            "doi": clean_doi(doi),
            "url": val(s, "url", "value") or val(d, "url", "value"),
            "authors": [a for a in authors if a],
            "scopus": "eid" in id_types,
            "wos": "wosuid" in id_types,
        })
    return works


def clean_doi(doi):
    """Tira prefixos como http://dx.doi.org/ e completa identificadores da SciELO (S0103-...)."""
    if not doi:
        return None
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.I)
    if re.match(r"^S\d{4}-\d{3}[\dX]", doi, flags=re.I):
        doi = "10.1590/" + doi
    return doi


def norm_venue(v):
    return re.sub(r"[^a-z]", "", (v or "").lower()
                  .translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")))


def propagate_by_venue(works):
    """Artigos sem identificador do Scopus/WoS herdam a indexação de outro artigo do mesmo periódico."""
    venue_idx = {}
    for w in works:
        if w["type"] == "journal-article" and w.get("venue") and w["indexers"]:
            venue_idx.setdefault(norm_venue(w["venue"]), set()).update(w["indexers"])
    for w in works:
        if (w["cat"] == "nao_indexada" and not w.get("forced") and w["type"] == "journal-article"
                and norm_venue(w.get("venue")) in venue_idx):
            w["indexers"] = sorted(venue_idx[norm_venue(w["venue"])])
            w["cat"] = "indexada"
    return works


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def norm(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())


def dedupe(works):
    """Remove duplicatas pelo título normalizado, mantendo a versão com DOI e somando os índices."""
    best = {}
    for w in works:
        key = norm(w["title"])
        if not key:
            continue
        cur = best.get(key)
        if cur is None:
            best[key] = w
            continue
        keep, other = (w, cur) if (not cur["doi"] and w["doi"]) else (cur, w)
        keep["scopus"] = keep.get("scopus") or other.get("scopus")
        keep["wos"] = keep.get("wos") or other.get("wos")
        best[key] = keep
    return sorted(best.values(),
                  key=lambda w: (w["year"] or 0, w["title"].lower()), reverse=True)


def classify(w, manual):
    doi = (w.get("doi") or "").lower()
    w["indexers"] = []
    if w.get("scopus"):
        w["indexers"].append("Scopus")
    if w.get("wos"):
        w["indexers"].append("Web of Science")
    for prefix, name in INDEXER_DOI.items():
        if doi.startswith(prefix):
            w["indexers"].append(name)

    forced = manual.get(doi) or manual.get(w["title"])
    if forced:
        w["cat"] = forced
        w["forced"] = True
    elif w.get("cat"):  # já definido em publicacoes_extras.json
        pass
    elif w["type"] == "preprint" or doi.startswith(PREPRINT_DOI):
        w["cat"] = "preprint"
    elif w["indexers"]:
        w["cat"] = "indexada"
    else:
        w["cat"] = "nao_indexada"
    return w


def is_me(name):
    n = name.lower()
    return "costa" in n and ("helder" in n or re.search(r"\bh\.", n) is not None)


def render_authors(authors):
    if not authors:
        return ""
    shown = authors[:MAX_AUTHORS]
    parts = [f"<b>{html.escape(a)}</b>" if is_me(a) else html.escape(a) for a in shown]
    text = "; ".join(parts)
    if len(authors) > MAX_AUTHORS:
        text += " et al."
    return f'<span class="pub-authors">{text}.</span> '


def render_item(w):
    group, pt, en = TYPES.get(w["type"], OTHER)
    title = html.escape(w["title"].rstrip("."))
    venue = f' <span class="pub-venue">{html.escape(w["venue"])}</span>.' if w.get("venue") else ""
    link = ""
    if w.get("doi"):
        doi = html.escape(w["doi"])
        link = f'<a href="https://doi.org/{doi}">doi:{doi}</a>'
    elif w.get("url"):
        link = f'<a href="{html.escape(w["url"])}">link</a>'
    idx = "".join(f'<span class="badge idx">{html.escape(i)}</span>' for i in w["indexers"])
    return (
        f'        <li class="pub" data-group="{group}">\n'
        f'          {render_authors(w["authors"])}<span class="pub-title">{title}.</span>{venue}\n'
        f'          <div class="pub-meta"><span class="badge"><span lang="pt">{pt}</span>'
        f'<span lang="en">{en}</span></span>{idx}{link}</div>\n'
        f"        </li>"
    )


def render_years(works):
    out, years = [], []
    for w in works:
        if w["year"] not in years:
            years.append(w["year"])
    for y in years:
        label = (str(y) if y else
                 '<span lang="pt">Sem data</span><span lang="en">Undated</span>')
        items = "\n".join(render_item(w) for w in works if w["year"] == y)
        out.append(
            f'    <div class="pub-year">\n      <h3>{label}</h3>\n'
            f'      <ol class="pub-list">\n{items}\n      </ol>\n    </div>'
        )
    return "\n".join(out)


def render(works):
    out = []
    for key, anchor, pt, en, dpt, den in CATS:
        sel = [w for w in works if w["cat"] == key]
        out.append(
            f'  <section class="pub-cat" id="{anchor}" data-cat="{key}">\n'
            f'    <h2 class="cat-title"><span lang="pt">{pt}</span><span lang="en">{en}</span>'
            f' <span class="cat-n">{len(sel)}</span></h2>\n'
            f'    <p class="cat-desc"><span lang="pt">{dpt}</span><span lang="en">{den}</span></p>\n'
            f"{render_years(sel)}\n  </section>"
        )
    today = datetime.date.today().isoformat()
    out.append(
        f'    <p class="updated"><span lang="pt">Atualizado em {today}.</span>'
        f'<span lang="en">Updated on {today}.</span></p>'
    )
    return "\n".join(out)


def main():
    print(f"Baixando trabalhos do ORCID {ORCID}…")
    works = fetch_works() + load_json(EXTRAS, [])
    manual = {k.lower() if k.startswith("10.") else k: v
              for k, v in load_json(MANUAL, {}).items() if not k.startswith("_")}
    works = propagate_by_venue([classify(w, manual) for w in dedupe(works)])
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(works, ensure_ascii=False, indent=1), encoding="utf-8")

    page = PAGE.read_text(encoding="utf-8")
    pattern = re.compile(r"(<!-- PUBLICACOES:INICIO[^>]*-->\n).*?(<!-- PUBLICACOES:FIM -->)", re.S)
    if not pattern.search(page):
        sys.exit("Marcadores PUBLICACOES:INICIO/FIM não encontrados em publicacoes.html")
    page = pattern.sub(lambda m: m.group(1) + render(works) + "\n" + m.group(2), page)
    PAGE.write_text(page, encoding="utf-8")
    counts = {c[0]: sum(1 for w in works if w["cat"] == c[0]) for c in CATS}
    print(f"{len(works)} publicações gravadas em {PAGE.name}: {counts}")


if __name__ == "__main__":
    main()
