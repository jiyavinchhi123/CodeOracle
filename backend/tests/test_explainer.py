"""Tests for natural-language explanation generation."""

from app.ai.explainer import ExplainerService
from app.ai.nl_generator import explain_function_nl, explain_module_nl
from app.ai.provider import HeuristicProvider
from app.analyzers.base import ParsedFile
from app.config import Settings

SAMPLE = '''
"""User authentication routes."""
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.post("/login")
async def login(username: str, password: str) -> dict:
    """Authenticate a user and return a token."""
    if not username:
        raise HTTPException(status_code=400, detail="Missing username")
    token = build_token(username, password)
    return {"token": token}

def build_token(user: str, pwd: str) -> str:
    return f"{user}-token"
'''


def _parsed():
    from app.analyzers.python_analyzer import PythonAnalyzer
    return PythonAnalyzer().analyze_file("app/api/auth.py", SAMPLE)


BANNED_GENERIC = (
    "performs logic defined in this module",
    "supports the overall codebase",
    "provides specialized behavior",
    "uses conditional branches to handle different cases",
    "implements behavior declared in this Java compilation unit",
)


def test_function_nl_human_friendly_not_trace():
    pf = _parsed()
    login = next(f for f in pf.functions if f["name"] == "login")
    nl = explain_function_nl(login, pf)
    assert nl.purpose
    assert nl.how_it_works
    assert "→" not in nl.how_it_works
    assert "Step-by-step" not in nl.how_it_works
    assert "username" in nl.input_desc.lower() or "username" in nl.purpose.lower()
    assert nl.technical_detail  # trace lives separately
    assert "→" in nl.technical_detail or "Checks" in nl.technical_detail or "Returns" in nl.technical_detail


def test_module_nl_has_sections():
    pf = _parsed()
    result = explain_module_nl(pf, ["app/api/auth.py"])
    nl = result["nl"]
    assert nl.purpose
    assert nl.how_it_works
    assert "→" not in nl.how_it_works


def test_explainer_separates_structural_and_nl():
    pf = _parsed()
    svc = ExplainerService(HeuristicProvider(), "heuristic", Settings())
    mod = svc._explain(pf, [pf.path])
    assert mod.structural_summary
    assert mod.explanation
    assert mod.structural_summary != mod.explanation
    login_fn = next(f for f in mod.functions if f.name == "login")
    assert login_fn.nl.purpose
    assert login_fn.nl.how_it_works
    assert "→" not in login_fn.nl.how_it_works
