#!/usr/bin/env python3
"""
WeWantPeace Newsletter Renderer
--------------------------------
Renders the Handlebars template with data from a JSON file.

Usage:
    python render-newsletter.py --data vol1-us.json --output newsletter-rendered.html
    python render-newsletter.py --data vol1-kr.json --template newsletter-v1-final-ko.html

Template: newsletter-v1-final-en.html (default)
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import chevron
except ImportError:
    print("Error: chevron not installed. Run: pip install chevron")
    sys.exit(1)


def render(template_path: str, data_path: str, output_path: str) -> None:
    template_dir = Path(template_path).parent

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Resolve HTML block file references (e.g., "@file:blocks/tension_table.html")
    for key, value in list(data.items()):
        if isinstance(value, str) and value.startswith("@file:"):
            ref_path = template_dir / value[6:]
            if ref_path.exists():
                with open(ref_path, "r", encoding="utf-8") as f:
                    data[key] = f.read()
            else:
                print(f"Warning: referenced file not found: {ref_path}")

    rendered = chevron.render(template, data)

    # Check Gmail 102KB limit
    size_kb = len(rendered.encode("utf-8")) / 1024
    if size_kb > 102:
        print(f"WARNING: Output is {size_kb:.1f}KB — exceeds Gmail 102KB clip limit!")
    else:
        print(f"Size: {size_kb:.1f}KB (under 102KB limit)")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"Rendered: {output_path}")

    # Count unresolved variables
    import re
    unresolved = re.findall(r"\{\{[^}]+\}\}", rendered)
    if unresolved:
        unique = set(unresolved)
        print(f"WARNING: {len(unique)} unresolved variable(s): {', '.join(sorted(unique)[:10])}")


def main():
    parser = argparse.ArgumentParser(description="Render WeWantPeace newsletter")
    parser.add_argument(
        "--template",
        default="newsletter-v1-final-en.html",
        help="Handlebars template file (default: newsletter-v1-final-en.html)",
    )
    parser.add_argument("--data", required=True, help="JSON data file")
    parser.add_argument(
        "--output",
        default="newsletter-rendered.html",
        help="Output HTML file (default: newsletter-rendered.html)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    template_path = script_dir / args.template
    data_path = script_dir / args.data if not Path(args.data).is_absolute() else Path(args.data)
    output_path = script_dir / args.output if not Path(args.output).is_absolute() else Path(args.output)

    if not template_path.exists():
        print(f"Error: template not found: {template_path}")
        sys.exit(1)
    if not data_path.exists():
        print(f"Error: data file not found: {data_path}")
        sys.exit(1)

    render(str(template_path), str(data_path), str(output_path))


if __name__ == "__main__":
    main()
