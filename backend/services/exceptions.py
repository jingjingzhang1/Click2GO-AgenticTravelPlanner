"""
Domain exceptions
=================
Raised by the service layer to signal business outcomes without importing
web-framework types. Routers translate these into HTTP responses, keeping the
service layer transport-agnostic and unit-testable.
"""
from __future__ import annotations


class ServiceError(Exception):
    """Base class for all service-layer errors."""


class NotFoundError(ServiceError):
    """Requested aggregate does not exist."""


class ConflictError(ServiceError):
    """Request conflicts with the resource's current state (e.g. not ready)."""


class InProgressError(ServiceError):
    """Resource exists but the async pipeline has not finished yet."""
