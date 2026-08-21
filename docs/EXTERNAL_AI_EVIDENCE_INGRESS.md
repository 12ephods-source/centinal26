# External AI evidence ingress

Automation OS / Frost Forge treats external AI conversations as provenance-controlled source artifacts. A shared link is a locator, not proof that the underlying conversation was acquired.

## Lifecycle

`Acquire -> Validate -> Normalize -> Preserve -> Analyze -> Extract -> Classify -> Integrate`

The first four stages establish what source material actually exists. Analysis begins only after content acquisition has been demonstrated.

## Ingress states

- `UNAVAILABLE`: the source locator is known, but no transcript content is available.
- `PARTIAL`: some transcript content was acquired and completeness is explicitly partial.
- `ACQUIRED`: transcript content was acquired; completeness must be `COMPLETE` or `PARTIAL`.

`UNAVAILABLE` records may not carry transcript content or a transcript hash. They are not analysis-ready.

For acquired content, `ExternalAIEvidenceIngestor` requires the caller to provide transcript text and its SHA-256. The ingestor recomputes the digest and rejects a mismatch before storing the transcript.

## Evidence classes

- `EXTERNAL_AI_LOCATOR`: source/platform metadata only.
- `EXTERNAL_AI_PRIMARY_SOURCE`: acquired transcript bytes represented as UTF-8 text plus SHA-256.

The latter means primary evidence of what the external AI conversation said. It does not mean claims inside the transcript are independently verified facts.

## Authority boundary

The ingestor does not fetch arbitrary URLs, summarize unavailable content, extract or promote claims automatically, advance canonical aliases, resolve contradictions, enable capabilities, execute actions, or delete/rewrite prior evidence.

Downstream analysis may project claims, decisions, project candidates, or reusable components only after source acquisition and while retaining provenance and completeness caveats.
