#!/usr/bin/env bash
# tools/compile_paper.sh — Compilador PDF Académico (Pandoc + IEEE/Elsevier)
# ===========================================================================
# Transforma el borrador GFM generado por el Scientific Narrator a un PDF
# listo para subir al Author Submission System de la revista objetivo.
#
# Uso:
#   ./tools/compile_paper.sh articles/drafts/paper_Q1_Espectro.md
#   ./tools/compile_paper.sh articles/drafts/paper_Q1_Espectro.md --template ieee
#
# Requisitos:
#   sudo apt-get install pandoc texlive-xetex texlive-fonts-recommended
#
# Templates disponibles:
#   ieee      -> IEEE Transactions (2 columnas, 10pt, Times New Roman)
#   elsevier  -> Elsevier (1 columna, 12pt, Computer Modern)
#   plain     -> Reporte técnico simple (sin plantilla LaTeX externa)

set -euo pipefail
cd "$(dirname "$0")/.."

# Parse arguments: supports both positional and flags
DRAFT=""
TEMPLATE="plain"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --template|-t) TEMPLATE="$2"; shift 2 ;;
        --help|-h) echo "Usage: ./tools/compile_paper.sh <draft.md> [--template ieee|elsevier|conference|plain]"; exit 0 ;;
        *) DRAFT="$1"; shift ;;
    esac
done

OUT_DIR="articles/compiled"
BIB_FILE="articles/references.bib"

# Auto-generate BibTeX if not present
if [ ! -f "$BIB_FILE" ]; then
  echo "  Generating BibTeX file..."
  python3 tools/generate_bibtex.py --output "$BIB_FILE" 2>/dev/null || true
fi

# Build citeproc flag if .bib exists
CITE_FLAGS=""
if [ -f "$BIB_FILE" ]; then
  CITE_FLAGS="--citeproc --bibliography=$BIB_FILE"
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ -z "$DRAFT" ]; then
  echo -e "${RED}[ERROR] Especifica el archivo draft:${NC}"
  echo "  ./tools/compile_paper.sh articles/drafts/paper_Q1_xxx.md"
  exit 1
fi

if [ ! -f "$DRAFT" ]; then
  echo -e "${RED}[ERROR] Archivo no encontrado: $DRAFT${NC}"
  exit 1
fi

# Pre-validate draft — BLOQUEANTE: no se compila si la validación falla
if command -v python3 &>/dev/null && [ -f "tools/validate_submission.py" ]; then
    echo "Running pre-validation..."
    if ! python3 tools/validate_submission.py "$DRAFT"; then
        echo -e "${RED}BLOQUEADO: validate_submission.py encontró errores críticos.${NC}"
        echo -e "  Ejecuta con --diagnose para ver el detalle:"
        echo -e "  python3 tools/validate_submission.py \"$DRAFT\" --diagnose"
        exit 1
    fi
fi

mkdir -p "$OUT_DIR"

# Nombre base sin extensión
BASENAME=$(basename "$DRAFT" .md)
PDF_OUT="$OUT_DIR/${BASENAME}.pdf"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE} 📄 COMPILADOR PANDOC → PDF (Bélico Stack EIU)    ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "  Draft  : $DRAFT"
echo -e "  Output : $PDF_OUT"
echo ""

# ── 1. Verificar Pandoc instalado ──
if ! command -v pandoc &> /dev/null; then
  echo -e "${RED}[ERROR] Pandoc no instalado.${NC}"
  echo "  Instalar: sudo apt-get install pandoc texlive-xetex"
  exit 1
fi

# ── 2. Compilación según template ──
TEMPLATE_DIR="$(dirname "$0")/../.agent/templates"

case "$TEMPLATE" in
  "ieee")
    echo "  Template  : IEEE Transactions (journal, single-col)"
    TEX_TEMPLATE=""
    if [ -f "$TEMPLATE_DIR/ieee.tex" ]; then
      TEX_TEMPLATE="--template=$TEMPLATE_DIR/ieee.tex"
      echo "  LaTeX tpl : .agent/templates/ieee.tex"
    fi
    pandoc "$DRAFT" \
      --pdf-engine=xelatex \
      $CITE_FLAGS \
      $TEX_TEMPLATE \
      --variable geometry:margin=2.5cm \
      --variable fontsize=10pt \
      --variable mainfont="TeX Gyre Termes" \
      --variable linestretch=1.0 \
      --toc \
      --number-sections \
      --highlight-style=pygments \
      -o "$PDF_OUT"
    ;;

  "conference")
    echo "  Template  : Conference (EWSHM/IMAC, compact)"
    TEX_TEMPLATE=""
    if [ -f "$TEMPLATE_DIR/conference.tex" ]; then
      TEX_TEMPLATE="--template=$TEMPLATE_DIR/conference.tex"
      echo "  LaTeX tpl : .agent/templates/conference.tex"
    fi
    pandoc "$DRAFT" \
      --pdf-engine=xelatex \
      $CITE_FLAGS \
      $TEX_TEMPLATE \
      --variable geometry:margin=2cm \
      --variable fontsize=10pt \
      --variable mainfont="TeX Gyre Termes" \
      --variable linestretch=1.08 \
      --number-sections \
      -o "$PDF_OUT"
    ;;

  "elsevier")
    echo "  Template  : Elsevier (single-col)"
    TEX_TEMPLATE=""
    if [ -f "$TEMPLATE_DIR/elsevier.tex" ]; then
      TEX_TEMPLATE="--template=$TEMPLATE_DIR/elsevier.tex"
      echo "  LaTeX tpl : .agent/templates/elsevier.tex"
    fi
    pandoc "$DRAFT" \
      --pdf-engine=xelatex \
      $CITE_FLAGS \
      $TEX_TEMPLATE \
      --variable geometry:margin=3cm \
      --variable fontsize=12pt \
      --variable linestretch=1.5 \
      --toc \
      --number-sections \
      --highlight-style=tango \
      -o "$PDF_OUT"
    ;;

  *)
    # Plain: reporte técnico sin dependencias LaTeX externas
    echo "  Template  : Plain PDF"
    pandoc "$DRAFT" \
      --pdf-engine=xelatex \
      $CITE_FLAGS \
      --variable geometry:margin=2.5cm \
      --variable fontsize=11pt \
      --variable colorlinks=true \
      --number-sections \
      -o "$PDF_OUT"
    ;;
esac

echo ""
echo -e "${GREEN}✅ PDF generado exitosamente:${NC}"
echo -e "   $PDF_OUT"
echo ""
echo -e "   Enviar a revista: Subir el PDF a Elsevier Editorial Manager"
echo -e "   o IEEE ScholarOne Manuscripts directamente."
