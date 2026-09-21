"""OpenAI Agents SDK `@function_tool`-wrapped versions of the shared tools.

Third of three wrappers over the same implementations in common/tools.py, so
tool semantics are identical across LangGraph, CrewAI and the OpenAI Agents
SDK and only the calling convention differs.
"""
from __future__ import annotations

from agents import function_tool

from agentstress import tools as impl


@function_tool
def search_docs(query: str) -> str:
    """Search internal documentation for a topic (e.g. policies, spec sheets). Returns the matching snippet."""
    return impl.search_docs(query)


@function_tool
def read_file(path: str) -> str:
    """Read the contents of a file at the given path."""
    return impl.read_file(path)


@function_tool
def write_file(path: str, content: str) -> str:
    """Write content to a file at the given path."""
    return impl.write_file(path, content)


@function_tool
def check_inventory(sku: str) -> str:
    """Check current stock count for a SKU."""
    return impl.check_inventory(sku)


@function_tool
def update_inventory(sku: str, delta: int) -> str:
    """Adjust stock count for a SKU by delta (can be negative)."""
    return impl.update_inventory(sku, delta)


@function_tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return impl.get_weather(city)


@function_tool
def get_user_profile(user_id: str) -> str:
    """Look up a user's profile by user_id."""
    return impl.get_user_profile(user_id)


@function_tool
def create_ticket(title: str, description: str) -> str:
    """Create a support/task ticket with a title and description."""
    return impl.create_ticket(title, description)


@function_tool
def calculate(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '0.15*84.50'."""
    return impl.calculate(expression)


TOOL_REGISTRY = {
    "search_docs": search_docs,
    "read_file": read_file,
    "write_file": write_file,
    "check_inventory": check_inventory,
    "update_inventory": update_inventory,
    "get_weather": get_weather,
    "get_user_profile": get_user_profile,
    "create_ticket": create_ticket,
    "calculate": calculate,
}


def get_tools(names: list[str]):
    return [TOOL_REGISTRY[n] for n in names]
