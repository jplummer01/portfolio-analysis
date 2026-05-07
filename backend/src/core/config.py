import os


class Settings:
    """Application settings loaded from environment variables."""

    backend_host: str
    backend_port: int
    log_level: str
    data_dir: str
    auth_enabled: bool
    cache_enabled: bool

    def __init__(self) -> None:
        self.backend_host = os.environ.get("BACKEND_HOST", "127.0.0.1")
        self.backend_port = int(os.environ.get("BACKEND_PORT", "8000"))
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")
        self.data_dir = os.environ.get("DATA_DIR", "./data")
        self.auth_enabled = os.environ.get("AUTH_ENABLED", "false").lower() == "true"
        self.cache_enabled = os.environ.get("CACHE_ENABLED", "false").lower() == "true"

    @property
    def use_workflows(self) -> bool:
        """Whether MAF workflow orchestration is enabled."""
        return os.environ.get("USE_WORKFLOWS", "false").lower() == "true"


settings = Settings()
