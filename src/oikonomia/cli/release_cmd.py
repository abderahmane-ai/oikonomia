"""`oik release` — publish the trained models to the Hugging Face Hub.

Runs on the laptop, against the weights already pulled off the Modal volume. Modal
is for the GPU work; an upload of local files needs no container, and routing an
auth token through one to push a folder that is already on this disk buys nothing.

Authentication is deliberately *not* handled here: the token is read by
``huggingface_hub`` from your stored login (``hf auth login``) or the ``HF_TOKEN``
environment variable. It is never accepted as a command-line argument — argv lands
in shell history and is visible to every process on the machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from oikonomia.models.release import (
    MODELS,
    NotReadyError,
    ReleaseSpec,
    check_ready,
    stage_card,
)

release_app = typer.Typer(help="Publish the trained models (deliverable #1).", no_args_is_help=True)

REPO = Path(__file__).resolve().parents[3]


def _spec(model: str) -> ReleaseSpec:
    if model not in MODELS:
        typer.secho(f"unknown model {model!r} — expected one of {', '.join(sorted(MODELS))}", fg="red")
        raise typer.Exit(1)
    return MODELS[model]


@release_app.command("check")
def check(
    model: Annotated[str, typer.Argument(help="grammateus | homologia")],
) -> None:
    """Pre-flight a release without uploading: licence, card, and checkpoint files."""
    spec = _spec(model)
    try:
        files = check_ready(REPO, spec)
    except NotReadyError as exc:
        typer.secho(f"✗ {spec.name} is not ready:\n  {exc}", fg="red")
        raise typer.Exit(1) from exc

    total = sum(f.stat().st_size for f in files)
    typer.echo(f"✓ {spec.name} — ready to publish as {spec.repo_id}")
    typer.echo(f"  licence lineage verified · card {spec.card}")
    typer.echo(f"  {len(files)} files, {total / 1e6:.0f} MB from {spec.local_dir}:")
    for f in files:
        typer.echo(f"    {f.name:28} {f.stat().st_size / 1e6:8.1f} MB")


@release_app.command("push")
def push(
    model: Annotated[str, typer.Argument(help="grammateus | homologia")],
    repo_id: Annotated[str | None, typer.Option("--repo-id", help="Override the default Hub repo id.")] = None,
    private: Annotated[bool, typer.Option("--private/--public", help="Publish private (default) or public.")] = True,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Check and stage the card, but upload nothing.")] = False,
) -> None:
    """Upload a model to the Hub — licence firewall first, private by default.

    Needs an HF **write** token from your stored login (``hf auth login``) or
    ``HF_TOKEN``. Starts private so the repo can be reviewed before it is public;
    pass ``--public`` only when you mean it.
    """
    spec = _spec(model)
    target = repo_id or spec.repo_id
    try:
        files = check_ready(REPO, spec)
    except NotReadyError as exc:
        typer.secho(f"✗ {spec.name} is not ready:\n  {exc}", fg="red")
        raise typer.Exit(1) from exc

    stage_card(REPO, spec)  # the card becomes the repo's README.md
    for extra in spec.extras:  # optional companions (e.g. the BIO label schema)
        src = REPO / extra
        if src.is_file():
            (REPO / spec.local_dir / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    size = sum(f.stat().st_size for f in files) / 1e6
    typer.echo(f"{spec.name} → https://huggingface.co/{target} ({'private' if private else 'PUBLIC'}, ~{size:.0f} MB)")
    if dry_run:
        typer.secho("  --dry-run: card staged, nothing uploaded.", fg="yellow")
        return

    from huggingface_hub import HfApi  # optional extra: pip install -e ".[release]"

    api = HfApi()  # token from the stored login / HF_TOKEN — never from argv
    api.create_repo(repo_id=target, repo_type="model", private=private, exist_ok=True)
    api.upload_folder(repo_id=target, folder_path=str(REPO / spec.local_dir), repo_type="model")
    typer.secho(f"✓ pushed → https://huggingface.co/{target}", fg="green")
    if private:
        typer.echo("  (private — flip it public in the HF repo settings when you are ready)")
