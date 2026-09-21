"""CrewAI `@tool`-wrapped versions of the shared tool implementations."""
from __future__ import annotations

from crewai.tools import tool

from agentstress import tools as impl


@tool("search_docs")
def search_docs(query: str) -> str:
    """Search internal documentation for a topic (e.g. policies, spec sheets). Returns the matching snippet."""
    return impl.search_docs(query)


@tool("read_file")
def read_file(path: str) -> str:
    """Read the contents of a file at the given path."""
    return impl.read_file(path)


@tool("write_file")
def write_file(path: str, content: str) -> str:
    """Write content to a file at the given path."""
    return impl.write_file(path, content)


@tool("check_inventory")
def check_inventory(sku: str) -> str:
    """Check current stock count for a SKU."""
    return impl.check_inventory(sku)


@tool("update_inventory")
def update_inventory(sku: str, delta: int) -> str:
    """Adjust stock count for a SKU by delta (can be negative)."""
    return impl.update_inventory(sku, delta)


@tool("get_weather")
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return impl.get_weather(city)


@tool("get_user_profile")
def get_user_profile(user_id: str) -> str:
    """Look up a user's profile by user_id."""
    return impl.get_user_profile(user_id)


@tool("create_ticket")
def create_ticket(title: str, description: str) -> str:
    """Create a support/task ticket with a title and description."""
    return impl.create_ticket(title, description)


@tool("calculate")
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
