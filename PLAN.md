# Fresco Hardware Set Extractor - Implementation Plan

> This document is the living technical design and implementation plan for the project.
>
> `CHALLENGE.md` defines **what must be built**. This document defines **how we currently plan to build it**.
>
> Technical decisions in this document may change when experiments or evaluation results provide evidence for a better approach.

---

## 1. Goal

Build a system that extracts hardware sets and their components from Division 08 construction specification PDFs into a consistent structured representation.

The system should prioritize:

1. Extraction accuracy
2. Robustness across different specbook formats
3. Correct interpretation of document layout
4. Traceability to the source document
5. Simple and maintainable implementation

Target extraction accuracy: **~90%+**, consistent with the challenge success criteria.

---

## 2. Success Criteria

The system should:

* Detect all hardware sets
* Extract hardware-set descriptions where present
* Extract components accurately
* Correctly map component fields
* Correctly distinguish manufacturer from finish
* Preserve meaningful page/location information
* Handle section/list layouts
* Handle table layouts
* Handle multi-page sets
* Handle `NOT USED`, `N/A` and equivalent sets
* Return `null` rather than guessing missing quantities
* Generalize across different specbook formats

Bonus features should only be considered after the core extraction pipeline performs reliably.

---

## 3. Engineering Priorities

Development effort should be prioritized approximately as follows:

1. Extraction correctness
2. Evaluation and regression detection
3. Handling difficult document formats
4. Code quality and maintainability
5. Clear local execution
6. Demo usability
7. Bonus features
8. Infrastructure sophistication

Do not introduce production infrastructure unless it solves a demonstrated problem.

---

## 4. Proposed Architecture

Initial architecture:

```text
Specification PDF
        |
        v
+-------------------+
|   PDF Parsing     |
+-------------------+
        |
        v
+-------------------+
| Layout            |
| Representation    |
+-------------------+
        |
        v
+-------------------+
| Hardware Set      |
| Detection         |
+-------------------+
        |
        v
+-------------------+
| Component / Field |
| Extraction        |
+-------------------+
        |
        v
+-------------------+
| Validation &      |
| Normalization     |
+-------------------+
        |
        v
+-------------------+
| HardwareSet[]     |
| JSON              |
+-------------------+
```

The pipeline should preserve spatial information for as long as possible because document position may be necessary for determining:

* Set boundaries
* Table columns
* Manufacturer vs. finish
* Component grouping
* Source location

This architecture is provisional and may change based on document exploration.

---

## 5. Technical Stack

### 5.1 Language

**Decision:** Python 3.11+

**Reasons:**

* Strong PDF/document-processing ecosystem
* Recommended by the challenge
* Suitable for document and AI processing workflows
* Matches Fresco's backend language

---

### 5.2 PDF Processing

**Decision:** PyMuPDF (default), with pdfplumber retained as a selectable backend.

Both were measured against the fixture corpus (`evals/parser_comparison.py`). They
produced **identical** words, lines and bounding boxes on every fixture; PyMuPDF
was 4-14x faster and also renders page images, which the review UI needs. The
pipeline keeps `--backend pdfplumber` working and a test asserts the two agree,
so the decision stays re-measurable rather than baked in.

Candidates considered:

* PyMuPDF
* pdfplumber

The parser should ideally expose:

* Page numbers
* Text
* Words
* Lines
* Bounding boxes
* Coordinates
* Reading order
* Table/layout information where available

The parser will be selected after testing representative PDFs rather than choosing solely based on library features.

#### Experiment

Test candidate parsers against representative documents containing:

1. Section/list sets
2. Table sets
3. Multi-page sets
4. Different column layouts
5. Difficult or irregular formatting

Evaluate:

* Text extraction quality
* Bounding-box accuracy
* Reading order
* Table preservation
* Ease of downstream processing
* Runtime

**Decision:** PyMuPDF - recorded in the Decision Log below.

---

### 5.3 Structured Models

**Initial decision:** Pydantic

Purpose:

* Define the expected extraction schema
* Validate structured output
* Normalize nullable fields
* Validate LLM output if an LLM is used

Initial conceptual models:

