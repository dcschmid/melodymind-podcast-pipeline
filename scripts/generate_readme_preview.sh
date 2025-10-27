#!/usr/bin/env bash
# Generate a simple HTML preview of README.md using Python's 'markdown' package.
# Usage: bash scripts/generate_readme_preview.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MD_IN="${REPO_ROOT}/README.md"
OUT="${REPO_ROOT}/README_preview.html"

if [ ! -f "${MD_IN}" ]; then
  echo "README.md not found at ${MD_IN}"
  exit 1
fi

# Check for python markdown package
python - <<'PY'
import sys
try:
    import markdown
except Exception:
    sys.exit(2)
sys.exit(0)
PY
RC=$?
if [ "$RC" -eq 2 ]; then
  echo "Python 'markdown' package not found. Install with: pip install markdown"
  exit 2
fi

python - <<PY
import markdown,io,os
md_path = os.path.join(r"${REPO_ROOT}", 'README.md')
html_path = os.path.join(r"${REPO_ROOT}", 'README_preview.html')
md = open(md_path, 'r', encoding='utf-8').read()
# enable some useful extensions
html_body = markdown.markdown(md, extensions=['fenced_code','tables','toc'])
html = f"""<!doctype html>
<html>
<head>
<meta charset=\"utf-8\">
<title>README preview</title>
<style>body{{font-family:Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial;max-width:900px;margin:30px auto;padding:0 20px;line-height:1.6}}pre{{background:#111;color:#eee;padding:12px;border-radius:6px;overflow:auto}}</style>
</head>
<body>
{html_body}
</body>
</html>
"""
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Wrote {html_path}")
PY

exit 0
