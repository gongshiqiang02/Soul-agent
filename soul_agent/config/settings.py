"""配置加载与验证"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from soul_agent.config.defaults import DEFAULT_CONFIG


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096


class AgentConfig(BaseModel):
    max_iterations: int = 10
    system_prompt_path: str | None = None
    planning_enabled: bool = True
    planning_complexity_threshold: int = 2


class MemoryConfig(BaseModel):
    enabled: bool = True
    db_path: str = "./data/memory.db"
    vector_db_path: str = "./data/chroma"
    max_memories_per_query: int = 5
    importance_threshold: float = 0.5
    embedding_model: str = "text-embedding-3-small"


class ShellConfig(BaseModel):
    timeout: int = 30
    blocked_commands: list[str] = Field(default_factory=lambda: ["rm -rf /", "format"])


class ToolsConfig(BaseModel):
    enabled: list[str] = Field(
        default_factory=lambda: [
            "read_file", "write_file", "list_directory",
            "run_command", "web_request", "search_files",
        ]
    )
    shell: ShellConfig = Field(default_factory=ShellConfig)


class UIConfig(BaseModel):
    theme: str = "monokai"
    stream: bool = True
    show_thinking: bool = False
    language: str = "zh"


class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _resolve_env_vars(config: dict) -> dict:
    """递归解析配置中的环境变量引用 ${VAR_NAME}"""
    resolved = {}
    for key, value in config.items():
        if isinstance(value, dict):
            resolved[key] = _resolve_env_vars(value)
        elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            resolved[key] = os.environ.get(env_var)
        else:
            resolved[key] = value
    return resolved


def load_config(config_path: str | None = None) -> AppConfig:
    """加载配置：默认值 -> YAML文件 -> 环境变量"""
    load_dotenv()

    config_data = DEFAULT_CONFIG.copy()

    # 加载YAML配置文件
    if config_path:
        yaml_path = Path(config_path)
    else:
        yaml_path = Path("config/default.yaml")

    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}
        config_data = _deep_merge(config_data, yaml_config)

    # 解析环境变量引用
    config_data = _resolve_env_vars(config_data)

    # 环境变量覆盖
    if os.environ.get("OPENAI_API_KEY"):
        config_data.setdefault("llm", {})["api_key"] = os.environ["OPENAI_API_KEY"]
    if os.environ.get("OPENAI_BASE_URL"):
        config_data.setdefault("llm", {})["base_url"] = os.environ["OPENAI_BASE_URL"]
    if os.environ.get("SOUL_AGENT_MODEL"):
        config_data.setdefault("llm", {})["model"] = os.environ["SOUL_AGENT_MODEL"]

    return AppConfig(**config_data)
