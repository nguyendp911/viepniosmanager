import asyncio
import json
from datetime import datetime, timedelta, timezone
from viepn.service import Manager
from viepn.db import utcnow
from test_api import config
from test_ipa import sample_ipa, UDID


def test_due_and_restart_job_policy(tmp_path):
    mgr = Manager(config(tmp_path))
    ipa = mgr.add_ipa(sample_ipa(tmp_path / 'test.ipa'))
    now = datetime.now(timezone.utc)
    end = (now + timedelta(hours=23)).isoformat()
    mgr.db.exec('''INSERT INTO installations(id,device_udid,bundle_id,source_ipa_id,
        current_ipa_id,expires_at,auto_renew,state,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)''',
        ('install1', UDID, ipa['bundle_id'], ipa['id'], ipa['id'],
         end, 1, 'active', utcnow()))
    due = mgr.due_installations()
    assert len(due) == 1
    mgr.db.exec('UPDATE installations SET last_attempt=? WHERE id=?', (utcnow(), 'install1'))
    assert mgr.due_installations() == []


def test_no_profile_does_not_claim_renewal(tmp_path):
    mgr = Manager(config(tmp_path))
    ipa = mgr.add_ipa(sample_ipa(tmp_path / 'test.ipa'))
    # Profile metadata in an IPA is not sufficient for renewal: a *new*,
    # device-compatible profile needs to exist in the profiles library.
    try:
        mgr.get_profile(None, ipa['bundle_id'], UDID)
    except ValueError as exc:
        assert 'provisioning profile' in str(exc)
    else:
        raise AssertionError('Should require a new provisioning profile')
