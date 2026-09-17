#!/usr/bin/env python3
"""Download a Modrinth mod + declared required dependencies into a pack manifest.

Does not install, run Minecraft, or infer dependencies absent from the catalog.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import zipfile

from modpack import read, write


def request(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'PrismModpackWorkbench/0.2 (local personal modpack)'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def api(endpoint):
    return json.loads(request('https://api.modrinth.com/v2/' + endpoint))


def fetch(project, manifest_path, version_id=None):
    manifest_path = Path(manifest_path).resolve()
    manifest = read(manifest_path)
    game, loader = manifest['minecraft'], manifest['loader']
    entries = {m['project_id']: m for m in manifest['mods'] if m.get('project_id')}
    selected = {}

    def resolve(key, pinned=None, root=False):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', key):
            raise ValueError('Informe o slug ou ID do projeto no Modrinth')
        project = api('project/' + key)
        pid = project['id']
        if pid in selected:
            if pinned and selected[pid]['version']['id'] != pinned:
                raise ValueError('Dependências fixadas em versões conflitantes: ' + pid)
            return
        if not root and pid in entries and (not pinned or entries[pid].get('version_id') == pinned):
            return
        if pinned:
            version = api('version/' + urllib.parse.quote(pinned, safe=''))
        else:
            query = urllib.parse.urlencode({'game_versions': json.dumps([game]), 'loaders': json.dumps([loader])})
            versions = api('project/' + pid + '/version?' + query)
            releases = [v for v in versions if v['version_type'] == 'release']
            if not releases:
                raise ValueError('Nenhuma release compatível para ' + project['title'])
            version = releases[0]
        if version['project_id'] != pid or game not in version['game_versions'] or loader not in version['loaders']:
            raise ValueError('Versão pertence a outro projeto, jogo ou loader')
        selected[pid] = {'project': project, 'version': version}
        for dep in version['dependencies']:
            if dep['dependency_type'] != 'required':
                continue
            dep_pid, dep_vid = dep.get('project_id'), dep.get('version_id')
            if not dep_pid and dep_vid:
                dep_pid = api('version/' + dep_vid)['project_id']
            if not dep_pid:
                raise ValueError('Dependência sem projeto identificável: ' + str(dep))
            resolve(dep_pid, dep_vid)

    resolve(project, version_id, root=True)
    downloads = manifest_path.parent / 'downloads'
    downloads.mkdir(exist_ok=True)
    additions = []
    for pid, selection in selected.items():
        p, v = selection['project'], selection['version']
        f = next((f for f in v['files'] if f.get('primary')), v['files'][0])
        name = f['filename']
        url = urllib.parse.urlparse(f['url'])
        if Path(name).name != name or not name.endswith('.jar') or url.scheme != 'https' or url.hostname != 'cdn.modrinth.com':
            raise ValueError('Arquivo ou origem de download inesperado')
        data = request(f['url'])
        if hashlib.sha512(data).hexdigest() != f['hashes']['sha512']:
            raise ValueError('SHA-512 não confere: ' + name)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if archive.testzip():
                raise ValueError('JAR corrompido: ' + name)
        target = downloads / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Arquivo local de mesmo nome tem conteúdo diferente: ' + name)
        # Prevent two projects from producing the same destination filename.
        for old in manifest['mods'] + additions:
            if old.get('project_id') != pid and Path(old['file']).name == name:
                raise ValueError('Colisão de nomes entre projetos: ' + name)
        target.write_bytes(data)
        additions.append({'file': 'downloads/' + name, 'sha256': hashlib.sha256(data).hexdigest(),
                          'required': True, 'name': p['title'], 'version': v['version_number'],
                          'project_id': pid, 'version_id': v['id'], 'source': 'https://modrinth.com/mod/' + p['slug']})
    replaced = {m['project_id'] for m in additions}
    manifest['mods'] = [m for m in manifest['mods'] if m.get('project_id') not in replaced] + additions
    write(manifest_path, manifest)
    return {'manifest': str(manifest_path), 'downloaded': additions, 'installed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--version-id')
    args = parser.parse_args()
    try:
        print(json.dumps(fetch(args.project, args.manifest, args.version_id), indent=2, ensure_ascii=False))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error) + '\n')
