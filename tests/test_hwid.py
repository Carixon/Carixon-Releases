from __future__ import annotations

from jbs_client.hwid import compute_hwid


def test_hwid_is_deterministic(monkeypatch):
    hwid1 = compute_hwid()
    hwid2 = compute_hwid()
    assert hwid1 == hwid2
    assert len(hwid1) == 24
