import asyncio
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT))
import backend.device_api as dev


def test_paired_agent_receives_only_own_job_and_revokes(tmp_path, monkeypatch):
    monkeypatch.setattr(dev, 'DB_PATH', tmp_path/'devices.db')
    monkeypatch.setattr(dev, '_user', lambda req: (req.headers.get('x-user',''), 'member'))
    app=FastAPI(); app.include_router(dev.router)
    client=TestClient(app)

    # User A creates a single-use code and pairs their local device.
    code=client.post('/api/v1/devices/pairing-code',headers={'x-user':'user-a'}).json()['pairing_code']
    paired=client.post('/api/v1/devices/pair',json={'pairing_code':code,'name':'dev-a','platform':'linux'}).json()
    token=paired['device_token']; device_id=paired['device_id']
    agent_headers={'Authorization':f'Bearer {token}'}

    # Agent is already polling; dispatch an echo task through the actual queue routine.
    result_box={}
    def fake_agent():
        response=client.get('/api/v1/devices/agent/jobs/next',params={'wait':5},headers=agent_headers)
        job=response.json().get('job')
        if not job:
            result_box['missing']=True; return
        result_box['job']=job
        client.post(f"/api/v1/devices/agent/jobs/{job['job_id']}/result",headers=agent_headers,
                    json={'exit_code':0,'stdout':'DEVICE_OK\\n','stderr':''})
    thread=threading.Thread(target=fake_agent); thread.start()
    dispatched=asyncio.run(dev.run_on_user_device('user-a',device_id,'echo DEVICE_OK','shell',timeout=5))
    thread.join(timeout=6)
    assert dispatched['ok'] is True
    assert 'DEVICE_OK' in dispatched['stdout']
    assert result_box['job']['command']=='echo DEVICE_OK'

    # User B cannot view or revoke A's device, and the agent token stops working after revocation.
    monkeypatch.setattr(dev, '_user', lambda req: ('user-b','member'))
    assert client.delete(f'/api/v1/devices/{device_id}').status_code==404
    monkeypatch.setattr(dev, '_user', lambda req: ('user-a','member'))
    assert client.delete(f'/api/v1/devices/{device_id}').status_code==200
    assert client.get('/api/v1/devices/agent/jobs/next',headers=agent_headers).status_code==401


def test_pairing_code_failures_are_rate_limited(tmp_path, monkeypatch):
    monkeypatch.setattr(dev, 'DB_PATH', tmp_path/'devices.db')
    monkeypatch.setattr(dev, '_user', lambda req: ('user-a','member'))
    app=FastAPI(); app.include_router(dev.router)
    client=TestClient(app)
    for _ in range(dev.PAIR_FAILURE_LIMIT):
        response=client.post('/api/v1/devices/pair', json={'pairing_code':'wrong-code'})
        assert response.status_code == 401
    assert client.post('/api/v1/devices/pair', json={'pairing_code':'wrong-code'}).status_code == 429


def test_agent_bounded_output_and_timeout():
    import importlib.util
    import sys
    agent_path = ROOT / "scripts" / "aios-agent.py"
    spec = importlib.util.spec_from_file_location("aios_agent", agent_path)
    agent = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = agent
    spec.loader.exec_module(agent)
    big = agent._run_bounded([sys.executable, "-c", "import sys; print('x'*500000); print('e'*500000, file=sys.stderr)"], 5, str(ROOT))
    assert big["exit_code"] == 0
    assert len(big["stdout"].encode()) <= agent.MAX_OUTPUT
    assert len(big["stderr"].encode()) <= agent.MAX_OUTPUT
    timed = agent._run_bounded([sys.executable, "-c", "import time; time.sleep(2)"], 1, str(ROOT))
    assert timed["exit_code"] == 124
