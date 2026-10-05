#!/usr/bin/env bash
# Render a scanned survey PDF into page images and half-page crops.
#
# Usage: render_pages.sh <pdf> <outdir> [dpi]
#   <outdir>/survey_pages/page-NN.png      full pages
#   <outdir>/crops/page-NN-top|bot.png     halves for high-resolution re-reading
set -euo pipefail

PDF="${1:?usage: render_pages.sh <pdf> <outdir> [dpi]}"
OUT="${2:?usage: render_pages.sh <pdf> <outdir> [dpi]}"
DPI="${3:-150}"

[ -f "$PDF" ] || { echo "ERROR: pdf not found: $PDF" >&2; exit 1; }
command -v pdftoppm >/dev/null || { echo "ERROR: pdftoppm (poppler-utils) required" >&2; exit 1; }

echo "== PDF info =="
pdfinfo "$PDF" | sed -n '1p;/Pages/p;/Page size/p;/Page rot/p'
echo "== text layer =="
CHARS=$(pdftotext "$PDF" - 2>/dev/null | wc -c)
echo "embedded text chars: $CHARS  (≈0 => pure scan, vision OCR required)"

mkdir -p "$OUT/survey_pages" "$OUT/crops"
pdftoppm -png -r "$DPI" "$PDF" "$OUT/survey_pages/page"
echo "rendered: $(ls "$OUT/survey_pages" | wc -l) page(s) at ${DPI} DPI"

python3 - "$OUT" <<'PY'
import os, sys
try:
    from PIL import Image
except ImportError:
    print("WARN: Pillow not installed — skipped crops. Install: pip install pillow", file=sys.stderr)
    raise SystemExit(0)
out = sys.argv[1]
n = 0
for fn in sorted(os.listdir(os.path.join(out, "survey_pages"))):
    if not fn.endswith(".png"):
        continue
    im = Image.open(os.path.join(out, "survey_pages", fn))
    w, h = im.size
    stem = fn[:-4]
    im.crop((0, 0, w, h // 2)).save(os.path.join(out, "crops", f"{stem}-top.png"))
    im.crop((0, h // 2, w, h)).save(os.path.join(out, "crops", f"{stem}-bot.png"))
    n += 1
print(f"crops: {n * 2} half-page images in {out}/crops")
PY
