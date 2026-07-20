"""`oik` — the OIKONOMIA command-line entry point."""

from __future__ import annotations

import typer

from oikonomia import __version__
from oikonomia.cli.corpus_cmd import corpus_app
from oikonomia.cli.ingest_cmd import ingest_app
from oikonomia.cli.lexicon_cmd import lexicon_app

app = typer.Typer(
    help="OIKONOMIA — information extraction from ancient Greek documentary papyri.",
    no_args_is_help=True,
)
app.add_typer(ingest_app, name="ingest")
app.add_typer(corpus_app, name="corpus")
app.add_typer(lexicon_app, name="lexicon")


@app.command("version")
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
