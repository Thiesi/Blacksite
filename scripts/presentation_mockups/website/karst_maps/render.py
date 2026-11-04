"""Render the three Karst maps for the website.

Each gen_*.py writes a design-canvas page to project/; this script turns
those pages into plain HTML, screenshots them at 2x in headless Chromium
or Edge, and writes the website files to docs/assets/website/.

Run from this directory. Set CHROME to the browser executable if it is
not Edge's default Windows path. Needs Pillow.
"""
import io
import os
import re
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', '..', '..', 'docs', 'assets', 'website')
BROWSER = os.environ.get('CHROME', r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
BOARDS = [  # page, width, height, output, format
    ('Main', 1800, 1200, 'karst-city-map.png', 'png256'),
    ('Night', 1600, 1200, 'karst-by-ringlight.jpg', 'jpeg'),
    ('Transit', 1700, 1240, 'karst-transit-map.png', 'png256'),
]


def plain(name):
    """Resolve the page's template holes to their defaults and drop the canvas wrappers."""
    s = io.open(os.path.join(HERE, 'project', f'{name}.dc.html'), encoding='utf-8').read()
    s = s.replace('{{ringColor}}', '#F2D9A0')
    s = re.sub(r'\{\{[a-zA-Z]+\}\}', '1', s)
    for tag in ('<x-dc>', '</x-dc>', '<helmet>', '</helmet>'):
        s = s.replace(tag, '')
    path = os.path.join(HERE, 'build', f'{name}.html')
    io.open(path, 'w', encoding='utf-8').write(s)
    return path


def main():
    os.makedirs(os.path.join(HERE, 'project'), exist_ok=True)
    os.makedirs(os.path.join(HERE, 'build'), exist_ok=True)
    for gen in ('gen_main.py', 'gen_night.py', 'gen_transit.py'):
        subprocess.run([sys.executable, gen], cwd=HERE, check=True)
    for name, w, h, out, fmt in BOARDS:
        page = plain(name)
        shot = os.path.join(HERE, 'build', f'{name}@2x.png')
        subprocess.run([BROWSER, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                        f'--window-size={w},{h}', '--virtual-time-budget=6000', f'--screenshot={shot}',
                        'file:///' + page.replace(os.sep, '/')], check=True, capture_output=True)
        im = Image.open(shot).convert('RGB')
        im = im.resize((2400, round(im.height * 2400 / im.width)), Image.LANCZOS)
        target = os.path.join(OUT, out)
        if fmt == 'jpeg':
            im.save(target, quality=90, optimize=True, progressive=True, subsampling=0)
        else:
            im.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                        dither=Image.Dither.FLOYDSTEINBERG).save(target, optimize=True)
        print(out, os.path.getsize(target))


if __name__ == '__main__':
    main()
