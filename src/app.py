import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from src.config import env_wizard
from src.graph.states import RunState
from src.graph.graph import compile_graph
from src.kit.cost_meter import CostSession

LOG_PATH = Path('logs/release-copilot.log')
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=5)
logging.getLogger().addHandler(handler)

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--wizard', action='store_true')
    parser.add_argument('--fix-version')
    parser.add_argument('--project')
    parser.add_argument('--repo')
    parser.add_argument('--branch')
    parser.add_argument('--since')
    parser.add_argument('--enable-confluence', action='store_true')
    parser.add_argument('--enable-llamaindex', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.wizard:
        env_wizard.run_wizard()
        return

    state = RunState(
        fix_version=args.fix_version,
        project=args.project,
        repo=args.repo,
        branch=args.branch,
        since=args.since,
    )

    graph = compile_graph()

    with CostSession() as cost:
        with Progress() as progress:
            task = progress.add_task('Running', total=1)
            graph(state)
            progress.update(task, advance=1)

    console.print('Artifacts:')
    for name, path in state.artifacts.items():
        console.print(f" - {name}: {path}")

    console.print('Run complete.')


if __name__ == '__main__':
    main()
