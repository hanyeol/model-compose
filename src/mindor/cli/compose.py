from typing import Optional, List
import importlib.metadata
from pathlib import Path
import click
import asyncio
import json

def _load_compose_config(config_files: List[Path], env_files: List[Path], env_data: List[str]):
    from mindor.dsl.loader import load_compose_config
    from mindor.core.runtime.env import load_env_files, merge_env_data

    env = load_env_files(".", env_files or [])
    env = merge_env_data(env, env_data)

    return load_compose_config(".", config_files, env)

@click.group()
@click.option(
    "--file", "-f", "config_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Compose configuration files."
)
@click.version_option(
    version=importlib.metadata.version("model-compose"),
    message="%(prog)s %(version)s"
)
@click.pass_context
def compose_command(ctx: click.Context, config_files: List[Path]) -> None:
    """model-compose"""
    ctx.ensure_object(dict)
    ctx.obj["config_files"] = list(config_files)

@click.command(name="up")
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode.")
@click.option(
    "--env-file", "env_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a .env file containing environment variables."
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable."
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.pass_context
def up_command(
    ctx: click.Context,
    detach: bool,
    env_files: List[Path],
    env_data: List[str],
    verbose: bool
) -> None:
    from mindor.core.compose import launch_services
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            config = _load_compose_config(config_files, env_files, env_data)
            await launch_services(config, detach, verbose)
        except Exception as e:
            click.echo(f"❌ {e}", err=True)
    asyncio.run(_async_command())

@click.command(name="down")
@click.option(
    "--env-file", "env_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a .env file containing environment variables."
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable."
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.pass_context
def down_command(
    ctx: click.Context,
    env_files: List[Path],
    env_data: List[str],
    verbose: bool
) -> None:
    from mindor.core.compose import terminate_services
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            config = _load_compose_config(config_files, env_files, env_data)
            await terminate_services(config, verbose)
        except Exception as e:
            click.echo(f"❌ {e}", err=True)
    asyncio.run(_async_command())

@click.command(name="start")
@click.option(
    "--env-file", "env_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a .env file containing environment variables."
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable.",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.pass_context
def start_command(
    ctx: click.Context,
    env_files: List[Path],
    env_data: List[str],
    verbose: bool
) -> None:
    from mindor.core.compose import start_services
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            config = _load_compose_config(config_files, env_files, env_data)
            await start_services(config, verbose)
        except Exception as e:
            click.echo(f"❌ {e}", err=True)
    asyncio.run(_async_command())

@click.command(name="stop")
@click.option(
    "--env-file", "env_files", multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a .env file containing environment variables."
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable."
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.pass_context
def stop_command(
    ctx: click.Context,
    env_files: List[Path],
    env_data: List[str],
    verbose: bool
) -> None:
    from mindor.core.compose import stop_services
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            config = _load_compose_config(config_files, env_files, env_data)
            await stop_services(config, verbose)
        except Exception as e:
            click.echo(f"❌ {e}", err=True)
    asyncio.run(_async_command())

@click.command(name="run")
@click.argument("workflow_id", required=False)
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
    help="Path to a .env file containing environment variables."
)
@click.option(
    "--env", "-e", "env_data", multiple=True,
    help="Environment variable in the form KEY=VALUE. Repeatable."
)
@click.option(
    "--output", "-o", "output_path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    required=False,
    help="Path to save the output result as a file."
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.pass_context
def run_command(
    ctx: click.Context,
    workflow_id: Optional[str],
    input_json: Optional[str],
    env_files: List[Path],
    env_data: List[str],
    output_path: Optional[Path],
    verbose: bool
) -> None:
    from mindor.core.compose import run_workflow
    config_files = ctx.obj.get("config_files", [])
    async def _async_command():
        try:
            config = _load_compose_config(config_files, env_files, env_data)
            input = json.loads(input_json) if input_json else {}
            state = await run_workflow(config, workflow_id or "__default__", input, output_path, verbose)
            if isinstance(state.output, (dict, list)) or state.error:
                click.echo(json.dumps(
                    state.output or state.error,
                    indent=2,
                    ensure_ascii=False
                ))
            else:
                if state.output is not None:
                    click.echo(state.output)
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

if __name__ == "__main__":
    compose_command()
