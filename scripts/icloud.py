#!/usr/bin/env python3
"""Optional iCloud packaging and local macOS signing; no Apple credentials in CI."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

IPA_NAME = 'D2RMobile-icloud-unsigned.ipa'
CONFIG_MEMBER = 'dm/icloud-config.json'
ID_PATTERN = r'[A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9][A-Za-z0-9-]*)+'
ICLOUD_KEYS = (
    'com.apple.developer.icloud-container-identifiers',
    'com.apple.developer.icloud-services',
    'com.apple.developer.ubiquity-container-identifiers',
)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def validate_ids(bundle, container):
    if len(bundle) > 255 or not re.fullmatch(ID_PATTERN, bundle):
        raise ValueError('iCloud builds require an explicit bundle ID owned by the signing team (no wildcard)')
    if not container.startswith('iCloud.') or len(container) > 255 or not re.fullmatch(ID_PATTERN, container[7:]):
        raise ValueError('Invalid iCloud container ID; expected iCloud.<reverse-DNS identifier>')
    return {'bundle_identifier': bundle, 'icloud_container_identifier': container}


def build_options(environ=None):
    environ = os.environ if environ is None else environ
    enabled = environ.get('ICLOUD_SYNC', 'false')
    if enabled not in ('true', 'false'):
        raise ValueError('ICLOUD_SYNC must be true or false')
    if enabled == 'false':
        return None
    bundle = environ.get('ICLOUD_BUNDLE_ID', '')
    container = environ.get('ICLOUD_CONTAINER_ID', '') or 'iCloud.' + bundle
    return validate_ids(bundle, container)


def cloud_entitlements(config):
    container = config['icloud_container_identifier']
    return dict(zip(ICLOUD_KEYS, ([container], ['CloudDocuments'], [container])))


def app_base(archive):
    """Validate archive paths before either repacking or extracting an IPA."""
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError('Duplicate IPA member')
    for entry in archive.infolist():
        path = PurePosixPath(entry.filename)
        if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                or stat.S_ISLNK(entry.external_attr >> 16)):
            raise ValueError('Unsafe IPA member: ' + entry.filename)
    apps = [name[:-len('Info.plist')] for name in names
            if re.fullmatch(r'Payload/[^/]+\.app/Info\.plist', name)]
    if len(apps) != 1:
        raise ValueError('Expected exactly one top-level app in IPA')
    return apps[0]


def configure_outputs(output, config):
    """Make a separate unsigned variant after the existing IPA verifier succeeds."""
    if config is None:
        print('iCloud disabled: standard unsigned IPA and publication are unchanged')
        return
    validate_ids(config['bundle_identifier'], config['icloud_container_identifier'])
    output = Path(output)
    source = output / 'D2RMobile-unsigned.ipa'
    report = json.loads((output / 'build-report.json').read_text())
    if (report.get('signed') is not False or digest(source) != report['ipa_sha256']
            or source.stat().st_size != report['ipa_bytes']):
        raise ValueError('Base IPA does not match the unsigned verification report')
    target = output / 'icloud'
    target.mkdir(exist_ok=True)
    ipa = target / IPA_NAME
    partial = target / (IPA_NAME + '.part')
    try:
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(partial, 'w') as result:
            base = app_base(original)
            if (base + 'embedded.mobileprovision' in original.namelist()
                    or any(name.startswith(base + '_CodeSignature/') for name in original.namelist())):
                raise ValueError('Expected unsigned base app')
            for entry in original.infolist():
                data = original.read(entry)
                if entry.filename == base + 'Info.plist':
                    info = plistlib.loads(data)
                    info['CFBundleIdentifier'] = config['bundle_identifier']
                    data = plistlib.dumps(info, fmt=plistlib.FMT_BINARY)
                if entry.filename == base + CONFIG_MEMBER:
                    raise ValueError('Base IPA already has iCloud build metadata')
                result.writestr(entry, data)
            result.writestr(base + CONFIG_MEMBER, json.dumps(config, sort_keys=True) + '\n')
        with zipfile.ZipFile(partial) as archive:
            if archive.testzip():
                raise ValueError('Corrupt iCloud IPA')
            base = app_base(archive)
            assert plistlib.loads(archive.read(base + 'Info.plist'))['CFBundleIdentifier'] == config['bundle_identifier']
            assert json.loads(archive.read(base + CONFIG_MEMBER)) == config
        partial.replace(ipa)
    finally:
        partial.unlink(missing_ok=True)
    entitlements = target / 'iCloud-entitlements.plist'
    entitlements.write_bytes(plistlib.dumps(cloud_entitlements(config)))
    report.update(config, icloud_sync=True, icloud_sync_verified=False, requires_paid_developer_account=True,
                  signed=False, ipa_sha256=digest(ipa), ipa_bytes=ipa.stat().st_size,
                  entitlements_sha256=digest(entitlements))
    (target / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    (target / 'SHA256SUMS.txt').write_text(
        f"{report['ipa_sha256']}  {ipa.name}\n{report['entitlements_sha256']}  {entitlements.name}\n")
    shutil.copyfile(__file__, target / 'icloud.py')
    (target / 'ICLOUD-INSTALL.txt').write_text(
        'This is an UNSIGNED iCloud variant. A paid Apple Developer Program account is required.\n'
        f"Bundle ID: {config['bundle_identifier']}\nContainer: {config['icloud_container_identifier']}\n\n"
        'Enable iCloud (CloudDocuments / iCloud Drive) for this explicit App ID, assign the container,\n'
        'and download a new development or ad-hoc profile covering your devices and local certificate.\n'
        'On a Mac with Xcode and that certificate/private key in Keychain:\n'
        f'python3 icloud.py sign --ipa {IPA_NAME} --profile your.mobileprovision '
        '--identity YOUR_CERTIFICATE_SHA1 --output D2RMobile-icloud-signed.ipa\n\n'
        'Do not upload Apple credentials, private keys, certificates or profiles to GitHub Actions.\n'
        'Use the same team, bundle ID and container on both devices; sign in to the same iCloud account,\n'
        'enable iCloud Drive and the in-game iCloud setting. Game resources are imported separately.\n'
        'Back up Documents/save first. Changing bundle ID installs a separate app: manually migrate saves\n'
        'and resources rather than uninstalling the old app. Play the same character on one device at a time.\n'
        'A build succeeding does not verify real iCloud sync; validate upload/download on both devices.\n')
    print('Unsigned iCloud variant prepared:', ipa.name, '(paid-account signing required)')


def signing_entitlements(profile, config, identity, now=None):
    """Fail before signing when a free/wildcard/wrong-device profile is supplied."""
    validate_ids(config['bundle_identifier'], config['icloud_container_identifier'])
    if not re.fullmatch(r'[0-9A-Fa-f]{40}', identity):
        raise ValueError('Use the certificate SHA1 from security find-identity -v -p codesigning')
    expires = profile.get('ExpirationDate')
    now = now or datetime.now(timezone.utc)
    if not isinstance(expires, datetime) or expires.replace(tzinfo=timezone.utc) <= now:
        raise ValueError('Provisioning profile is expired or lacks an expiration date')
    if not profile.get('ProvisionedDevices'):
        raise ValueError('Use a development or ad-hoc profile containing your devices')
    certificates = {hashlib.sha1(cert).hexdigest().upper() for cert in profile.get('DeveloperCertificates', [])}
    if identity.upper() not in certificates:
        raise ValueError('Signing certificate is not authorized by the profile')
    prefixes = profile.get('ApplicationIdentifierPrefix', [])
    teams = profile.get('TeamIdentifier', [])
    if len(prefixes) != 1 or len(teams) != 1:
        raise ValueError('Ambiguous signing team or application identifier prefix')
    allowed = profile.get('Entitlements', {})
    app_id = prefixes[0] + '.' + config['bundle_identifier']
    if allowed.get('application-identifier') != app_id:
        raise ValueError('Profile must authorize the exact bundle ID; wildcard profiles cannot enable iCloud')
    requested = cloud_entitlements(config)
    for key, values in requested.items():
        if not isinstance(allowed.get(key), list) or not set(values) <= set(allowed[key]):
            raise ValueError('Profile lacks required iCloud permission: ' + key)
    requested.update({'application-identifier': app_id,
                      'com.apple.developer.team-identifier': teams[0],
                      'get-task-allow': bool(allowed.get('get-task-allow', False))})
    return requested


def sign(ipa, profile_path, identity, output):
    if sys.platform != 'darwin':
        raise ValueError('Local signing requires macOS with Xcode; CI never signs this variant')
    ipa, profile_path, output = map(lambda path: Path(path).resolve(), (ipa, profile_path, output))
    if output.exists():
        raise ValueError('Refusing to overwrite an existing output IPA')
    # security decodes the Apple-signed profile; no Apple account credentials are read.
    profile = plistlib.loads(subprocess.check_output(['security', 'cms', '-D', '-i', str(profile_path)]))
    with zipfile.ZipFile(ipa) as archive:
        base = app_base(archive)
        config = json.loads(archive.read(base + CONFIG_MEMBER))
        if plistlib.loads(archive.read(base + 'Info.plist'))['CFBundleIdentifier'] != config['bundle_identifier']:
            raise ValueError('IPA bundle ID differs from iCloud build metadata')
        entitlements = signing_entitlements(profile, config, identity)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='d2r-sign-', dir=output.parent) as temporary:
            root = Path(temporary)
            archive.extractall(root)
            # zipfile extracts files without preserving executable permissions.
            for entry in archive.infolist():
                mode = (entry.external_attr >> 16) & 0o777
                if mode:
                    (root / entry.filename).chmod(mode)
            app = root / base
            shutil.copyfile(profile_path, app / 'embedded.mobileprovision')
            ent_path = root / 'entitlements.plist'
            ent_path.write_bytes(plistlib.dumps(entitlements))
            frameworks = list(app.rglob('*.framework')) + list(app.rglob('*.dylib'))
            for framework in sorted(frameworks, key=lambda path: len(path.parts), reverse=True):
                subprocess.run(['codesign', '--force', '--sign', identity, '--timestamp=none', str(framework)], check=True)
            subprocess.run(['codesign', '--force', '--sign', identity, '--timestamp=none',
                            '--entitlements', str(ent_path), str(app)], check=True)
            subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
            signed = root / 'signed.ipa'
            subprocess.run(['ditto', '-c', '-k', '--keepParent', str(root / 'Payload'), str(signed)], check=True)
            os.link(signed, output)  # Atomic publication without overwriting a concurrent output.
    print('Signed IPA:', output, '\nProfile expires:', profile['ExpirationDate'].isoformat())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('validate')
    configure = commands.add_parser('configure')
    configure.add_argument('--outputs', type=Path, default=Path(__file__).resolve().parents[1] / 'outputs')
    signer = commands.add_parser('sign')
    for name in ('ipa', 'profile', 'identity', 'output'):
        signer.add_argument('--' + name, required=True)
    args = parser.parse_args()
    if args.command == 'validate':
        print('Build mode:', 'iCloud (paid-account signing required)' if build_options() else 'standard (iCloud not provisioned)')
    elif args.command == 'configure':
        configure_outputs(args.outputs, build_options())
    else:
        sign(args.ipa, args.profile, args.identity, args.output)


if __name__ == '__main__':
    main()