```python
class Location(BaseModel):
    page: int
    bbox: list[float] | None = None
    line_range: list[int] | None = None


class Component(BaseModel):
    qty: int | None
    description: str | None
    catalog_number: str | None
    mfr: str | None
    finish: str | None
    notes: str | None


class HardwareSet(BaseModel):
    set_number: str
    description: str | None
    location: Location
    components: list[Component]
```

The exact representation of multi-page locations remains TBD.

---

### 5.4 LLM / AI Extraction

**Decision:** Strategy A (deterministic) is the shipped system; Strategy C
(hybrid) is available behind `--llm` and is off by default.

The deterministic column model reaches 100% on the evaluation corpus, including
every manufacturer/finish case, so an LLM is not on the critical path. Making it
optional also means a reviewer with no API key can run and evaluate the whole
system. The LLM pass only revisits sets the deterministic pass scored as
low-confidence, and its output is schema-validated and then checked to appear
verbatim in the source region before any value is accepted.

Do not assume that every page or extraction stage requires an LLM.

Possible strategies to evaluate:

#### Strategy A - Deterministic

```text
PDF
 ↓
Layout parsing
 ↓
Rules / heuristics
 ↓
Structured output
```

#### Strategy B - LLM-based

```text
PDF/layout representation
 ↓
LLM structured extraction
 ↓
Schema validation
```

#### Strategy C - Hybrid

```text
Deterministic parsing/detection
 ↓
Relevant document region
 ↓
LLM semantic extraction
 ↓
Deterministic validation
```

The implementation should choose the simplest strategy that achieves acceptable accuracy.

Questions to answer experimentally:

* Is an LLM necessary for set detection?
* Is an LLM necessary for component extraction?
* Can table structure be recovered deterministically?
* Does an LLM materially improve manufacturer/finish classification?
* What information should be provided to the model?
* How should malformed or uncertain model output be handled?

**Decision:** Deterministic core with an optional LLM pass - recorded in the Decision Log below.

---

### 5.5 API

**Status:** Implemented (FastAPI) once the review UI required it.

`src/hardware_sets/api.py` exposes upload/extract, page-image rendering for the
bounding-box overlay, and reviewer-correction storage. The extractor itself is
importable and runnable without it.

Original reasoning, kept for the record:

The extraction pipeline should first work through a CLI or directly callable Python interface.

An API should only be introduced if needed for:

* Deployment
* Demo UI
* Feedback UI

Possible implementation if needed:

* FastAPI

Do not introduce an API before the core extractor works.

---

### 5.6 Frontend

**Status:** Implemented - Next.js 15 + TypeScript + React Context (`frontend/`).

Covers uploading a PDF, browsing the extracted sets, seeing each set drawn on the
rendered source page, per-field confidence, and correcting and saving mistakes.

It was built after the extractor met the accuracy target, not before. Original
scope:

* Uploading PDFs
* Viewing extracted hardware sets
* Viewing source locations
* Correcting extraction errors

Possible stack:
* Next.js
* TypeScript
* React Context API

A feedback UI is a bonus feature and should not delay extraction work.

---

### 5.7 Database

**Decision:** None - unchanged. Reviewer corrections are stored as one JSON file
per uploaded document, which is all the feedback feature needs.

**Initial reasoning:**

Reason:

The challenge does not require persistence.

Structured extraction results can initially be returned and/or written as JSON.

A database should only be introduced if persistence becomes useful for a implemented feature such as feedback/corrections.

---

### 5.8 Async Processing

**Initial decision:** None.

Start with synchronous extraction.

If processing time creates a demonstrated usability problem, asynchronous processing can be considered later.

---

### 5.9 Cloud / Deployment

**Decision:** Local run, documented end to end in `README.md`.

The challenge accepts either a deployed link or clear local run steps. Both
services start with one command each and need no cloud account, API key or
managed service, so local run is the lower-friction option for a reviewer and
avoids infrastructure that solves no demonstrated problem.

**Original status:** TBD.

Do not choose deployment infrastructure until the extraction pipeline is stable.

The challenge allows either:

* A deployed application
* Clear local run instructions

Therefore deployment is secondary to extraction accuracy.

