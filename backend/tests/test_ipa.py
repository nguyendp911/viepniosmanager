import io
import plistlib
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from viepn.ipa import inspect_ipa, parse_provision, profile_compatible, supports_bundle

UDID = '00008110-000A12345678901E'


def provision(expiry=None, bundle='com.example.app', devices=None):
    expiry = expiry or datetime.now(timezone.utc) + timedelta(days=6)
    return ('\x30CMS' + plistlib.dumps({
        'ExpirationDate': expiry,
        'TeamIdentifier': ['TEAM12345'],
        'Entitlements': {'application-identifier': 'TEAM12345.' + bundle},
        'ProvisionedDevices': devices or [UDID],
        'UUID': 'test-uuid',
    }).decode()).encode()


def sample_ipa(path, signed=True):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('Payload/Sample.app/Info.plist', plistlib.dumps({
            'CFBundleIdentifier': 'com.example.app', 'CFBundleName': 'Sample',
            'CFBundleShortVersionString': '1.1.0',
        }))
        if signed:
            z.writestr('Payload/Sample.app/embedded.mobileprovision', provision())
    return path


def test_ipa_metadata(tmp_path):
    metadata = inspect_ipa(sample_ipa(tmp_path / 'ok.ipa'))
    assert metadata['name'] == 'Sample'
    assert metadata['bundle_id'] == 'com.example.app'
    assert metadata['signed_candidate'] is True
    assert metadata['profile_expires']
    assert inspect_ipa(sample_ipa(tmp_path / 'unsigned.ipa', False))['signed_candidate'] is False


def test_invalid_ipa(tmp_path):
    path = tmp_path / 'bad.ipa'
    path.write_bytes(b'not a zip')
    with pytest.raises(ValueError):
        inspect_ipa(path)


def test_profile_newer_and_udid():
    metadata = parse_provision(provision())
    assert metadata['bundle_pattern'] == 'com.example.app'
    assert profile_compatible(metadata, 'com.example.app', UDID)
    assert not profile_compatible(metadata, 'com.example.other', UDID)
    assert not profile_compatible(metadata, 'com.example.app', '0000000000000000')
    assert not profile_compatible(metadata, 'com.example.app', UDID, metadata['expires_at'])
    assert supports_bundle('com.example.*', 'com.example.app')
    assert not supports_bundle('com.example.*', 'org.example.app')
