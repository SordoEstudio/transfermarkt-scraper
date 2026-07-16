"""Download and organize player images from a players_full JSON dump.

Reads a JSONL file (default: mv_players_rich.json) and downloads, per player:
  images/<code>/portrait.<ext>      -> high-res portrait (image_urls.big)
  images/<code>/club_logo.<ext>     -> current club emblem
  images/<code>/gallery/NN-slug.jpg -> picture-gallery photos

Also writes images/manifest.json mapping every local file to its source URL and
the storage key it should get when uploaded (storage/<code>/...), so a later
upload step (S3, Supabase Storage, etc.) is a straight loop over the manifest.

Usage:
  python download_images.py [input.json] [out_dir]

Note: gallery photos are IMAGO/licensed press images (premium=true). Verify you
have rights before redistributing them from your own storage.
"""
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


def slugify(text, fallback):
    if not text:
        return fallback
    s = re.sub(r'[^a-zA-Z0-9]+', '-', text.lower()).strip('-')
    return s[:60] or fallback


def ext_of(url, default='.jpg'):
    m = re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', url or '', re.I)
    return ('.' + m.group(1).lower()) if m else default


def download(url, path):
    if not url or os.path.exists(path):
        return 'skip' if os.path.exists(path) else 'no-url'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            data = r.read()
        with open(path, 'wb') as f:
            f.write(data)
        return 'ok'
    except Exception as e:
        return f'err:{str(e)[:40]}'


def main():
    inp = sys.argv[1] if len(sys.argv) > 1 else 'mv_players_rich.json'
    out = sys.argv[2] if len(sys.argv) > 2 else 'images'

    rows = [json.loads(l) for l in open(inp, encoding='utf-8') if l.strip()]
    jobs = []          # (url, local_path, storage_key)
    manifest = []

    for p in rows:
        code = p.get('code') or p.get('href', '').strip('/').split('/')[0] or 'unknown'
        base = os.path.join(out, code)

        portrait = (p.get('image_urls') or {}).get('big') or p.get('image_url')
        if portrait:
            path = os.path.join(base, 'portrait' + ext_of(portrait))
            jobs.append((portrait, path)); manifest.append({'code': code, 'kind': 'portrait',
                'url': portrait, 'file': path, 'storage_key': f'{code}/portrait{ext_of(portrait)}'})

        logo = (p.get('current_club') or {}).get('logo_url')
        if logo:
            path = os.path.join(base, 'club_logo' + ext_of(logo, '.png'))
            jobs.append((logo, path)); manifest.append({'code': code, 'kind': 'club_logo',
                'url': logo, 'file': path, 'storage_key': f'{code}/club_logo{ext_of(logo, ".png")}'})

        for i, img in enumerate(p.get('gallery') or [], 1):
            url = img.get('url')
            if not url:
                continue
            fn = f"{i:02d}-{slugify(img.get('title'), 'photo')}{ext_of(url)}"
            path = os.path.join(base, 'gallery', fn)
            jobs.append((url, path)); manifest.append({'code': code, 'kind': 'gallery',
                'title': img.get('title'), 'source': img.get('source'), 'premium': img.get('premium'),
                'url': url, 'file': path, 'storage_key': f'{code}/gallery/{fn}'})

    print(f'{len(rows)} players, {len(jobs)} files to fetch -> {out}/')
    counts = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(lambda j: download(j[0], j[1]), jobs):
            key = res.split(':')[0]
            counts[key] = counts.get(key, 0) + 1

    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print('done:', counts)
    print('manifest:', os.path.join(out, 'manifest.json'))


if __name__ == '__main__':
    main()
