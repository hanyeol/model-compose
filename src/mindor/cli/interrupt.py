from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any
import click
import json

if TYPE_CHECKING:
    from mindor.core.controller.base import TaskState

def prompt_for_interrupt(state: TaskState) -> Any:
    interrupt = state.interrupt

    if interrupt.message:
        click.echo(interrupt.message, err=True)

    if interrupt.metadata:
        click.echo(json.dumps(interrupt.metadata, indent=2, ensure_ascii=False), err=True)

    click.echo("", err=True)
    click.echo("✋ Action required — press Enter to continue, or type a response (JSON or text):", err=True)
    raw = input()

    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
