#!/usr/bin/env python3
"""Generate the home page and every spot page without running a web server."""
import shutil
from pathlib import Path
from urllib.parse import quote

from ickost_final import app, SPOT_DATA


def build(output=Path('dist')):
    # All output is generated. Do not leave pages for removed spots behind.
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    paths = ['/'] + [
        f'/spot/{quote(region, safe="")}/{quote(name, safe="")}'
        for region, data in SPOT_DATA.items() for name in data['spots']
    ]
    app.config['TESTING'] = True
    with app.test_client() as client:
        for url in paths:
            response = client.get(url)
            if response.status_code != 200:
                raise RuntimeError(f'Build failed: {url} ({response.status_code})')
            content = response.get_data(as_text=True)
            if 'CartoDB dark_matter' in content or 'cartodb-basemaps-' in content:
                raise RuntimeError('Legacy CARTO tile URL remains')
            # File names are Unicode; browsers request their percent-encoded URLs.
            from urllib.parse import unquote
            target = output / unquote(url).lstrip('/') / 'index.html'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
    shutil.copytree('static', output / 'static', dirs_exist_ok=True)
    (output / '_headers').write_text(
        '/*\n  Referrer-Policy: strict-origin-when-cross-origin\n'
        '  X-Content-Type-Options: nosniff\n', encoding='utf-8')
    print(f'Built {len(paths)} pages in {output}/')


if __name__ == '__main__':
    build()
