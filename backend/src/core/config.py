import os
from enum import Enum


def _read_bool_env(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() == "true"


class ExecutionMode(str, Enum):
    DIRECT = "direct"
    WORKFLOW = "workflow"
    AGENT_LOCAL = "agent_local"
    AGENT_DISTRIBUTED = "agent_distributed"


class Settings:
    """Application settings loaded from environment variables."""

    backend_host: str
    backend_port: int
    log_level: str
    data_dir: str
    auth_enabled: bool
    cache_enabled: bool
    execution_mode: ExecutionMode
    foundry_project_endpoint: str
    foundry_model: str

    def __init__(self) -> None:
        self.backend_host = os.environ.get("BACKEND_HOST", "127.0.0.1")
        self.backend_port = int(os.environ.get("BACKEND_PORT", "8000"))
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")
        self.data_dir = os.environ.get("DATA_DIR", "./data")
        self.auth_enabled = _read_bool_env("AUTH_ENABLED")
        self.cache_enabled = _read_bool_env("CACHE_ENABLED")
        self.execution_mode = self._load_execution_mode()
        self.foundry_project_endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
        self.foundry_model = os.environ.get("FOUNDRY_MODEL", "")

    def _load_execution_mode(self) -> ExecutionMode:
        execution_mode = os.environ.get("EXECUTION_MODE")
        if execution_mode:
            return ExecutionMode(execution_mode.strip().lower())

        if _read_bool_env("USE_WORKFLOWS"):
            return ExecutionMode.WORKFLOW

        return ExecutionMode.DIRECT

    @property
    def is_direct(self) -> bool:
        return self.execution_mode == ExecutionMode.DIRECT

    @property
    def is_workflow(self) -> bool:
        return self.execution_mode == ExecutionMode.WORKFLOW

    @property
    def is_agent_local(self) -> bool:
        return self.execution_mode == ExecutionMode.AGENT_LOCAL

    @property
    def is_agent_distributed(self) -> bool:
        return self.execution_mode == ExecutionMode.AGENT_DISTRIBUTED


settings = Settings()
