"""Tests for v1.0 P1.4 — manifest management & rerun reproducibility."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

from packages.artifacts.canonical import canonical, stable_hash
from packages.artifacts.registry import save_manifest, load_manifest, list_manifests
from packages.artifacts.run_manifest import build_run_manifest, manifest_result_hash
from packages.artifacts.rerun import rerun_manifest, DriftError


def _sample_manifest(seed=42, result=None):
    return build_run_manifest(
        job_type="backtest",
        parameters={"a": 1, "b": [2, 3], "weights": {"X": 0.5}},
        data=[
            {
                "source": "demo",
                "symbol": "IWDA",
                "data_hash": "sha256:abc",
                "currency": "EUR",
            }
        ],
        seed=seed,
        result=result if result is not None else {"metric": 1.234},
        known_kinds=["backtest"],
    )


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("LML_MANIFEST_DIR", str(tmp_path / "manifests"))


class TestCanonical:
    def test_order_independent(self):
        assert canonical({"a": 1, "b": 2}) == canonical({"b": 2, "a": 1})

    def test_decimal_stable(self):
        from decimal import Decimal

        assert canonical(Decimal("1.50")) == '"1.50"'

    def test_nan_inf(self):
        import math

        # json.dumps emits bare NaN/Infinity (not valid JSON) — we document that
        # canonical() wraps them in quotes for a stable *string* representation
        assert canonical({"x": float("nan")}) == '{"x":"NaN"}'
        assert canonical({"x": math.inf}) == '{"x":"Infinity"}'

    def test_metadata_does_not_break_repro(self):
        m = _sample_manifest()
        h1 = manifest_result_hash(m)
        m2 = dict(m)
        m2["created_at"] = "2099-01-01T00:00:00+00:00"
        m2["run_id"] = "different"
        assert h1 == manifest_result_hash(m2)


class TestManifestStorage:
    def test_unique_id_and_immutable(self):
        m = _sample_manifest()
        mid = save_manifest(m)
        assert mid == m["manifest_id"]
        with pytest.raises(FileExistsError):
            save_manifest(m)

    def test_load_roundtrip(self):
        m = _sample_manifest()
        save_manifest(m)
        loaded = load_manifest(m["manifest_id"])
        assert loaded["parameters_hash"] == m["parameters_hash"]
        assert loaded["manifest_digest"] == m["manifest_digest"]

    def test_save_compute_digest_equal(self):
        from packages.artifacts.registry import manifest_digest_of

        m = _sample_manifest()
        save_manifest(m)
        stored = load_manifest(m["manifest_id"])
        assert stored["manifest_digest"] == manifest_digest_of(m)

    def test_tampered_field_detected(self):
        m = _sample_manifest()
        save_manifest(m)
        loaded = load_manifest(m["manifest_id"])
        loaded["parameters"]["a"] = 999  # mutate a normal field
        # Keep the ORIGINAL (correct) digest so the tampering is detected
        import json, os
        from pathlib import Path

        d = Path(os.environ["LML_MANIFEST_DIR"])
        p = d / f"{m['manifest_id']}.json"
        p.write_text(json.dumps(loaded, indent=2, sort_keys=True), encoding="utf-8")
        with pytest.raises(ValueError):
            load_manifest(m["manifest_id"])

    def test_tampered_digest_field_detected(self):
        m = _sample_manifest()
        save_manifest(m)
        loaded = load_manifest(m["manifest_id"])
        loaded["manifest_digest"] = "sha256:deadbeef"
        import json, os
        from pathlib import Path

        d = Path(os.environ["LML_MANIFEST_DIR"])
        (d / f"{m['manifest_id']}.json").write_text(
            json.dumps(loaded, indent=2, sort_keys=True), encoding="utf-8"
        )
        with pytest.raises(ValueError):
            load_manifest(m["manifest_id"])

    def test_key_order_does_not_change_digest(self):
        from packages.artifacts.registry import manifest_digest_of

        m = _sample_manifest()
        reordered = json.loads(json.dumps(m, sort_keys=False))
        assert manifest_digest_of(reordered) == manifest_digest_of(m)

    def test_decimal_stability_in_digest(self):
        from decimal import Decimal
        from packages.artifacts.registry import manifest_digest_of
        from packages.artifacts.canonical import stable_hash

        assert stable_hash({"x": Decimal("1.50")}) == stable_hash(
            {"x": Decimal("1.50")}
        )

    def test_missing_manifest_digest_legacy_ok(self):
        import json, os
        from pathlib import Path

        m = _sample_manifest()
        save_manifest(m)
        loaded = load_manifest(m["manifest_id"])
        loaded.pop("manifest_digest", None)
        d = Path(os.environ["LML_MANIFEST_DIR"])
        (d / f"{m['manifest_id']}.json").write_text(
            json.dumps(loaded, indent=2, sort_keys=True), encoding="utf-8"
        )
        # legacy (no digest) must load, not raise integrity error
        reloaded = load_manifest(m["manifest_id"])
        assert reloaded["manifest_id"] == m["manifest_id"]

    def test_extra_unknown_fields_preserved(self):
        m = _sample_manifest()
        m["custom_field"] = "x"
        save_manifest(m)
        loaded = load_manifest(m["manifest_id"])
        assert loaded.get("custom_field") == "x"

    def test_missing_manifest_raises(self):
        with pytest.raises(FileNotFoundError):
            load_manifest("does_not_exist")

    def test_path_traversal_rejected(self):
        from packages.artifacts.registry import _safe_id

        with pytest.raises(ValueError):
            _safe_id("../../etc/passwd")

    def test_corrupted_manifest_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LML_MANIFEST_DIR", str(tmp_path / "manifests"))
        from pathlib import Path

        d = Path(os.environ["LML_MANIFEST_DIR"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "man_corrupt.json").write_text("{not valid", encoding="utf-8")
        with pytest.raises(ValueError):
            load_manifest("man_corrupt")


class TestHashes:
    def test_same_params_same_hash(self):
        assert stable_hash({"a": 1}) == stable_hash({"a": 1})

    def test_different_params_different_hash(self):
        assert stable_hash({"a": 1}) != stable_hash({"a": 2})

    def test_result_hash_stable(self):
        m = _sample_manifest(result={"x": 1.0})
        assert manifest_result_hash(m) == manifest_result_hash(
            dict(m, created_at="X", run_id="Y")
        )


class TestSecrets:
    def test_no_secrets_stored(self):
        m = build_run_manifest(
            job_type="backtest",
            parameters={"api_key": "SECRET123", "token": "T"},
            seed=1,
            result={"ok": 1},
        )
        raw = json.dumps(m)
        assert "SECRET123" not in raw
        assert '"token": "T"' not in raw


class TestRerun:
    def _exec(self, manifest):
        return {"metric": round(manifest["seed"] * 0.029, 4) + 1.234}

    def test_byte_identical_rerun(self):
        m = _sample_manifest(seed=42, result={"metric": 1.234 + 42 * 0.029})
        save_manifest(m)
        report = rerun_manifest(
            m["manifest_id"], self._exec, m["system_version"], m["environment_hash"]
        )
        assert report.rerun_status == "byte_identical"
        assert report.original_result_hash == report.rerun_result_hash

    def test_system_version_drift_aborts(self):
        m = _sample_manifest()
        save_manifest(m)
        with pytest.raises(DriftError):
            rerun_manifest(
                m["manifest_id"], self._exec, "different_version", m["environment_hash"]
            )

    def test_environment_drift_warns(self):
        m = _sample_manifest()
        save_manifest(m)
        report = rerun_manifest(
            m["manifest_id"], self._exec, m["system_version"], "different_env_hash"
        )
        assert report.environment_hash_status == "mismatch"
        assert report.rerun_status == "rerun_with_drift"

    def test_allow_environment_drift_flag(self):
        m = _sample_manifest()
        save_manifest(m)
        report = rerun_manifest(
            m["manifest_id"],
            self._exec,
            m["system_version"],
            "different_env_hash",
            allow_environment_drift=True,
        )
        assert any("environment drift allowed" in w for w in report.warnings)


class TestCliRerun:
    def _run(self, *args):
        env = dict(os.environ)
        env["LML_MANIFEST_DIR"] = tempfile.mkdtemp()
        return subprocess.run(
            [sys.executable, "-m", "apps.cli.main", *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def test_manifests_list_empty(self):
        r = self._run("manifests", "list")
        assert r.returncode == 0

    def test_rerun_missing_manifest_cli_error(self):
        r = self._run("manifests", "rerun", "nope")
        assert r.returncode == 1


class TestAsyncRerun:
    """Async rerun via the job queue; needs the API server (skipped if down)."""

    @pytest.fixture(autouse=True)
    def _api(self):
        from apps.cli.jobs_client import JobsClient

        base = os.environ.get("LML_API", "http://127.0.0.1:8322")
        c = JobsClient(base_url=base)
        health = c._get("/api/v1/health")
        if not isinstance(health, dict) or "error" in health:
            pytest.skip("API server not running — skipping async rerun test")
        yield c

    def test_async_rerun_submits_and_completes(self, _api, tmp_path, monkeypatch):
        monkeypatch.setenv("LML_MANIFEST_DIR", str(tmp_path / "manifests"))
        from packages.artifacts.run_manifest import build_run_manifest
        from packages.artifacts.registry import save_manifest

        m = build_run_manifest(
            job_type="backtest", parameters={"x": 1}, seed=7, result={"ok": 1.23}
        )
        save_manifest(m)
        env = dict(os.environ)
        env["LML_MANIFEST_DIR"] = str(tmp_path / "manifests")
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "apps.cli.main",
                "manifests",
                "rerun",
                m["manifest_id"],
                "--async",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert r.returncode == 0, r.stderr
        import re

        job_id = re.search(r"job (\S+)", r.stdout).group(1)
        out = _api.wait(job_id, timeout=30)
        assert out["status"] == "succeeded", out
        assert "rerun_status" in out["result"]
