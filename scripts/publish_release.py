#!/usr/bin/env python3
"""Automatically publish matching IPA and resources to a GitHub Release."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import unquote, urlparse

import ci
from icloud import build_options

PART_BYTES = 1_900_000_000  # Strictly below GitHub's 2 GiB per-asset limit.
OUT = ci.ROOT / 'outputs'
STAGE = ci.ROOT / '.release-assets'
RESOURCE_PART_NAMES = tuple(f'D2R-Mobile-Resources.zip.{i:03d}' for i in range(1, 4))


def gh(*args):
    return subprocess.check_output(['gh', *map(str, args)], text=True).strip()


def api(path):
    return json.loads(gh('api', path))


def validate_report(report):
    for key in ('game_version', 'switch_version', 'upstream_commit'):
        if report.get(key) != ci.CONFIG[key]:
            raise ValueError('Release input is incompatible: ' + key)
    revision = report.get('input_revision')
    if revision is not None and revision != os.environ['INPUT_REVISION']:
        raise ValueError('Release input cache revision differs')


def split_resources(source, destination, expected_sha, part_bytes=PART_BYTES):
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    whole = hashlib.sha256()
    with source.open('rb') as stream:
        index = 1
        while True:
            first = stream.read(min(8 * 1024**2, part_bytes))
            if not first:
                break
            path = destination / f'D2R-Mobile-Resources.zip.{index:03d}'
            digest = hashlib.sha256()
            written = 0
            with path.open('wb') as part:
                data = first
                while data:
                    part.write(data)
                    digest.update(data)
                    whole.update(data)
                    written += len(data)
                    if written == part_bytes:
                        break
                    data = stream.read(min(8 * 1024**2, part_bytes - written))
            files.append((path, digest.hexdigest()))
            print('Prepared resource volume:', path.name, written, flush=True)
            index += 1
    if whole.hexdigest() != expected_sha:
        raise ValueError('Resource ZIP SHA256 mismatch before publishing')
    (destination / 'Resources-Parts-SHA256SUMS.txt').write_text(
        ''.join(f'{digest}  {path.name}\n' for path, digest in files))
    return [path for path, _ in files]


def release_info(repo, tag):
    # Only an explicit 404 means absent; never turn a permission/network error
    # into a request to create another release.
    result = subprocess.run(['gh', 'api', f'repos/{repo}/releases/tags/{tag}'],
                            text=True, capture_output=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    if 'HTTP 404' in result.stderr:
        # Draft creation may not create the Git tag until publication, so the
        # tag endpoint can return 404 for an existing draft. Authenticated list
        # results include drafts and let the two workflows share that draft.
        pages = json.loads(gh('api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100'))
        for page in pages:
            for release in page:
                if release['tag_name'] == tag:
                    return release
        return None
    raise RuntimeError('Could not inspect release: ' + result.stderr.strip())


def release_title():
    upstream_version = unquote(urlparse(ci.CONFIG['shell_url']).path.split('/releases/download/', 1)[1].split('/', 1)[0])
    return f"D2R Mobile {upstream_version} · Game {ci.CONFIG['game_version']}"


def publish_complete(repo, tag, notes, title=None):
    args = ['release', 'edit', tag, '--repo', repo, '--notes-file', notes, '--draft=false', '--latest']
    if title is not None:
        args += ['--title', title]
    gh(*args)
    release = release_info(repo, tag)
    if release is None or release['draft']:
        raise RuntimeError('Release did not become published')
    return release


def wait_for_created_release(repo, tag):
    # A successful create can precede visibility in the tag/list endpoints.
    # Retry reads only: never create another draft after a successful create.
    for attempt in range(6):
        release = release_info(repo, tag)
        if release is not None:
            return release
        if attempt < 5:
            time.sleep(2)
    raise RuntimeError('Created release could not be found after retrying')


def write_install_guide(destination):
    path = destination / 'RESOURCE-INSTALL.txt'
    path.write_text(
        '下载本 Release 的所有 D2R-Mobile-Resources.zip.00* 分卷及两个 Resources 校验文件。\n\n'
        'Mac / Linux：在分卷所在目录执行：\n'
        'shasum -a 256 -c Resources-Parts-SHA256SUMS.txt\n'
        f"cat {' '.join(RESOURCE_PART_NAMES)} > D2R-Mobile-Resources.zip\n"
        'shasum -a 256 -c Resources-SHA256SUMS.txt\n\n'
        'Windows：在分卷所在目录用命令提示符执行：\n'
        f"copy /b {'+'.join(RESOURCE_PART_NAMES)} D2R-Mobile-Resources.zip\n\n"
        '解压合并后的 ZIP，将 D2R Mobile Resources 文件夹通过 Finder → iPhone → 文件 → D2R Mobile 拷入应用。\n'
        '打开应用点击重试；首次启动等待着色器编译。IPA 使用 Sideloadly 签名安装，需要 iOS 26 或以上。\n'
        '真机运行验证：iPhone 17 Pro Max，首次着色器编译约 6 分钟；其他机型耗时取决于设备。\n')
    return path


def main(mode):
    if mode == 'ipa' and build_options() is not None:
        raise ValueError('iCloud variants are Actions artifacts only; do not replace the standard Release')
    repo = os.environ['GITHUB_REPOSITORY']
    revision = os.environ['INPUT_REVISION']
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', revision):
        raise ValueError('Invalid input revision')
    repository = api(f'repos/{repo}')
    print('Release visibility:', 'private' if repository['private'] else 'public', flush=True)
    tag = f"d2r-{ci.CONFIG['game_version']}-{ci.CONFIG['upstream_commit'][:8]}-{revision}"
    title = release_title()
    STAGE.mkdir(exist_ok=True)
    if mode == 'ipa':
        report = json.loads((OUT / 'build-report.json').read_text())
        validate_report(report)
        path = OUT / 'D2RMobile-unsigned.ipa'
        if path.stat().st_size != report['ipa_bytes'] or ci.sha256(path) != report['ipa_sha256']:
            raise ValueError('IPA SHA256 mismatch before publishing')
        assets = [path, OUT / 'build-report.json', OUT / 'SHA256SUMS.txt']
    elif mode == 'resources':
        report = json.loads((OUT / 'resources-report.json').read_text())
        validate_report(report)
        if report['archive_count'] != 18 or report['resource_bytes'] != 5561224037:
            raise ValueError('Unexpected phone resource set')
        path = OUT / 'D2R-Mobile-Resources.zip'
        if path.stat().st_size != report['zip_bytes']:
            raise ValueError('Resource ZIP size mismatch')
        assets = split_resources(path, STAGE, report['zip_sha256'])
        if tuple(path.name for path in assets) != RESOURCE_PART_NAMES:
            raise ValueError('Unexpected number of resource volumes')
        assets += [STAGE / 'Resources-Parts-SHA256SUMS.txt',
                   OUT / 'resources-report.json', OUT / 'Resources-SHA256SUMS.txt']
    else:
        raise ValueError('Expected ipa or resources')
    assets.append(write_install_guide(STAGE))

    notes = STAGE / 'RELEASE.md'
    notes.write_text(
        f"自动构建的 D2R Mobile，游戏版本 **{ci.CONFIG['game_version']}**，Switch 更新 **{ci.CONFIG['switch_version']}**。\n\n"
        f'详细使用方式请参考 [README](https://github.com/{repo}#readme)（[简体中文](https://github.com/{repo}/blob/main/README.zh-CN.md)），包含 IPA 安装、资源分卷合并和导入步骤。\n\n'
        '- `D2RMobile-unsigned.ipa`：用 Sideloadly 签名安装，需要 iOS 26 或以上。\n'
        '- `D2R-Mobile-Resources.zip.001` 等：必须下载全部分卷，按 `RESOURCE-INSTALL.txt` 合并并校验，再解压导入应用。\n'
        '- `build-report.json`、`resources-report.json` 与 SHA256 文件：版本及完整性信息。\n\n'
        'IPA 与 18 个资源文件配套使用；首次启动在手机上编译着色器。真机运行验证：iPhone 17 Pro Max，首次着色器编译约 6 分钟；其他机型耗时取决于设备。\n\n'
        '本 Release 由成功构建自动维护，同一配套版本的后续构建会更新对应附件。\n')
    release = release_info(repo, tag)
    if release is None:
        gh('release', 'create', tag, '--repo', repo, '--target', os.environ['GITHUB_SHA'],
           '--title', title, '--notes-file', notes, '--draft')
        release = wait_for_created_release(repo, tag)
    if release is None:
        raise RuntimeError('Created release could not be found')
    if release.get('immutable'):
        raise ValueError('Cannot update an immutable release')
    current = {item['name']: item for item in release['assets']}
    for path in assets:
        digest = 'sha256:' + ci.sha256(path)
        existing = current.get(path.name)
        if existing and existing.get('digest') == digest and existing['size'] == path.stat().st_size:
            print('Release asset unchanged:', path.name, flush=True)
            continue
        print('Uploading release asset:', path.name, flush=True)
        gh('release', 'upload', tag, path, '--repo', repo, '--clobber')
    release = release_info(repo, tag)
    remote = {item['name']: item for item in release['assets']}
    for path in assets:
        item = remote.get(path.name)
        if not item or item['size'] != path.stat().st_size:
            raise ValueError('Uploaded asset missing or incomplete: ' + path.name)
        if item.get('digest') and item['digest'] != 'sha256:' + ci.sha256(path):
            raise ValueError('Uploaded asset SHA256 mismatch: ' + path.name)
    required = {'D2RMobile-unsigned.ipa', 'build-report.json', 'SHA256SUMS.txt',
                'D2R-Mobile-Resources.zip.001', 'D2R-Mobile-Resources.zip.002',
                'D2R-Mobile-Resources.zip.003', 'resources-report.json',
                'Resources-SHA256SUMS.txt', 'Resources-Parts-SHA256SUMS.txt', 'RESOURCE-INSTALL.txt'}
    if required <= remote.keys():
        # Refresh after publication: GitHub assigns a temporary untagged URL
        # to drafts, which must not be used as the final download link.
        release = publish_complete(repo, tag, notes, title=title)
        print('Published complete release:', release['html_url'], flush=True)
        status = 'Published complete Release'
    else:
        print('Assets uploaded; automatically waiting for matching IPA/resources', flush=True)
        status = 'Draft prepared; waiting for the other successful build'
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            stream.write(f'\n{status}: {release["html_url"]}\n')


if __name__ == '__main__':
    main(sys.argv[1])
