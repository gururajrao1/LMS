import argparse
import hashlib
import json
import os
import re
import time
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "sources" / "pfizer_us.toml"
DATA = Path(os.getenv("PHARMALEARN_DATA_DIR", ".pharmalearn"))
DATA = DATA if DATA.is_absolute() else ROOT / DATA
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def now():
    return datetime.now(UTC).isoformat()


def safe_name(value: str):
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", unquote(value)).strip("-.") or "document"


def validate(path: Path):
    if path.suffix == ".pdf" and path.read_bytes()[:4] != b"%PDF":
        raise ValueError(f"not a PDF: {path.name}")
    if path.suffix == ".json":
        json.loads(path.read_text())
    if path.suffix == ".xml":
        ET.parse(path)
    if path.suffix == ".zip" and not zipfile.is_zipfile(path):
        raise ValueError(f"not a ZIP: {path.name}")


def download(client: httpx.Client, root: Path, path: Path, url: str, role: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    for attempt in range(3):
        try:
            digest = hashlib.sha256()
            size = 0
            with client.stream("GET", url) as response:
                response.raise_for_status()
                headers = dict(response.headers)
                final_url = str(response.url)
                with part.open("wb") as file:
                    for chunk in response.iter_bytes():
                        file.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
            part.replace(path)
            validate(path)
            time.sleep(0.35)
            return {
                "path": path.relative_to(root).as_posix(),
                "role": role,
                "request_url": url,
                "final_url": final_url,
                "content_type": headers.get("content-type"),
                "bytes": size,
                "sha256": digest.hexdigest(),
                "last_modified": headers.get("last-modified"),
                "etag": headers.get("etag"),
            }
        except Exception:
            part.unlink(missing_ok=True)
            path.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def derived(root: Path, path: Path, content: bytes, role: str, origin: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    validate(path)
    return {
        "path": path.relative_to(root).as_posix(),
        "role": role,
        "origin": origin,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def links(html: str, base_url: str):
    parser = LinkParser()
    parser.feed(html)
    embedded_pdfs = re.findall(r'''^\s*[a-z0-9_]+\s*:\s*["']([^"']+\.pdf)["']''', html, re.IGNORECASE | re.MULTILINE)
    return [urljoin(base_url, href) for href in parser.links + embedded_pdfs]


def unique_path(folder: Path, url: str):
    name = safe_name(Path(urlparse(url).path).name)
    path = folder / name
    if path.exists():
        path = folder / f"{path.stem}-{hashlib.sha256(url.encode()).hexdigest()[:8]}{path.suffix}"
    return path


def fetch_label(client, root, source):
    raw = root / "raw"
    set_id = source["identifiers"]["set_id"]
    base = "https://dailymed.nlm.nih.gov/dailymed"
    files = [
        download(client, root, raw / "label.zip", f"{base}/downloadzipfile.cfm?setId={set_id}", "label_package"),
        download(client, root, raw / "label.pdf", f"{base}/downloadpdffile.cfm?setId={set_id}", "label_pdf"),
        download(client, root, raw / "history.json", f"{base}/services/v2/spls/{set_id}/history.json", "version_history"),
    ]
    with zipfile.ZipFile(raw / "label.zip") as archive:
        for name in archive.namelist():
            suffix = Path(name).suffix.lower()
            if suffix == ".xml":
                files.append(derived(root, raw / "spl.xml", archive.read(name), "label_xml", "raw/label.zip"))
            elif suffix in {".jpg", ".jpeg", ".png", ".gif"}:
                target = raw / "images" / safe_name(Path(name).name)
                files.append(derived(root, target, archive.read(name), "label_image", "raw/label.zip"))
    return "full_text", files, [], {"set_id": set_id}


def fetch_trial(client, root, source):
    raw = root / "raw"
    nct = source["identifiers"]["nct"]
    study = raw / "study.json"
    files = [download(client, root, study, f"https://clinicaltrials.gov/api/v2/studies/{nct}", "study_record")]
    data = json.loads(study.read_text())
    documents = data.get("documentSection", {}).get("largeDocumentModule", {}).get("largeDocs", [])
    warnings = []
    for index, document in enumerate(documents, 1):
        filename = document["filename"]
        label = safe_name(document.get("label", f"attachment-{index}")).lower()
        url = f"https://cdn.clinicaltrials.gov/large-docs/{nct[-2:]}/{nct}/{filename}"
        try:
            target = raw / "attachments" / f"{label}-{safe_name(filename)}"
            files.append(download(client, root, target, url, document.get("typeAbbrev", "attachment")))
        except Exception as error:
            warnings.append(f"{filename}: {error}")
    coverage = {"nct": nct, "has_results": bool(data.get("resultsSection")), "attachments_found": len(documents)}
    return "full_text", files, warnings, coverage


def main_article_id(root: ET.Element, kind: str):
    node = root.find(f".//PubmedData/ArticleIdList/ArticleId[@IdType='{kind}']")
    return node.text if node is not None else None


def fetch_publication(client, root, source):
    raw = root / "raw"
    pmid = source["identifiers"]["pmid"]
    pubmed = raw / "pubmed.xml"
    url = f"{EUTILS}?db=pubmed&id={pmid}&retmode=xml"
    files = [download(client, root, pubmed, url, "pubmed_record")]
    document = ET.parse(pubmed).getroot()
    abstract = document.find(".//AbstractText") is not None
    pmcid = main_article_id(document, "pmc")
    warnings = []
    access = "abstract_only" if abstract else "metadata_only"
    if pmcid:
        fulltext = raw / "fulltext.xml"
        try:
            files.append(download(client, root, fulltext, f"{EUTILS}?db=pmc&id={pmcid}&retmode=xml", "full_text"))
            if ET.parse(fulltext).getroot().find(".//body") is None:
                raise ValueError("PMC response did not contain an article body")
            access = "full_text"
        except Exception as error:
            fulltext.unlink(missing_ok=True)
            files = [item for item in files if item["path"] != "raw/fulltext.xml"]
            warnings.append(f"PMC {pmcid}: {error}")
    return access, files, warnings, {"pmid": pmid, "pmcid": pmcid}


def fetch_pmc(client, root, source):
    """An open-access article by its PMC identifier.

    `fetch_publication` walks PMID to PMC when a record links one. This goes the
    other way, for the many citations that name the PMC article directly and have
    no PMID recorded alongside them.
    """
    raw = root / "raw"
    pmcid = source["identifiers"]["pmcid"]
    fulltext = raw / "fulltext.xml"
    files = [download(client, root, fulltext, f"{EUTILS}?db=pmc&id={pmcid}&retmode=xml", "full_text")]
    if ET.parse(fulltext).getroot().find(".//body") is None:
        # Present in PMC but not open access: metadata only, and reported as such
        # rather than counted as a document we can check quotes against.
        return "metadata_only", files, [f"{pmcid}: no article body in the PMC response"], {"pmcid": pmcid}
    return "full_text", files, [], {"pmcid": pmcid}


def fda_url(url: str):
    return urlparse(url).hostname in {"accessdata.fda.gov", "www.accessdata.fda.gov"}


def fetch_fda_application(client, root, source):
    raw = root / "raw"
    identifiers = source["identifiers"]
    application = identifiers.get("application", f"NDA{identifiers.get('nda')}")
    query = quote(f'application_number:"{application}"')
    files, warnings = [], []
    try:
        files.append(download(client, root, raw / "application.json", f"https://api.fda.gov/drug/drugsfda.json?search={query}&limit=1", "application_record"))
    except Exception as error:
        warnings.append(f"openFDA {application}: {error}")
    overview = raw / "application.html"
    try:
        files.append(download(client, root, overview, source["url"], "application_page"))
        discovered = links(overview.read_text(errors="replace"), source["url"])
    except Exception as error:
        warnings.append(f"application page: {error}")
        discovered = []
    if application.startswith("BLA"):
        artifacts = {item["url"]: item for item in source.get("artifacts", [])}
        documents = set(artifacts) | {url for url in discovered if (urlparse(url).hostname or "").endswith("fda.gov") and "/media/" in urlparse(url).path}
        downloaded = 0
        for url in sorted(documents):
            artifact = artifacts.get(url, {})
            name = artifact.get("name", f"document-{hashlib.sha256(url.encode()).hexdigest()[:10]}.pdf")
            role = artifact.get("role", "supporting_document")
            path = raw / "supporting-documents" / safe_name(name)
            try:
                files.append(download(client, root, path, url, role))
                downloaded += 1
            except Exception as error:
                warnings.append(f"{url}: {error}")
        access = "full_text" if downloaded else "unavailable"
        return access, files, warnings, {"application": application, "supporting_documents": downloaded}
    review_pages = {url for url in discovered if fda_url(url) and "/drugsatfda_docs/nda/" in url.lower() and urlparse(url).path.lower().endswith((".htm", ".html"))}
    pdfs = {url for url in discovered if fda_url(url) and "/drugsatfda_docs/" in url.lower() and urlparse(url).path.lower().endswith(".pdf")}
    for url in sorted(review_pages):
        path = unique_path(raw / "reviews", url)
        try:
            files.append(download(client, root, path, url, "review_index"))
            pdfs.update(link for link in links(path.read_text(errors="replace"), url) if fda_url(link) and urlparse(link).path.lower().endswith(".pdf"))
        except Exception as error:
            warnings.append(f"{url}: {error}")
    counts = {"approval_letters": 0, "reviews": 0, "archived_labels": 0}
    for url in sorted(pdfs):
        lower = url.lower()
        category = "approval-letters" if "/appletter/" in lower else "archived-labels" if "/label/" in lower else "reviews"
        role = category.replace("-", "_").rstrip("s")
        try:
            files.append(download(client, root, unique_path(raw / category, url), url, role))
            counts[category.replace("-", "_")] += 1
        except Exception as error:
            warnings.append(f"{url}: {error}")
    access = "full_text" if counts["reviews"] or counts["approval_letters"] else "metadata_only"
    return access, files, warnings, {"application": application, **counts}


def fetch_webpage(client, root, source):
    path = root / "raw" / "document.html"
    files = [download(client, root, path, source["url"], "official_webpage")]
    access = source.get("webpage_access_level", "full_text" if source["kind"] == "fda_safety" else "metadata_only")
    return access, files, [], {}


def fetch_guideline(client, root, source):
    return fetch_publication(client, root, source) if source.get("identifiers", {}).get("pmid") else fetch_webpage(client, root, source)


HANDLERS = {
    "current_fda_label": fetch_label,
    "fda_application": fetch_fda_application,
    "trial_registry": fetch_trial,
    "peer_reviewed_publication": fetch_publication,
    "pmc_article": fetch_pmc,
    "us_guideline": fetch_guideline,
    "fda_safety": fetch_webpage,
}


def validate_registry(registry):
    required_ids = {
        "current_fda_label": "set_id",
        "trial_registry": "nct",
        "peer_reviewed_publication": "pmid",
        "pmc_article": "pmcid",
    }
    for drug in registry["drugs"]:
        seen = set()
        for source in drug["sources"]:
            if source["id"] in seen:
                raise ValueError(f"duplicate source ID for {drug['id']}: {source['id']}")
            seen.add(source["id"])
            if source["kind"] not in HANDLERS:
                raise ValueError(f"unsupported source kind: {source['kind']}")
            identifier = required_ids.get(source["kind"])
            if identifier and identifier not in source.get("identifiers", {}):
                raise ValueError(f"{source['id']} requires identifier {identifier}")
            if source["kind"] == "fda_application" and not ({"nda", "application"} & source.get("identifiers", {}).keys()):
                raise ValueError(f"{source['id']} requires an NDA or application identifier")


def fetch_source(client, target, drug, source):
    target.mkdir(parents=True)
    try:
        access, files, warnings, coverage = HANDLERS[source["kind"]](client, target, source)
        status = "fetched"
        error = None
    except Exception as exception:
        access, files, warnings, coverage = "unavailable", [], [], {}
        status, error = "failed", str(exception)
    manifest = {
        "schema_version": 2,
        "drug_id": drug["id"],
        "source_id": source["id"],
        "fetched_at": now(),
        "status": status,
        "access_level": access,
        "coverage": coverage,
        "warnings": warnings,
        "error": error,
        "registry": source,
        "files": files,
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Fetch an immutable snapshot from the Pfizer source registry.")
    parser.add_argument("--drug", required=True, help="Registry drug ID, for example: ibrance")
    args = parser.parse_args()
    registry_bytes = REGISTRY.read_bytes()
    registry = tomllib.loads(registry_bytes.decode())
    validate_registry(registry)
    drug = next((item for item in registry["drugs"] if item["id"] == args.drug.lower()), None)
    if not drug:
        parser.error(f"unknown drug: {args.drug}")

    snapshot_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    drug_root = DATA / "sources" / drug["id"]
    staging = drug_root / f".{snapshot_id}.partial"
    final = drug_root / snapshot_id
    staging.mkdir(parents=True)
    results = []
    headers = {"User-Agent": "PharmaLearn/0.2 source-audit (local development)"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=120) as client:
        for source in drug["sources"]:
            print(f"FETCH   {source['id']}", flush=True)
            manifest = fetch_source(client, staging / source["id"], drug, source)
            results.append({key: manifest[key] for key in ["source_id", "status", "access_level", "warnings", "error"]})
            print(f"{manifest['status'].upper():7} {source['id']} ({manifest['access_level']})", flush=True)

    failures = [item for item in results if item["status"] == "failed"]
    limited = any(item["warnings"] or item["access_level"] != "full_text" for item in results)
    snapshot_status = "incomplete" if failures else "complete_with_limits" if limited else "complete"
    snapshot = {
        "schema_version": 2,
        "snapshot_id": snapshot_id,
        "drug_id": drug["id"],
        "created_at": now(),
        "status": snapshot_status,
        "registry_path": str(REGISTRY.relative_to(ROOT)),
        "registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "sources": results,
    }
    (staging / "snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    staging.replace(final)
    if not failures:
        (drug_root / "latest.json").write_text(json.dumps({"snapshot_id": snapshot_id, "path": final.name, "status": snapshot["status"]}, indent=2) + "\n")
    print(f"\n{drug['brand']}: {len(results) - len(failures)} fetched, {len(failures)} failed")
    print(final)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