---

## 6. Extraction Strategy

### Stage 1 - Document Parsing

Input:

```text
PDF
```

Output should preserve enough information to reason about layout:

```text
Document
 └── Pages
      └── Lines / Words / Blocks
           ├── text
           ├── bbox
           └── position
```

Capture where available:

* Text
* Page number
* Bounding boxes
* Words
* Lines
* Blocks
* Table structure

Do not flatten the entire document into plain text prematurely.

---

### Stage 2 - Hardware Set Detection

Identify candidate hardware-set starts.

Potential signals include:

* `SET #1`
* `SET 3A`
* `HARDWARE SET 15`
* Set-number columns
* Table grouping
* Blank rows
* Typography/layout changes

Detection logic must account for different document formats.

Output:

```text
CandidateHardwareSetRegion[]
```

Each candidate should retain its source location.

---

### Stage 3 - Set Boundary Detection

Determine where each hardware set ends.

Potential signals:

* Next hardware-set header
* New set number
* Blank row
* Table grouping change
* Section transition
* End of document

A page boundary must **not automatically terminate a set**.

Continuation onto the next page must be considered.

---

### Stage 4 - Component Extraction

For each detected hardware set, extract:

```text
qty
description
catalog_number
mfr
finish
notes
```

Extraction should use both textual and layout information when useful.

Missing information must remain `null`.

---

### Stage 5 - Manufacturer / Finish Resolution

Manufacturer and finish classification is a high-priority challenge requirement.

Do not classify ambiguous codes independently.

Consider:

* Column header
* Column position
* Neighboring values
* Other values in the same column
* Known manufacturer patterns
* Known finish patterns
* Overall table structure

For example:

```text
MK
LCN
SCH
```

provides evidence of a manufacturer column.

Whereas:

```text
US26D
630
BSP
```

provides evidence of a finish column.

The exact classification strategy will be determined experimentally.

---

### Stage 6 - Multi-Page Resolution

When a page ends while a hardware set is active:

1. Inspect the beginning of the next page
2. Determine whether it represents a continuation
3. Merge continuation components into the active set when appropriate
4. Preserve source location information

The location schema for sets spanning multiple pages must be finalized during implementation.

---

### Stage 7 - Validation and Normalization

Before returning results:

* Validate schema
* Normalize empty values
* Preserve `null` values
* Verify set identifiers
* Verify component grouping
* Check manufacturer/finish mapping
* Preserve source location

Do not silently invent missing information.

---

## 7. Evaluation Strategy

Evaluation should be established early rather than added after implementation.

### Evaluation Corpus

Select representative examples covering:

* Section/list format
* Table format
* Different table schemas
* Ambiguous manufacturer/finish columns
* Multi-page sets
* `NOT USED` sets
* Missing quantities
* Unusual set boundaries

Create manually verified expected JSON outputs for these examples.

These expected outputs become the **golden evaluation corpus**.

---

### Metrics

Where practical, measure:

#### Set-level

* Set detection accuracy
* Set-number accuracy
* Description accuracy

#### Component-level

* Component detection accuracy
* Quantity accuracy
* Description accuracy
* Catalog-number accuracy
* Manufacturer accuracy
* Finish accuracy
* Notes accuracy

#### Structural

* Set boundary accuracy
* Multi-page association accuracy
* Location accuracy

The final metric definitions should be documented once the evaluator is implemented.

---

## 8. Development Loop

Extraction development should follow an evaluation-driven loop:

```text
Select failure
      |
      v
Reproduce with fixture
      |
      v
Classify failure
      |
      v
Understand root cause
      |
      v
Implement smallest fix
      |
      v
Run focused tests
      |
      v
Run evaluation corpus
      |
      v
Compare metrics
      |
      v
Check regressions
      |
      +------ regression ------> investigate
      |
      v
Accept change
```

When architecture changes as a result of the experiment, update this document and the Decision Log.

---

## 9. Failure Categories

Extraction failures should be categorized before implementing fixes.

Initial categories:

