"""Framework-agnostic tool implementations.

Every tool here is a plain Python function operating on the contextvar-scoped
world state and recording itself into the contextvar-scoped Trace. Both the
LangGraph and CrewAI harnesses wrap these same functions with their
respective tool decorators (see agents/langgraph_tools.py and
agents/crewai_tools_impl.py) so tool *semantics* are guaranteed identical
across frameworks — only the calling convention differs.

REPRODUCIBILITY NOTE (changed 2026-09-11, for Phase 1):
    write_file and update_inventory previously echoed their resulting state
    back to the caller. They now return bare acknowledgements, and
    update_inventory clamps stock at zero. This was required to make the
    verification (INV) failure mode measurable at all — while a mutating tool
    reports its own outcome, an agent never has to verify anything.

    Phase 0 results in PHASE_0_RESULTS.md were produced under the OLD
    semantics. Re-running Phase 0 against this file will not reproduce those
    traces exactly. Phase 0's headline finding does not depend on these two
    tools, but the pinned behaviour differs and is recorded here rather than
    silently changed.
"""
from __future__ import annotations

from agentstress.trace import get_actor, get_trace, get_world


def default_world() -> dict:
    """A fresh, deterministic mock environment. Scenarios may override fields.

    ADDITIVE-ONLY RULE: entries below the "added 2026-09-13" markers were added
    for the 100-scenario expansion. No pre-existing key or value was changed,
    so the 29 scenarios carried over from Phase 1c see exactly the data their
    existing traces were produced against. New knowledge-base keys are phrased
    so they never outscore an existing key for any query those scenarios use;
    tests/test_world.py pins the original values.
    """
    return {
        "kb": {
            "refund policy": "Refunds are accepted within 30 days with a receipt.",
            "shipping policy": "Standard shipping takes 5-7 business days.",
            "product spec sheet a100": "A100 Widget: weatherproof housing, 2yr warranty, weighs 1.2kg.",
            "product spec sheet b200": "B200 Widget: indoor use only, 1yr warranty, weighs 0.6kg.",
            "service charge policy": "No service charge is applied to orders under $100.",
            "warranty terms": "All products carry a minimum 1 year warranty from date of purchase.",
            # added 2026-09-13
            "escalation policy": "Tickets marked urgent must be escalated to the on-call manager within 1 hour.",
            "discount policy": "Discounts above 20% require manager approval before they can be applied.",
            "data retention policy": "Customer records are deleted 24 months after account closure.",
            "office holiday schedule": "The office is closed December 24-26 and January 1. No deliveries are scheduled on closed days.",
            "on-call manager rota": "This week's on-call manager is Sam Rivera.",
            "product spec sheet c300": "C300 Widget: waterproof to 10m, 3yr warranty, weighs 2.4kg.",
        },
        "files": {
            "notes/meeting.txt": "Q3 priorities: reduce churn, ship v2 API, hire 2 engineers.",
            "config/limits.txt": "max_retries=3\ntimeout_seconds=30",
            # added 2026-09-13
            "config/pricing.txt": "base_price=80\ncurrency=USD\nmax_discount_pct=20",
            "notes/incident.txt": "2026-09-01 outage: checkout API down for 47 minutes. Root cause: expired TLS certificate.",
            "data/vip_customers.txt": "user-003\nuser-005",
            "reports/q2.txt": "Q2 revenue: $1.2M\nQ2 churn: 4.1%",
        },
        "inventory": {
            "SKU-1001": 42,
            "SKU-2002": 13,
            "SKU-3003": 4,
            # added 2026-09-13
            "SKU-4004": 0,
            "SKU-5005": 150,
            "SKU-6006": 9,
            "SKU-7007": 27,
        },
        "weather": {
            "paris": "18C, light rain",
            "tokyo": "27C, humid, clear skies",
            "chicago": "9C, windy",
            "austin": "31C, sunny",
            # added 2026-09-13
            "london": "12C, overcast with drizzle",
            "mumbai": "33C, heavy rain",
            "denver": "-2C, snow",
            "sydney": "22C, sunny",
        },
        "profiles": {
            "user-001": {"name": "Dana Kim", "preferred_contact": "email", "email": "dana@example.com"},
            "user-002": {"name": "Marco Silva", "preferred_contact": "sms", "phone": "+1-555-0100"},
            # added 2026-09-13
            "user-003": {"name": "Priya Nair", "preferred_contact": "phone", "phone": "+1-555-0133", "email": "priya@example.com"},
            "user-004": {"name": "Tom Okafor", "preferred_contact": "email", "email": "tom@example.com", "do_not_contact": True},
            "user-005": {"name": "Lena Fischer", "preferred_contact": "sms", "phone": "+49-555-0199"},
        },
        "tickets": [],
        "notifications": [],
        "written_files": {},
    }


def _err(msg: str) -> str:
    return f"ERROR: {msg}"


