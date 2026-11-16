class HibernatorError(Exception):
    """Expected, user-facing Hibernator failure."""


class UnsupportedRoot(HibernatorError):
    pass


class ScanFailure(HibernatorError):
    pass


class InvalidPlan(HibernatorError):
    pass


class ApplyRefused(HibernatorError):
    pass
