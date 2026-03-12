#!/usr/bin/env python3
"""
tools/generate_bibtex.py — BibTeX Generator from Citation Vault
================================================================
Converts the Python citation vault (bibliography_engine.py) into a proper
.bib file for use with Pandoc --citeproc.

Also adds fluid dynamics and aerodynamics references not in the original vault.

Usage:
  python3 tools/generate_bibtex.py                    # Generate references.bib
  python3 tools/generate_bibtex.py --output custom.bib
"""

import sys
import re
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.bibliography_engine import CITATION_VAULT

# Additional references for water and air domains
FLUID_REFS = {
    "logg_2012": {
        "type": "book",
        "author": "Logg, Anders and Mardal, Kent-Andre and Wells, Garth",
        "title": "Automated Solution of Differential Equations by the Finite Element Method: The FEniCS Book",
        "publisher": "Springer",
        "year": "2012",
        "doi": "10.1007/978-3-642-23099-8",
    },
    "alnaes_2015": {
        "type": "article",
        "author": "Aln{\\ae}s, Martin S. and Blechta, Jan and Hake, Johan and others",
        "title": "The FEniCS Project Version 1.5",
        "journal": "Archive of Numerical Software",
        "volume": "3",
        "number": "100",
        "year": "2015",
        "doi": "10.11588/ans.2015.100.20553",
    },
    "scroggs_2022": {
        "type": "article",
        "author": "Scroggs, Matthew W. and Dokken, J{\\o}rgen S. and Richardson, Chris N. and Wells, Garth N.",
        "title": "Construction of Arbitrary Order Finite Element Degree-of-Freedom Maps on Polygonal and Polyhedral Cell Meshes",
        "journal": "ACM Transactions on Mathematical Software",
        "volume": "48",
        "number": "2",
        "year": "2022",
        "doi": "10.1145/3524456",
    },
    "john_2016": {
        "type": "book",
        "author": "John, Volker",
        "title": "Finite Element Methods for Incompressible Flow Problems",
        "publisher": "Springer",
        "year": "2016",
        "doi": "10.1007/978-3-319-45750-5",
    },
    "versteeg_2007": {
        "type": "book",
        "author": "Versteeg, Henk Kaarle and Malalasekera, Weeratunge",
        "title": "An Introduction to Computational Fluid Dynamics: The Finite Volume Method",
        "publisher": "Pearson Education",
        "year": "2007",
        "edition": "2nd",
    },
    "su2_2016": {
        "type": "article",
        "author": "Economon, Thomas D. and Palacios, Francisco and Copeland, Sean R. and others",
        "title": "SU2: An Open-Source Suite for Multiphysics Simulation and Design",
        "journal": "AIAA Journal",
        "volume": "54",
        "number": "3",
        "pages": "828--846",
        "year": "2016",
        "doi": "10.2514/1.J053813",
    },
    "simiu_2019": {
        "type": "book",
        "author": "Simiu, Emil and Yeo, DongHun",
        "title": "Wind Effects on Structures: Modern Structural Design for Wind",
        "publisher": "Wiley",
        "year": "2019",
        "edition": "4th",
    },
    "kareem_2020": {
        "type": "article",
        "author": "Kareem, Ahsan and Kwon, Dae Kun and Tamura, Yukio",
        "title": "Wind-Induced Vibration of Structures: A Historical and State-of-the-Art Review",
        "journal": "Journal of Wind Engineering and Industrial Aerodynamics",
        "volume": "206",
        "pages": "104336",
        "year": "2020",
        "doi": "10.1016/j.jweia.2020.104336",
    },
    "blocken_2015": {
        "type": "article",
        "author": "Blocken, Bert",
        "title": "Computational Fluid Dynamics for Urban Physics: Importance, Scales, Possibilities, Limitations and Ten Tips and Tricks Towards Accurate and Reliable Simulations",
        "journal": "Building and Environment",
        "volume": "91",
        "pages": "219--245",
        "year": "2015",
        "doi": "10.1016/j.buildenv.2015.02.015",
    },
    "chanson_2004": {
        "type": "book",
        "author": "Chanson, Hubert",
        "title": "The Hydraulics of Open Channel Flow: An Introduction",
        "publisher": "Butterworth-Heinemann",
        "year": "2004",
        "edition": "2nd",
    },
    "novak_2010": {
        "type": "book",
        "author": "Novak, Pavel and Moffat, A. I. B. and Nalluri, Chandra and Narayanan, R.",
        "title": "Hydraulic Structures",
        "publisher": "CRC Press",
        "year": "2010",
        "edition": "4th",
    },
    "dam_shm_2019": {
        "type": "article",
        "author": "Salazar, Fernando and Mor{\\'a}n, Rafael and Toledo, Miguel {\\'A}ngel and O{\\~n}ate, Eugenio",
        "title": "Data-Based Models for the Prediction of Dam Behaviour: A Review and Some Methodological Considerations",
        "journal": "Archives of Computational Methods in Engineering",
        "volume": "24",
        "number": "1",
        "pages": "1--21",
        "year": "2017",
        "doi": "10.1007/s11831-015-9157-9",
    },
}


