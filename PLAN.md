# Fresco Hardware Set Extractor - Implementation Plan

## 1. Goal

Extract hardware sets and their components from Division 08
specification PDFs with 90%+ accuracy.

## 2. Success Criteria

- Detect all hardware sets
- Extract components accurately
- Correctly distinguish manufacturer vs finish
- Preserve page/location information
- Handle multi-page sets
- Handle NOT USED sets
- Return null rather than guessing missing quantities

## 3. Architecture

PDF
 ↓
PDF Parser
 ↓
Layout Representation
 ↓
Set Detection
 ↓
Structured Extraction
 ↓
Validation / Normalization
 ↓
HardwareSet[]

## 4. Technical Decisions

### Language
Python

Why:
- Strong PDF/document-processing ecosystem
- Recommended by assignment
- Matches Fresco backend

### PDF parsing
TBD

Candidates:
- PyMuPDF
- pdfplumber

Decision:
TBD after testing representative PDFs.

### Structured models
Pydantic

### LLM
TBD

### API
TBD - only add if required by demo/UI.

### Database
None initially.

Reason:
Persistence isn't required by the assignment.

## 5. Extraction Strategy

### Stage 1 - Parse
Extract:
- text
- page
- bounding boxes
- words/lines
- table/layout information

### Stage 2 - Detect sets
Identify candidate hardware-set boundaries.

### Stage 3 - Extract components
Map source content into HardwareSet schema.

### Stage 4 - Normalize
Resolve:
- manufacturer vs finish
- missing quantities
- NOT USED
- continuation pages

## 6. Evaluation Strategy

Create manually verified expected outputs for representative
documents.

Measure:

- set detection
- component detection
- field accuracy
- manufacturer accuracy
- finish accuracy

Every extraction change must run against the evaluation corpus.

## 7. Development Loop

Choose failure
 ↓
Reproduce
 ↓
Understand cause
 ↓
Implement smallest fix
 ↓
Run tests
 ↓
Run evals
 ↓
Compare metrics
 ↓
Check regressions
 ↓
Update PLAN.md if architecture changed

## 8. Implementation Milestones

### Milestone 1 - PDF exploration
- [ ] Inspect representative PDFs
- [ ] Identify major document formats
- [ ] Compare PDF parsing libraries
- [ ] Choose parser

### Milestone 2 - Baseline extractor
- [ ] Detect simple set headers
- [ ] Extract simple components
- [ ] Produce HardwareSet JSON
- [ ] Preserve location

### Milestone 3 - Evaluation harness
- [ ] Create golden examples
- [ ] Build evaluator
- [ ] Establish baseline metrics

### Milestone 4 - Hard cases
- [ ] Manufacturer vs finish
- [ ] Multi-page sets
- [ ] NOT USED
- [ ] Missing quantities
- [ ] Different table layouts

### Milestone 5 - Polish
- [ ] Improve error handling
- [ ] Final eval
- [ ] README
- [ ] Demo
- [ ] Optional bonus UI

## 9. Definition of Done

A change is complete only when:

1. Tests pass
2. Evaluation suite passes
3. Existing extraction accuracy does not regress
4. New behavior has an evaluation case
5. Output remains schema-valid

## 10. Open Questions

- Which PDF parser performs best?
- Is an LLM necessary for every page?
- Can tables be handled deterministically first?
- How should multi-page bounding boxes be represented?
- What confidence threshold should trigger fallback extraction?

## 11. Decision Log

### YYYY-MM-DD - PDF Parser

Decision:
TBD

Reason:
TBD

Alternatives considered:
TBD

### YYYY-MM-DD - Extraction Strategy

Decision:
TBD

Reason:
TBD