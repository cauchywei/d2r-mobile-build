from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import icloud
import publish_release


CONFIG = {'bundle_identifier': 'com.example.game',
          'icloud_container_identifier': 'iCloud.com.example.game'}
CERT = b'fixture-certificate'
IDENTITY = hashlib.sha1(CERT).hexdigest().upper()
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def profile():
    allowed = icloud.cloud_entitlements(CONFIG)
    allowed.update({'application-identifier': 'TEAM.com.example.game', 'get-task-allow': True})
    return {'ExpirationDate': datetime(2030, 1, 1), 'ProvisionedDevices': ['fixture-device'],
            'DeveloperCertificates': [CERT], 'ApplicationIdentifierPrefix': ['TEAM'],
            'TeamIdentifier': ['TEAM'], 'Entitlements': allowed}


def base_ipa(root, extras=None):
    root.mkdir(exist_ok=True)
    path = root / 'D2RMobile-unsigned.ipa'
    contents = {
        'Payload/Game.app/Info.plist': plistlib.dumps({'CFBundleIdentifier': 'org.d2rmobile.app', 'CFBundleExecutable': 'Game'}),
        'Payload/Game.app/Game': b'host including existing cloud-sync code',
        'Payload/Game.app/Frameworks/Guest.framework/Guest': b'unchanged generated game',
        'Payload/Game.app/msl/b-test/example_b.metallib': b'unchanged shader',
    }
    contents.update(extras or {})
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            entry = zipfile.ZipInfo(name)
            entry.external_attr = 0o100755 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    (root / 'build-report.json').write_text(json.dumps({
        'signed': False, 'ipa_bytes': path.stat().st_size, 'ipa_sha256': icloud.digest(path),
        'shader_chain': 'test', 'upstream_commit': 'pinned',
    }))
    return contents


