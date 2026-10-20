from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Dict
import click
import json

if TYPE_CHECKING:
    from mindor.core.controller.base import TaskState

def prompt_for_interrupts(state: TaskState) -> Dict[str, Any]:
    """Prompt the user for each pending interrupt point and return a
    `{point.id: answer}` dict suitable for `resume_workflow`.
    """
    points = state.interrupt or []
    answers: Dict[str, Any] = {}

    for index, point in enumerate(points, start=1):
        if len(points) > 1:
            click.echo(f"[{index}/{len(points)}] interrupt — job '{point.job_id}' ({point.phase})", err=True)

        if point.message:
            click.echo(point.message, err=True)

        if point.metadata:
            click.echo(json.dumps(point.metadata, indent=2, ensure_ascii=False), err=True)

        click.echo("", err=True)
        click.echo("✋ Action required — press Enter to continue, or type an answer (JSON or text):", err=True)
        raw = input()

        if not raw:
            answers[point.id] = None
            continue

        try:
            answers[point.id] = json.loads(raw)
        except json.JSONDecodeError:
            answers[point.id] = raw

    return answers
