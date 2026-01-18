from portkey_ai import Portkey
import json
import os
import yaml
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, List

load_dotenv()


class EvalRunner:
    def __init__(
        self,
        config_path: str,
        team_id: str,
        agent_id: str,
        log_file_path: str,
    ):
        self.config = self._load_config(config_path)

        self.team_id = team_id
        self.agent_id = agent_id
        self.log_file_path = log_file_path

        self.models: List[str] = self.config["models"]

        ## This varies per agent.
        self.system_prompt: str = self.config["agents"][self.agent_id]["system_prompt_for_runners"]

        # Placeholder for now (will be wired later)
        ## Pick this from the logs. The request content.
        ## This data is in file of jsonl and we need to extract the fields.
        self.inputs: List[str] = self._extract_inputs_from_logs()

        self.portkey = Portkey(
            api_key=os.getenv("PORTKEY_API_KEY")
        )


# ------------------------------ LOG PARSING --------------------

    def _extract_inputs_from_logs(self) -> List[str]:
        """
        Extract request message content from JSONL logs.

        Path:
        request -> messages -> [1] -> content
        """
        inputs: List[str] = []

        log_path = Path(self.log_file_path)
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")

        with log_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                try:
                    entry = json.loads(line)
                    content = (
                        entry["request"]["messages"][1]["content"]
                    )
                    inputs.append(content)
                except Exception as e:
                    print(
                        f"[EvalRunner] Skipping line {line_no}: {e}"
                    )

        print(
            f"[EvalRunner] Extracted {len(inputs)} inputs"
            f"from {self.log_file_path}"
        )

        return inputs


    # ---------- CONFIG ----------

    @staticmethod
    def _load_config(path: str) -> Dict[str, Any]:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"config not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # ---------- CORE LOGIC ----------

    def run(self) -> None:
        """
        Run evals across all models.
        """
        print(
            f"[EvalRunner] team={self.team_id} "
            f"agent={self.agent_id} "
            f"models={len(self.models)}"
        )

        for model in self.models:
            self._run_for_model(model)
        


    def _run_for_model(self, model: str) -> None:
        print(f"[EvalRunner] Running model={model}")

        for idx, input_data in enumerate(self.inputs, start=1):
            self._process_input(model, idx, input_data)

    def _process_input(
        self,
        model: str,
        index: int,
        input_data: Dict[str, Any],
    ) -> None:
        payload = json.dumps(input_data)

        ##TODO: Fix this hack: As these are the Eval Logs, we don't want to mix this with team's agentic logs. 
        ## So for now proceeding with team and agent as eval.

        response = self.portkey.with_options(
            metadata={
                "_user": "Rithvik",
                "environment": "dev",
                "feature": "eval",
                "team": "portkey",
                "agent": self.agent_id,
                "model": model,
            }
        ).chat.completions.create(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": payload},
            ],
            model=model,
        )

        self._handle_response(model, index, response)

    # ---------- RESPONSE HANDLING ----------

    def _handle_response(self, model: str, index: int, response: Any) -> None:
        print(
            f"[EvalRunner] Completed model={model} input=#{index}"
        )