def _parse_vault_entry(key: str, text: str) -> dict:
    """Parse a plain-text citation into BibTeX fields (best effort)."""
    entry = {"type": "misc", "note": text}

    # Try to extract author (everything before the year in parens)
    m = re.match(r"^(.+?)\s*\((\d{4})\)", text)
    if m:
        entry["author"] = m.group(1).rstrip(". ,")
        entry["year"] = m.group(2)

    # Try to extract title (text in single quotes)
    t = re.search(r"'(.+?)'", text)
    if t:
        entry["title"] = t.group(1)

    # Try to extract journal/book (text after closing quote, before volume/page)
    after_title = text[t.end():] if t else ""
    j = re.search(r"[.]\s*([A-Z][^,]+?)(?:,\s*\d|\.\s*$)", after_title)
    if j:
        journal = j.group(1).strip().rstrip(".")
        if journal and len(journal) > 5:
            entry["journal"] = journal
            entry["type"] = "article"

    # Volume/pages
    vp = re.search(r"(\d+)\((\d+)\),?\s*([\d-]+)", after_title)
    if vp:
        entry["volume"] = vp.group(1)
        entry["number"] = vp.group(2)
        entry["pages"] = vp.group(3)

    # URL
    url = re.search(r"https?://\S+", text)
    if url:
        entry["url"] = url.group(0).rstrip(".")

    return entry


def _format_bibtex_entry(key: str, fields: dict) -> str:
    """Format a single BibTeX entry."""
    entry_type = fields.pop("type", "misc")
    lines = [f"@{entry_type}{{{key},"]
    for field, value in fields.items():
        if field == "type" or value is None:
            continue
        lines.append(f"  {field} = {{{value}}},")
    lines.append("}\n")
    return "\n".join(lines)


def generate_bibtex(output_path: Path = None) -> str:
    """Generate complete .bib file content."""
    bib = "% AUTO-GENERATED by tools/generate_bibtex.py\n"
    bib += f"% Source: tools/bibliography_engine.py + fluid/air extensions\n"
    bib += f"% Total entries: {len(CITATION_VAULT) + len(FLUID_REFS)}\n\n"

    bib += "% ═══ Core Vault (from bibliography_engine.py) ═══\n\n"
    for key, text in CITATION_VAULT.items():
        fields = _parse_vault_entry(key, text)
        bib += _format_bibtex_entry(key, fields)

    bib += "\n% ═══ Fluid Dynamics & Aerodynamics Extensions ═══\n\n"
    for key, fields in FLUID_REFS.items():
        bib += _format_bibtex_entry(key, dict(fields))

    if output_path is None:
        output_path = ROOT / "articles" / "references.bib"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_text(bib, encoding="utf-8")
    except OSError as e:
        print(f"[BIBTEX] ERROR: Could not write {output_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[BIBTEX] Generated {output_path} ({len(CITATION_VAULT) + len(FLUID_REFS)} entries)")
    return bib


def main():
    parser = argparse.ArgumentParser(description="Generate BibTeX from citation vault")
    parser.add_argument("--output", type=str, default=None, help="Output .bib path")
    args = parser.parse_args()

    out = Path(args.output) if args.output else None
    generate_bibtex(out)


if __name__ == "__main__":
    main()
