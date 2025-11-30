#!/usr/bin/env python3
"""
Automated release script for HomeConnect Coffee.

Increments version, creates git tag, and pushes to GitHub.
GitHub Actions will automatically create a release.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def get_current_version() -> str:
    """Read current version from VERSION file."""
    version_file = Path(__file__).parent.parent / "VERSION"
    if not version_file.exists():
        raise FileNotFoundError("VERSION file not found")
    return version_file.read_text(encoding="utf-8").strip()


def write_version(version: str) -> None:
    """Write version to VERSION file."""
    version_file = Path(__file__).parent.parent / "VERSION"
    version_file.write_text(f"{version}\n", encoding="utf-8")


def parse_version(version_str: str) -> tuple[int, int, int, str, int]:
    """Parse version string into components.
    
    Returns: (major, minor, patch, prerelease_type, prerelease_num)
    """
    version_str = version_str.strip()
    
    prerelease_type = ""
    prerelease_num = 0
    
    # Extract prerelease info
    # Support both formats: with hyphen (1.2.1-b2) and without (1.2.1b2) for backward compatibility
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


def remove_prerelease_suffix(version: str) -> str:
    """Remove prerelease suffix from version (e.g., 1.2.1-b3 -> 1.2.1).
    
    Args:
        version: Version string with optional prerelease suffix
    
    Returns:
        Version string without prerelease suffix
    """
    major, minor, patch, _, _ = parse_version(version)
    return f"{major}.{minor}.{patch}"


def increment_version(
    current_version: str,
    prerelease_type: str | None = None,
) -> str:
    """Increment version for prerelease types.
    
    For release (no prerelease_type), use remove_prerelease_suffix() instead.
    
    Args:
        current_version: Current version string
        prerelease_type: Prerelease type ('dev', 'alpha', 'beta', 'rc')
    
    Returns:
        New version string with prerelease suffix
    """
    major, minor, patch, current_prerelease_type, current_prerelease_num = parse_version(current_version)
    
    # If current version is a prerelease, increment the prerelease number if same type
    if current_prerelease_type and prerelease_type == current_prerelease_type:
        if prerelease_type == "dev":
            # Dev versions don't have numbers, just return the same
            return f"{major}.{minor}.{patch}-dev"
        elif prerelease_type == "alpha":
            return f"{major}.{minor}.{patch}-a{current_prerelease_num + 1}"
        elif prerelease_type == "beta":
            return f"{major}.{minor}.{patch}-b{current_prerelease_num + 1}"
        elif prerelease_type == "rc":
            return f"{major}.{minor}.{patch}-rc{current_prerelease_num + 1}"
    
    # Add prerelease marker to base version
    if prerelease_type:
        if prerelease_type == "dev":
            return f"{major}.{minor}.{patch}-dev"
        elif prerelease_type == "alpha":
            return f"{major}.{minor}.{patch}-a1"
        elif prerelease_type == "beta":
            return f"{major}.{minor}.{patch}-b1"
        elif prerelease_type == "rc":
            return f"{major}.{minor}.{patch}-rc1"
        else:
            raise ValueError(f"Invalid prerelease type: {prerelease_type}")
    
    # No prerelease type specified - this shouldn't happen in normal flow
    return f"{major}.{minor}.{patch}"


def check_git_status() -> None:
    """Check that git repository is clean and on correct branch."""
    # Check if we're in a git repository
    try:
        subprocess.run(["git", "status"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        raise RuntimeError("Not in a git repository")
    except FileNotFoundError:
        raise RuntimeError("git command not found")
    
    # Check for uncommitted changes
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    if result.stdout.strip():
        raise RuntimeError("Uncommitted changes detected. Please commit or stash them first.")
    
    # Check branch (should be main or master)
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    )
    branch = result.stdout.strip()
    if branch not in ("main", "master"):
        raise RuntimeError(f"Not on main/master branch (current: {branch})")


def check_changelog(version: str) -> None:
    """Check that CHANGELOG.md contains the new version."""
    changelog_file = Path(__file__).parent.parent / "CHANGELOG.md"
    if not changelog_file.exists():
        raise FileNotFoundError("CHANGELOG.md not found")
    
    changelog_content = changelog_file.read_text(encoding="utf-8")
    
    # Check for version in changelog (format: ## [1.2.0] or ## [1.2.0] - date)
    version_pattern = rf"##\s*\[{re.escape(version)}\]"
    if not re.search(version_pattern, changelog_content):
        raise RuntimeError(
            f"CHANGELOG.md does not contain version {version}. "
            "Please update CHANGELOG.md before releasing."
        )


def create_git_tag(version: str, dry_run: bool = False) -> None:
    """Create git tag for version.
    
    Dev versions are NOT tagged (only committed).
    Pre-release versions already use hyphen format (e.g., 1.2.1-b2).
    """
    # Check if this is a dev version - don't create tags for dev versions
    if "-dev" in version or ".dev" in version:
        if dry_run:
            print(f"[DRY RUN] Would skip tag creation for dev version: {version}")
        else:
            print(f"Skipping tag creation for dev version: {version}")
        return
    
    # Version already uses hyphen format, just add 'v' prefix
    tag = f"v{version}"
    
    if dry_run:
        print(f"[DRY RUN] Would create tag: {tag}")
        return
    
    # Check if tag already exists
    result = subprocess.run(
        ["git", "tag", "-l", tag],
        capture_output=True,
        text=True,
        check=True,
    )
    if result.stdout.strip():
        raise RuntimeError(f"Tag {tag} already exists")
    
    # Create tag
    subprocess.run(["git", "tag", tag], check=True)
    print(f"Created tag: {tag}")


def commit_version(version: str, dry_run: bool = False) -> None:
    """Commit VERSION file changes."""
    if dry_run:
        print(f"[DRY RUN] Would commit VERSION file with version {version}")
        return
    
    subprocess.run(["git", "add", "VERSION"], check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Bump version to {version}"],
        check=True,
    )
    print(f"Committed version {version}")


def push_to_github(version: str, dry_run: bool = False) -> None:
    """Push commits and tags to GitHub.
    
    Dev versions only push commits, no tags.
    Version already uses hyphen format, so tag is just v{version}.
    """
    # Check if this is a dev version - don't push tags for dev versions
    is_dev = "-dev" in version or ".dev" in version
    
    if dry_run:
        if is_dev:
            print(f"[DRY RUN] Would push commits only (no tag) for dev version: {version}")
        else:
            tag = f"v{version}"
            print(f"[DRY RUN] Would push commits and tag {tag} to GitHub")
        return
    
    # Push commits
    subprocess.run(["git", "push"], check=True)
    
    if is_dev:
        print(f"Pushed commits to GitHub (no tag for dev version)")
    else:
        # Version already uses hyphen format, just add 'v' prefix
        tag = f"v{version}"
        subprocess.run(["git", "push", "origin", tag], check=True)
        print(f"Pushed to GitHub (tag: {tag})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new release or prerelease")
    parser.add_argument(
        "--release",
        action="store_true",
        help="Create a release by removing prerelease suffix (e.g., 1.2.1-b3 -> 1.2.1)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Create development version (e.g., 1.2.1-dev). Dev versions are committed but NOT tagged. "
             "Note: Dev versions are automatically created after each release, so manual creation is rarely needed.",
    )
    parser.add_argument(
        "--alpha",
        action="store_true",
        help="Create alpha version (e.g., 1.2.1-a1)",
    )
    parser.add_argument(
        "--beta",
        action="store_true",
        help="Create beta version (e.g., 1.2.1-b1)",
    )
    parser.add_argument(
        "--rc",
        action="store_true",
        help="Create release candidate (e.g., 1.2.1-rc1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()
    
    # Determine action type
    action_types = [args.release, args.dev, args.alpha, args.beta, args.rc]
    if sum(action_types) != 1:
        parser.error("Exactly one of --release, --dev, --alpha, --beta, or --rc must be specified")
    
    # Determine prerelease type (None for release)
    prerelease_type = None
    if args.dev:
        prerelease_type = "dev"
    elif args.alpha:
        prerelease_type = "alpha"
    elif args.beta:
        prerelease_type = "beta"
    elif args.rc:
        prerelease_type = "rc"
    
    try:
        # Get current version
        current_version = get_current_version()
        print(f"Current version: {current_version}")
        
        # Calculate new version
        if args.release:
            # Remove prerelease suffix
            new_version = remove_prerelease_suffix(current_version)
            # Check if version already has no suffix
            major, minor, patch, current_prerelease_type, _ = parse_version(current_version)
            if not current_prerelease_type:
                parser.error(f"Current version {current_version} is already a release version. Use prerelease types (--alpha, --beta, --rc) to create prereleases.")
        else:
            # Add or increment prerelease suffix
            new_version = increment_version(current_version, prerelease_type)
        print(f"New version: {new_version}")
        
        if args.dry_run:
            print("\n[DRY RUN MODE - No changes will be made]\n")
        
        # Validate git status
        if not args.dry_run:
            check_git_status()
            print("✓ Git repository is clean")
        
        # Check changelog (only for release versions, not prereleases)
        if args.release and not args.dry_run:
            check_changelog(new_version)
            print(f"✓ CHANGELOG.md contains version {new_version}")
        
        # Update VERSION file
        if args.dry_run:
            print(f"[DRY RUN] Would update VERSION file to {new_version}")
        else:
            write_version(new_version)
            print(f"✓ Updated VERSION file to {new_version}")
        
        # Commit changes
        if not args.dry_run:
            commit_version(new_version, dry_run=args.dry_run)
        
        # Create tag (skipped for dev versions)
        create_git_tag(new_version, dry_run=args.dry_run)
        
        # Push to GitHub
        if not args.dry_run:
            push_to_github(new_version, dry_run=args.dry_run)
            if args.release:
                print(f"\n✓ Release {new_version} created successfully!")
                print("GitHub Actions will automatically create a release.")
                print("After successful release, GitHub Actions will create the next dev version.")
            elif prerelease_type == "dev":
                print(f"\n✓ Dev version {new_version} committed successfully!")
                print("(No tag created for dev versions)")
            else:
                print(f"\n✓ Pre-release {new_version} created successfully!")
                print("GitHub Actions will automatically create a pre-release.")
        else:
            print("\n[DRY RUN] No changes were made.")
            if args.release:
                # Show what would happen after release
                major, minor, patch, _, _ = parse_version(new_version)
                next_dev_version = f"{major}.{minor}.{patch + 1}-dev"
                print(f"[DRY RUN] After release, GitHub Actions would create dev version: {next_dev_version}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

