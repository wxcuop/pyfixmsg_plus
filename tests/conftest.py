"""
PyFixMsg Plus Test Configuration
Provides pytest configuration and imports all test fixtures.
"""
import pytest
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import all fixtures from our fixtures module
from tests.fixtures.test_fixtures import *

def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption("--spec", action='store', help="Specification file path")
    parser.addoption("--run-slow", action="store_true", default=False, help="run slow tests")
    parser.addoption("--run-chaos", action="store_true", default=False, help="run chaos tests")

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "chaos: Chaos engineering tests")
    config.addinivalue_line("markers", "property: Property-based tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "network: Tests requiring network access")
    config.addinivalue_line("markers", "database: Tests requiring database")
    config.addinivalue_line("markers", "quickfix: QuickFIX interoperability tests")

def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle markers and skip conditions."""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    
    if not config.getoption("--run-chaos"):
        skip_chaos = pytest.mark.skip(reason="need --run-chaos option to run")
        for item in items:
            if "chaos" in item.keywords:
                item.add_marker(skip_chaos)

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()
