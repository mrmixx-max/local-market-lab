"""CLI: `lml jobs` — client binding for the in-process job queue.

  lml jobs list [--json]
  lml jobs status <job_id> [--json]
  lml jobs cancel <job_id>
  lml jobs wait <job_id> [--timeout SECONDS]
  lml jobs artifact <job_id>

Exit codes: 0 on succeeded/OK; non-zero on failed/cancelled/timeout/not_found.
No API keys, tokens, or portfolio contents are printed.
"""

from __future__ import annotations

import json

import typer

from apps.cli.jobs_client import JobsClient, runtime_seconds

jobs_app = typer.Typer(help="Job queue client — analysis only, no execution.")
API_OPT = typer.Option("http://127.0.0.1:8322", "--api", envvar="LML_API")
JSON_OPT = typer.Option(False, "--json", help="Emit JSON instead of tables.")


def _client(api: str) -> JobsClient:
    return JobsClient(base_url=api)


_STATUS_COLOR = {
    "queued": "dim",
    "running": "amber",
    "cancelling": "amber",
    "cancelled": "red",
    "succeeded": "green",
    "failed": "red",
}


def _emit(obj) -> None:
    typer.echo(json.dumps(obj, indent=2, default=str))


@jobs_app.command("list")
def list_jobs(api: str = API_OPT, json_out: bool = JSON_OPT):
    """List recent jobs with id, type, status, progress, phase, runtime."""
    jobs = _client(api).list()
    if isinstance(jobs, dict) and "error" in jobs:
        typer.echo(f"error: {jobs['error']}", err=True)
        raise typer.Exit(1)
    if json_out:
        _emit(jobs)
        return
    if not jobs:
        typer.echo("no jobs")
        return
    typer.echo(
        f"{'JOB_ID':<14} {'TYPE':<14} {'STATUS':<11} {'PROG':>6}  {'PHASE':<11} {'RT':>7}"
    )
    for j in jobs:
        rt = runtime_seconds(j) if isinstance(j, dict) else None
        typer.echo(
            f"{str(j['job_id']):<14} {str(j['job_type']):<14} "
            f"{j['status']:<11} {j['progress']*100:>5.0f}%  "
            f"{j['phase']:<11} {str(rt):>7}"
        )


@jobs_app.command("status")
def status_job(job_id: str, api: str = API_OPT, json_out: bool = JSON_OPT):
    """Show full status of one job."""
    job = _client(api).get(job_id)
    if not isinstance(job, dict):
        typer.echo("error: no response", err=True)
        raise typer.Exit(1)
    if "error" in job:
        typer.echo(f"error: {job['error']}", err=True)
        raise typer.Exit(1 if job.get("status_code") == 404 else 2)
    if json_out:
        _emit(job)
        return
    typer.echo(f"job_id:        {job['job_id']}")
    typer.echo(f"type:          {job['job_type']}")
    typer.echo(f"status:        {job['status']}")
    typer.echo(f"progress:      {job['progress']*100:.1f}%")
    typer.echo(f"phase:         {job['phase']}")
    typer.echo(f"message:       {job['message']}")
    typer.echo(f"created_at:    {job['created_at']}")
    typer.echo(f"started_at:    {job['started_at']}")
    typer.echo(f"finished_at:   {job['finished_at']}")
    typer.echo(f"cancel_flag:   {job['cancel_requested']}")
    typer.echo(f"run_id:        {job['run_id']}")
    typer.echo(f"artifact_id:   {job['artifact_id']}")
    if job["error_message"]:
        typer.echo(f"error:         {job['error_message']}")
    for w in job.get("warnings", []):
        typer.echo(f"warning:       {w}")


@jobs_app.command("cancel")
def cancel_job(job_id: str, api: str = API_OPT):
    """Cancel a job. Idempotent — cancelling an already terminal job is a no-op."""
    job = _client(api).cancel(job_id)
    if not isinstance(job, dict) or "error" in job:
        err = job.get("error") if isinstance(job, dict) else "no response"
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(1)
    typer.echo(f"cancel requested for {job_id} -> status={job['status']}")


@jobs_app.command("wait")
def wait_job(
    job_id: str,
    timeout: float = typer.Option(300.0, "--timeout", help="Max seconds to wait."),
    api: str = API_OPT,
):
    """Poll until terminal status. Exit 0 on succeeded; non-zero otherwise."""
    res = _client(api).wait(job_id, timeout=timeout)
    if not isinstance(res, dict) or "error" in res:
        err = res.get("error") if isinstance(res, dict) else "no response"
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(2 if err == "timeout" else 1)
    status = res["status"]
    typer.echo(f"{job_id} -> {status} (progress {res['progress']*100:.0f}%)")
    if status == "succeeded":
        raise typer.Exit(0)
    if status == "failed":
        typer.echo(f"error: {res.get('error_message')}", err=True)
        raise typer.Exit(3)
    if status == "cancelled":
        typer.echo("job was cancelled", err=True)
        raise typer.Exit(4)
    raise typer.Exit(2)


@jobs_app.command("artifact")
def artifact_job(
    job_id: str,
    api: str = API_OPT,
    open_file: bool = typer.Option(
        False, "--open", help="Open artifact in default viewer."
    ),
):
    """Fetch and print the result artifact of a SUCCEEDED job only."""
    job = _client(api).get(job_id)
    if not isinstance(job, dict) or "error" in job:
        err = job.get("error") if isinstance(job, dict) else "no response"
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(1)
    if job["status"] != "succeeded":
        typer.echo(
            f"error: job {job_id} is '{job['status']}', not 'succeeded' "
            f"— no artifact available",
            err=True,
        )
        raise typer.Exit(5)
    result = job.get("result")
    if result is None:
        typer.echo("artifact: (empty result payload)")
    else:
        _emit(result)
        if open_file:
            typer.echo(f"(artifact reference: {job['artifact_id']})")
