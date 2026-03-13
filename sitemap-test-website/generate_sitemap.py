"""Generate a standard sitemap.xml and optionally update robots.txt."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
import xml.etree.ElementTree as ET


NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
ET.register_namespace("", NAMESPACE)


@dataclass(frozen=True)
class SitemapEntry:
    path: str
    changefreq: str
    priority: str


ENTRIES = [
    SitemapEntry("/index.html", "weekly", "1.0"),
    SitemapEntry("/products/index.html", "monthly", "0.8"),
    SitemapEntry("/features/index.html", "monthly", "0.8"),
    SitemapEntry("/standards/index.html", "monthly", "0.8"),
    SitemapEntry("/products/claude-opus.html", "monthly", "0.6"),
    SitemapEntry("/products/claude-sonnet.html", "monthly", "0.6"),
    SitemapEntry("/products/claude-haiku.html", "monthly", "0.6"),
    SitemapEntry("/features/extended-thinking.html", "monthly", "0.6"),
    SitemapEntry("/features/computer-use.html", "monthly", "0.6"),
    SitemapEntry("/features/tool-use.html", "monthly", "0.6"),
    SitemapEntry("/standards/mcp.html", "monthly", "0.6"),
    SitemapEntry("/standards/model-spec.html", "monthly", "0.6"),
    SitemapEntry("/standards/system-prompts.html", "monthly", "0.6"),
    SitemapEntry("/standards/skills.html", "monthly", "0.6"),
]


def normalize_base_url(base_url: str) -> str:
    cleaned = base_url.strip()
    if not cleaned:
        raise ValueError("base URL cannot be empty")
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    return cleaned.rstrip("/") + "/"


def indent_xml(element: ET.Element, level: int = 0) -> None:
    indent = "\n" + "  " * level
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + "  "
        for child in element:
            indent_xml(child, level + 1)
        if not element[-1].tail or not element[-1].tail.strip():
            element[-1].tail = indent
    elif level and (not element.tail or not element.tail.strip()):
        element.tail = indent


def build_sitemap(base_url: str, lastmod: str) -> ET.ElementTree:
    root = ET.Element(f"{{{NAMESPACE}}}urlset")
    for entry in ENTRIES:
        url_elem = ET.SubElement(root, f"{{{NAMESPACE}}}url")
        ET.SubElement(url_elem, f"{{{NAMESPACE}}}loc").text = urljoin(base_url, entry.path.lstrip("/"))
        ET.SubElement(url_elem, f"{{{NAMESPACE}}}lastmod").text = lastmod
        ET.SubElement(url_elem, f"{{{NAMESPACE}}}changefreq").text = entry.changefreq
        ET.SubElement(url_elem, f"{{{NAMESPACE}}}priority").text = entry.priority
    indent_xml(root)
    return ET.ElementTree(root)


def write_robots_txt(robots_path: Path, base_url: str) -> None:
    robots_path.write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {urljoin(base_url, 'sitemap.xml')}\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate sitemap.xml with absolute URLs for a target domain.",
    )
    parser.add_argument(
        "base_url",
        nargs="?",
        default="https://lawrence565.github.io/test_toolbox",
        help="Base URL used in <loc> entries, for example https://abc.tunnelmole.net",
    )
    parser.add_argument(
        "--output",
        default="sitemap.xml",
        help="Path to the generated sitemap file. Default: sitemap.xml",
    )
    parser.add_argument(
        "--lastmod",
        default=date.today().isoformat(),
        help="Date written to <lastmod>. Default: today's date",
    )
    parser.add_argument(
        "--update-robots",
        action="store_true",
        help="Also rewrite robots.txt so its Sitemap line matches the base URL.",
    )
    parser.add_argument(
        "--robots-output",
        default="robots.txt",
        help="Path to robots.txt when --update-robots is used. Default: robots.txt",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_url = normalize_base_url(args.base_url)
    output_path = Path(args.output)

    sitemap_tree = build_sitemap(base_url, args.lastmod)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sitemap_tree.write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"Generated {output_path} with base URL {base_url}")

    if args.update_robots:
        robots_path = Path(args.robots_output)
        robots_path.parent.mkdir(parents=True, exist_ok=True)
        write_robots_txt(robots_path, base_url)
        print(f"Updated {robots_path}")


if __name__ == "__main__":
    main()