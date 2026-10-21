#!/bin/sh
# Builds the paper's PDFs from docs/paper.md and its translations (docs/paper.<lang>.md) with pandoc and LaTeX (tectonic).
#   sh docs/paper/build.sh            # every language
# Needs pandoc 3, tectonic and pdftocairo. figures.lua runs before citeproc and french.lua (French
# spacing in the bibliography) after it. Figures are compiled first from docs/figures/*.tex (data in
# docs/figures/*.dat, written by tools/paper-figures.py) to PDF for the paper and SVG for the markdown.
set -e
here=$(cd "$(dirname "$0")" && pwd)
docs=$(dirname "$here")
for f in "$docs"/figures/*.tex; do
  [ -e "$f" ] || continue
  b=${f%.tex}
  base=${b%.fr}
  # a figure is rebuilt when it, its English source (for x.fr.tex), the shared settings or any data file is newer
  stale=0
  [ -e "$b.pdf" ] || stale=1
  for dep in "$f" "$base.tex" "$docs"/figures/common.tikz "$docs"/figures/*.dat; do
    [ -e "$dep" ] && [ "$dep" -nt "$b.pdf" ] && stale=1
  done
  if [ $stale = 1 ]; then
    (cd "$docs/figures" && tectonic -X compile "$(basename "$f")" 2>&1 | grep -v "^note:\|^warning: accessing absolute path" || true)
    pdftocairo -svg "$b.pdf" "$b.svg"
  fi
done
build() { # $1 source, $2 output
  pandoc "$docs/$1" --from markdown+tex_math_dollars+raw_tex --template "$here/template.tex" \
    --lua-filter "$here/figures.lua" --citeproc --bibliography "$here/references.bib" --csl "$here/ieee.csl" --lua-filter "$here/french.lua" \
    -H "$here/style.tex" -H "$here/colours.tex" --resource-path "$docs:$here" --number-sections --toc --pdf-engine=tectonic -o "$docs/$2"
}
base=n-ways-addressing-sierra-leone
for src in "$docs"/paper.md "$docs"/paper.*.md; do
  [ -e "$src" ] || continue
  name=$(basename "$src")
  case $name in paper.md) lang=en ;; *) lang=${name#paper.}; lang=${lang%.md} ;; esac
  build "$name" "$base-$lang.pdf"
done