```text
PARSING
LAYOUT
SET_DETECTION
SET_BOUNDARY
COMPONENT_DETECTION
FIELD_MAPPING
MFR_FINISH
MULTI_PAGE
NOT_USED
LOCATION
NORMALIZATION
LLM
UNKNOWN
```

This should help distinguish systematic problems from document-specific failures.

---

## 10. Implementation Milestones

### Milestone 1 - Document Exploration

* [x] Build a representative fixture corpus (the challenge PDFs are not redistributable)
* [x] Inspect representative pages manually
* [x] Identify major document/layout families
* [x] Identify difficult examples
* [x] Test PyMuPDF
* [x] Test pdfplumber
* [x] Compare extraction quality
* [x] Select initial parser
* [x] Record parser decision

**Deliverable:** reliable layout representation for representative PDFs.

---

### Milestone 2 - Data Model and Baseline Extractor

* [x] Define Pydantic models
* [x] Parse PDF pages
* [x] Preserve spatial information
* [x] Detect straightforward hardware-set headers
* [x] Detect basic boundaries
* [x] Extract basic components
* [x] Produce schema-valid JSON
* [x] Preserve source location

**Deliverable:** end-to-end extraction for simple examples.

---

### Milestone 3 - Evaluation Harness

* [x] Select representative evaluation examples
* [x] Manually verify expected outputs
* [x] Create golden JSON fixtures
* [x] Implement evaluator
* [x] Define metrics
* [x] Establish baseline accuracy
* [x] Categorize baseline failures

**Deliverable:** repeatable evaluation command and baseline metrics.

---

### Milestone 4 - Extraction Improvement Loops

Work through evaluation failures by category.

* [x] Improve set detection
* [x] Improve set boundaries
* [x] Improve component extraction
* [x] Resolve manufacturer vs. finish
* [x] Handle multi-page sets
* [x] Handle `NOT USED`
* [x] Handle missing quantities
* [x] Handle inconsistent table layouts
* [x] Improve location accuracy

After each meaningful change:

```text
tests → evals → regression check
```

**Deliverable:** approximately 90%+ extraction accuracy on the evaluation corpus.

---

### Milestone 5 - Robustness

* [x] Test a held-out fixture written after the pipeline (fixture 04)
* [x] Identify overfitting
* [x] Add regression fixtures for newly discovered failures
* [x] Improve error handling
* [x] Verify malformed documents fail gracefully
* [x] Review dependency usage
* [x] Review code structure

**Deliverable:** extraction that generalizes beyond development examples.

---

### Milestone 6 - Submission

* [x] Final evaluation run
* [x] Record final metrics
* [x] Update README with actual architecture
* [x] Verify setup instructions
* [x] Verify run instructions
* [x] Remove unused dependencies/code
* [x] Verify no credentials are committed
* [x] Select representative demo examples
* [ ] Record Loom demo

**Deliverable:** submission-ready repository.

---

### Milestone 7 - Bonus Features

Only begin after the core requirements are satisfied.

Potential features:

* [x] Confidence scores
* [x] Feedback/correction UI
* [x] Spec/catalog code resolution (page abbreviation legend)

Do not sacrifice core extraction accuracy for bonus features.

---

## 11. Definition of Done

A code change affecting extraction is complete when:

1. The intended behavior works
2. Relevant tests pass
3. Relevant evaluation cases pass
4. The full evaluation suite has been checked when appropriate
5. Existing extraction accuracy does not materially regress
6. Output remains schema-valid
7. Missing information is not guessed
8. A regression/evaluation case exists for newly supported behavior
9. Documentation is updated when the technical design changes

A feature is not complete merely because it works on one example.

---

## 12. Initial Project Structure

Proposed initial structure:

```text
.
├── src/
│   ├── models/
│   ├── parsing/
│   ├── detection/
│   ├── extraction/
│   └── normalization/
│
├── tests/
│
├── evals/
│   ├── fixtures/
│   ├── expected/
│   └── evaluator/
│
├── samples/
│
├── CHALLENGE.md
├── PLAN.md
├── AGENTS.md
├── README.md
├── requirements.txt
└── .gitignore
```

This structure is provisional.

Do not create empty architectural layers merely to match this diagram. Add directories when implementation requires them.

---

