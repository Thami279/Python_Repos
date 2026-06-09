#!/usr/bin/env python3
"""Weekly Neuroradiology Journal Digest Generator.

Queries PubMed for articles from the past 7 days across target journals,
filters for neuroradiology relevance, then uses Claude to generate
practical 2-3 sentence summaries and rank the top 3 papers.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
from xml.etree import ElementTree as ET

import anthropic
import requests

# ---------------------------------------------------------------------------
# Journal definitions
# AJNR Clinical Practice is a specific article category within AJNR;
# we capture it by fetching all AJNR articles then separating by type.
# ---------------------------------------------------------------------------
JOURNALS = {
    "ajnr": {
        "display": "AJNR: American Journal of Neuroradiology",
        "pubmed_ta": "AJNR Am J Neuroradiol",
    },
    "neuroimaging_clinics": {
        "display": "Neuroimaging Clinics of North America",
        "pubmed_ta": "Neuroimaging Clin N Am",
    },
    "radiographics": {
        "display": "RadioGraphics",
        "pubmed_ta": "Radiographics",
    },
}

# PubMed publication types that map to AJNR Clinical Practice bucket
CLINICAL_PRACTICE_TYPES = {
    "Case Reports",
    "Clinical Trial",
    "Technical Report",
    "Evaluation Study",
    "Validation Study",
    "Observational Study",
    "Multicenter Study",
    "Comparative Study",
}

NEURORADIOLOGY_KEYWORDS = [
    "brain", "cerebr", "intracranial", "cranial", "skull", "meninges",
    "spine", "spinal", "myelopathy", "radiculopathy", "disc herniation",
    "spinal cord", "vertebr",
    "head and neck", "temporal bone", "orbit", "sinonasal", "paranasal",
    "pituitary", "sellar", "suprasellar", "sella",
    "posterior fossa", "cerebellum", "brainstem", "ventricular", "hydrocephalus",
    "glioma", "glioblastoma", "meningioma", "astrocytoma", "ependymoma",
    "lymphoma", "metastasis", "metastases",
    "stroke", "ischemic", "hemorrhage", "hemorrhagic", "infarct",
    "aneurysm", "arteriovenous", "malformation", "cavernoma", "cavernous",
    "white matter", "leukoencephalopathy", "demyelination",
    "multiple sclerosis", "neuromyelitis",
    "dementia", "alzheimer", "frontotemporal", "lewy body",
    "parkinson", "huntington", "neurodegeneration",
    "epilepsy", "seizure",
    "neuro", "neuroimaging",
    "diffusion", "perfusion", "flair", "susceptibility", "dwi", "dti",
    "mri", "mr imaging", "ct scan", "computed tomography",
    "spectroscopy", "functional mri", "fmri", "bold",
]

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "digest-bot@github-actions.local")
NCBI_TOOL = "neuroradiology-weekly-digest"


# ---------------------------------------------------------------------------
# PubMed fetching
# ---------------------------------------------------------------------------

def _ncbi_params(**kwargs) -> dict:
    return {"email": NCBI_EMAIL, "tool": NCBI_TOOL, **kwargs}


def fetch_journal_articles(pubmed_ta: str, days_back: int = 7) -> list[dict]:
    """Return all articles from *pubmed_ta* published in the last *days_back* days."""
    end = datetime.now()
    start = end - timedelta(days=days_back)
    date_range = f"{start.strftime('%Y/%m/%d')}:{end.strftime('%Y/%m/%d')}[dp]"

    query = f'"{pubmed_ta}"[ta] AND {date_range}'

    # --- eSearch ---
    try:
        resp = requests.get(
            f"{PUBMED_BASE}/esearch.fcgi",
            params=_ncbi_params(db="pubmed", term=query, retmax=200, retmode="json"),
            timeout=30,
        )
        resp.raise_for_status()
        pmids = resp.json().get("esearchresult", {}).get("idlist", [])
    except Exception as exc:
        print(f"  [eSearch error] {exc}", file=sys.stderr)
        return []

    if not pmids:
        return []

    time.sleep(0.4)  # NCBI courtesy rate-limit

    # --- eFetch ---
    try:
        resp = requests.get(
            f"{PUBMED_BASE}/efetch.fcgi",
            params=_ncbi_params(db="pubmed", id=",".join(pmids), retmode="xml"),
            timeout=60,
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"  [eFetch error] {exc}", file=sys.stderr)
        return []

    return _parse_xml(resp.text)


def _parse_xml(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        print(f"  [XML parse error] {exc}", file=sys.stderr)
        return []

    articles = []
    for elem in root.findall(".//PubmedArticle"):
        article = _extract(elem)
        if article:
            articles.append(article)
    return articles


def _extract(elem) -> Optional[dict]:
    medline = elem.find(".//MedlineCitation")
    if medline is None:
        return None
    art = medline.find(".//Article")
    if art is None:
        return None

    # Title
    t = art.find(".//ArticleTitle")
    title = "".join(t.itertext()).strip() if t is not None else "Untitled"

    # Abstract
    abstract = " ".join(
        "".join(a.itertext()) for a in art.findall(".//AbstractText")
    ).strip()

    # Date  (prefer MedlineDate fallback)
    pub = art.find(".//PubDate")
    if pub is not None:
        year = pub.findtext("Year", "")
        month = pub.findtext("Month", "")
        day = pub.findtext("Day", "")
        date_str = " ".join(filter(None, [year, month, day])) or pub.findtext("MedlineDate", "Unknown")
    else:
        date_str = "Unknown"

    # Article types (publication types)
    pub_types = [pt.text for pt in art.findall(".//PublicationType") if pt.text]

    # PMID
    pmid_elem = medline.find("PMID")
    pmid = pmid_elem.text if pmid_elem is not None else None

    # DOI  (preferred link)
    doi = None
    for id_elem in elem.findall(".//ArticleId"):
        if id_elem.get("IdType") == "doi":
            doi = id_elem.text
            break

    link = (
        f"https://doi.org/{doi}"
        if doi
        else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None)
    )

    # Journal
    j = art.find(".//Journal/Title")
    journal_name = j.text.strip() if j is not None else "Unknown"

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "date": date_str,
        "pub_types": pub_types,
        "journal": journal_name,
        "link": link,
        "doi": doi,
    }


# ---------------------------------------------------------------------------
# Relevance filtering
# ---------------------------------------------------------------------------

def is_neuroradiology_relevant(article: dict) -> bool:
    text = (article.get("title", "") + " " + article.get("abstract", "")).lower()
    return any(kw in text for kw in NEURORADIOLOGY_KEYWORDS)


def classify_ajnr_type(article: dict) -> str:
    """Distinguish AJNR research vs. clinical practice articles by pub_type."""
    types = set(article.get("pub_types", []))
    if types & CLINICAL_PRACTICE_TYPES:
        return "clinical_practice"
    return "research"


# ---------------------------------------------------------------------------
# Digest generation via Claude
# ---------------------------------------------------------------------------

def generate_digest(articles_payload: dict) -> str:
    """Call Claude to write the formatted digest markdown."""
    client = anthropic.Anthropic()

    prompt = f"""You are a senior neuroradiologist creating a weekly journal digest for practicing neuroradiologists.

