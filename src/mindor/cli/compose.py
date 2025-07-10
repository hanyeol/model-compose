import click
import json
from pathlib import Path
import asyncio

from mindor.dsl.loader import load_compose_config
from mindor.core.runtime.env import load_env_files
from mindor.core.compose import *

@click.group()
@click.option(
    "--file", "-f", "config_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Compose configuration files",
)
@click.pass_context
def compose_command(ctx: click.Context, config_files: List[Path]) -> None:
    """model-compose (from Mindor)"""
    ctx.ensure_object(dict)
    ctx.obj["config_files"] = list(config_files)

@click.command(name="up")
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode.")
@click.option(
    "--env-file", "env_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a .env file containing environment variables.",
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable.",
)
@click.pass_context
def up_command(
    ctx: click.Context, 
    detach: bool,
    env_files: List[Path],
    env_data: List[str]
) -> None:
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            env = load_env_files(".", env_files or [])
            config = load_compose_config(".", config_files, env)
            await launch_services(config, detach)
        except Exception as e:
            click.echo(f"❌ {e}", err=True)
    asyncio.run(_async_command())

@click.command(name="down")
@click.option(
    "--env-file", "env_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a .env file containing environment variables.",
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable.",
)
@click.pass_context
def down_command(
    ctx: click.Context,
    env_files: List[Path],
    env_data: List[str],
) -> None:
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            env = load_env_files(".", env_files or [])
            config = load_compose_config(".", config_files, env)
            await shutdown_services(config)
        except Exception as e:
            click.echo(f"❌ {e}", err=True)
    asyncio.run(_async_command())

@click.command(name="start")
@click.option(
    "--env-file", "env_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a .env file containing environment variables.",
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable.",
)
@click.pass_context
def start_command(
    ctx: click.Context,
    env_files: List[Path],
    env_data: List[str],
) -> None:
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            env = load_env_files(".", env_files or [])
            config = load_compose_config(".", config_files, env)
            await start_services(config)
        except Exception as e:
            click.echo(f"❌ {e}", err=True)
    asyncio.run(_async_command())

@click.command(name="stop")
@click.option(
    "--env-file", "env_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a .env file containing environment variables.",
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable.",
)
@click.pass_context
def stop_command(
    ctx: click.Context,
    env_files: List[Path],
    env_data: List[str],
) -> None:
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            env = load_env_files(".", env_files or [])
            config = load_compose_config(".", config_files, env)
            await stop_services(config)
        except Exception as e:
            click.echo(f"❌ {e}", err=True)
    asyncio.run(_async_command())

@click.command(name="run")
@click.argument("workflow", required=False)
@click.option(
    "--input", "-i", "input_json",
    type=str,
    required=False,
    help="JSON input string for the workflow",
)
@click.option(
    "--env-file", "env_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a .env file containing environment variables.",
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable.",
)
@click.pass_context
def run_command(
    ctx: click.Context,
    workflow: Optional[str],
    input_json: Optional[str],
    env_files: List[Path],
    env_data: List[str],
) -> None:
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            env = load_env_files(".", env_files or [])
            config = load_compose_config(".", config_files, env)
            input = json.loads(input_json) if input_json else {}
            state = await run_workflow(config, workflow, input)
            click.echo(json.dumps(
                state.error if state.error else state.output, 
                indent=2, 
                ensure_ascii=False
            ))
        except json.JSONDecodeError:
            click.echo("❌ Invalid JSON provided for --input", err=True)
        except Exception as e:
            click.echo(f"❌ {e}", err=True)
    asyncio.run(_async_command())

compose_command.add_command(up_command)
compose_command.add_command(down_command)
compose_command.add_command(start_command)
compose_command.add_command(stop_command)
compose_command.add_command(run_command)
