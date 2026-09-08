from __future__ import annotations

import json
import os
import subprocess

import pytest

from tests.conftest import ROOT, pg_enabled

SAMPLE_MD = ROOT / "samples" / "refund_policy_v3.md"


def _pg_env() -> dict[str, str]:
    env = os.environ.copy()
    env["AKOS_USE_PG"] = "true"
    return env


@pytest.mark.skipif(not pg_enabled(), reason="needs PG")
def test_cli_cross_command_with_kb(seeded_kb_id):
    env = _pg_env()

    subprocess.run(
        ["akos", "ingest", str(SAMPLE_MD), "--kb", seeded_kb_id],
        check=True,
        env=env,
        cwd=str(ROOT),
    )
    result = subprocess.run(
        ["akos", "ask", "定制商品能否七天无理由退货？", "--kb", seeded_kb_id],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        cwd=str(ROOT),
    )
    payload = json.loads(result.stdout)
    assert "claim_ids" in result.stdout
    assert payload["claim_ids"]
    assert "依据不足" not in payload["text"]
