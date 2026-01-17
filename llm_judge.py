import json
import argparse
import sys
import os
from pathlib import Path
from typing import Dict, Any, List
from portkey_ai import Portkey
from dotenv import load_dotenv
import yaml

load_dotenv()


class LLMJudge:
    def __init__(
        self,
        agent_name: str,
        model_name: str,
        config_path: str = "config.yaml",
        log_file_path: str = "logs.jsonl"
    ):
        self.agent_name = agent_name
        self.model_name = model_name
        self.log_file_path = log_file_path
        self.config = self._load_config(config_path)

        agents_cfg = self.config.get("agents", {})
        if agent_name not in agents_cfg:
            sys.exit(f"Agent '{agent_name}' not found in config")

        self.judge_cfg = agents_cfg[agent_name]["judge"]
        self.prompt_template = self._load_prompt(
            self.judge_cfg["prompt_file"]
        )

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

    def _extract_outputs_from_logs(self) -> List[str]:
        """
        Extract response message content from JSONL logs.

        Path:
        response -> messages -> [1] -> content
        """
        outputs: List[str] = []

        log_path = Path(self.log_file_path)
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")

        with log_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                try:
                    entry = json.loads(line)
                    content = (
                        entry["response"]["choices"][0]["message"]["content"]
                    )
                    outputs.append(content)
                except Exception as e:
                    print(
                        f"[EvalRunner] Skipping line {line_no}: {e}"
                    )

        print(
            f"[EvalRunner] Extracted {len(outputs)} outputs"
            f"from {self.log_file_path}"
        )

        return outputs

    def _extract_metadata_from_logs(self) -> list[Dict[str, Any]]:
        """
        Extract trace_id,cost,response_time from JSONL logs.

        Path: 

        trace_id, cost, reponseTime at the root it self.

        """

        metadata_list = []

        log_path = Path(self.log_file_path)
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")

        with log_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                try:
                    entry = json.loads(line)
                    metadata = {}   
                    metadata["trace_id"] = entry.get("trace_id", "")
                    metadata["cost"] = entry.get("cost", 0)
                    metadata["response_time"] = entry.get("responseTime", 0)
                    metadata_list.append(metadata)
                except Exception as e:
                    print(
                        f"[EvalRunner] Skipping line {line_no}: {e}"
                    )

        print(
            f"[EvalRunner] Extracted metadata from {self.log_file_path}"
        )

        return metadata_list    

    # ---------- CONFIG ----------

    @staticmethod
    def _load_config(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def _load_prompt(prompt_path: str) -> str:
        path = Path(prompt_path)
        if not path.exists():
            sys.exit(f"Prompt file not found: {prompt_path}")
        return path.read_text(encoding="utf-8")

    # ---------- PROMPT ----------

    @staticmethod
    def _build_judge_prompt(
        template: str,
        input_obj: str,
        output_obj: str,
    ) -> str:
        return (
            template
            .replace(
                "{{INPUT_JSON}}",
                input_obj,
            )
            .replace(
                "{{OUTPUT_JSON}}",
                output_obj,
            )
        )

    # ---------- LLM CALL ----------

    def _call_judge(self, prompt: str) -> dict:
        response = self.portkey.with_options(
            metadata=self.judge_cfg.get("metadata", {})
        ).chat.completions.create(
            model=self.judge_cfg["model"],
            temperature=self.judge_cfg.get("temperature", 0),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI evaluator. "
                        "Return ONLY valid JSON exactly matching "
                        "the required output format."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(
                f"Invalid JSON returned by judge:\n{content}"
            )

    # ---------- Evaluate ----------

    def run(
        self
    ) -> List[Dict[str, Any]]:

        inputs = self._extract_inputs_from_logs()

        outputs = self._extract_outputs_from_logs()

        metadata = self._extract_metadata_from_logs()


        ## Iterate over inputs and we will have the same output and metadata

        evals = []

        print(f"[LLMJUDGE] Starting evaluation for {len(inputs)} items")

        for i in range(len(inputs)):
            input_data = inputs[i]
            output_data = outputs[i]
            metadata_ = metadata[i]


            prompt = self._build_judge_prompt(
                self.prompt_template,
                input_data,
                output_data,
            )

            ## This Judge call is for quality evaluation
            evaluation = self._call_judge(prompt)
            ## trace_id
            ## response_time_ms
            ## cost

            total_score = 0
            for _, value in evaluation.items():
                total_score += value.get("score", 0)

            ## Here you can extract additional metadata if needed
            trace_id = metadata_.get("trace_id", "")
            response_time_ms = metadata_.get("response_time_ms", 0)
            cost = metadata_.get("cost", 0)

            eval = {
                "agent": self.agent_name,
                "model": self.model_name,
                "trace_id": trace_id,
                "response_time_ms": response_time_ms,
                "cost": cost,
                "quality_score": total_score,
            }

            evals.append(eval)

        return evals
