#!/usr/bin/env python3
"""Terminal color utilities for formatted output"""


class Colors:
    """ANSI color codes for terminal output."""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_info(msg: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")


def print_success(msg: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")


def print_error(msg: str) -> None:
    """Print an error message."""
    import sys
    print(f"{Colors.RED}✗ {msg}{Colors.END}", file=sys.stderr)
