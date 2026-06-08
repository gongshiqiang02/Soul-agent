"""计划进度追踪器"""

from dataclasses import dataclass, field


@dataclass
class PlanStep:
    """计划中的单个步骤"""
    id: int
    description: str
    tool: str | None = None
    depends_on: list[int] = field(default_factory=list)
    status: str = "pending"  # "pending" | "done"


class PlanTracker:
    """追踪计划执行进度，将工具调用匹配到计划步骤"""

    def __init__(self, plan: dict):
        self.task: str = plan.get("task", "")
        self.complexity: str = plan.get("complexity", "simple")
        self.steps: list[PlanStep] = []
        for i, s in enumerate(plan.get("steps", [])):
            self.steps.append(PlanStep(
                id=s.get("id", i + 1),
                description=s.get("description", ""),
                tool=s.get("tool"),
                depends_on=s.get("depends_on", []),
            ))

    def mark_tool_done(self, tool_name: str) -> int | None:
        """将工具调用匹配到第一个 pending 步骤，标记为 done。
        返回匹配到的 step id，没有匹配到则返回 None。
        """
        for step in self.steps:
            if step.tool == tool_name and step.status == "pending":
                step.status = "done"
                return step.id
        return None

    @property
    def done_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "done")

    @property
    def total_count(self) -> int:
        return len(self.steps)

    @property
    def all_done(self) -> bool:
        return self.done_count == self.total_count and self.total_count > 0

    @property
    def has_any_done(self) -> bool:
        return self.done_count > 0

    @property
    def has_tool_steps(self) -> bool:
        """是否有至少一个需要工具的步骤"""
        return any(s.tool for s in self.steps)
