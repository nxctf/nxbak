class NxbakError(Exception):
    """Base exception for user-facing NXBAK failures."""


class ConfigError(NxbakError):
    """Configuration is missing or invalid."""


class GitError(NxbakError):
    """Git operation failed."""


class DependencyError(NxbakError):
    """Required external executable is unavailable."""
