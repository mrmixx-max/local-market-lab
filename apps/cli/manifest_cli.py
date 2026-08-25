"""CLI: `lml manifests` and `lml rerun` (v1.0 P1.4)."""

from __future__ import annotations

import json

import typer

from packages.artifacts.registry import list_manifests, load_manifest

manifests_app = typer.Typer(help="Run manifest inspection and reruns.")
JSON_OPT = typer.Option(False, "--json", help="Emit JSON.")


def _emit(obj) -> None:
    typer.echo(json.dumps(obj, indent=2, default=str))


@manifests_app.command("list")
def list_cmd(json_out: bool = JSON_OPT):
    """List stored run manifests (newest first)."""
    items = list_manifests()
    if json_out:
        _emit(items)
        return
    if not items:
        typer.echo("no manifests")
        return
    typer.echo(f"{'MANIFEST_ID':<28} {'TYPE':<14} {'VERSION':<10} {'CREATED':<21}")
    for m in items:
        ca = str(m.get("created_at") or "")[:19].replace("T", " ")
        typer.echo(
            f"{str(m.get('manifest_id')):<28} "
            f"{str(m.get('job_type')):<14} "
            f"{str(m.get('system_version')):<10} {ca}"
        )


@manifests_app.command("show")
def show_cmd(manifest_id: str, json_out: bool = JSON_OPT):
    """Show a single manifest's full content."""
    try:
        m = load_manifest(manifest_id)
    except FileNotFoundError:
        typer.echo(f"error: manifest {manifest_id} not found", err=True)
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1)
    if json_out:
        _emit(m)
    else:
        typer.echo(json.dumps(m, indent=2, sort_keys=True, default=str))


@manifests_app.command("compare")
def compare_cmd(manifest_id: str, json_out: bool = JSON_OPT):
    """Compare original vs stored rerun record (if any)."""
    try:
        m = load_manifest(manifest_id)
    except FileNotFoundError:
        typer.echo(f"error: manifest {manifest_id} not found", err=True)
        raise typer.Exit(1)
    out = {
        "manifest_id": manifest_id,
        "result_hash": m.get("result_hash"),
        "parameters_hash": m.get("parameters_hash"),
        "environment_hash": m.get("environment_hash"),
        "system_version": m.get("system_version"),
    }
    if json_out:
        _emit(out)
    else:
        for k, v in out.items():
            typer.echo(f"{k}: {v}")


# ─── rerun ────────────────────────────────────────────────────────
from packages.artifacts.rerun import DriftError, rerun_manifest
from packages.artifacts.run_manifest import _env_hash, _system_version


@manifests_app.command("rerun")
def rerun_cmd(
    manifest_id: str,
    async_mode: bool = typer.Option(False, "--async", help="Run via job queue."),
    json_out: bool = typer.Option(False, "--json"),
    allow_data_drift: bool = typer.Option(False, "--allow-data-drift"),
    allow_environment_drift: bool = typer.Option(False, "--allow-environment-drift"),
):
    """Re-execute a stored manifest and compare result hashes.

    Requires the caller to provide an executor via the job registry; for the
    CLI we use the registered rerun executors keyed by job_type.
    """
    from packages.artifacts.rerun_cli_helpers import get_executor

    try:
        executor = get_executor()
    except Exception as exc:
        typer.echo(f"error: no executor available: {exc}", err=True)
        raise typer.Exit(1)

    # async path → submit to job queue
    if async_mode:
        from apps.cli.jobs_client import JobsClient

        c = JobsClient()
        resp = c.submit(
            "rerun",
            {
                "manifest_id": manifest_id,
                "allow_data_drift": allow_data_drift,
                "allow_environment_drift": allow_environment_drift,
            },
        )
        if not isinstance(resp, dict) or "job_id" not in resp:
            typer.echo(f"error: async submit failed: {resp}", err=True)
            raise typer.Exit(1)
        typer.echo(f"rerun queued as job {resp['job_id']}")
        typer.echo("poll with: lml jobs wait " + resp["job_id"])
        raise typer.Exit(0)

    cur_ver = _system_version()
    cur_env, _ = _env_hash()
    try:
        report = rerun_manifest(
            manifest_id,
            executor,
            cur_ver,
            cur_env,
            allow_data_drift=allow_data_drift,
            allow_environment_drift=allow_environment_drift,
        )
    except FileNotFoundError:
        typer.echo(f"error: manifest {manifest_id} not found", err=True)
        raise typer.Exit(1)
    except DriftError as exc:
        typer.echo(f"drift abort: {exc}", err=True)
        raise typer.Exit(2)
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(3)

    if json_out:
        _emit(report.to_dict())
        return
    d = report.to_dict()
    typer.echo(f"Manifest: {d['manifest_id']}")
    typer.echo(f"Original Result Hash: {d['original_result_hash']}")
    typer.echo(f"Rerun Result Hash:    {d['rerun_result_hash']}")
    typer.echo(f"Data Hash:    {d['data_hash_status'].upper()}")
    typer.echo(f"Parameters:   {d['parameter_hash_status'].upper()}")
    typer.echo(f"Model:        {d['model_hash_status'].upper()}")
    typer.echo(f"Environment:  {d['environment_hash_status'].upper()}")
    typer.echo(f"Result: {d['rerun_status'].upper()}")
    for w in d["warnings"]:
        typer.echo(f"  warning: {w}")
