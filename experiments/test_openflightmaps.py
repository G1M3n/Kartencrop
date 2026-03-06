from __future__ import annotations

import xml.etree.ElementTree as ET

from kartencrop.http import request_bytes


def inspect_publication_xml(url: str) -> None:
    result = request_bytes(url)
    print(f"status: {result.status_code}")
    print(f"content-type: {result.content_type}")
    print(f"size: {len(result.content)} bytes")

    if "xml" not in result.content_type.lower():
        print(result.content[:200].decode("utf-8", errors="replace"))
        return

    root = ET.fromstring(result.content)
    print(f"root: {root.tag}")
    print(f"children: {len(list(root))}")


if __name__ == "__main__":
    inspect_publication_xml("https://snapshots.openflightmaps.org/publicationServices/EFIN_2510.xml")