class CloudPackagingTests(unittest.TestCase):
    def test_default_mode_does_not_touch_standard_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base_ipa(root)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            self.assertIsNone(icloud.build_options({}))
            # Retained input fields have no effect when the toggle is disabled.
            self.assertIsNone(icloud.build_options({'ICLOUD_SYNC': 'false', 'ICLOUD_BUNDLE_ID': 'ignored'}))
            icloud.configure_outputs(root, None)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_enabled_mode_requires_valid_explicit_ids(self):
        with self.assertRaisesRegex(ValueError, 'explicit bundle ID'):
            icloud.build_options({'ICLOUD_SYNC': 'true'})
        for bundle in ('com.example.*', '../example', 'com..example', 'com.example;echo bad'):
            with self.subTest(bundle=bundle), self.assertRaises(ValueError):
                icloud.build_options({'ICLOUD_SYNC': 'true', 'ICLOUD_BUNDLE_ID': bundle})
        for container in ('Cloud.example.game', 'iCloud.com.example.*', 'iCloud.com.example/game'):
            with self.subTest(container=container), self.assertRaises(ValueError):
                icloud.validate_ids(CONFIG['bundle_identifier'], container)
        with self.assertRaisesRegex(ValueError, 'true or false'):
            icloud.build_options({'ICLOUD_SYNC': 'yes'})
        self.assertEqual(icloud.build_options({'ICLOUD_SYNC': 'true', 'ICLOUD_BUNDLE_ID': 'com.example.game'}), CONFIG)

    def test_cloud_variant_preserves_game_and_standard_ipa_and_records_matching_entitlements(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entries = base_ipa(root)
            original = (root / 'D2RMobile-unsigned.ipa').read_bytes()
            icloud.configure_outputs(root, CONFIG)
            self.assertEqual((root / 'D2RMobile-unsigned.ipa').read_bytes(), original)
            target = root / 'icloud'
            with zipfile.ZipFile(target / icloud.IPA_NAME) as archive:
                self.assertIsNone(archive.testzip())
                info = plistlib.loads(archive.read('Payload/Game.app/Info.plist'))
                self.assertEqual(info['CFBundleIdentifier'], CONFIG['bundle_identifier'])
                for name, data in entries.items():
                    if not name.endswith('/Info.plist'):
                        self.assertEqual(archive.read(name), data)
                        self.assertEqual(archive.getinfo(name).external_attr, 0o100755 << 16)
                self.assertEqual(json.loads(archive.read('Payload/Game.app/' + icloud.CONFIG_MEMBER)), CONFIG)
                self.assertNotIn('Payload/Game.app/embedded.mobileprovision', archive.namelist())
            entitlements = plistlib.loads((target / 'iCloud-entitlements.plist').read_bytes())
            self.assertEqual(entitlements, icloud.cloud_entitlements(CONFIG))
            report = json.loads((target / 'build-report.json').read_text())
            self.assertFalse(report['signed'])
            self.assertFalse(report['icloud_sync_verified'])
            self.assertTrue(report['requires_paid_developer_account'])
            self.assertEqual(report['shader_chain'], 'test')
            self.assertEqual(report['ipa_sha256'], icloud.digest(target / icloud.IPA_NAME))
            self.assertEqual(report['entitlements_sha256'], icloud.digest(target / 'iCloud-entitlements.plist'))
            self.assertTrue((target / 'icloud.py').is_file())

    def test_modified_base_ipa_is_rejected_before_variant_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base_ipa(root)
            with (root / 'D2RMobile-unsigned.ipa').open('ab') as stream:
                stream.write(b'tampered')
            with self.assertRaisesRegex(ValueError, 'verification report'):
                icloud.configure_outputs(root, CONFIG)
            self.assertFalse((root / 'icloud').exists())

    def test_unsafe_or_signed_archives_are_not_published(self):
        for name, error in [('Payload/Game.app/../../outside', 'Unsafe'),
                            ('Payload/Game.app/embedded.mobileprovision', 'unsigned'),
                            ('Payload/Second.app/Info.plist', 'exactly one')]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                base_ipa(root, {name: b'extra'})
                with self.assertRaisesRegex(ValueError, error):
                    icloud.configure_outputs(root, CONFIG)
                self.assertFalse((root / 'icloud' / icloud.IPA_NAME).exists())
                self.assertFalse((root / 'icloud' / (icloud.IPA_NAME + '.part')).exists())

    def test_cloud_build_cannot_publish_over_the_standard_release(self):
        with patch.dict('os.environ', {'ICLOUD_SYNC': 'true', 'ICLOUD_BUNDLE_ID': 'com.example.game'}), patch.object(publish_release, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'Actions artifacts only'):
                publish_release.main('ipa')
            api.assert_not_called()


class CloudSigningTests(unittest.TestCase):
    def test_authorized_profile_builds_minimal_entitlements(self):
        entitlements = icloud.signing_entitlements(profile(), CONFIG, IDENTITY, NOW)
        self.assertEqual(entitlements['application-identifier'], 'TEAM.com.example.game')
        self.assertEqual(entitlements['com.apple.developer.icloud-services'], ['CloudDocuments'])
        self.assertTrue(entitlements['get-task-allow'])
        self.assertNotIn('com.apple.developer.kernel.increased-memory-limit', entitlements)
        adhoc = profile()
        adhoc['Entitlements']['get-task-allow'] = False
        self.assertFalse(icloud.signing_entitlements(adhoc, CONFIG, IDENTITY, NOW)['get-task-allow'])

    def test_free_wildcard_expired_and_wrong_certificate_profiles_are_rejected(self):
        for change, error in [
            (lambda p: p['Entitlements'].update({'application-identifier': 'TEAM.*'}), 'exact bundle ID'),
            (lambda p: p.update({'ExpirationDate': datetime(2025, 1, 1)}), 'expired'),
            (lambda p: p.update({'DeveloperCertificates': [b'other certificate']}), 'certificate'),
            (lambda p: p.update({'ProvisionedDevices': []}), 'devices'),
        ]:
            with self.subTest(error=error):
                p = profile()
                change(p)
                with self.assertRaisesRegex(ValueError, error):
                    icloud.signing_entitlements(p, CONFIG, IDENTITY, NOW)
        for key in icloud.ICLOUD_KEYS:
            with self.subTest(key=key):
                p = profile()
                p['Entitlements'].pop(key)
                with self.assertRaisesRegex(ValueError, 'lacks required iCloud permission'):
                    icloud.signing_entitlements(p, CONFIG, IDENTITY, NOW)
        p = profile()
        p['Entitlements']['com.apple.developer.icloud-container-identifiers'] = ['iCloud.other.app']
        with self.assertRaisesRegex(ValueError, 'lacks required iCloud permission'):
            icloud.signing_entitlements(p, CONFIG, IDENTITY, NOW)

    def test_missing_cloud_permission_fails_before_codesign_or_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base_ipa(root)
            icloud.configure_outputs(root, CONFIG)
            p = profile()
            p['Entitlements'].pop(icloud.ICLOUD_KEYS[0])
            output = root / 'signed.ipa'
            with patch.object(icloud.sys, 'platform', 'darwin'), patch.object(icloud.subprocess, 'check_output', return_value=plistlib.dumps(p)), patch.object(icloud.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'lacks required iCloud permission'):
                    icloud.sign(root / 'icloud' / icloud.IPA_NAME, root / 'profile', IDENTITY, output)
                run.assert_not_called()
                self.assertFalse(output.exists())

    def test_signer_preserves_executable_modes_and_signs_framework_before_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base_ipa(root)
            icloud.configure_outputs(root, CONFIG)
            pp = root / 'profile.mobileprovision'
            pp.write_bytes(b'profile installed in signed app')
            output = root / 'signed.ipa'
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                if args[0] == 'codesign' and '--entitlements' in args:
                    app = Path(args[-1])
                    self.assertEqual((app / 'Game').stat().st_mode & 0o777, 0o755)
                    self.assertEqual((app / 'embedded.mobileprovision').read_bytes(), pp.read_bytes())
                    ent = plistlib.loads(Path(args[args.index('--entitlements') + 1]).read_bytes())
                    self.assertEqual(ent['application-identifier'], 'TEAM.com.example.game')
                    self.assertEqual(ent['com.apple.developer.icloud-services'], ['CloudDocuments'])
                if args[0] == 'ditto':
                    Path(args[-1]).write_bytes(b'signed archive fixture')

            with patch.object(icloud.sys, 'platform', 'darwin'), patch.object(icloud.subprocess, 'check_output', return_value=plistlib.dumps(profile())), patch.object(icloud.subprocess, 'run', side_effect=run):
                icloud.sign(root / 'icloud' / icloud.IPA_NAME, pp, IDENTITY, output)
            self.assertEqual(output.read_bytes(), b'signed archive fixture')
            self.assertTrue(calls[0][-1].endswith('Guest.framework'))
            self.assertTrue(calls[1][-1].endswith('Game.app'))
            self.assertIn('--verify', calls[2])
            self.assertEqual(calls[3][0], 'ditto')


if __name__ == '__main__':
    unittest.main()
