# Fresco Hardware Set Extractor

Technical assignment for extracting structured hardware sets from Division 08 construction specification documents.

## Overview

Construction specification documents contain hardware sets that define groups of door hardware components such as hinges, locksets, closers and related equipment.

These sets can appear in different formats, including structured tables and section-based lists.

The goal of this project is to identify every hardware set in a provided specification document and return it in a consistent structured format while preserving its location in the source document.

## Expected Output

Each extracted hardware set follows this structure:

```json
{
  "set_number": "3A",
  "description": "ENTRANCE DOORS",
  "location": {
    "page": 12,
    "bbox": [72, 180, 540, 610]
  },
  "components": [
    {
      "qty": 3,
      "description": "HINGE",
      "catalog_number": "TA2714",
      "mfr": "MK",
      "finish": "US26D",
      "notes": null
    }
  ]
}
```

Each hardware set contains:

* `set_number` - hardware set identifier such as `1`, `3A` or `15`
* `description` - optional set heading
* `location` - page number and source location
* `components` - hardware components belonging to the set

Each component may contain:

* `qty`
* `description`
* `catalog_number`
* `mfr`
* `finish`
* `notes`

Missing values are returned as `null` rather than guessed.

## Requirements

The extractor is designed to handle:

* Section/list-based hardware sets
* Table-based hardware sets
* Different column layouts across specbooks
* Ambiguous manufacturer and finish codes
* Hardware sets spanning multiple pages
* Sets marked `NOT USED`, `N/A` or similar
* Missing quantities
* Non-obvious set boundaries
* Source location information for extracted sets

### Manufacturer vs. Finish

Some short codes can have different meanings depending on their context.

For example, `PE` may refer to a manufacturer or a finish depending on where it appears.

The extraction system should therefore consider surrounding values and document structure rather than classify ambiguous values independently.

## Approach

The extraction pipeline is organized around four stages:

```text
Specification PDF
       |
       v
Document Parsing
       |
       v
Hardware Set Detection
       |
       v
Structured Extraction
       |
       v
Validation / Normalization
       |
       v
Structured JSON
```

### 1. Document Parsing

Extract text and layout information from each page while preserving information needed to locate extracted hardware sets in the original document.

### 2. Hardware Set Detection

Identify hardware-set headers, component regions and boundaries between sets.

### 3. Structured Extraction

Convert the detected content into the expected hardware-set and component schema.

### 4. Validation and Normalization

Normalize extracted values and handle ambiguous or missing information without guessing unsupported values.

## Evaluation

The system is evaluated primarily on:

* Hardware set detection accuracy
* Component extraction accuracy
* Correct field mapping
* Manufacturer vs. finish classification
* Set boundary detection
* Multi-page set handling
* Location accuracy
* Performance across different specification formats

The target is approximately **90%+ extraction accuracy** across representative documents.

## Project Structure

```text
.
├── src/
│   └── extraction logic
├── tests/
│   └── automated tests
├── evals/
│   └── extraction evaluation
├── samples/
│   └── sample input documents
├── AGENTS.md
├── README.md
└── requirements.txt
```

The exact structure may evolve as the implementation develops.

## Setup

### Prerequisites

* Python 3.11+

### Installation

Clone the repository:

```bash
git clone <repository-url>
cd <repository-name>
```

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If the extractor uses an external AI provider, create a `.env` file with the required API credentials.

Do not commit API keys or other secrets to the repository.

## Running the Extractor

```bash
python <entrypoint> <path-to-specification>
```

Example:

```bash
python <entrypoint> samples/example.pdf
```

The extractor returns structured hardware-set data as JSON.

> The exact command will be updated once the implementation entrypoint is finalized.

## Running Tests

```bash
pytest
```

## Running Evaluations

```bash
python <evaluation-entrypoint>
```

The evaluation suite compares extracted results against expected outputs across representative specification formats.

> Evaluation commands and metrics will be updated as the evaluation pipeline is implemented.

## Important Edge Cases

### NOT USED Sets

Sets marked `NOT USED`, `N/A` or equivalent should still be returned even when they contain no hardware components.

### Missing Quantities

If a quantity cannot be determined from the source document, the extractor returns:

```json
{
  "qty": null
}
```

rather than attempting to infer it.

### Multi-page Sets

A hardware set may begin on one page and continue onto another. Continuation content should remain associated with the same set.

### Inconsistent Layouts

The extractor should not depend on a single fixed column structure because different specification documents may organize component fields differently.

### Ambiguous Codes

Manufacturer and finish codes should be interpreted using surrounding context such as column position, headers and neighboring values.

## Design Decisions and Tradeoffs

This section will document the major implementation decisions made during development, including:

* PDF parsing strategy
* Set boundary detection
* Table vs. list handling
* Manufacturer/finish disambiguation
* Use of deterministic logic vs. AI-based extraction
* Multi-page set handling
* Location representation

## Bonus Features

If time permits, additional features may include:

* Feedback UI for correcting extraction errors
* Confidence scores for extracted fields
* Spec/catalog shorthand resolution

## Demo

The submission includes a short demo showing the extractor running against multiple specification formats and explaining the major implementation decisions and tradeoffs.

## Challenge Materials

The source specification documents were provided as part of the Fresco Hardware Sets coding challenge.