## 13. Open Questions

### Document Processing

* Which PDF parser performs best across representative specbooks?
* How reliably can tables be reconstructed from PDF coordinates?
* Are any supplied PDFs scanned rather than text-based?

### Extraction

* Can hardware-set detection remain deterministic?
* Is an LLM necessary for component extraction?
* Would a hybrid approach outperform either strategy alone?
* How should ambiguous manufacturer/finish fields be resolved?
* How much surrounding context is necessary?

### Multi-Page Sets

* How should continuation pages be detected?
* Should `location` support multiple bounding boxes?
* Should each component retain its own source location internally?

### Evaluation

* How should partial field matches be scored?
* How should component alignment between expected and predicted output work?
* What constitutes the final 90% accuracy metric?
* How large should the golden evaluation corpus be?

### AI

* Which model, if any, provides the best accuracy/cost/latency tradeoff?
* What structured-output mechanism should be used?
* Should low-confidence extraction trigger a fallback?
* How should model uncertainty be represented?

### Product

* Is a UI valuable enough to justify implementation time?
* Would confidence scores provide more value than a feedback UI?

These questions should be answered through experiments rather than assumptions.

---

## 14. Decision Log

Major technical decisions should be recorded here.

Do not record trivial implementation details.

### 2026-08-19 - Python

**Decision:** Use Python as the primary extraction language.

**Reason:**

* Strong document-processing ecosystem
* Recommended by the challenge
* Appropriate for AI/document extraction
* Matches Fresco's backend language

**Alternatives considered:**

* TypeScript / Node.js

**Status:** Accepted

---

### 2026-08-19 - PDF Parser

**Decision:** PyMuPDF as the default backend; pdfplumber kept selectable.

**Evidence:** `evals/parser_comparison.py` over the fixture corpus. Identical
word counts, line grouping and bounding boxes on every fixture; PyMuPDF ran
0.003-0.05s per document against pdfplumber's 0.013-0.74s (4-14x faster).

**Reason:** No accuracy difference to trade off, so speed decided it. PyMuPDF
also rasterises pages, which the review UI needs for the bounding-box overlay -
adopting it avoided a second PDF dependency. `--backend pdfplumber` still works
and `test_pdfplumber_backend_agrees_with_pymupdf` asserts the two stay in
agreement, so this is reversible if a real specbook exposes a difference.

**Alternatives considered:**

* pdfplumber - equal quality here, materially slower, no rasteriser
* pypdf / pdfminer.six - no bounding boxes in a usable form

**Status:** Accepted

---

### 2026-08-19 - Extraction Strategy

**Decision:** Deterministic column model as the shipped system, with an optional
LLM refinement pass behind `--llm`.

**Evidence:** The deterministic pipeline scores 100% (348/348 assertions) on the
evaluation corpus, including every manufacturer/finish case and the held-out
fixture written after the pipeline existed. Nothing was left for an LLM to fix.

**Reason:** The core problem is a layout problem, not a language problem. Which
column a value sits in is the evidence that decides manufacturer vs. finish, and
that is recoverable from word geometry - deterministically, in milliseconds, with
no API key and no per-page cost. An LLM is kept for the case this reasoning does
not cover: a set the column model itself reports low confidence in. Because the
deterministic path is the default, a reviewer can run and evaluate the entire
system with no model access at all.

**Alternatives considered:**

* LLM-per-page - slower, costs per page, needs a key to run at all, and cannot be
  evaluated deterministically for regressions
* Deterministic only - what ships; the LLM pass is additive, not load-bearing

**Status:** Accepted

---

### 2026-08-19 - Manufacturer vs. Finish Resolution

**Decision:** Classify the *column*, never the individual value. Codes that are
genuinely ambiguous (PE, NO, AL, PC, BR, SP) contribute nothing to the score in
either direction, so a column is decided by its unambiguous members.

**Evidence:** `PE` resolves to a manufacturer in fixture 01 (column also holds
VON, LCN) and to a finish in fixture 02 (column also holds 628, BSP, US26D), from
the same code table and with no per-document configuration. In fixture 04 a
column of `PE US26D` pairs splits correctly because `US26D` is unambiguously a
finish, which forces `PE` into the manufacturer slot.

