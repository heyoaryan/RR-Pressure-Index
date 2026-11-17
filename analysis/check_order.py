"""Final check: the top-10 order must be identical in the website data, the static HTML table and the PDF.
Prints the list to enter on Unstop. Exits non-zero on any mismatch."""
import json, re, sys, html
import fitz  # pymupdf

D = json.load(open('../dashboard_data.json'))
js = json.loads(open('../dashboard/frontend/data.js').read().split('=', 1)[1].strip().rstrip(';'))
idx = open('../dashboard/frontend/index.html').read()
static = re.search(r'STATIC-TOP10:START(.*?)STATIC-TOP10:END', idx, re.S).group(1)
pdf = ''.join(p.get_text() for p in fitz.open('../ClutchRank_Methodology.pdf'))
ok = True
for role, label in (('bat', 'BATTERS'), ('bowl', 'BOWLERS')):
    names = [p['name'] for p in D[role]]
    if [p['name'] for p in js[role]] != names: ok = False; print(f'MISMATCH {role}: data.js')
    st = [html.unescape(n) for n in re.findall(r'<tr><td>\d+</td><td>([^<]+)</td>', static.split('Top 10 bowlers')[0 if role == 'bat' else 1])]
    if st != names: ok = False; print(f'MISMATCH {role}: static HTML table', st)
    # page-1 table in the PDF: "1\nName\n..." rows; check each rank is followed by the right name
    sec = pdf.split('Final top 10 — batters')[1].split('Final top 10 — bowlers')
    part = sec[0] if role == 'bat' else sec[1]
    for i, n in enumerate(names, 1):
        if not re.search(rf'(^|\n){i}\n{re.escape(n)}\n', part): ok = False; print(f'MISMATCH {role}: PDF rank {i} != {n}')
    if len(set(names)) != 10: ok = False; print(f'DUPLICATE in {role}')
    print(f'\n{label} — Unstop rank 1..10')
    for i, n in enumerate(names, 1): print(f'  {i:2d}. {n}')
print('\nALL MATCH ✓' if ok else '\nFIX THE MISMATCHES ABOVE'); sys.exit(0 if ok else 1)