Today's date: {datetime.now().strftime('%B %d, %Y')}
Coverage period: past 7 days

Below is JSON containing newly published neuroradiology-relevant articles, organised by source:

{json.dumps(articles_payload, indent=2)}

Write a well-formatted weekly digest in markdown. Use exactly this structure:

---
# Weekly Neuroradiology Digest
**{datetime.now().strftime('%B %d, %Y')} | Past 7 Days**
---

## AJNR: American Journal of Neuroradiology
For each article under this journal:
- **[Article Title](link)** — *Article Type* | *Date*
  [2–3 sentence practical summary: what was studied, key finding, and direct clinical implication for a working neuroradiologist. Avoid generic filler.]

If none: > No relevant new items found this week.

## AJNR: Clinical Practice
(Articles from AJNR that are case reports, clinical trials, technical reports, or practice-focused)
Same format as above.
If none: > No relevant new items found this week.

## Neuroimaging Clinics of North America
Same format as above.
If none: > No relevant new items found this week.

## RadioGraphics
Same format as above.
If none: > No relevant new items found this week.

---

## Most Practice-Relevant This Week

**Rank 1 — [Journal]**
**[Title](link)**
*Why it matters:* [1–2 sentences on direct impact on daily neuroradiology practice]

**Rank 2 — [Journal]**
**[Title](link)**
*Why it matters:* [1–2 sentences]

**Rank 3 — [Journal]**
**[Title](link)**
*Why it matters:* [1–2 sentences]

---

Rules:
- Do not duplicate any article across sections.
- Prioritise original research and high-impact findings over editorials/letters.
- The "Most Practice-Relevant" ranking should reflect immediate clinical utility, not academic novelty.
- If total articles across all journals is 0, state that clearly in each section and skip the ranking section.
- Keep summaries clinically grounded. No marketing language.
"""

    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    print(f"Weekly Neuroradiology Digest — {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 60)

    payload: dict[str, list[dict]] = {
        "ajnr_research": [],
        "ajnr_clinical_practice": [],
        "neuroimaging_clinics": [],
        "radiographics": [],
    }

    for key, cfg in JOURNALS.items():
        print(f"\nFetching: {cfg['display']}")
        raw = fetch_journal_articles(cfg["pubmed_ta"])
        print(f"  Total articles from PubMed: {len(raw)}")

        relevant = [a for a in raw if is_neuroradiology_relevant(a)]
        print(f"  Neuroradiology-relevant: {len(relevant)}")

        if key == "ajnr":
            for a in relevant:
                bucket = classify_ajnr_type(a)
                if bucket == "clinical_practice":
                    payload["ajnr_clinical_practice"].append(a)
                else:
                    payload["ajnr_research"].append(a)
        elif key == "neuroimaging_clinics":
            payload["neuroimaging_clinics"].extend(relevant)
        elif key == "radiographics":
            payload["radiographics"].extend(relevant)

        time.sleep(0.4)

    total = sum(len(v) for v in payload.values())
    print(f"\nTotal relevant articles across all journals: {total}")

    print("\nGenerating digest with Claude...")
    digest = generate_digest(payload)

    # Save output
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "digests")
    os.makedirs(out_dir, exist_ok=True)
    filename = os.path.join(out_dir, f"digest_{datetime.now().strftime('%Y-%m-%d')}.md")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(digest)

    print(f"\nDigest written to: {filename}")
    print("\n" + "=" * 60)
    print(digest)


if __name__ == "__main__":
    run()