**Reason:** This is the challenge's central caveat. Any per-value lookup is wrong
by construction for the values that matter.

**Supporting signals, in order of strength:** an explicit page legend
(`PE = PEMKO`); an explicit column header; the aggregate content of the column;
the same column position elsewhere in the document.

**Status:** Accepted

---

### 2026-08-19 - LLM Provider

**Decision:** Anthropic (`claude-opus-5`) via the official `anthropic` SDK, used
only on the optional `--llm` path.

**Reason:** Structured outputs give a schema-validated response directly, which
is what the refinement pass needs. The model is overridable with
`HARDWARE_SETS_LLM_MODEL`.

**Caveat:** This path has unit tests against a fake client covering the merge and
verification rules, but it has not been exercised against the live API in this
environment (no key was available). It is off by default for that reason.

**Status:** Accepted, optional

---

### 2026-08-19 - API

**Decision:** Superseded. FastAPI was added once the review UI needed it.

The original reasoning held until the bonus feedback UI was built: the UI needs
somewhere to upload a PDF, needs rendered page images to draw bounding boxes on,
and needs somewhere to store corrections. The extractor remains fully usable as a
CLI and as a Python import without the API.

**Superseded decision, kept for the record:** No API initially.

**Reason:**

The extraction pipeline can be developed and evaluated without an HTTP layer.

An API will only be introduced if required for deployment or UI integration.

**Status:** Accepted

---

### 2026-08-19 - Database

**Decision:** No database. Still holds.

Reviewer corrections are written as one JSON file per uploaded document. A
database would add operational surface without changing what the feature does.

**Reason:**

Persistence is not required by the challenge and does not improve initial extraction accuracy.

**Status:** Accepted

---

## 15. Current Focus

The current implementation focus should always be explicitly recorded here so coding agents do not attempt to implement the entire plan at once.

### Current Milestone

**Milestones 1-7 complete.** The extractor, evaluation harness, CLI, API, review
UI and bonus features are implemented and passing.

### Where things stand

| Area | State |
| --- | --- |
| Extraction pipeline | Deterministic, 100% (348/348) on the evaluation corpus |
| Evaluation | 4 fixtures, hand-written goldens, `python evals/evaluate.py` |
| Tests | 93 passing (`pytest`) |
| CLI | `python -m hardware_sets <pdf>` |
| API | FastAPI - upload, page images, corrections |
| UI | Next.js review interface with bbox overlay and inline correction |
| Bonus | Confidence scores, feedback UI, page legend resolution |

### Known limitations

Recorded honestly rather than hidden:

* **The evaluation corpus is synthetic.** The challenge PDFs are not
  redistributable, so the fixtures were authored to reproduce the layout families
  and caveats the challenge names. 100% on this corpus means the pipeline handles
  those structures correctly; it is not a measurement against the real corpus.
  Fixture 04 was deliberately written *after* the pipeline, as a generalisation
  check, and did surface four real bugs.
* **Scanned pages are not handled.** A page with no text layer is reported in
  `warnings` rather than OCR'd.
* **Columns closer together than ~1.6 character widths merge.** The mfr/finish
  case has a dedicated splitter; a description running into a catalog column does
  not.
* **The `--llm` path is untested against the live API** - unit-tested with a fake
  client only.

### Next steps

* [ ] Run against the real challenge specbooks and re-measure
* [ ] Add any newly discovered failures as regression fixtures
* [ ] Record the demo walkthrough

### Do Not Implement

Not needed by anything demonstrated so far:

* Database persistence
* Async job infrastructure
* Cloud infrastructure
* OCR (until a scanned specbook is actually encountered)

---

## 16. Plan Maintenance

This document should evolve as implementation progresses.

Update `PLAN.md` when:

* An experiment resolves an open technical question
* A major architectural decision changes
* A milestone is completed
* Evaluation identifies a new systematic failure category
* A major dependency is introduced or replaced
* A significant engineering tradeoff is accepted

Do not rewrite historical decisions silently.

When a decision changes, preserve the previous decision in the Decision Log and record why it was superseded.
