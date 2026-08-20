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

**Status:** TBD

Initial candidates:

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

**Decision:** TBD after Milestone 1.

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

**Status:** TBD

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

**Decision:** TBD after establishing a baseline.

---

### 5.5 API

**Status:** Not required initially.

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

**Status:** (Implement anyway)
A frontend is not required for the core challenge.
If time permits, a small UI may be implemented for:

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

**Initial decision:** None.

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

**Status:** TBD.

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

* [ ] Download/select representative specbooks
* [ ] Inspect representative pages manually
* [ ] Identify major document/layout families
* [ ] Identify difficult examples
* [ ] Test PyMuPDF
* [ ] Test pdfplumber
* [ ] Compare extraction quality
* [ ] Select initial parser
* [ ] Record parser decision

**Deliverable:** reliable layout representation for representative PDFs.

---

### Milestone 2 - Data Model and Baseline Extractor

* [ ] Define Pydantic models
* [ ] Parse PDF pages
* [ ] Preserve spatial information
* [ ] Detect straightforward hardware-set headers
* [ ] Detect basic boundaries
* [ ] Extract basic components
* [ ] Produce schema-valid JSON
* [ ] Preserve source location

**Deliverable:** end-to-end extraction for simple examples.

---

### Milestone 3 - Evaluation Harness

* [ ] Select representative evaluation examples
* [ ] Manually verify expected outputs
* [ ] Create golden JSON fixtures
* [ ] Implement evaluator
* [ ] Define metrics
* [ ] Establish baseline accuracy
* [ ] Categorize baseline failures

**Deliverable:** repeatable evaluation command and baseline metrics.

---

### Milestone 4 - Extraction Improvement Loops

Work through evaluation failures by category.

* [ ] Improve set detection
* [ ] Improve set boundaries
* [ ] Improve component extraction
* [ ] Resolve manufacturer vs. finish
* [ ] Handle multi-page sets
* [ ] Handle `NOT USED`
* [ ] Handle missing quantities
* [ ] Handle inconsistent table layouts
* [ ] Improve location accuracy

After each meaningful change:

```text
tests → evals → regression check
```

**Deliverable:** approximately 90%+ extraction accuracy on the evaluation corpus.

---

### Milestone 5 - Robustness

* [ ] Test additional unseen specbooks
* [ ] Identify overfitting
* [ ] Add regression fixtures for newly discovered failures
* [ ] Improve error handling
* [ ] Verify malformed documents fail gracefully
* [ ] Review dependency usage
* [ ] Review code structure

**Deliverable:** extraction that generalizes beyond development examples.

---

### Milestone 6 - Submission

* [ ] Final evaluation run
* [ ] Record final metrics
* [ ] Update README with actual architecture
* [ ] Verify setup instructions from a clean environment
* [ ] Verify run instructions
* [ ] Remove unused dependencies/code
* [ ] Verify no credentials are committed
* [ ] Select 2-3 representative demo examples
* [ ] Record Loom demo

**Deliverable:** submission-ready repository.

---

### Milestone 7 - Bonus Features

Only begin after the core requirements are satisfied.

Potential features:

* [ ] Confidence scores
* [ ] Feedback/correction UI
* [ ] Spec/catalog code resolution

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

### YYYY-MM-DD - Python

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

### YYYY-MM-DD - PDF Parser

**Decision:** TBD

**Evidence:** TBD

**Reason:** TBD

**Alternatives considered:**

* PyMuPDF
* pdfplumber

**Status:** Pending experiment

---

### YYYY-MM-DD - Extraction Strategy

**Decision:** TBD

**Evidence:** TBD

**Alternatives considered:**

* Deterministic extraction
* LLM-based extraction
* Hybrid extraction

**Status:** Pending baseline evaluation

---

### YYYY-MM-DD - LLM Provider

**Decision:** TBD

**Evidence:** TBD

**Reason:** TBD

**Status:** Pending

---

### YYYY-MM-DD - API

**Decision:** No API initially.

**Reason:**

The extraction pipeline can be developed and evaluated without an HTTP layer.

An API will only be introduced if required for deployment or UI integration.

**Status:** Accepted

---

### YYYY-MM-DD - Database

**Decision:** No database initially.

**Reason:**

Persistence is not required by the challenge and does not improve initial extraction accuracy.

**Status:** Accepted

---

## 15. Current Focus

The current implementation focus should always be explicitly recorded here so coding agents do not attempt to implement the entire plan at once.

### Current Milestone

**Milestone 1 - Document Exploration**

### Current Objective

Inspect representative PDFs and determine the most reliable way to preserve text and spatial layout.

### Next Steps

* [ ] Select representative PDFs
* [ ] Identify section/list examples
* [ ] Identify table examples
* [ ] Identify difficult examples
* [ ] Compare PyMuPDF and pdfplumber
* [ ] Record findings
* [ ] Choose initial parser

### Do Not Implement Yet

Until the document exploration milestone provides evidence for the architecture, do not prematurely implement:

* Database persistence
* Async job infrastructure
* Cloud infrastructure
* Full frontend
* Feedback UI
* Complex LLM orchestration

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
