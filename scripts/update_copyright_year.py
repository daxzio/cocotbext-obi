#!/usr/bin/env python3
"""
Pre-commit hook to update copyright years in file headers.
This script handles three formats:
1. Single year: "2024" -> "2024-<current_year>"
2. Range with dot: "2024.2025" -> "2024-<current_year>"
3. Range with dash: "2024-2025" -> "2024-<current_year>"
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence


def update_copyright_year(file_path: Path, current_year: int) -> bool:
    """
    Update copyright year in a file.

    Args:
        file_path: Path to the file to update
        current_year: Current year to update to

    Returns:
        True if file was modified, False otherwise
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Skip binary files
        return False

    # Pattern to match copyright lines with various year formats
    # Matches: Copyright (c) YYYY or Copyright (c) YYYY-YYYY or Copyright (c) YYYY.YYYY
    # But only if the line contains "Daxzio" and is likely a copyright header (not code)
    # Match lines that start with Copyright, or have # or // or /* before Copyright
    pattern = (
        r"^(\s*(?:#|//|/\*|\*)??\s*)(Copyright.*\(c\)\s*)(\d{4})([.-](\d{4}))?\s*(.*)"
    )

    modified = False
    lines = content.splitlines()
    new_lines = []

    for line in lines:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            comment_prefix = match.group(1)  # The comment characters (# // /* etc)
            copyright_prefix = match.group(2)  # "Copyright (c) "
            start_year = int(match.group(3))
            end_year_str = match.group(5)
            suffix = match.group(6)

            # Only update if the line contains "Daxzio"
            if "Daxzio" not in line:
                new_lines.append(line)
                continue

            # Determine the new copyright line
            if end_year_str:
                # Already has a range, update the end year
                new_line = f"{comment_prefix}{copyright_prefix}{start_year}-{current_year} {suffix}"
            else:
                # Single year, convert to range if not current year
                if start_year != current_year:
                    new_line = f"{comment_prefix}{copyright_prefix}{start_year}-{current_year} {suffix}"
                else:
                    new_line = line  # Keep as is if it's already current year

            if line != new_line:
                new_lines.append(new_line)
                modified = True
                print(f"Updated copyright in {file_path}:")
                print(f"  Old: {line}")
                print(f"  New: {new_line}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if modified:
        file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return modified


def should_process_file(file_path: Path) -> bool:
    """Determine if a file should be processed for copyright updates."""
    if not file_path.is_file():
        return False

    text_extensions = {
        ".py",
        ".js",
        ".ts",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".md",
        ".txt",
        ".rst",
        ".yml",
        ".yaml",
        ".json",
        ".xml",
        ".html",
        ".css",
        ".sh",
        ".bat",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".sv",
        ".v",
        ".vhd",
        ".vhdl",
    }

    if file_path.suffix.lower() in text_extensions:
        return True

    if not file_path.suffix:
        try:
            content = file_path.read_bytes()[:1024]
            if b"\x00" in content:
                return False
            content.decode("utf-8")
            return True
        except (UnicodeDecodeError, IOError):
            return False

    return False


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main function for the copyright year updater."""
    parser = argparse.ArgumentParser(
        description="Update copyright years in file headers"
    )
    parser.add_argument("filenames", nargs="*", help="Filenames to check and update")
    parser.add_argument(
        "--current-year",
        type=int,
        default=datetime.now().year,
        help="Current year to update to (default: current year)",
    )

    args = parser.parse_args(argv)

    modified_files = []

    for filename in args.filenames:
        file_path = Path(filename)

        if not should_process_file(file_path):
            continue

        if update_copyright_year(file_path, args.current_year):
            modified_files.append(filename)

    if modified_files:
        print(f"\nUpdated copyright years in {len(modified_files)} file(s):")
        for filename in modified_files:
            print(f"  - {filename}")
        return 1  # Return 1 to indicate files were modified

    return 0


if __name__ == "__main__":
    sys.exit(main())
