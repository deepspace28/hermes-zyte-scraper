"""
Production-grade operational layer for managing spiders on Scrapy Cloud.

Uses official Scrapy Cloud HTTP API:
- run.json — schedule one-off jobs
- jobs/list.json — list jobs
- storage.zyte.com/items/{job_id} — fetch scraped items
"""

import json
import os
import random
import subprocess
import time
from pathlib import Path
from typing import Any

import requests
import requests.auth


class ScrapyCloudError(Exception):
    """Base exception for Scrapy Cloud operational errors."""


class ScrapyCloudClient:
    """Client for Scrapy Cloud deploy, schedule, list jobs, and fetch results."""

    API_BASE = "https://app.zyte.com/api"
    STORAGE_BASE = "https://storage.zyte.com"

    def __init__(self, api_key: str | None = None, timeout: int = 60, dry_run: bool = False):
        self.api_key = api_key or os.getenv("SCRAPY_CLOUD_API_KEY")
        if not self.api_key:
            raise ScrapyCloudError(
                "SCRAPY_CLOUD_API_KEY is not set. "
                "Please set it in ~/.hermes/.env or pass it explicitly."
            )
        self.timeout = timeout
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.auth = requests.auth.HTTPBasicAuth(self.api_key, "")

    def _request(
        self,
        method: str,
        base: str,
        endpoint: str,
        max_retries: int = 3,
        **kwargs,
    ) -> requests.Response:
        url = f"{base}{endpoint}"

        if self.dry_run:
            print(f"[DRY-RUN] {method} {url} kwargs={kwargs}")
            return type(
                "DryRunResponse",
                (object,),
                {
                    "status_code": 200,
                    "text": json.dumps(
                        {
                            "status": "ok",
                            "jobid": "867424/1/99",
                            "jobs": [],
                            "count": 0,
                        }
                    ),
                    "json": lambda self=None, **kw: json.loads(
                        '{"status":"ok","jobid":"867424/1/99","jobs":[],"count":0}'
                    ),
                },
            )()

        for attempt in range(max_retries):
            try:
                resp = self.session.request(
                    method,
                    url,
                    timeout=kwargs.pop("timeout", self.timeout),
                    **kwargs,
                )
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        wait_time = (2**attempt) + random.random()
                        print(
                            f"[ScrapyCloud] {resp.status_code} — retrying in {wait_time:.2f}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                if resp.status_code >= 400:
                    raise ScrapyCloudError(
                        f"Scrapy Cloud API error {resp.status_code}: {resp.text}"
                    )
                return resp
            except requests.RequestException as exc:
                if attempt == max_retries - 1:
                    raise ScrapyCloudError(
                        f"Network error after {max_retries} attempts: {exc}"
                    ) from exc
                wait_time = (2**attempt) + random.random()
                print(f"[ScrapyCloud] Network error — retrying in {wait_time:.2f}s: {exc}")
                time.sleep(wait_time)

        raise ScrapyCloudError("Request failed after retries")

    def resolve_project(self, name_or_id: str) -> str:
        """Return numeric project ID."""
        if name_or_id.isdigit():
            return name_or_id

        env_default = os.getenv("SCRAPY_CLOUD_PROJECT_ID", "")
        if env_default.isdigit():
            return env_default

        raise ScrapyCloudError(
            f"Project '{name_or_id}' is not numeric. Set SCRAPY_CLOUD_PROJECT_ID "
            f"in ~/.hermes/.env or pass the numeric project ID (e.g. 867424)."
        )

    def deploy(self, project_path: str, project_name: str | None = None) -> dict[str, Any]:
        """Deploy a local Scrapy project to Scrapy Cloud via shub."""
        path = Path(project_path).expanduser().resolve()
        if not path.exists():
            raise ScrapyCloudError(f"Project path does not exist: {path}")

        name = project_name or path.name
        shub_yml = path / "scrapinghub.yml"
        if not shub_yml.exists():
            project_id = os.getenv("SCRAPY_CLOUD_PROJECT_ID", name)
            shub_yml.write_text(
                f"project: {project_id}\n\nrequirements:\n  file: requirements.txt\n\n"
                f"stack: scrapy:2.11\n"
            )

        if self.dry_run:
            print(f"[DRY-RUN] shub deploy in {path}")
            return {
                "success": True,
                "project_name": name,
                "stdout": "[DRY-RUN] Deploy skipped",
            }

        deploy_env = os.environ.copy()
        deploy_env["SHUB_API_KEY"] = self.api_key
        deploy_env["SCRAPY_CLOUD_API_KEY"] = self.api_key

        result = subprocess.run(
            ["shub", "deploy"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=180,
            env=deploy_env,
        )
        if result.returncode != 0:
            raise ScrapyCloudError(
                f"shub deploy failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )

        return {
            "success": True,
            "project_name": name,
            "stdout": result.stdout.strip(),
        }

    def schedule(
        self,
        project_id: str,
        spider: str,
        schedule: str | None = None,
        units: int = 1,
        tags: list | None = None,
        job_settings: dict | None = None,
        priority: int = 2,
    ) -> dict[str, Any]:
        """Schedule a spider via run.json (one-time) or schedules API (cron)."""
        project_id = self.resolve_project(project_id)

        if schedule:
            payload = {
                "project": project_id,
                "spider": spider,
                "cron": schedule,
                "units": units,
                "priority": priority,
            }
            if job_settings:
                payload["job_settings"] = json.dumps(job_settings)
            if tags:
                payload["add_tag"] = tags[0] if isinstance(tags, list) else tags
            resp = self._request(
                "POST", self.API_BASE, "/schedules.json", data=payload
            )
            return resp.json()

        data: dict[str, Any] = {
            "project": project_id,
            "spider": spider,
            "units": units,
            "priority": priority,
        }
        if job_settings:
            data["job_settings"] = json.dumps(job_settings)
        if tags:
            tag_list = tags if isinstance(tags, list) else [tags]
            if tag_list:
                data["add_tag"] = tag_list[0]

        resp = self._request("POST", self.API_BASE, "/run.json", data=data)
        result = resp.json()
        if result.get("status") != "ok":
            raise ScrapyCloudError(f"Schedule failed: {result}")
        return result

    def list_jobs(
        self,
        project_id: str,
        spider: str | None = None,
        state: str | None = None,
        limit: int = 20,
        tags: list | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List jobs via jobs/list.json."""
        project_id = self.resolve_project(project_id)
        params: dict[str, Any] = {"project": project_id, "count": limit}
        if offset > 0:
            params["offset"] = offset
        if spider:
            params["spider"] = spider
        if state and state != "all":
            params["state"] = state
        if tags:
            params["has_tag"] = ",".join(tags) if isinstance(tags, list) else tags

        resp = self._request("GET", self.API_BASE, "/jobs/list.json", params=params)
        data = resp.json()
        return data.get("jobs", [])

    def get_results(
        self,
        job_id: str,
        fmt: str = "jsonlines",
        limit: int = 0,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch items from storage.zyte.com."""
        api_fmt = "jl" if fmt in ("jsonlines", "jl") else fmt
        params: dict[str, Any] = {"format": api_fmt}
        if limit > 0:
            params["count"] = limit
        if offset > 0:
            params["start"] = offset

        resp = self._request("GET", self.STORAGE_BASE, f"/items/{job_id}", params=params)

        if api_fmt == "jl":
            lines = [line for line in resp.text.strip().split("\n") if line.strip()]
            items = []
            for line in lines:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return items

        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        if isinstance(items, list) and limit > 0:
            return items[:limit]
        return items if isinstance(items, list) else []


def zyte_deploy(args: dict, **kwargs) -> str:
    try:
        client = ScrapyCloudClient(dry_run=args.get("dry_run", False))
        result = client.deploy(
            project_path=args["project_path"],
            project_name=args.get("project_name"),
        )
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def zyte_schedule(args: dict, **kwargs) -> str:
    try:
        client = ScrapyCloudClient(dry_run=args.get("dry_run", False))
        result = client.schedule(
            project_id=args["project_id"],
            spider=args["spider"],
            schedule=args.get("schedule"),
            units=args.get("units", 1),
            tags=args.get("tags"),
            job_settings=args.get("job_settings"),
            priority=args.get("priority", 2),
        )
        return json.dumps({"success": True, "data": result, "job_id": result.get("jobid")})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def zyte_list_jobs(args: dict, **kwargs) -> str:
    try:
        client = ScrapyCloudClient(dry_run=args.get("dry_run", False))
        jobs = client.list_jobs(
            project_id=args["project_id"],
            spider=args.get("spider"),
            state=args.get("state", "all"),
            limit=args.get("limit", 20),
            tags=args.get("tags"),
            offset=args.get("offset", 0),
        )
        return json.dumps({"success": True, "jobs": jobs, "count": len(jobs)})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def zyte_get_results(args: dict, **kwargs) -> str:
    try:
        client = ScrapyCloudClient(dry_run=args.get("dry_run", False))
        items = client.get_results(
            job_id=args["job_id"],
            fmt=args.get("format", "jsonlines"),
            limit=args.get("limit", 0),
            offset=args.get("offset", 0),
        )
        return json.dumps({"success": True, "items": items, "count": len(items)})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})
