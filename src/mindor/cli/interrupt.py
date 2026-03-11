from __future__ import annotations
from typing import TYPE_CHECKING, Any
import click
import json

if TYPE_CHECKING:
    from mindor.core.controller.base import TaskState

def prompt_for_interrupt(state: TaskState) -> Any:
    interrupt = state.interrupt

    click.echo("", err=True)
    click.echo(f"--- Interrupted (job: {interrupt.job_id}, phase: {interrupt.phase}) ---", err=True)

    if interrupt.message:
        click.echo(f"\n{interrupt.message}", err=True)

    if interrupt.metadata:
        click.echo(json.dumps(interrupt.metadata, indent=2, ensure_ascii=False), err=True)

    click.echo("", err=True)
    raw = click.prompt("Enter response (JSON or text, empty to continue)", default="", show_default=False)

    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
