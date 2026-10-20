"""Build a versioned runtime ZIP without user data or developer artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

FILES = ('SKILL.md', 'README.md', 'LICENSE', 'NOTICE.md', 'CHANGELOG.md', 'version.json',
         'UPSTREAM_MANIFEST.json', 'scripts/memory_store.py')
DIRS = ('agents', 'references', 'docs')


def build(source: Path, output: Path, layout: str = 'flat') -> Path:
    if layout not in {'flat', 'folder'}:
        raise ValueError('Unknown archive layout')
    version = json.loads((source / 'version.json').read_text(encoding='utf-8'))
    if version['name'] != 'youzhao' or not re.fullmatch(r'\d+\.\d+\.\d+', version['version']):
        raise ValueError('Invalid release identity/version')
    files = [source / name for name in FILES]
    for directory in DIRS:
        d = source / directory
        if not d.is_dir():
            raise FileNotFoundError(d)
        files += [p for p in sorted(d.rglob('*')) if p.is_file()]
    for p in files:
        if not p.is_file():
            raise FileNotFoundError(p)
        if p.is_symlink() or not p.resolve().is_relative_to(source.resolve()):
            raise ValueError('Runtime path must stay inside source: ' + str(p))
        if p.suffix in {'.db', '.sqlite3', '.pyc', '.pyo'} or any(n in p.parts for n in ('__pycache__', '.git')):
            raise ValueError('Private or generated file in runtime: ' + str(p))
    skill = (source / 'SKILL.md').read_text(encoding='utf-8')
    if not re.search(r'^name: youzhao$', skill, re.M) or f'version: "{version["version"]}"' not in skill:
        raise ValueError('SKILL and version.json identity mismatch')
    for p in files:
        if p.suffix == '.md':
            content = p.read_text(encoding='utf-8')
            links = re.findall(r'`(references/[^`]+\.md)`', content)
            links += [t.split('#')[0] for t in re.findall(r'\]\(([^)]+)\)', content)
                      if not re.match(r'^(?:https?://|mailto:|#)', t)]
            for link in links:
                path = source / link if link.startswith('references/') else p.parent / link
                if not path.exists():
                    raise ValueError(f'Broken path in {p}: {link}')
    suffix = '-folder' if layout == 'folder' else ''
    prefix = 'youzhao/' if layout == 'folder' else ''
    target = output / f'youzhao-v{version["version"]}{suffix}.zip'
    checksum = target.with_suffix('.zip.sha256')
    if target.exists() or checksum.exists():
        raise FileExistsError(target)
    output.mkdir(parents=True, exist_ok=True)
    hashes = []
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            name = p.relative_to(source).as_posix()
            data = p.read_bytes()
            info = zipfile.ZipInfo(prefix + name, (2026, 10, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
            hashes.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        info = zipfile.ZipInfo(prefix + 'RELEASE_FILES.json', (2026, 10, 20, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, json.dumps(hashes, ensure_ascii=False, indent=2).encode('utf-8'))
    checksum.write_text(f'{hashlib.sha256(target.read_bytes()).hexdigest()}  {target.name}\n', encoding='utf-8')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--layout', choices=['flat', 'folder'], default='flat')
    args = parser.parse_args()
    print(build(Path(__file__).resolve().parents[1], args.output.resolve(), layout=args.layout))
