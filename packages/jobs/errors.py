"""Job errors."""

from __future__ import annotations


class JobError(RuntimeError):
    """Base class for job subsystem errors."""


class UnknownJobKind(JobError):
    """Submitted kind has no registered executor."""


class JobNotFound(JobError):
    """Job id does not exist."""


class InvalidTransition(JobError):
    """Requested status change violates the state machine."""
