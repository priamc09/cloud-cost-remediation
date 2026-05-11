from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Logging ──────────────────────────────────────────────────────────────
    # DEBUG | INFO | WARNING | ERROR | CRITICAL
    LOG_LEVEL: str = "INFO"

    # ── Azure Service Principal ──────────────────────────────────────────────
    AZURE_TENANT_ID: str
    AZURE_CLIENT_ID: str
    AZURE_CLIENT_SECRET: str
    AZURE_SUBSCRIPTION_ID: str

    # ── Azure Key Vault ──────────────────────────────────────────────────────
    AZURE_KEYVAULT_URL: str
    KV_SECRET_DB_SAS: str = "storage-db-sas-token"
    KV_SECRET_EXPORTS_SAS: str = "storage-exports-sas-token"

    # ── Azure Storage ────────────────────────────────────────────────────────
    AZURE_STORAGE_ACCOUNT_URL: str
    AZURE_DB_CONTAINER_NAME: str = "optimizer-db"
    AZURE_EXPORTS_CONTAINER_NAME: str = "optimizer-exports"

    # ── Local Paths ──────────────────────────────────────────────────────────
    LOCAL_DB_PATH: str = "/tmp/optimizer.db"
    DB_BLOB_NAME: str = "optimizer.db"
    LOCAL_SCRIPTS_DIR: str = "/tmp/deletion_scripts"

    # ── Database Provider ────────────────────────────────────────────────────
    # Supported: sqlite | postgresql | mysql | sqlserver
    DATABASE_PROVIDER: str = "sqlite"

    # Shared relational DB connection (used by postgresql / mysql / sqlserver)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432          # override per provider: 3306 MySQL, 1433 SQL Server
    DB_NAME: str = "cost_optimizer"
    DB_USER: str = "optimizer_user"
    DB_PASSWORD: str = ""
    DB_SSL_MODE: str = "require"              # postgresql
    DB_CHARSET: str = "utf8mb4"              # mysql
    DB_DRIVER: str = "ODBC Driver 18 for SQL Server"  # sqlserver
    DB_ENCRYPT: str = "yes"                  # sqlserver
    DB_TRUST_SERVER_CERT: str = "no"         # sqlserver
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # ── Analysis Thresholds ──────────────────────────────────────────────────
    IDLE_VM_CPU_THRESHOLD_PCT: float = 5.0
    IDLE_STORAGE_DAYS: int = 30
    IDLE_APP_DAYS: int = 30
    IDLE_DB_DAYS: int = 30
    IDLE_AKS_CPU_THRESHOLD_PCT: float = 10.0
    ANALYSIS_LOOKBACK_DAYS: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
