"""Atualiza a lista de publicações do site a partir do perfil público do ORCID.

Uso (na pasta do site):
    python scripts/atualizar_publicacoes.py

O script:
  1. baixa os trabalhos do ORCID (API pública, sem login);
  2. salva os dados em data/publicacoes.json;
  3. reescreve o trecho entre os marcadores PUBLICACOES:INICIO e PUBLICACOES:FIM
     em publicacoes.html.

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
    for s in summaries:
        d = details.get(s["put-code"], {})
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
            "doi": doi.strip() if doi else None,
            "url": val(s, "url", "value") or val(d, "url", "value"),
            "authors": [a for a in authors if a],
        })
    return dedupe(works)


def dedupe(works):
    """Remove duplicatas pelo título normalizado, mantendo a versão com DOI."""
    best = {}
    for w in works:
        key = re.sub(r"[^a-z0-9]", "", w["title"].lower())
        if not key:
            continue
        cur = best.get(key)
        if cur is None or (not cur["doi"] and w["doi"]):
            best[key] = w
    return sorted(best.values(),
                  key=lambda w: (w["year"] or 0, w["title"].lower()), reverse=True)


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
    venue = f' <span class="pub-venue">{html.escape(w["venue"])}</span>.' if w["venue"] else ""
    link = ""
    if w["doi"]:
        doi = html.escape(w["doi"])
        link = f'<a href="https://doi.org/{doi}">doi:{doi}</a>'
    elif w["url"]:
        link = f'<a href="{html.escape(w["url"])}">link</a>'
    return (
        f'        <li class="pub" data-group="{group}">\n'
        f'          {render_authors(w["authors"])}<span class="pub-title">{title}.</span>{venue}\n'
        f'          <div class="pub-meta"><span class="badge"><span lang="pt">{pt}</span>'
        f'<span lang="en">{en}</span></span>{link}</div>\n'
        f"        </li>"
    )


def render(works):
    out = []
    years = []
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
    today = datetime.date.today().isoformat()
    out.append(
        f'    <p class="updated"><span lang="pt">Atualizado em {today}.</span>'
        f'<span lang="en">Updated on {today}.</span></p>'
    )
    return "\n".join(out)


def main():
    print(f"Baixando trabalhos do ORCID {ORCID}…")
    works = fetch_works()
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(works, ensure_ascii=False, indent=1), encoding="utf-8")

    page = PAGE.read_text(encoding="utf-8")
    pattern = re.compile(r"(<!-- PUBLICACOES:INICIO[^>]*-->\n).*?(<!-- PUBLICACOES:FIM -->)", re.S)
    if not pattern.search(page):
        sys.exit("Marcadores PUBLICACOES:INICIO/FIM não encontrados em publicacoes.html")
    page = pattern.sub(lambda m: m.group(1) + render(works) + "\n" + m.group(2), page)
    PAGE.write_text(page, encoding="utf-8")
    print(f"{len(works)} publicações gravadas em {PAGE.name}.")


if __name__ == "__main__":
    main()
