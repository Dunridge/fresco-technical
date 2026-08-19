# AGENTS.md

## Purpose

This file defines how AI coding agents should work on the Fresco Hardware Set Extractor.

The system extracts structured hardware sets from Division 08 construction specification documents.

The primary objective is **extraction accuracy and robustness across different specbook formats**, not infrastructure complexity.

Read `PLAN.md` before making architectural or implementation decisions.

---

## 1. Project Priorities

Optimize for these priorities in order:

1. Extraction accuracy
2. Correct hardware-set detection
3. Correct component extraction
4. Correct manufacturer vs. finish classification
5. Accurate source location information
6. Robustness across different document formats
7. Maintainable and understandable code
8. Evaluation coverage
9. Performance
10. UI and infrastructure polish

Do not sacrifice extraction quality to add unnecessary infrastructure or abstractions.

---

## 2. Success Criteria

The implementation should:

* Find all hardware sets in a specification document
* Target 90%+ extraction accuracy
* Extract component fields correctly
* Correctly distinguish manufacturer and finish columns
* Handle ambiguous codes using surrounding context
* Preserve meaningful page/location information
* Handle table and list formats
* Handle multi-page sets
* Extract `NOT USED`, `N/A` and equivalent sets
* Return `null` for missing quantities rather than guessing
* Work across different specbook layouts

---

## 3. Required Output

The conceptual output model is:

```python
class Location:
    page: int
    bbox: list[float] | None
    line_range: list[int] | None


class Component:
    qty: int | None
    description: str | None
    catalog_number: str | None
    mfr: str | None
    finish: str | None
    notes: str | None


class HardwareSet:
    set_number: str
    description: str | None
    location: Location
    components: list[Component]
```

The exact implementation may evolve in `PLAN.md`.

Do not change the public extraction schema without documenting the reason.

---

## 4. Source of Truth

Before implementing a task, read:

1. `AGENTS.md` - engineering workflow and agent rules
2. `PLAN.md` - architecture, technical decisions and current milestones
3. `README.md` - user-facing behavior and setup instructions
4. Relevant tests and evaluation fixtures

If these documents conflict:

* The challenge requirements have highest priority
* `PLAN.md` is the source of truth for architecture
* `AGENTS.md` is the source of truth for development workflow
* Actual tested behavior takes precedence over stale documentation

If implementation changes invalidate documentation, update the relevant documentation.

---

## 5. Engineering Principles

### Prefer Simple Solutions

Implement the smallest solution that reliably solves the current problem.

Do not introduce:

* Databases
* Message queues
* Distributed workers
* Cloud infrastructure
* Complex abstraction layers
* Additional frameworks

unless they solve a demonstrated requirement.

### Accuracy Before Architecture

This is primarily a document extraction problem.

Prioritize:

```text
PDF
 ↓
Document Parsing
 ↓
Layout Representation
 ↓
Hardware Set Detection
 ↓
Structured Extraction
 ↓
Validation / Normalization
 ↓
HardwareSet[]
```

over production infrastructure.

### Do Not Guess

When source information is unavailable or ambiguous beyond a reasonable confidence level, preserve uncertainty.

For example:

```json
{
  "qty": null
}
```

is preferable to inventing a quantity.

### Preserve Source Evidence

Whenever practical, extracted information should remain traceable to its source page and location.

Do not discard spatial information prematurely.

---

## 6. Extraction Principles

### Layout Matters

Do not treat the PDF as plain text when spatial information is available.

Preserve information such as:

* Page number
* Bounding boxes
* Line grouping
* Relative position
* Column position
* Table structure

### Manufacturer vs. Finish

Never classify ambiguous short codes based only on the individual value.

For example:

```text
PE
NO
```

may have multiple interpretations.

Use contextual evidence such as:

* Column headers
* Neighboring values
* Other values in the same column
* Relative column position
* Known manufacturer patterns
* Known finish patterns
* Document-level structure

A column containing values such as:

```text
MK
LCN
SCH
```

is evidence that the column represents manufacturers.

A column containing values such as:

```text
US26D
630
BSP
```

is evidence that the column represents finishes.

Prefer contextual classification over isolated lookup tables.

### Set Boundaries

Do not assume every set has an explicit closing marker.

Consider:

* New set headers
* Blank rows
* Layout changes
* Set-number changes
* Page breaks
* Continuation rows

### Multi-page Sets

Do not automatically terminate a set at a page boundary.

Determine whether content on the next page continues the active set.

### NOT USED Sets

Sets marked with values such as:

```text
NOT USED
N/A
NOT APPLICABLE
```

must still be extracted.

They may legitimately contain zero components.

### Missing Quantities

Never infer a quantity simply because a component normally has a particular quantity.

If quantity is absent:

```text
qty = null
```

---

## 7. AI / LLM Usage

AI models may be used where semantic reasoning improves extraction.

However, do not use an LLM where deterministic logic is clearly more reliable.

Prefer a hybrid approach:

```text
Deterministic parsing
        +
Semantic extraction
        +
Deterministic validation
```

LLM output must be:

* Structured
* Schema validated
* Checked for missing or malformed fields
* Treated as untrusted input

Do not silently accept invalid model output.

Avoid prompts that encourage guessing.

When possible, provide the model with relevant layout/context rather than isolated values.

---

## 8. Evaluation-Driven Development

Evaluation is part of the implementation, not a final step.

Every meaningful extraction improvement should follow this loop:

```text
Identify failure
      ↓
Create/reproduce evaluation case
      ↓
Understand root cause
      ↓
Implement smallest reasonable change
      ↓
Run focused tests
      ↓
Run evaluation suite
      ↓
Compare results
      ↓
Check for regressions
      ↓
Repeat
```

Do not optimize against a single PDF without checking other representative documents.

---

## 9. Golden Evaluation Data

Representative manually verified examples should be stored in the evaluation corpus.

Golden outputs should contain the expected:

* Hardware sets
* Set numbers
* Descriptions
* Components
* Manufacturer fields
* Finish fields
* Quantities
* Locations where appropriate

Do not modify expected outputs merely to make a failing implementation pass.

If a golden output is incorrect, document why it is being changed.

---

## 10. Evaluation Metrics

Where practical, track:

* Set detection accuracy
* Component detection accuracy
* Field accuracy
* Manufacturer accuracy
* Finish accuracy
* Set-number accuracy
* Location accuracy
* Multi-page set accuracy

When making an extraction change, compare metrics before and after.

A local improvement that causes significant regressions elsewhere should not be accepted without justification.

---

## 11. Testing Requirements

Add tests for new deterministic behavior.

Important edge cases should have regression tests or evaluation fixtures.

Before considering a task complete, run the relevant test suite.

Example:

```bash
pytest
```

Run the evaluation suite when extraction behavior changes.

The exact evaluation command should be documented in `PLAN.md` or `README.md` once finalized.

---

## 12. Definition of Done

An implementation task is complete only when:

1. The requested behavior works
2. Relevant tests pass
3. Relevant evaluation cases pass
4. Existing extraction behavior has been checked for regressions
5. Output remains schema-valid
6. Missing information is not guessed
7. New edge cases have appropriate tests or evaluation coverage
8. Documentation is updated if architecture or behavior changed

Do not declare success solely because the code runs.

---

## 13. Working With Failures

When an extraction failure occurs, classify it before changing code.

Suggested categories:

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

Determine the root cause before implementing a fix.

Prefer fixing the underlying category rather than adding document-specific exceptions.

---

## 14. Avoid Overfitting

Do not add logic such as:

```python
if filename == "example_17.pdf":
    ...
```

Do not hard-code values that only solve one provided document unless they represent a general domain rule.

Every extraction heuristic should answer:

> Why should this work on another specbook with the same structural pattern?

---

## 15. Refactoring

