"""Pytest-only integration suite."""


def load_tests(loader, tests, pattern):
    """Keep Django's unittest discovery out of this pytest-only package."""
    return tests
