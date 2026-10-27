# Pfizer US source registry

`pfizer_us.toml` is the human-auditable allowlist for source collection. It contains no downloaded documents and no generated course content.

## What “exhaustive” means here

The registry is exhaustive for a **defined US course scope**, not for everything ever published about a drug. For each course it fixes:

1. the current manufacturer/NDA-holder FDA label for every relevant formulation;
2. the FDA application record and any required safety communication;
3. the named pivotal or required safety trials used by the course;
4. the matching primary peer-reviewed publications; and
5. one current US professional-society guideline for clinical context.

This gives collection a clear stop condition. New literature is not added unless it changes the label, safety position, guideline, or a claim the course needs to teach.

## How to audit it

For each drug in `pfizer_us.toml`:

1. Open every `required = true` URL.
2. Confirm the brand, generic name, formulation, indication, and identifier.
3. For DailyMed, confirm the labeler is the manufacturer/NDA holder—not a repackager—and compare the current SPL version with `spl_version`.
4. For a publication, confirm its PMID/DOI and NCT number match the registered trial.
5. For a guideline, confirm no newer replacement has been published.
6. Update `reviewed_on` whenever the full registry is rechecked.

The current course boundaries are intentionally narrow:

- Ibrance: HR-positive/HER2-negative advanced or metastatic breast cancer
- Eliquis: nonvalvular atrial fibrillation
- Vyndaqel/Vyndamax: transthyretin amyloid cardiomyopathy
- Prevnar 20: adult pneumococcal vaccination

Other approved indications require their own trial and guideline additions before content generation.

## Later fetch behavior

Run the fetcher for one registered drug:

```bash
uv run python scripts/fetch_pfizer.py --drug ibrance
```

Every run creates an immutable timestamped snapshot. The script retrieves only registered sources:

```text
.pharmalearn/sources/<drug-id>/
  latest.json
  <timestamp>/
    snapshot.json
    <source-id>/
      manifest.json
      raw/
```

`snapshot.json` summarizes the run and `latest.json` selects the newest usable snapshot. Each source manifest retains its URLs, access time, checksums, registry entry, warnings, and one honest access level:

- `full_text`: the substantive official document or registry record was downloaded;
- `abstract_only`: the abstract is available but the complete publication is not publicly downloadable;
- `metadata_only`: only the official record or landing page is available;
- `unavailable`: the source could not be retrieved.

Raw label packages are unpacked for inspection. FDA application sources include the structured application record and linked review, approval-letter, and archived-label PDFs. Trial sources include official protocol and analysis-plan attachments when posted. Publication and guideline full text is downloaded only through public official access such as PMC; the fetcher does not bypass paywalls.

The fetcher records failures and never substitutes web-search results. For the current demo, citation gaps remain visible warnings rather than publishing failures.
