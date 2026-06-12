"""主题配置"""

THEMES = {
    "monokai": {
        "user_color": "bright_green",
        "assistant_color": "bright_cyan",
        "system_color": "yellow",
        "error_color": "bright_red",
        "tool_color": "bright_magenta",
        "info_color": "dim",
        "border_color": "bright_blue",
        "connector_color": "dim",
        "success_color": "#00d700",
        "stats_color": "dim",
    },
    "dracula": {
        "user_color": "green",
        "assistant_color": "cyan",
        "system_color": "yellow",
        "error_color": "red",
        "tool_color": "magenta",
        "info_color": "dim",
        "border_color": "purple",
        "connector_color": "dim",
        "success_color": "#00d700",
        "stats_color": "dim",
    },
    "default": {
        "user_color": "green",
        "assistant_color": "white",
        "system_color": "yellow",
        "error_color": "red",
        "tool_color": "blue",
        "info_color": "dim",
        "border_color": "white",
        "connector_color": "dim",
        "success_color": "#00d700",
        "stats_color": "dim",
    },
}


def get_theme(name: str) -> dict:
    """获取主题,与default主题合并返回,确保所有key存在"""
    base = THEMES["default"].copy()
    selected = THEMES.get(name, {})
    base.update(selected)
    return base
