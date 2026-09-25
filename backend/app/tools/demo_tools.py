"""Demo tools for the MVP agent.

Tools are standalone: the agent only registers them (backend/app/agent/agent.py),
and the UI renders any tool generically via tool_start/tool_result events.
Add future tools (web_search, database, mcp, ...) in this package without
touching UI code.
"""

import ast
import operator
from datetime import UTC, datetime

from langchain_core.tools import tool

_BIN_OPS: dict[type[ast.operator], object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], object] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_Value = int | float


def _eval_node(node: ast.expr) -> _Value:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _eval_node(node.left), _eval_node(node.right)
        result = _BIN_OPS[type(node.op)](left, right)  # type: ignore[operator]
        assert isinstance(result, (int, float))
        return result
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        result = _UNARY_OPS[type(node.op)](_eval_node(node.operand))  # type: ignore[operator]
        assert isinstance(result, (int, float))
        return result
    raise ValueError(f"unsupported expression element: {type(node).__name__}")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression and return the numeric result.

    Supports +, -, *, /, // (integer division), % (modulo) and **
    (power), including parentheses and negative numbers. Use this tool
    for any calculation instead of computing by yourself.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid arithmetic expression: {expression!r}") from exc
    result = _eval_node(tree)
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


@tool
def get_current_time() -> str:
    """Return the current date and time in ISO 8601 format (UTC)."""
    return datetime.now(UTC).isoformat()


DEMO_TOOLS: list = [calculator, get_current_time]
