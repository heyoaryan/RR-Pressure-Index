"""Writes frontend/data.js from ../dashboard_data.json.

Run after re-running the analysis:
    python3 dashboard/build_data.py
Player photos are not stored locally: they load live from the URLs in the PHOTOS map
inside frontend/index.html.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(HERE, '..', 'dashboard_data.json')))
with open(os.path.join(HERE, 'frontend', 'data.js'), 'w') as fh:
    fh.write('window.DATA = ' + json.dumps(data, separators=(',', ':')) + ';\n')
print('data.js written')
