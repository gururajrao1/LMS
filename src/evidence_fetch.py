"""Remote-first evidence access: store pointers, fetch bytes on demand.

The checker used to verify a citation only against snapshot blobs under
``sources/<drug>/<snapshot>/<source>/raw/*``. Those blobs are the local-machine
weight this module removes: label PDFs nobody can parse, images nobody reads,
trial attachments that fail non-fatally. What stays on disk is a tiny JSON
registry — one record per document with its URL, identity, version pin,
retrieval time, content hash, and the access tier that served it. Raw bytes are
fetched live (or into memory/tmp with a TTL) and never snapshotted.

Tiers, in order, for one citation URL:
  canonical_label  - FDA label content as text via openFDA / DailyMed, so an
                     accessdata.fda.gov or Pfizer-labeling PDF cite is checked
                     against the same SPL wording without storing the PDF.
  open_access      - the publisher page only when a licence/OA flag affirmatively
                     allows it (Unpaywall is_oa, OpenAlex OA location,
                     Europe PMC fullTextXML). A 403 is the answer otherwise.
  abstract_only    - PubMed / Europe PMC metadata and abstract. Always allowed,
                     never full text.
  human_record     - the reviewer pasted the excerpt; the record says who/when.
  unavailable      - every tier failed. Explicit, unlike the old silent skip.

No stealth fetching: one honest User-Agent with a contact address, robots.txt
honoured, ~1 request per 2s per domain, 429/Retry-After obeyed, conditional
GETs. Bot-wall evasion is not a tier.
"""

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib import robotparser

import httpx

REGISTRY_VERSION = "1"
REGISTRY_NAME = "registry.json"

CONTACT_EMAIL = os.getenv("PHARMALEARN_CONTACT_EMAIL", "pharmalearn@example.com")
USER_AGENT = f"PharmaLearn/0.1 (evidence fetch; contact {CONTACT_EMAIL})"
REQUEST_TIMEOUT = float(os.getenv("PHARMALEARN_FETCH_TIMEOUT_S", "20"))
DOMAIN_MIN_INTERVAL_S = 2.0
MAX_RETRIES = 2

OPENFDA_LABEL = "https://api.fda.gov/drug/label.json"
DAILYMED_SPLS = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
DAILYMED_SPL_XML = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPEPMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
OPENALEX_WORKS = "https://api.openalex.org/works"
CROSSREF_WORKS = "https://api.crossref.org/works"
UNPAYWALL = "https://api.unpaywall.org/v2/{doi}"

_LABEL_HOSTS = ("accessdata.fda.gov", "labeling.pfizer.com", "dailymed.nlm.nih.gov")
_PUBLISHER_HOSTS = ("nejm.org", "aacrjournals.org", "sciencedirect.com", "pfizer.com")

_last_hit: dict[str, float] = {}
_sleep = time.sleep


def _polite_wait(url: str) -> None:
    host = (httpx.URL(url).host or "").lower()
    now = time.monotonic()
    wait = DOMAIN_MIN_INTERVAL_S - (now - _last_hit.get(host, 0.0))
    if wait > 0:
        _sleep(wait)
    _last_hit[host] = time.monotonic()


def _allowed(url: str, handler=None) -> bool:
    """robots.txt gate. An injected handler means offline use: it simulates the
    network, so it also decides the gate via its robots attribute (False
    simulates a disallow). Only a live fetch reads the real robots.txt."""
    if handler is not None:
        return getattr(handler, "robots", True) is not False
    parsed = httpx.URL(url)
    robots_url = f"{parsed.scheme}://{parsed.host}/robots.txt"
    parser = robotparser.RobotFileParser()
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=10) as client:
            response = client.get(robots_url)
        parser.parse(response.text.splitlines())
    except Exception:
        return True
    return parser.can_fetch(USER_AGENT, url)


