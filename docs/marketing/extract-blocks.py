#!/usr/bin/env python3
"""
Extract HTML blocks from a rendered newsletter to create block files.
These block files can be referenced in data JSON with @file: prefix.

Usage:
    python extract-blocks.py --source newsletter-v1-final-en-us.html --prefix vol1-us
"""

import argparse
import re
import sys
from pathlib import Path


def extract_between(html: str, start_marker: str, end_marker: str) -> str:
    """Extract content between two markers (not including markers)."""
    start_idx = html.find(start_marker)
    if start_idx == -1:
        return ""
    start_idx += len(start_marker)
    end_idx = html.find(end_marker, start_idx)
    if end_idx == -1:
        return html[start_idx:]
    return html[start_idx:end_idx]


def extract_section(lines: list[str], start_line: int, end_line: int) -> str:
    """Extract lines from start_line to end_line (1-indexed, inclusive)."""
    return "\n".join(lines[start_line - 1 : end_line])


def main():
    parser = argparse.ArgumentParser(description="Extract HTML blocks from newsletter")
    parser.add_argument("--source", required=True, help="Source rendered HTML file")
    parser.add_argument("--prefix", default="vol1", help="Output file prefix")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    source_path = script_dir / args.source
    blocks_dir = script_dir / "blocks"
    blocks_dir.mkdir(exist_ok=True)

    if not source_path.exists():
        print(f"Error: source not found: {source_path}")
        sys.exit(1)

    with open(source_path, "r", encoding="utf-8") as f:
        html = f.read()

    lines = html.split("\n")

    # Define extraction ranges based on EN-US file line numbers
    # These are approximate and may need adjustment per file
    blocks = {}

    # Today's Brief items: 3 <tr> blocks with headlines
    brief_start = None
    brief_end = None
    for i, line in enumerate(lines):
        if 'class="r6 br pe bE"' in line and brief_start is None:
            brief_start = i
        if "IN THIS ISSUE" in line:
            brief_end = i - 2
            break
    if brief_start and brief_end:
        blocks["todays-brief"] = "\n".join(lines[brief_start : brief_end + 1])

    # Tension table
    tension_start = None
    tension_end = None
    for i, line in enumerate(lines):
        if "COUNTRY</td>" in line and "SCORE" in lines[i + 1] if i + 1 < len(lines) else False:
            tension_start = i - 1
        if "Tension Index = density" in line:
            tension_end = i - 2
            break
    if tension_start and tension_end:
        blocks["tension-table"] = "\n".join(lines[tension_start : tension_end + 1])

    # Conflict stories: from first TOP STORY to "All XXX active issues"
    conflict_start = None
    conflict_end = None
    for i, line in enumerate(lines):
        if "TOP STORY" in line and conflict_start is None:
            # Go back to find the <tr> that contains this
            for j in range(i, max(i - 5, 0), -1):
                if "<tr>" in lines[j] or "<td" in lines[j]:
                    conflict_start = j
                    break
            if conflict_start is None:
                conflict_start = i - 3
        if "active issues" in line and conflict_start is not None:
            # Go back to find </td></tr> before this
            for j in range(i, max(i - 5, 0), -1):
                if "</table>" in lines[j]:
                    conflict_end = j + 3
                    break
            break
    if conflict_start and conflict_end:
        blocks["conflicts"] = "\n".join(lines[conflict_start : conflict_end + 1])

    # Energy section intro
    for i, line in enumerate(lines):
        if "Oil from $95" in line or "유가 $95" in line or "$95 to" in line:
            blocks["energy-intro"] = lines[i].strip()
            break

    # Energy section (breaking card + analysis + quote)
    energy_start = None
    energy_end = None
    for i, line in enumerate(lines):
        if "BREAKING" in line and "Severity" in line:
            for j in range(i, max(i - 10, 0), -1):
                if "<tr>" in lines[j]:
                    energy_start = j
                    break
        if "DEEP DIVE" in line and energy_start is not None:
            for j in range(i, max(i - 5, 0), -1):
                if "</tr>" in lines[j]:
                    energy_end = j
                    break
            break
    if energy_start and energy_end:
        blocks["energy"] = "\n".join(lines[energy_start : energy_end + 1])

    # Deep dive section
    deep_start = None
    deep_end = None
    for i, line in enumerate(lines):
        if "Strait of Hormuz" in line and 'alt=' in line:
            deep_start = i - 3
        if "YOUR COUNTRY" in line and deep_start is not None:
            deep_end = i - 5
            break
    if deep_start and deep_end:
        blocks["deep-dive"] = "\n".join(lines[deep_start : deep_end + 1])

    # Write extracted blocks
    for name, content in blocks.items():
        out_path = blocks_dir / f"{args.prefix}-{name}.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        size = len(content.encode("utf-8"))
        print(f"  {name}: {size:,} bytes → {out_path.name}")

    # List blocks that need manual extraction
    all_needed = [
        "tension-table", "todays-brief", "conflicts", "energy-intro", "energy",
        "deep-dive", "country-issues", "country-impact", "did-you-know",
        "travel-intro", "travel", "numbers", "calendar", "editors-note", "next-week"
    ]
    missing = [b for b in all_needed if b not in blocks]
    if missing:
        print(f"\nBlocks needing manual extraction ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")

    print(f"\nExtracted {len(blocks)}/{len(all_needed)} blocks")


if __name__ == "__main__":
    main()
