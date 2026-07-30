import re
from pathlib import Path

from app.main import create_app

METHODS = {"get", "post", "put", "patch", "delete"}
CONTRACT = Path(__file__).resolve().parents[2] / "docs" / "backend" / "api-contract.md"
OPERATION_LINE = re.compile(
    r"^(GET|POST|PUT|PATCH|DELETE)"
    r"(?:/(GET|POST|PUT|PATCH|DELETE))?"
    r"(?:/(GET|POST|PUT|PATCH|DELETE))?"
    r"\s+(/[^\s]+)$"
)


def _normalized_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def _documented_operations() -> set[tuple[str, str]]:
    operations = set()
    for line in CONTRACT.read_text(encoding="utf-8").splitlines():
        match = OPERATION_LINE.match(line.strip())
        if match is None:
            continue
        methods = [item for item in match.groups()[:3] if item]
        path = f"/api/v1{match.group(4)}"
        operations.update((method, _normalized_path(path)) for method in methods)
    return operations


def test_every_documented_api_operation_exists_in_openapi():
    schema = create_app().openapi()
    actual = {
        (method.upper(), _normalized_path(path))
        for path, item in schema["paths"].items()
        for method in item
        if method.lower() in METHODS
    }
    documented = _documented_operations()

    assert len(documented) >= 100
    assert documented - actual == set()
