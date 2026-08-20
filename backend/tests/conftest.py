import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIXTURES = ROOT / "evals" / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def ensure_fixtures():
    if not any(FIXTURES.glob("*.pdf")):
        sys.path.insert(0, str(ROOT / "evals"))
        import generate_fixtures

        generate_fixtures.main()
    return FIXTURES


@pytest.fixture(scope="session")
def fixtures_dir(ensure_fixtures):
    return ensure_fixtures
