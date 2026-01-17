import os
import time
import yaml
import requests
from typing import List, Optional
from dotenv import load_dotenv
from portkey_ai import Portkey

load_dotenv()


class LogExtractor:
    def __init__(
        self,
        api_key: Optional[str] = None,
        workspace_id: str = "",
        poll_interval: int = 5,
    ):
        self.portkey = Portkey(
            api_key=api_key or os.getenv("PORTKEY_API_KEY")
        )
        self.workspace_id = workspace_id
        self.poll_interval = poll_interval

    # ---------- EXPORT WORKFLOW ----------

    def create_export(
        self,
        team_id: str,
        agent_id: str,
        time_min: str,
        time_max: str,
        description: str = "Log Export",
    ) -> str:
        """
        Create a log export and return export_id.
        """
        res = self.portkey.logs.exports.create(
            filters={
                "time_of_generation_min": time_min,
                "time_of_generation_max": time_max,
                "metadata": {
                    "team": team_id,
                    "agent": agent_id,
                },
            },
            workspace_id=self.workspace_id,
            description=description,
            requested_data=[
                "id",
                "trace_id",
                "created_at",
                "request",
                "response",
                "is_success",
                "ai_org",
                "ai_model",
                "req_units",
                "res_units",
                "total_units",
                "request_url",
                "cost",
                "cost_currency",
                "response_time",
                "response_status_code",
                "mode",
                "config",
                "prompt_slug",
                "metadata",
            ],
        )
        return res.id

    def start_export(self, export_id: str) -> None:
        """
        Start export execution.
        """
        self.portkey.logs.exports.start(export_id=export_id)

    def wait_for_export(self, export_id: str) -> None:
        """
        Poll until export completes successfully.
        """
        while True:
            res = self.portkey.logs.exports.list(
                workspace_id=self.workspace_id
            )
            exports = [x for x in res["data"] if x["id"] == export_id]

            if not exports:
                raise RuntimeError(f"Export ID {export_id} not found")

            status = exports[0]["status"]

            if status == "success":
                return

            if status == "failed":
                raise RuntimeError(f"Export {export_id} failed")

            time.sleep(self.poll_interval)

    def get_download_url(self, export_id: str) -> str:
        """
        Fetch signed download URL.
        """
        res = self.portkey.logs.exports.download(export_id=export_id)
        return res.signed_url

    # ---------- FILE HANDLING ----------

    @staticmethod
    def download_file(url: str, output_path: str) -> None:
        """
        Download exported logs to file.
        """
        response = requests.get(url)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)

    # ---------- HIGH-LEVEL API ----------

    def export_logs_for_agent(
        self,
        team_id: str,
        agent_id: str,
        time_min: str,
        time_max: str,
        output_file: str,
    ) -> None:
        """
        End-to-end export for a single agent.
        """
        export_id = self.create_export(
            team_id=team_id,
            agent_id=agent_id,
            time_min=time_min,
            time_max=time_max,
        )

        self.start_export(export_id)
        self.wait_for_export(export_id)

        url = self.get_download_url(export_id)
        self.download_file(url, output_file)