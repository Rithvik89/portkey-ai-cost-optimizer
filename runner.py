from portkey_ai import Portkey
import json
import sys,os
from types import SimpleNamespace
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

portkey = Portkey(
    api_key=os.getenv("PORTKEY_API_KEY")
)


## Gather all the inputs from the runner file that is passed while running this .
def load_config(config_path: str):
    """
    Load JSON config and expose keys as attributes.
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return SimpleNamespace(**data)


def main():
    if len(sys.argv) < 2:
        print("Usage: python runner.py <config.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    config = load_config(config_path)

    # Expose commonly used variables
    agent_id = config.agent_id
    team_id = config.team_id
    system_prompt = config.system_prompt
    inputs = config.inputs

    # Example usage
    print(f"Agent ID: {agent_id}")
    print(f"Team ID: {team_id}")
    print(f"Total inputs: {len(inputs)}")

    # ---- Your processing logic starts here ----
    for input_data in inputs:
        # Add metadata to track context
        input = json.dumps(input_data)
        print(f"Processing input: {input}")
        response = portkey.with_options(
            metadata={
                "_user": "Rithvik",
                "environment": "dev",
                "feature": "summarization",
                "team": team_id,
                "agent": agent_id
            }
        ).chat.completions.create(
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(input)}
            ],
            model="@vertex/qwen3@qwen3-32b"
        )



if __name__ == "__main__":
    main()









