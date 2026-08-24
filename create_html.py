# -*- coding: utf-8 -*-
import base64
import os
import markdown2
from pathlib import Path

os.chdir(r"C:\Users\webma\Projects\local-market-lab")

# Read all images and convert to base64
images = {}
for name in ['architecture.png', 'prediction_models.png', 'risk_metrics.png', 'performance.png', 'equity_drawdown.png']:
    path = f"docs/images/{name}"
    if os.path.exists(path):
        with open(path, 'rb') as f:
            images[name] = base64.b64encode(f.read()).decode('utf-8')
        print(f"Loaded {name}")

# Read markdown files
with open("docs/documentation_de.md", 'r', encoding='utf-8') as f:
    doc_de = f.read()
with open("docs/documentation_en.md", 'r', encoding='utf-8') as f:
    doc_en = f.read()
with open("docs/brochure_de.md", 'r', encoding='utf-8') as f:
    broch_de = f.read()
with open("docs/brochure_en.md", 'r', encoding='utf-8') as f:
    broch_en = f.read()

css = """
<style>
@page { size: A4; margin: 2cm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #222; max-width: 800px; margin: 0 auto; padding: 20px; }
h1 { color: #FFA028; border-bottom: 2px solid #FFA028; padding-bottom: 5px; font-size: 22pt; }
h2 { color: #FFA028; border-bottom: 1px solid #ddd; padding-bottom: 3px; font-size: 16pt; margin-top: 25px; }
h3 { color: #333; font-size: 13pt; }
code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; font-size: 10pt; }
pre { background: #1a1a1a; color: #FFA028; padding: 12px; border-radius: 5px; font-size: 9pt; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th { background: #FFA028; color: #000; padding: 8px; text-align: left; }
td { border: 1px solid #ddd; padding: 6px; }
tr:nth-child(even) { background: #f9f9f9; }
blockquote { border-left: 4px solid #FFA028; padding-left: 15px; color: #555; font-style: italic; }
img { max-width: 100%; height: auto; margin: 10px 0; border: 1px solid #ddd; }
strong { color: #FFA028; }
</style>
"""

def md_to_html(md, title, imgs):
    html = markdown2.markdown(md, extras=['tables', 'fenced-code-blocks'])
    for name, b64 in imgs.items():
        html = html.replace(f'src="images/{name}"', f'src="data:image/png;base64,{b64}"')
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{title}</title>{css}</head>
<body>{html}</body></html>"""

files = [
    ("Documentation_DE.html", md_to_html(doc_de, "Local Market Lab — Technische Dokumentation DE", images)),
    ("Documentation_EN.html", md_to_html(doc_en, "Local Market Lab — Technical Documentation EN", images)),
    ("Broschuere_DE.html", md_to_html(broch_de, "Local Market Lab — Werbebroschüre DE", images)),
    ("Broschuere_EN.html", md_to_html(broch_en, "Local Market Lab — Sales Brochure EN", images)),
]

for fname, content in files:
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"{fname} created ({len(content)} bytes)")

print("All HTML files created")