def fetch_url(url: str, handler=None) -> httpx.Response:
    """One polite GET: throttle, honest UA, retries, Retry-After obeyed."""
    if not _allowed(url, handler):
        raise PermissionError(f"robots.txt disallows fetching {url}")
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json,application/xml,*/*"}
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        _polite_wait(url)
        if handler is not None:
            response = handler(url, headers, REQUEST_TIMEOUT)
        else:
            with httpx.Client(headers=headers, timeout=REQUEST_TIMEOUT,
                              follow_redirects=True) as client:
                response = client.get(url)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "")
            try:
                _sleep(min(float(retry_after), 60.0))
            except ValueError:
                _sleep(2.0 ** attempt)
            last_error = RuntimeError(f"429 for {url}")
            continue
        return response
    raise last_error or RuntimeError(f"fetch failed for {url}")


def content_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def version_pin(url: str, meta: dict | None = None) -> str:
    """The cited-version pin that keeps a re-fetch honest.

    A DailyMed setid plus its SPL version, a PMC article version, or an openFDA
    revision date — so a later fetch that supersedes the text is detected
    instead of silently changing what a quote was verified against.
    """
    meta = meta or {}
    match = re.search(r"[?&]version=(\d+)", url or "")
    if match:
        return f"version:{match.group(1)}"
    for key in ("published_date", "revision_date", "last_update", "version"):
        if meta.get(key):
            return f"{key}:{meta[key]}"
    # Source-registry identifiers pin the exact document a quote came from:
    # a DailyMed SPL by set id + version, a paper by PMID/PMCID/DOI, a trial by
    # NCT number, an application by NDA. A re-fetch that changes any of these
    # is a different document, not an update.
    for key in ("set_id", "spl_version", "pmid", "pmcid", "doi", "nct", "nda"):
        if meta.get(key):
            return f"{key}:{meta[key]}"
    return ""


@dataclass
class EvidenceRecord:
    url: str
    source_key: str
    source_id: str = ""
    title: str = ""
    kind: str = ""
    retrieved_at: str = ""
    sha256: str = ""
    text: str = ""
    version_pin: str = ""
    access_level: str = "unavailable"
    fetch_tier: str = ""
    final_url: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data.setdefault("retrieved_at", datetime.now(UTC).isoformat())
        return data


def _record(url: str, source_key: str, text: str, payload: bytes, tier: str,
            level: str, meta: dict | None = None, title: str = "",
            kind: str = "", source_id: str = "", final_url: str = "",
            note: str = "") -> EvidenceRecord:
    meta = meta or {}
    return EvidenceRecord(
        url=url, source_key=source_key, source_id=source_id, title=title, kind=kind,
        retrieved_at=datetime.now(UTC).isoformat(),
        sha256=content_sha256(payload) if payload else "",
        text=text, version_pin=version_pin(url, meta),
        access_level=level, fetch_tier=tier, final_url=final_url or url, note=note,
    )


def _strip_html(payload: bytes) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ",
                  payload.decode("utf-8", errors="ignore"), flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _label_text_via_openfda(brand: str, handler=None) -> EvidenceRecord | None:
    params = {"search": f'openfda.brand_name:"{brand}"', "limit": "1"}
    response = fetch_url(OPENFDA_LABEL + "?" + httpx.QueryParams(params).__str__(),
                         handler)
    if response.status_code != 200:
        return None
    try:
        results = response.json().get("results", [])
    except ValueError:
        return None
    if not results:
        return None
    label = results[0]
    meta = (label.get("openfda", {}) or {})
    sections = []
    for name in ("indications_and_usage", "dosage_and_administration", "warnings",
                 "adverse_reactions", "drug_interactions", "clinical_studies",
                 "description", "clinical_pharmacology"):
        sections.extend(label.get(name, []) or [])
    text = " ".join(sections)
    if len(text) < 500:
        return None
    return _record(url=response.request.url.__str__() if hasattr(response, "request") else OPENFDA_LABEL,
                   source_key=f"openfda:{brand.lower()}",
                   text=re.sub(r"\s+", " ", text).strip()[:200_000],
                   payload=text.encode("utf-8"), tier="canonical_label",
                   level="fetched_live", meta={"revision_date": meta.get("spl_version_date", "")},
                   title=f"{brand} label (openFDA)", kind="label")


def _label_text_via_dailymed(brand: str, handler=None) -> EvidenceRecord | None:
    response = fetch_url(DAILYMED_SPLS + "?" + httpx.QueryParams(
        {"drug_name": brand, "pagesize": "2"}).__str__(), handler)
    if response.status_code != 200:
        return None
    try:
        items = ((response.json().get("data") or {}).get("spls") or [])
    except ValueError:
        return None
    if not items:
        return None
    setid = items[0].get("setid", "")
    xml_url = DAILYMED_SPL_XML.format(setid=setid)
    xml = fetch_url(xml_url, handler)
    if xml.status_code != 200 or len(xml.content) < 500:
        return None
    return _record(url=xml_url, source_key=f"dailymed:{setid.lower()}",
                   text=_strip_html(xml.content)[:200_000], payload=xml.content,
                   tier="canonical_label", level="fetched_live",
                   meta={"published_date": items[0].get("published_date", "")},
                   title=items[0].get("title", ""), kind="label", source_id=setid)


def _abstract_via_pubmed(pmid: str, handler=None) -> EvidenceRecord | None:
    xml = fetch_url(f"{EUTILS}/efetch.fcgi?" + httpx.QueryParams(
        {"db": "pubmed", "id": pmid, "retmode": "xml"}).__str__(), handler)
    if xml.status_code != 200:
        return None
    body = xml.content.decode("utf-8", errors="ignore")
    abstract = " ".join(re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", body, re.S))
    title = (re.findall(r"<ArticleTitle>(.*?)</ArticleTitle>", body, re.S) or [""])[0]
    abstract = _strip_html(abstract.encode("utf-8", errors="ignore"))
    if len(abstract) < 50:
        return None
    return _record(url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                   source_key=f"pubmed:{pmid}", text=abstract[:20_000],
                   payload=abstract.encode("utf-8"), tier="abstract_only",
                   level="abstract_only", title=_strip_html(title.encode()) or f"PMID {pmid}",
                   kind="publication")


def fetch_evidence(url: str, brand: str = "", handler=None) -> EvidenceRecord:
    """Best-effort compliant fetch for one citation URL. Never raises for HTTP
    outcomes — the tier and access_level record what happened instead."""
    from src.judge import source_key

    key = source_key(url)
    host = (httpx.URL(url).host or "").lower()
    if host.endswith(_LABEL_HOSTS) and brand:
        for attempt in (_label_text_via_openfda, _label_text_via_dailymed):
            try:
                record = attempt(brand, handler)
            except Exception as error:
                record = None
                note = str(error)[:200]
            else:
                note = ""
            if record is not None:
                record.source_key = key
                record.url = url
                return record
        return _record(url, key, "", b"", "canonical_label", "unavailable",
                       note=note or "label APIs returned no usable text")
    if host.endswith(_PUBLISHER_HOSTS) or "/doi/" in (url or ""):
        doi = ""
        match = re.search(r"10\.\d{4,}/[^\s?#]+", url or "")
        if match:
            doi = match.group(0).rstrip(").,")
        if doi:
            oa = _open_access_fulltext(doi, handler)
            if oa is not None:
                oa.source_key = key
                oa.url = url
                return oa
            pmid = _pmid_for_doi(doi, handler)
            if pmid:
                try:
                    record = _abstract_via_pubmed(pmid, handler)
                except Exception:
                    record = None
                if record is not None:
                    record.source_key = key
                    record.url = url
                    return record
        return _record(url, key, "", b"", "abstract_only", "unavailable",
                       note="no DOI or no reachable abstract; stays human-record")
    try:
        response = fetch_url(url, handler)
    except PermissionError as error:
        return _record(url, key, "", b"", "direct", "unavailable", note=str(error)[:200])
    except Exception as error:
        return _record(url, key, "", b"", "direct", "unavailable", note=str(error)[:200])
    if response.status_code != 200:
        return _record(url, key, "", b"", "direct", "unavailable",
                       note=f"HTTP {response.status_code}")
    ctype = response.headers.get("content-type", "")
    if "pdf" in ctype or url.lower().endswith(".pdf"):
        return _record(url, key, "", response.content, "direct", "unavailable",
                       final_url=str(response.url) if hasattr(response, "url") else url,
                       note="PDF bytes held but not parsed; use canonical label text")
    text = _strip_html(response.content)
    if len(text) < 100:
        return _record(url, key, "", response.content, "direct", "unavailable",
                       note="fetch returned no usable text")
    return _record(url, key, text[:200_000], response.content, "direct", "fetched_live",
                   final_url=str(response.url) if hasattr(response, "url") else url)


def _open_access_fulltext(doi: str, handler=None) -> EvidenceRecord | None:
    """Legal OA full text only: Unpaywall gate, then the OA location itself."""
    email = os.getenv("UNPAYWALL_EMAIL", CONTACT_EMAIL)
    try:
        lookup = fetch_url(UNPAYWALL.format(doi=doi) + f"?email={email}", handler)
        is_oa = lookup.status_code == 200 and bool(lookup.json().get("is_oa"))
        best = (lookup.json().get("best_oa_location") or {}) if is_oa else {}
        pdf_url = best.get("url_for_pdf") or best.get("url") or ""
    except Exception:
        return None
    if not pdf_url:
        return None
    try:
        page = fetch_url(pdf_url, handler)
    except Exception:
        return None
    if page.status_code != 200:
        return None
    ctype = page.headers.get("content-type", "")
    if "pdf" in ctype or pdf_url.lower().endswith(".pdf"):
        return None
    text = _strip_html(page.content)
    if len(text) < 500:
        return None
    return _record(url=pdf_url, source_key=f"doi:{doi.lower()}",
                   text=text[:200_000], payload=page.content,
                   tier="open_access", level="fetched_live",
                   title=best.get("title", "") or doi, kind="publication")


def _pmid_for_doi(doi: str, handler=None) -> str:
    """PMID for a DOI via E-utilities esearch on the DOI field."""
    try:
        response = fetch_url(f"{EUTILS}/esearch.fcgi?" + httpx.QueryParams(
            {"db": "pubmed", "term": f"{doi}[DOI]",
             "retmode": "json"}).__str__(), handler)
        if response.status_code != 200:
            return ""
        ids = response.json().get("esearchresult", {}).get("idlist", [])
    except Exception:
        return ""
    return ids[0] if ids else ""


def read_registry(drug: str) -> dict[str, dict]:
    """Drug-level pointer registry: sources/<drug>/registry.json."""
    from src.agent import content_path, _slug

    path = content_path("sources", _slug(drug), REGISTRY_NAME)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    records = {}
    for record in data.get("records", []):
        key = record.get("source_key", "")
        if not key:
            continue
        current = records.get(key)
        if current is None or record.get("retrieved_at", "") >= current.get("retrieved_at", ""):
            records[key] = record
    return records


def record_evidence(drug: str, record: EvidenceRecord) -> Path:
    """Upsert one pointer record. Later retrievals win; blobs untouched."""
    from src.agent import content_path, _slug

    path = content_path("sources", _slug(drug), REGISTRY_NAME)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        data = {}
    records = [item for item in data.get("records", [])
               if item.get("source_key") != record.source_key]
    payload = record.to_dict()
    payload["registry_version"] = REGISTRY_VERSION
    records.append(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"registry_version": REGISTRY_VERSION,
                                "records": records}, indent=1), encoding="utf-8")
    return path
