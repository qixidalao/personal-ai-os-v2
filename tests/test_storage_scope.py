from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import backend.executor as executor
import tools.media as media


def test_local_media_is_written_to_user_directory(tmp_path,monkeypatch):
    monkeypatch.setattr(media,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(executor,'EXEC_ROOT',tmp_path/'storage'/'users')
    async def local_mode(uid,role): return ('local','~/aios-data')
    monkeypatch.setattr(executor,'remote_storage_mode',local_mode)
    record=asyncio.run(media.save_user_media('user-a','member','pic.png','image/png',b'png-bytes'))
    assert record['owner_user_id']=='user-a'
    assert Path(record['path']).is_relative_to(tmp_path/'storage'/'users'/'user-a')
    assert media.get_media_record(record['media_id'],'user-a','member') is not None
    assert media.get_media_record(record['media_id'],'user-b','member') is None


def test_remote_media_uses_remote_write_and_no_local_file(tmp_path,monkeypatch):
    monkeypatch.setattr(media,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(executor,'EXEC_ROOT',tmp_path/'storage'/'users')
    async def remote_mode(uid,role): return ('remote','~/aios-data')
    calls=[]
    async def write(uid,role,path,data): calls.append((uid,path,data)); return {'ok':True}
    monkeypatch.setattr(executor,'remote_storage_mode',remote_mode)
    monkeypatch.setattr(executor,'remote_write_bytes',write)
    record=asyncio.run(media.save_user_media('user-a','member','pic.png','image/png',b'png-bytes'))
    assert record['storage']=='remote'
    assert calls and calls[0][0]=='user-a' and calls[0][2]==b'png-bytes'
    assert not list((tmp_path/'storage'/'users'/'user-a'/'media').glob('*.png'))


def test_remote_binary_limits_fail_before_upload(tmp_path,monkeypatch):
    monkeypatch.setattr(executor,'EXEC_ROOT',tmp_path)
    async def remote_mode(uid,role): return ('remote','~/aios-data')
    monkeypatch.setattr(executor,'remote_storage_mode',remote_mode)
    with pytest.raises(ValueError):
        asyncio.run(executor.remote_write_bytes('user-a','member','media/x',b'x'*(executor.MAX_REMOTE_FILE_BYTES+1)))


def test_remote_storage_disabled_does_not_fallback_to_local(tmp_path,monkeypatch):
    monkeypatch.setattr(executor,'EXEC_ROOT',tmp_path)
    with pytest.raises(PermissionError):
        asyncio.run(executor.remote_write_bytes('user-a','member','media/x',b'data'))
    assert not list(tmp_path.rglob('*'))
