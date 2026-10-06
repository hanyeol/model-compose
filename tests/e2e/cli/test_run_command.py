"""CLI `model-compose run` end-to-end:

- streaming output flows to stdout (default) or file (--output).
- scalar/dict output: stdout vs --output.
- interrupt handling with --auto-resume and without a TTY.
- streaming + --auto-resume path round-trips through resume_workflow.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from mindor.cli.compose import compose_command
from mindor.core.component.component import ComponentInstances


@pytest.fixture(autouse=True)
def reset_component_instances():
    ComponentInstances.clear()
    yield
    ComponentInstances.clear()


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(dedent(content).lstrip())
    return path


def _streaming_compose(tmp_path: Path) -> Path:
    return _write(tmp_path, "model-compose.yml", """
        controller:
          runtime: native
          adapters: []
          max_concurrent_count: 0
        components:
          - id: lines
            type: shell
            action:
              command: [ sh, -c, "for i in 1 2 3; do echo line $i; done" ]
              streaming: true
        workflows:
          - id: wf
            jobs:
              - id: j
                component: lines
            output: ${jobs.j.output}
    """)


def _scalar_compose(tmp_path: Path) -> Path:
    return _write(tmp_path, "model-compose.yml", """
        controller:
          runtime: native
          adapters: []
          max_concurrent_count: 0
        components:
          - id: echo
            type: shell
            action:
              command: [ sh, -c, "echo hello" ]
              output: ${result.stdout}
        workflows:
          - id: wf
            jobs:
              - id: j
                component: echo
            output: ${jobs.j.output}
    """)


def _dict_compose(tmp_path: Path) -> Path:
    return _write(tmp_path, "model-compose.yml", """
        controller:
          runtime: native
          adapters: []
          max_concurrent_count: 0
        components:
          - id: echo
            type: shell
            action:
              command: [ sh, -c, "echo hello" ]
              output:
                greeting: ${result.stdout}
                code: 1
        workflows:
          - id: wf
            jobs:
              - id: j
                component: echo
            output: ${jobs.j.output}
    """)


def _interrupt_compose(tmp_path: Path) -> Path:
    return _write(tmp_path, "model-compose.yml", """
        controller:
          runtime: native
          adapters: []
          max_concurrent_count: 0
        components:
          - id: echo
            type: shell
            action:
              command: [ sh, -c, "echo hello" ]
              output: ${result.stdout}
        workflows:
          - id: wf
            jobs:
              - id: j
                component: echo
                interrupt:
                  before:
                    message: waiting
            output: ${jobs.j.output}
    """)


def _run_cli(args: list[str], cwd: Path) -> "click.testing.Result":
    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(cwd)
        return runner.invoke(compose_command, args, catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


class TestStreamingOutput:
    def test_stream_to_stdout(self, tmp_path: Path):
        config = _streaming_compose(tmp_path)
        result = _run_cli(["-f", str(config), "run"], cwd=tmp_path)

        assert result.exit_code == 0, result.output
        assert "line 1" in result.output
        assert "line 2" in result.output
        assert "line 3" in result.output

    def test_stream_to_file(self, tmp_path: Path):
        config = _streaming_compose(tmp_path)
        out = tmp_path / "lines.txt"
        result = _run_cli(
            ["-f", str(config), "run", "-o", str(out)],
            cwd=tmp_path,
        )

        assert result.exit_code == 0, result.output
        body = out.read_bytes()
        assert b"line 1" in body
        assert b"line 2" in body
        assert b"line 3" in body
        # stdout should NOT contain the chunks when --output is set.
        assert "line 1" not in result.output


class TestScalarOutput:
    def test_scalar_to_stdout(self, tmp_path: Path):
        config = _scalar_compose(tmp_path)
        result = _run_cli(["-f", str(config), "run"], cwd=tmp_path)

        assert result.exit_code == 0, result.output
        assert "hello" in result.output

    def test_scalar_to_file(self, tmp_path: Path):
        config = _scalar_compose(tmp_path)
        out = tmp_path / "out.txt"
        result = _run_cli(
            ["-f", str(config), "run", "-o", str(out)],
            cwd=tmp_path,
        )

        assert result.exit_code == 0, result.output
        assert "hello" in out.read_text()


class TestDictOutput:
    def test_dict_to_stdout_as_json(self, tmp_path: Path):
        config = _dict_compose(tmp_path)
        result = _run_cli(["-f", str(config), "run"], cwd=tmp_path)

        assert result.exit_code == 0, result.output
        # Output must be JSON-parseable.
        parsed = json.loads(result.output)
        assert "greeting" in parsed
        assert parsed["code"] == 1

    def test_dict_to_file_as_json(self, tmp_path: Path):
        config = _dict_compose(tmp_path)
        out = tmp_path / "out.json"
        result = _run_cli(
            ["-f", str(config), "run", "-o", str(out)],
            cwd=tmp_path,
        )

        assert result.exit_code == 0, result.output
        parsed = json.loads(out.read_text())
        assert "greeting" in parsed


class TestAutoResume:
    def test_auto_resume_scalar(self, tmp_path: Path):
        """Interrupt before the only job + --auto-resume should resume and emit output."""
        config = _interrupt_compose(tmp_path)
        result = _run_cli(
            ["-f", str(config), "run", "--auto-resume"],
            cwd=tmp_path,
        )

        assert result.exit_code == 0, result.output
        assert "hello" in result.output

    def test_interrupt_without_tty_errors(self, tmp_path: Path):
        """Without --auto-resume and without a TTY, interrupts must error out."""
        config = _interrupt_compose(tmp_path)
        # CliRunner's stdin is not a TTY by default.
        result = _run_cli(["-f", str(config), "run"], cwd=tmp_path)

        assert result.exit_code == 1
        assert "no TTY" in result.output or "no TTY" in (result.stderr if hasattr(result, "stderr") else "")

    def test_auto_resume_saves_to_file(self, tmp_path: Path):
        config = _interrupt_compose(tmp_path)
        out = tmp_path / "resumed.txt"
        result = _run_cli(
            ["-f", str(config), "run", "--auto-resume", "-o", str(out)],
            cwd=tmp_path,
        )

        assert result.exit_code == 0, result.output
        assert "hello" in out.read_text()
