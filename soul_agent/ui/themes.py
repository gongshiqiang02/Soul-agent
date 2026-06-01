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
    },
    "dracula": {
        "user_color": "green",
        "assistant_color": "cyan",
        "system_color": "yellow",
        "error_color": "red",
        "tool_color": "magenta",
        "info_color": "dim",
        "border_color": "purple",
    },
    "default": {
        "user_color": "green",
        "assistant_color": "white",
        "system_color": "yellow",
        "error_color": "red",
        "tool_color": "blue",
        "info_color": "dim",
        "border_color": "white",
    },
}


def get_theme(name: str) -> dict:
    return THEMES.get(name, THEMES["default"])
