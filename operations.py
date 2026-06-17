"""
Production-grade operational layer for managing spiders on Scrapy Cloud.

This module provides a clean, reusable client for the operational tools
(zyte_deploy, zyte_schedule, zyte_list_jobs, zyte_get_results).

Priority 2 fixes:
- HTTP Basic Auth instead of Bearer token (Scrapy Cloud requirement)
- Exponential backoff + jitter for 429/5xx responses
- Configurable timeout (not hardcoded 60s)
- Dry-run mode for safer testing
"""

import os
import json
import requests
import requests.auth
import time
import random
from typing import Any, Dict, List, Optional
from pathlib import Path


class ScrapyCloudError(Exception):
    """Base exception for Scrapy Cloud operational errors."""
    pass


class ScrapyCloudClient:
    """
    A production-oriented client for Scrapy Cloud operations.

    Handles authentication (HTTP Basic Auth), error handling with exponential backoff,
    name resolution, and provides a cleaner interface than raw API calls.
    """

    # Per 2026 Scrapy Cloud API reference:
    # - Jobs/schedules/run on app.zyte.com
    # - Items, logs, etc. primarily on storage.zyte.com
    JOBS_BASE = "https://app.zyte.com/api"
    STORAGE_BASE = "https://storage.zyte.com"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 60, dry_run: bool = False):
        self.api_key = api_key or os.getenv("SCRAPY_CLOUD_API_KEY")
        if not self.api_key:
            raise ScrapyCloudError(
                "SCRAPY_CLOUD_API_KEY is not set. "
                "Please set it in ~/.hermes/.env or pass it explicitly."
            )
        self.timeout = timeout
        self.dry_run = dry_run
        
        # FIXED: Use HTTP Basic Auth instead of Bearer token (Scrapy Cloud requirement)
        self.session = requests.Session()
        self.session.auth = requests.auth.HTTPBasicAuth(self.api_key, "")

    def _request(
        self,
        method: str,
        base: str,
        endpoint: str,
        max_retries: int = 3,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with exponential backoff + jitter for resilience.
        
        Priority 8 hardening: 3-attempt exponential backoff for 429/5xx.
        """
        url = f"{base}{endpoint}"
        
        # Dry-run mode: log but don't execute
        if self.dry_run:
            log_msg = f"[DRY-RUN] {method} {url} with kwargs: {kwargs}"
            print(log_msg)
            return type(
                "DryRunResponse",
                (object,),
                {
                    "status_code": 200,
                    "text": '{"projects": [{"id": 1, "name": "dry-run"}]}',
                    "json": lambda self=None, **kwargs: {"projects": [{"id": 1, "name": "dry-run"}]},
                },
            )()
        
        for attempt in range(max_retries):
            try:
                resp = self.session.request(
                    method,
                    url,
                    timeout=kwargs.pop('timeout', self.timeout),
                    **kwargs
                )
                
                # Retry on 429 (rate limit) or 5xx errors
                if resp.status_code in [429, 500, 502, 503, 504]:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random.random()  # exponential backoff + jitter
                        print(f"[ScrapyCloud] {resp.status_code} — retrying in {wait_time:.2f}s (attempt {attempt+1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                
                # Raise on other 4xx/5xx errors
                if resp.status_code >= 400:
                    raise ScrapyCloudError(
                        f"Scrapy Cloud API error {resp.status_code}: {resp.text}"
                    )
                
                return resp
            
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise ScrapyCloudError(f"Network error after {max_retries} attempts: {e}")
                wait_time = (2 ** attempt) + random.random()
                print(f"[ScrapyCloud] Network error — retrying in {wait_time:.2f}s: {e}")
                time.sleep(wait_time)

    def resolve_project(self, name_or_id: str) -> str:
        """Accepts project name or ID and returns the numeric project ID."""
        if name_or_id.isdigit():
            return name_or_id

        resp = self._request("GET", self.JOBS_BASE, "/projects", params={"name": name_or_id})
        data = resp.json()
        projects = data.get("projects", [])
        if not projects:
            raise ScrapyCloudError(f"Could not find project named '{name_or_id}'")
        return str(projects[0]["id"])

    def deploy(self, project_path: str, project_name: Optional[str] = None) -> Dict[str, Any]:
        """Deploy a local Scrapy project to Scrapy Cloud via shub."""
        path = Path(project_path).expanduser().resolve()
        if not path.exists():
            raise ScrapyCloudError(f"Project path does not exist: {path}")

        name = project_name or path.name

        # Ensure scrapinghub.yml exists
        shub_yml = path / "scrapinghub.yml"
        if not shub_yml.exists():
            shub_yml.write_text(f"""project: {name}

requirements:
  file: requirements.txt

stack: scrapy:2.11
""")

        # Run shub deploy
        import subprocess
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
        schedule: Optional[str] = None,
        units: int = 1,
        tags: Optional[list] = None,
        job_settings: Optional[dict] = None,
        priority: int = 2,
    ) -> Dict[str, Any]:
        """Schedule a spider (one-time or recurring via cron)."""
        project_id = self.resolve_project(project_id)

        payload = {"spider": spider, "units": units, "priority": priority}
        
        # FIXED: Proper tag handling (Priority 2)
        if tags:
            if isinstance(tags, list):
                payload["add_tag"] = tags
            else:
                payload["add_tag"] = [tags]
        
        if job_settings:
            payload["job_settings"] = job_settings

        if schedule:
            payload["cron"] = schedule
            endpoint = f"/projects/{project_id}/schedules"
        else:
            endpoint = f"/projects/{project_id}/jobs"

        resp = self._request("POST", self.JOBS_BASE, endpoint, json=payload)
        return resp.json()

    def list_jobs(
        self,
        project_id: str,
        spider: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 20,
        tags: Optional[list] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List jobs for a project with pagination support."""
        project_id = self.resolve_project(project_id)
        params = {"count": limit}
        
        if offset > 0:
            params["offset"] = offset
        if spider:
            params["spider"] = spider
        if state and state != "all":
            params["state"] = state
        if tags:
            params["has_tag"] = ",".join(tags) if isinstance(tags, list) else tags

        resp = self._request("GET", self.JOBS_BASE, f"/projects/{project_id}/jobs", params=params)
        return resp.json().get("jobs", [])

    def get_results(
        self,
        job_id: str,
        fmt: str = "jsonlines",
        limit: int = 0,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch items from a job with pagination support (Priority 2)."""
        params = {"format": fmt}
        
        if limit > 0:
            params["count"] = limit
        if offset > 0:
            params["offset"] = offset

        resp = self._request("GET", self.STORAGE_BASE, f"/items/{job_id}", params=params)

        if fmt in ("jsonlines", "jl"):
            lines = [line for line in resp.text.strip().split("\n") if line]
            items = []
            for line in lines:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # Skip malformed lines
            return items
        else:
            data = resp.json()
            items = data.get("items", data) if isinstance(data, dict) else data
            if isinstance(items, list) and limit > 0:
                return items[:limit]
            return items if isinstance(items, list) else []


# =============================================================================
# Convenience tool handler functions (matching Hermes tool interface)
# =============================================================================

def zyte_deploy(args: dict, **kwargs) -> str:
    """Handler for zyte_deploy tool."""
    try:
        client = ScrapyCloudClient(
            dry_run=args.get("dry_run", False)
        )
        result = client.deploy(
            project_path=args["project_path"],
            project_name=args.get("project_name"),
        )
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def zyte_schedule(args: dict, **kwargs) -> str:
    """Handler for zyte_schedule tool."""
    try:
        client = ScrapyCloudClient(
            dry_run=args.get("dry_run", False)
        )
        result = client.schedule(
            project_id=args["project_id"],
            spider=args["spider"],
            schedule=args.get("schedule"),
            units=args.get("units", 1),
            tags=args.get("tags"),
            job_settings=args.get("job_settings"),
            priority=args.get("priority", 2),
        )
        return json.dumps({"success": True, "data": result})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def zyte_list_jobs(args: dict, **kwargs) -> str:
    """Handler for zyte_list_jobs tool."""
    try:
        client = ScrapyCloudClient(
            dry_run=args.get("dry_run", False)
        )
        jobs = client.list_jobs(
            project_id=args["project_id"],
            spider=args.get("spider"),
            state=args.get("state", "all"),
            limit=args.get("limit", 20),
            tags=args.get("tags"),
            offset=args.get("offset", 0),
        )
        return json.dumps({"success": True, "jobs": jobs, "count": len(jobs)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def zyte_get_results(args: dict, **kwargs) -> str:
    """Handler for zyte_get_results tool."""
    try:
        client = ScrapyCloudClient(
            dry_run=args.get("dry_run", False)
        )
        items = client.get_results(
            job_id=args["job_id"],
            fmt=args.get("format", "jsonlines"),
            limit=args.get("limit", 0),
            offset=args.get("offset", 0),
        )
        return json.dumps({"success": True, "items": items, "count": len(items)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
