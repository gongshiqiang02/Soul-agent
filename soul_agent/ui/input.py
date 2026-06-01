"""终端输入处理"""

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from pathlib import Path


class InputHandler:
    """终端输入处理，支持历史记录和自动补全"""

    def __init__(self):
        history_dir = Path("data")
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / ".input_history"

        self.style = Style.from_dict({
            "prompt": "ansicyan bold",
        })

        self.session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            style=self.style,
        )

    async def get_input(self, prompt_text: str = ">>> ") -> str:
        """异步获取用户输入"""
        try:
            result = await self.session.prompt_async(
                [("class:prompt", prompt_text)],
            )
            return result.strip()
        except (EOFError, KeyboardInterrupt):
            return "/quit"