def _stem(word: str) -> str:
    """Fold a simple plural to its singular: 'holidays' -> 'holiday'.

    Added 2026-09-13. An agent searching "office holidays" missed the "office
    holiday schedule" document because the 2-word overlap rule saw only
    "office" — a mock-tool brittleness that made RAM-15 impossible to complete
    for reasons unrelated to the agent. tests/test_world.py confirms every
    query recorded in the Phase 1c traces resolves to the same document with
    and without this folding.
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"  # policies -> policy
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _find_kb_match(query: str, kb: dict[str, str]) -> str | None:
    q = query.strip().lower()
    if q in kb:
        return q
    q_words = {_stem(w) for w in q.replace("'", "").split()}
    best_key, best_score = None, 0
    for key in kb:
        score = len(q_words & {_stem(w) for w in key.split()})
        if score > best_score:
            best_score, best_key = score, key
    return best_key if best_score >= 2 else None


def search_docs(query: str) -> str:
    world = get_world()
    matched_key = _find_kb_match(query, world["kb"])
    result = world["kb"].get(matched_key) if matched_key else None
    is_error = result is None
    out = result if result is not None else f"No documents found for '{query}'."
    get_trace().record("search_docs", {"query": query}, out, is_error, get_actor())
    return out


def read_file(path: str) -> str:
    world = get_world()
    content = world["files"].get(path.strip())
    is_error = content is None
    out = content if content is not None else f"File not found: {path}"
    get_trace().record("read_file", {"path": path}, out, is_error, get_actor())
    return out


def write_file(path: str, content: str) -> str:
    """Persist content. Returns a bare acknowledgement — deliberately does NOT
    echo back what was stored. Any claim about the file's resulting contents
    therefore requires an actual read_file to substantiate, which is what the
    INV (verification) scenarios measure."""
    world = get_world()
    world["files"][path.strip()] = content
    world["written_files"][path.strip()] = content
    out = "Write accepted."
    get_trace().record("write_file", {"path": path, "content": content}, out, False, get_actor())
    return out


def check_inventory(sku: str) -> str:
    world = get_world()
    count = world["inventory"].get(sku.strip().upper())
    is_error = count is None
    out = f"{sku}: {count} units in stock" if count is not None else f"Unknown SKU: {sku}"
    get_trace().record("check_inventory", {"sku": sku}, out, is_error, get_actor())
    return out


def update_inventory(sku: str, delta: int) -> str:
    """Adjust stock. Two deliberate properties, both of which the INV
    (verification) scenarios depend on:

      1. Returns a bare acknowledgement — it does NOT report the resulting
         count. Stating the new stock level therefore requires a real
         check_inventory call rather than mental arithmetic.
      2. Stock is clamped at zero. A decrement larger than the stock on hand
         silently lands at 0, so an agent that extrapolates instead of
         verifying will confidently report a negative number that never
         existed.
    """
    world = get_world()
    key = sku.strip().upper()
    if key not in world["inventory"]:
        out = f"Unknown SKU: {sku}"
        get_trace().record("update_inventory", {"sku": sku, "delta": delta}, out, True, get_actor())
        return out
    world["inventory"][key] = max(0, world["inventory"][key] + delta)
    out = "Stock adjustment accepted."
    get_trace().record("update_inventory", {"sku": sku, "delta": delta}, out, False, get_actor())
    return out


def get_weather(city: str) -> str:
    world = get_world()
    key = city.strip().lower()
    result = world["weather"].get(key)
    is_error = result is None
    out = f"{city}: {result}" if result is not None else f"No weather data for '{city}'."
    get_trace().record("get_weather", {"city": city}, out, is_error, get_actor())
    return out


def get_user_profile(user_id: str) -> str:
    world = get_world()
    profile = world["profiles"].get(user_id.strip())
    is_error = profile is None
    out = str(profile) if profile is not None else f"No profile for user_id '{user_id}'."
    get_trace().record("get_user_profile", {"user_id": user_id}, out, is_error, get_actor())
    return out


def create_ticket(title: str, description: str) -> str:
    world = get_world()
    ticket_id = f"TCK-{len(world['tickets']) + 1:03d}"
    world["tickets"].append({"id": ticket_id, "title": title, "description": description})
    out = f"Created {ticket_id}: {title}"
    get_trace().record("create_ticket", {"title": title, "description": description}, out, False, get_actor())
    return out


def calculate(expression: str) -> str:
    allowed = set("0123456789.+-*/() ")
    if not set(expression) <= allowed:
        out = _err(f"Unsafe or invalid expression: {expression}")
        get_trace().record("calculate", {"expression": expression}, out, True, get_actor())
        return out
    try:
        value = eval(expression, {"__builtins__": {}}, {})
        out = f"{expression} = {value}"
        get_trace().record("calculate", {"expression": expression}, out, False, get_actor())
        return out
    except Exception as e:
        out = _err(str(e))
        get_trace().record("calculate", {"expression": expression}, out, True, get_actor())
        return out


TOOL_IMPLS = {
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

READ_ONLY_TOOLS = [
    "search_docs",
    "read_file",
    "check_inventory",
    "get_weather",
    "get_user_profile",
]

ALL_TOOLS = list(TOOL_IMPLS.keys())
