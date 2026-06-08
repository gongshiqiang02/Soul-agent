"""PlanTracker 单元测试"""
from soul_agent.core.plan_tracker import PlanTracker, PlanStep


class TestPlanStep:
    def test_create_step(self):
        step = PlanStep(id=1, description="读文件", tool="read_file")
        assert step.id == 1
        assert step.tool == "read_file"
        assert step.status == "pending"

    def test_default_values(self):
        step = PlanStep(id=2, description="分析")
        assert step.tool is None
        assert step.depends_on == []
        assert step.status == "pending"


class TestPlanTracker:
    def test_from_plan_dict(self):
        plan = {
            "task": "代码统计",
            "complexity": "complex",
            "steps": [
                {"id": 1, "description": "搜索文件", "tool": "search_files", "depends_on": []},
                {"id": 2, "description": "统计行数", "tool": "run_command", "depends_on": [1]},
                {"id": 3, "description": "写入结果", "tool": "write_file", "depends_on": [2]},
            ],
        }
        tracker = PlanTracker(plan)
        assert tracker.task == "代码统计"
        assert tracker.total_count == 3
        assert tracker.done_count == 0
        assert not tracker.all_done

    def test_mark_tool_done_matches_first_pending(self):
        plan = {
            "task": "两次读取",
            "complexity": "complex",
            "steps": [
                {"id": 1, "description": "读取 A", "tool": "read_file", "depends_on": []},
                {"id": 2, "description": "读取 B", "tool": "read_file", "depends_on": []},
            ],
        }
        tracker = PlanTracker(plan)

        # 第一次匹配 step 1
        matched = tracker.mark_tool_done("read_file")
        assert matched == 1
        assert tracker.steps[0].status == "done"
        assert tracker.steps[1].status == "pending"
        assert tracker.done_count == 1

        # 第二次匹配 step 2
        matched = tracker.mark_tool_done("read_file")
        assert matched == 2
        assert tracker.steps[1].status == "done"
        assert tracker.done_count == 2
        assert tracker.all_done

    def test_mark_tool_done_unknown_tool_returns_none(self):
        plan = {
            "task": "读取",
            "complexity": "simple",
            "steps": [{"id": 1, "description": "读取", "tool": "read_file", "depends_on": []}],
        }
        tracker = PlanTracker(plan)
        matched = tracker.mark_tool_done("unknown_tool")
        assert matched is None
        assert tracker.done_count == 0

    def test_mark_tool_done_already_done_returns_none(self):
        plan = {
            "task": "读取",
            "complexity": "simple",
            "steps": [{"id": 1, "description": "读取", "tool": "read_file", "depends_on": []}],
        }
        tracker = PlanTracker(plan)
        tracker.mark_tool_done("read_file")
        # 再次调用同一个工具——已经 done 了，不应再匹配
        matched = tracker.mark_tool_done("read_file")
        assert matched is None
        assert tracker.done_count == 1

    def test_has_tool_steps(self):
        plan_no_tool = {
            "task": "聊天",
            "complexity": "simple",
            "steps": [{"id": 1, "description": "回复", "tool": None, "depends_on": []}],
        }
        tracker = PlanTracker(plan_no_tool)
        assert not tracker.has_tool_steps

        plan_with_tool = {
            "task": "读取",
            "complexity": "simple",
            "steps": [{"id": 1, "description": "读取", "tool": "read_file", "depends_on": []}],
        }
        tracker = PlanTracker(plan_with_tool)
        assert tracker.has_tool_steps

    def test_empty_steps(self):
        plan = {"task": "空任务", "complexity": "simple", "steps": []}
        tracker = PlanTracker(plan)
        assert tracker.total_count == 0
        assert tracker.done_count == 0
        assert not tracker.all_done
        assert not tracker.has_tool_steps
