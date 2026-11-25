# helderhgc.github.io

Site pessoal de Helder Gomes Costa (UFF), publicado com GitHub Pages em
**https://helderhgc.github.io**.

Site estático em HTML/CSS, bilíngue (PT/EN), sem dependências externas.

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `index.html` | Início: apresentação, pesquisa, projetos, formação, contato |
| `publicacoes.html` | Publicações (a lista é gerada pelo script, não edite à mão) |
| `aplicativos.html` | Cartões com links para os aplicativos no Streamlit |
| `assets/css/style.css` | Visual do site (cores, fontes, modo escuro) |
| `assets/js/site.js` | Botão PT/EN e busca/filtros das publicações |
| `scripts/atualizar_publicacoes.py` | Baixa as publicações do ORCID e atualiza a página |
| `data/publicacoes.json` | Cópia dos dados do ORCID (gerada pelo script) |

## Como editar textos (bilíngue)

Todo texto aparece duas vezes, uma em cada idioma:

```html
<span lang="pt">Texto em português</span><span lang="en">Text in English</span>
```

Ao alterar um texto, altere as duas versões.

## Como atualizar as publicações

1. Mantenha o ORCID atualizado (dá para importar do Scopus, Crossref e outros pelo próprio ORCID).
2. Na pasta do site, rode:
   ```
   python scripts/atualizar_publicacoes.py
   ```
3. Envie as mudanças para o GitHub (veja abaixo).

## Como ver o site no computador

```
python -m http.server 8000
```
Depois abra http://localhost:8000 no navegador.

## Publicação (primeira vez)

1. No GitHub, crie um repositório **público** chamado exatamente `helderhgc.github.io`, sem README.
2. Nesta pasta:
   ```
   git init -b main
   git add .
   git commit -m "Primeira versão do site"
   git remote add origin https://github.com/helderhgc/helderhgc.github.io.git
   git push -u origin main
   ```
3. No repositório, vá em **Settings → Pages**, em *Source* escolha **Deploy from a branch**,
   branch `main`, pasta `/ (root)`.
4. Em 1 a 2 minutos o site estará em https://helderhgc.github.io.

## Atualizações seguintes

```
git add .
git commit -m "Descrição da mudança"
git push
```
