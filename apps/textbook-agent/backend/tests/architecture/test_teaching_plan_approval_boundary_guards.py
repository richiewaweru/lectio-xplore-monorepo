"""Architecture guards for the first-cut Teaching Plan approval boundary."""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = BACKEND_ROOT / "src"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


class EditApiReferenceVisitor(ast.NodeVisitor):
    """Find dormant edit API references, including imported aliases."""

    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self.function_stack: list[str] = []
        self.wrapper_calls = 0
        self.violations: list[str] = []
        self.allowed_edit_attributes: set[int] = set()

    def _violate(self, node: ast.AST, description: str) -> None:
        self.violations.append(
            f"{self.relative_path}:{getattr(node, 'lineno', 0)}: {description}"
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if any(alias.name == "edit_teaching_plan" for alias in node.names):
            self._violate(node, "import of dormant edit_teaching_plan helper")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "edit_teaching_plan":
            self._violate(node, "reference to dormant edit_teaching_plan helper")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "edit_teaching_plan":
            self._violate(node, "reference to dormant edit_teaching_plan helper")
        elif node.attr == "edit_plan" and id(node) not in self.allowed_edit_attributes:
            self._violate(node, "reference to dormant edit_plan method")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        target = _call_name(node)
        if target == "edit_plan":
            allowed_wrapper = (
                self.relative_path == "curriculum/teaching_plan/service.py"
                and self.function_stack == ["edit_teaching_plan"]
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "edit_plan"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "store"
            )
            if allowed_wrapper:
                self.wrapper_calls += 1
                self.allowed_edit_attributes.add(id(node.func))
            else:
                self._violate(node, "active edit_plan call")
        self.generic_visit(node)


def test_teaching_plan_edit_entrypoints_have_no_production_callers() -> None:
    """The generic edit API remains dormant while arbitrary edits are a non-goal."""
    violations: list[str] = []
    wrapper_calls = 0

    for path in BACKEND_SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = _parse(path)
        visitor = EditApiReferenceVisitor(path.relative_to(BACKEND_SRC).as_posix())
        visitor.visit(tree)
        wrapper_calls += visitor.wrapper_calls
        violations.extend(visitor.violations)

    assert wrapper_calls == 1, "the dormant service wrapper should be the only edit_plan caller"
    assert not violations, "\n".join(violations)


def test_edit_api_guard_rejects_aliased_production_imports() -> None:
    tree = ast.parse(
        "from curriculum.teaching_plan.service import edit_teaching_plan as edit_plan\n"
        "edit_plan(state, plan, preparation_hash='hash')\n"
        "import curriculum.teaching_plan.service as service\n"
        "service.edit_teaching_plan(state, plan, preparation_hash='hash')\n"
    )
    visitor = EditApiReferenceVisitor("example.py")
    visitor.visit(tree)

    assert any("import of dormant edit_teaching_plan helper" in line for line in visitor.violations)
    assert any("reference to dormant edit_teaching_plan helper" in line for line in visitor.violations)