Do not perform large unrelated refactors while fixing extraction behavior.

Prefer:

```text
small change
→ test
→ evaluate
→ commit
```

over:

```text
rewrite subsystem
→ introduce multiple changes
→ discover regressions
→ unclear root cause
```

Refactor when there is demonstrated complexity or duplication.

---

## 16. Dependencies

Before adding a dependency:

1. Determine whether an existing dependency can solve the problem
2. Confirm the dependency materially simplifies the implementation
3. Prefer mature and well-maintained libraries
4. Avoid adding large frameworks for small utilities

Document major dependency decisions in `PLAN.md`.

---

## 17. Performance

Correctness comes before optimization.

However, avoid obviously unnecessary work such as:

* Reprocessing unchanged pages
* Repeating identical LLM requests
* Sending entire documents when only a relevant region is needed
* Repeatedly parsing the same PDF during one extraction run

Optimize only after correctness is measurable.

---

## 18. Security

Never commit:

* API keys
* Access tokens
* Credentials
* `.env` files containing secrets

Use environment variables for external services.

Example files should contain placeholders only.

---

## 19. Code Quality

Prefer:

* Small focused functions
* Explicit types
* Descriptive names
* Clear data transformations
* Schema validation
* Minimal hidden state
* Testable extraction stages

Avoid unnecessary abstractions and excessive comments.

Comments should explain **why**, not restate obvious code.

---

## 20. Agent Behavior

When given an implementation task:

### Before Coding

1. Read the relevant portion of `PLAN.md`
2. Inspect the existing implementation
3. Inspect related tests/evals
4. Identify the smallest change required

### During Coding

1. Keep the change focused
2. Preserve existing interfaces unless change is necessary
3. Add/update tests
4. Avoid unrelated refactors

### After Coding

1. Run focused tests
2. Run broader tests when appropriate
3. Run extraction evaluations when extraction behavior changed
4. Inspect failures
5. Fix regressions or explain unavoidable tradeoffs
6. Update documentation when necessary

Never report a test/evaluation as passing unless it was actually executed.

---

## 21. Sub-Agent Usage

Sub-agents may be used for well-defined parallel investigation tasks.

Good examples:

* Analyze failures involving manufacturer vs. finish
* Investigate multi-page extraction failures
* Compare PDF parsing approaches
* Review evaluation mismatches
* Inspect table-layout edge cases

Avoid having multiple agents independently modify the same subsystem simultaneously.

The primary agent remains responsible for integrating and validating all changes.

---

## 22. Planning

`PLAN.md` is a living document.

Update it when:

* A major technical decision is made
* An architectural assumption changes
* A milestone is completed
* Evaluation reveals a new major problem category
* A significant tradeoff is accepted

Do not update `PLAN.md` for trivial implementation details.

Major decisions should be recorded in its decision log.

---

## 23. README

`README.md` is reviewer-facing.

It should eventually describe only what actually exists.

Do not claim:

* Unsupported accuracy numbers
* Features that were planned but not implemented
* Infrastructure that does not exist
* Evaluation results that were not measured

Before final submission, ensure README commands have actually been executed successfully.

---

## 24. Final Submission Checks

Before the project is considered ready for submission:

* [ ] Fresh environment setup works
* [ ] README instructions are accurate
* [ ] Extraction runs successfully
* [ ] Tests pass
* [ ] Evaluation suite runs successfully
* [ ] Representative specbook formats have been tested
* [ ] Manufacturer vs. finish ambiguity has explicit coverage
* [ ] Multi-page sets have explicit coverage
* [ ] NOT USED sets have explicit coverage
* [ ] Missing quantities return `null`
* [ ] Location information is meaningful
* [ ] No credentials are committed
* [ ] Demo examples are reproducible

The final goal is not to build the most complex system.

The goal is to build the **smallest robust extraction system that demonstrates strong accuracy, thoughtful engineering decisions and reliable behavior across different construction specification formats**.
