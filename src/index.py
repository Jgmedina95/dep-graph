import json
import os
from pathlib import Path
import argparse
from composio import Composio


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def main(toolkit: str) -> None:
    load_env_file(ENV_PATH)

    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        raise RuntimeError(
            "COMPOSIO_API_KEY is not set. Add it to .env or export it before running this script."
        )

    composio = Composio(api_key=api_key)

    # Raw tools are direct tools from Composio without provider-specific wrappers.
    tools = composio.tools.get_raw_composio_tools(
        toolkits=[toolkit],
        limit=1000,
    )
    OUTPUT_PATH = PROJECT_ROOT / f"{toolkit}_tools.json"

    serialized_tools = [tool.model_dump(mode="json") for tool in tools]

    print(serialized_tools)
    OUTPUT_PATH.write_text(json.dumps(serialized_tools, indent=2), encoding="utf-8")
    print(f"Tools written to {OUTPUT_PATH.name}")


if __name__ == "__main__":
    #let it be able to add the toolkit as an argument in the future if needed, use google as default for now
    parser = argparse.ArgumentParser(description="Fetch tools from Composio and write to JSON file")
    parser.add_argument("--toolkit", type=str, default="googlesuper", help="Toolkit name to fetch tools for")
    args = parser.parse_args()

    main(args.toolkit)