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
    if "-dev" in version_str:
        parts = version_str.split("-dev")
        version_str = parts[0]
        prerelease_type = "dev"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif ".dev" in version_str:
        # Legacy format support
        parts = version_str.split(".dev")
        version_str = parts[0]
        prerelease_type = "dev"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif "a" in version_str and not version_str.endswith("a"):
        parts = version_str.split("a")
        version_str = parts[0]
        prerelease_type = "alpha"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif "b" in version_str and not version_str.endswith("b"):
        parts = version_str.split("b")
        version_str = parts[0]
        prerelease_type = "beta"
        prerelease_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    elif "rc" in version_str:
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


def increment_version(
    current_version: str,
    bump_type: str,
    prerelease_type: str | None = None,
) -> str:
    """Increment version based on bump type.
    
    Args:
        current_version: Current version string
        bump_type: 'major', 'minor', or 'patch'
        prerelease_type: Optional prerelease type ('dev', 'alpha', 'beta', 'rc')
    
    Returns:
        New version string
    """
    major, minor, patch, current_prerelease_type, current_prerelease_num = parse_version(current_version)
    
    # If current version is a prerelease, remove prerelease marker first
    if current_prerelease_type:
        # Already a prerelease, increment the prerelease number if same type
        if prerelease_type == current_prerelease_type:
            if prerelease_type == "dev":
                return f"{major}.{minor}.{patch}-dev{current_prerelease_num + 1}"
            elif prerelease_type == "alpha":
                return f"{major}.{minor}.{patch}a{current_prerelease_num + 1}"
            elif prerelease_type == "beta":
                return f"{major}.{minor}.{patch}b{current_prerelease_num + 1}"
            elif prerelease_type == "rc":
                return f"{major}.{minor}.{patch}rc{current_prerelease_num + 1}"
        # Different prerelease type, use base version
        pass
    
    # Increment version based on bump type
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")
    
    # Add prerelease marker if specified
    if prerelease_type:
        if prerelease_type == "dev":
            return f"{major}.{minor}.{patch}-dev1"
        elif prerelease_type == "alpha":
            return f"{major}.{minor}.{patch}a1"
        elif prerelease_type == "beta":
            return f"{major}.{minor}.{patch}b1"
        elif prerelease_type == "rc":
            return f"{major}.{minor}.{patch}rc1"
        else:
            raise ValueError(f"Invalid prerelease type: {prerelease_type}")
    
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
    
    For prerelease versions, use '-' instead of '.' in tag (e.g., v1.2.1-a1).
    Dev versions are NOT tagged (only committed).
    """
    # Check if this is a dev version - don't create tags for dev versions
    if "-dev" in version or ".dev" in version:
        if dry_run:
            print(f"[DRY RUN] Would skip tag creation for dev version: {version}")
        else:
            print(f"Skipping tag creation for dev version: {version}")
        return
    
    # Convert version to tag format
    # For prerelease: 1.2.1a1 -> v1.2.1-a1, 1.2.1b1 -> v1.2.1-b1, 1.2.1rc1 -> v1.2.1-rc1
    tag_version = version
    if "a" in tag_version and not tag_version.endswith("a"):
        tag_version = tag_version.replace("a", "-a", 1)
    elif "b" in tag_version and not tag_version.endswith("b"):
        tag_version = tag_version.replace("b", "-b", 1)
    elif "rc" in tag_version:
        tag_version = tag_version.replace("rc", "-rc")
    
    tag = f"v{tag_version}"
    
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
    """
    # Check if this is a dev version - don't push tags for dev versions
    is_dev = "-dev" in version or ".dev" in version
    
    if dry_run:
        if is_dev:
            print(f"[DRY RUN] Would push commits only (no tag) for dev version: {version}")
        else:
            tag_version = version
            if "a" in tag_version and not tag_version.endswith("a"):
                tag_version = tag_version.replace("a", "-a", 1)
            elif "b" in tag_version and not tag_version.endswith("b"):
                tag_version = tag_version.replace("b", "-b", 1)
            elif "rc" in tag_version:
                tag_version = tag_version.replace("rc", "-rc")
            tag = f"v{tag_version}"
            print(f"[DRY RUN] Would push commits and tag {tag} to GitHub")
        return
    
    # Push commits
    subprocess.run(["git", "push"], check=True)
    
    if is_dev:
        print(f"Pushed commits to GitHub (no tag for dev version)")
    else:
        # Convert version to tag format and push tag
        tag_version = version
        if "a" in tag_version and not tag_version.endswith("a"):
            tag_version = tag_version.replace("a", "-a", 1)
        elif "b" in tag_version and not tag_version.endswith("b"):
            tag_version = tag_version.replace("b", "-b", 1)
        elif "rc" in tag_version:
            tag_version = tag_version.replace("rc", "-rc")
        tag = f"v{tag_version}"
        subprocess.run(["git", "push", "origin", tag], check=True)
        print(f"Pushed to GitHub (tag: {tag})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new release")
    parser.add_argument(
        "--patch",
        action="store_true",
        help="Increment patch version (1.2.0 -> 1.2.1)",
    )
    parser.add_argument(
        "--minor",
        action="store_true",
        help="Increment minor version (1.2.0 -> 1.3.0)",
    )
    parser.add_argument(
        "--major",
        action="store_true",
        help="Increment major version (1.2.0 -> 2.0.0)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Create development version (e.g., 1.2.1-dev1). Dev versions are committed but NOT tagged.",
    )
    parser.add_argument(
        "--alpha",
        action="store_true",
        help="Create alpha version (e.g., 1.2.1a1)",
    )
    parser.add_argument(
        "--beta",
        action="store_true",
        help="Create beta version (e.g., 1.2.1b1)",
    )
    parser.add_argument(
        "--rc",
        action="store_true",
        help="Create release candidate (e.g., 1.2.1rc1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()
    
    # Determine bump type
    bump_types = [args.patch, args.minor, args.major]
    if sum(bump_types) != 1:
        parser.error("Exactly one of --patch, --minor, or --major must be specified")
    
    bump_type = "patch" if args.patch else ("minor" if args.minor else "major")
    
    # Determine prerelease type
    prerelease_types = [args.dev, args.alpha, args.beta, args.rc]
    prerelease_type = None
    if sum(prerelease_types) > 1:
        parser.error("Only one prerelease type can be specified")
    elif args.dev:
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
        new_version = increment_version(current_version, bump_type, prerelease_type)
        print(f"New version: {new_version}")
        
        if args.dry_run:
            print("\n[DRY RUN MODE - No changes will be made]\n")
        
        # Validate git status
        if not args.dry_run:
            check_git_status()
            print("✓ Git repository is clean")
        
        # Check changelog (only for release versions, not prereleases)
        if not prerelease_type and not args.dry_run:
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
            if prerelease_type == "dev":
                print(f"\n✓ Dev version {new_version} committed successfully!")
                print("(No tag created for dev versions)")
            else:
                print(f"\n✓ Release {new_version} created successfully!")
                print("GitHub Actions will automatically create a release.")
        else:
            print("\n[DRY RUN] No changes were made.")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

