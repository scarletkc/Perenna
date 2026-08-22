class PerennaError(Exception):
    """Base class for expected, user-actionable Perenna failures."""


class ConfigurationError(PerennaError):
    """Runtime configuration is missing or invalid."""


class RepositoryError(PerennaError):
    """The memory Git repository cannot be used safely."""


class RepositoryDirtyError(RepositoryError):
    """A write was refused because the memory repository has local changes."""


class MemoryValidationError(PerennaError):
    """A memory input or committed Markdown document is invalid."""


class MemoryIntegrityError(PerennaError):
    """Committed memory documents conflict with each other."""


class IndexUnavailableError(PerennaError):
    """The Vexor retrieval index is unavailable."""
