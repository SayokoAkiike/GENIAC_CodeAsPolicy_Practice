"""Central logging configuration.

Every module gets its logger via ``get_logger(__name__)`` instead of using
``print``. The log level can be controlled with the ``GENIAC_CAP_LOG_LEVEL``
environment variable (see config.py) or by calling ``configure_logging``
directly (e.g. from the CLI's --verbose flag).
"""

from __future__ import annotations

import logging

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger for this package exactly once."""

    global _CONFIGURED
    if _CONFIGURED:
        logging.getLogger("geniac_cap").setLevel(level.upper())
        return

    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, configuring logging on first use."""

    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
