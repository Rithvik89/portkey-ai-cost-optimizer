from ast import List
import time
import yaml
import os
from eval_metric_store import EvalMetricStore
from llm_judge import LLMJudge
from log_extractor import LogExtractor
import shutil
import argparse

from runner_eval import EvalRunner



class Scheduler:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.interval = self.config["scheduler"]["interval_seconds"]
        self.workspace_id = self.config["workspace"]["id"]
        self.team_id = self.config["team"]["id"]
        self.output_dir = self.config["export"]["output_dir"]

        # ---- Clean start: delete output directory if exists ----
        if os.path.exists(self.output_dir):
            print(f"[Scheduler] Removing existing directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)

        # ---- Recreate output directory ----
        os.makedirs(self.output_dir, exist_ok=True)

        self.log_extractor = LogExtractor(
            workspace_id=self.workspace_id,
            poll_interval=5,  ## This is the time between the download status checks.
        )

        self.EvalMetricStore = EvalMetricStore(
            db_path="metrics.db"
        )

        self.EvalMetricStore.drop_evaluations_table()

    @staticmethod
    def _load_config(path: str) -> dict:
        with open(path, "r") as f:
            return yaml.safe_load(f)

    @staticmethod
    def get_team_agents(yaml_file: str, target_team_id: str) -> list[str]:
        """
        Extract agent names for a given team from YAML config.
        Supports single-team and multi-team structures.
        """
        with open(yaml_file, "r") as file:
            data = yaml.safe_load(file)

        if "team" in data and data["team"]["id"] == target_team_id:
            return [agent["name"] for agent in data["team"]["agents"]]

        if "teams" in data:
            for team in data["teams"]:
                if team["id"] == target_team_id:
                    return [agent["name"] for agent in team["agents"]]

        raise ValueError(f"Team '{target_team_id}' not found in {yaml_file}")

    def run_once(self):
        """
        Execute a single scheduled run.
        """
        time_from = self.config["export"]["time_window"]["from"]
        time_to = self.config["export"]["time_window"]["to"]

        agents = self.get_team_agents(
            yaml_file="config.yaml",
            target_team_id=self.team_id,
        ) # agent2 , agent3

        for agent in agents:
            os.mkdir(os.path.join(self.output_dir, agent))
            output_file = os.path.join(
                self.output_dir, agent, f"baseline.jsonl"
            )

            print(
                f"[Scheduler] Exporting logs "
                f"team={self.team_id} agent={agent}"
            )

            self.log_extractor.export_logs_for_agent(
                team_id=self.team_id,
                agent_id=agent,
                time_min=time_from,
                time_max=time_to,
                output_file=output_file,
            )


            ### LLM Judge for baseline of this specific agent
            eval_result = LLMJudge(
                agent_name=agent,
                model_name="baseline",
                config_path="config.yaml",
                log_file_path=output_file
            ).run()

            results = eval_result

            ## Run on differnt models mentioned in config.yaml and
            ## TODO: here we can achieve parallelism.
            EvalRunner(
                config_path="config.yaml",
                team_id=self.team_id,
                agent_id=agent,
                log_file_path=output_file
            ).run()

            ## export_logs for all the models on this agent.
            for model in self.config["models"]:
                output_file = os.path.join(
                    self.output_dir, agent, f"{model.split('/')[-1]}_logs.jsonl"
                )

                self.log_extractor.export_logs_for_agent(
                    team_id=self.team_id,
                    agent_id=agent,
                    time_min=time_from,
                    time_max=time_to,
                    output_file=output_file,
                )
            
            ##TODO: LLM Judge task for eval models
            ## Upsert Evaluations : For Baseline file write model as "baseline".
                result = LLMJudge(
                    agent_name=agent,
                    model_name=model,
                    log_file_path=output_file,
                    config_path="config.yaml",
                ).run()

                results = results + result
            

            for res in results:
                self.EvalMetricStore.upsert_evaluation(
                    trace_id=res["trace_id"],
                    model=res["model"],
                    agent=res["agent"],
                    quality_score=res["quality_score"],
                    response_time_ms=res["response_time_ms"],
                    cost=res["cost"]
                )

        ## Reporting the data.

        result = self.EvalMetricStore.aggregate_model_metrics()
        print(f"[Scheduler] Aggregated metrics: {result}")


    def run_forever(self):
        """
        Run scheduler at a fixed interval.
        """
        print(
            f"[Scheduler] Started | interval={self.interval}s"
        )

        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f"[Scheduler][ERROR] {e}")

            print(
                f"[Scheduler] Sleeping for {self.interval}s\n"
            )
            time.sleep(self.interval)


# ---------- ENTRY POINT ----------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Portkey Log Extraction Scheduler"
    )
    parser.add_argument(
        "--config",
        default=os.getenv("SCHEDULER_CONFIG", "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run scheduler once and exit",
    )

    args = parser.parse_args()

    scheduler = Scheduler(args.config)

    if args.once:
        print("[Scheduler] Running once")
        scheduler.run_once()
    else:
        scheduler.run_forever()
