# Copyright (c) 2026 Martial Systems LLC


class GateError(RuntimeError):
    """Stage hard gate failed."""


class CrsMissingError(GateError):
    """Layer has no CRS; refuse rather than assume."""


class CrsMismatchError(GateError):
    """CRS is present but is not the locked EPSG."""


class EmptyHucError(GateError):
    """HUC polygon missing or empty."""


class ClaimBanError(GateError):
    """Report text hit a banned claim."""


class FetchError(GateError):
    """Remote layer fetch failed closed."""
