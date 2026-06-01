"""默认配置"""

DEFAULT_CONFIG = {
    "llm": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key": None,
        "base_url": None,
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "agent": {
        "max_iterations": 10,
        "system_prompt_path": None,
    },
    "memory": {
        "enabled": True,
        "db_path": "./data/memory.db",
        "vector_db_path": "./data/chroma",
        "max_memories_per_query": 5,
        "importance_threshold": 0.3,
        "embedding_model": "text-embedding-3-small",
    },
    "tools": {
        "enabled": [
            "read_file",
            "write_file",
            "list_directory",
            "run_command",
            "web_request",
            "search_files",
        ],
        "shell": {
            "timeout": 30,
            "blocked_commands": ["rm -rf /", "format"],
        },
    },
    "ui": {
        "theme": "monokai",
        "stream": True,
        "show_thinking": False,
        "language": "zh",
    },
}
