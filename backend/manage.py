#!/usr/bin/env python
"""Django management entry point."""

import os
import sys


def main() -> None:
    """Run Django administrative commands."""
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "agentproof_backend.config.settings.local",
    )

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django could not be imported. Run `uv sync --all-packages --all-groups`.") from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
