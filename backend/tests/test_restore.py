"""Offline restore only after validation; no network endpoint is exposed."""
from pathlib import Path

from test_api import config
from test_ipa import sample_ipa
from viepn.backups import create_backup
from viepn.restore import restore_backup
from viepn.service import Manager


def test_offline_restore_recovers_ipa_metadata_and_preserves_token(tmp_path):
    mgr = Manager(config(tmp_path))
    original = mgr.add_ipa(sample_ipa(tmp_path / "sample.ipa"))
    backup = create_backup(mgr.cfg.root, mgr.db)
    archive = mgr.cfg.root / "backups" / backup["name"]
    token_file = mgr.cfg.root / "access_token.txt"
    token_file.write_text("sensitive-token-must-not-be-touched")
    mgr.rename_ipa(original["id"], "changed")
    try:
        restore_backup(mgr.cfg.root, archive, confirm="no", ports=())
        assert False
    except ValueError:
        pass
    report = restore_backup(mgr.cfg.root, archive, confirm="RESTORE VIEPN", ports=())
    assert report["restored"]
    restored = mgr.db.one("SELECT * FROM ipa WHERE id=?", (original["id"],))
    assert restored["alias"] is None
    assert token_file.read_text() == "sensitive-token-must-not-be-touched"
    assert Path(restored["file_path"]).is_file()
