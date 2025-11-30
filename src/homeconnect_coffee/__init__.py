"""HomeConnect Coffee Control."""

from __future__ import annotations

from pathlib import Path

__all__ = []

# Read version from VERSION file
_VERSION_FILE = Path(__file__).parent.parent.parent / "VERSION"
if _VERSION_FILE.exists():
    __version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
else:
    __version__ = "0.0.0"

# Parse version info for easier comparisons
def _parse_version(version_str: str) -> tuple[int, int, int, str, int]:
    """Parse version string into (major, minor, patch, prerelease_type, prerelease_num).
    
    Supports PEP 440 format: 1.2.3, 1.2.3.dev1, 1.2.3a1, 1.2.3b1, 1.2.3rc1
    """
    version_str = version_str.strip()
    
    # Extract prerelease info
    prerelease_type = ""
    prerelease_num = 0
    
    if "-dev" in version_str:
        parts = version_str.split("-dev")
        version_str = parts[0]
        prerelease_type = "dev"
        prerelease_num = 0  # Dev versions don't have numbers
    elif ".dev" in version_str:
        # Legacy format support
        parts = version_str.split(".dev")
        version_str = parts[0]
        prerelease_type = "dev"
        prerelease_num = 0  # Dev versions don't have numbers
    elif "-a" in version_str:
        parts = version_str.split("-a")
        version_str = parts[0]
        prerelease_type = "alpha"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif "-b" in version_str:
        parts = version_str.split("-b")
        version_str = parts[0]
        prerelease_type = "beta"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif "-rc" in version_str:
        parts = version_str.split("-rc")
        version_str = parts[0]
        prerelease_type = "rc"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif "a" in version_str and not version_str.endswith("a") and "-" not in version_str:
        # Legacy format without hyphen (backward compatibility)
        parts = version_str.split("a")
        version_str = parts[0]
        prerelease_type = "alpha"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif "b" in version_str and not version_str.endswith("b") and "-" not in version_str:
        # Legacy format without hyphen (backward compatibility)
        parts = version_str.split("b")
        version_str = parts[0]
        prerelease_type = "beta"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif "rc" in version_str and "-" not in version_str:
        # Legacy format without hyphen (backward compatibility)
        parts = version_str.split("rc")
        version_str = parts[0]
        prerelease_type = "rc"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    
    # Parse version numbers
    version_parts = version_str.split(".")
    major = int(version_parts[0]) if len(version_parts) > 0 and version_parts[0].isdigit() else 0
    minor = int(version_parts[1]) if len(version_parts) > 1 and version_parts[1].isdigit() else 0
    patch = int(version_parts[2]) if len(version_parts) > 2 and version_parts[2].isdigit() else 0
    
    return (major, minor, patch, prerelease_type, prerelease_num)

__version_info__ = _parse_version(__version__)

def is_release_version() -> bool:
    """Check if current version is a release version (not a pre-release)."""
    _, _, _, prerelease_type, _ = __version_info__
    return prerelease_type == ""

def get_version_type() -> str:
    """Get version type: 'release', 'dev', 'alpha', 'beta', or 'rc'."""
    _, _, _, prerelease_type, _ = __version_info__
    return prerelease_type if prerelease_type else "release"
