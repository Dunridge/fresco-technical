# Fresco Hardware Set Extractor

Extracts **hardware sets** from Division 08 (Openings) construction specification
PDFs into structured JSON, with the location of every set preserved back to the
source page.

The repository contains two projects:

| Path | What it is |
| --- | --- |
| [`backend/`](backend) | The extraction pipeline, its evaluation harness, a CLI and a small HTTP API (Python) |
| [`frontend/`](frontend) | A review UI for browsing, verifying and correcting extractions (Next.js + TypeScript) |

Setup and run instructions for both are at the end of this file:
**[Running the projects](#running-the-projects)**.

---

## What it produces

```json
{
  "set_number": "2",
  "description": "DOORS: 105, 106",
  "location": {
    "page": 1,
    "bbox": [72.0, 218.43, 515.3, 338.69],
    "line_range": [10, 18],
    "spans": [
      { "page": 1, "bbox": [72.0, 218.43, 515.3, 338.69], "line_range": [10, 18] }
    ]
  },
  "not_used": false,
  "confidence": 0.998,
  "column_mapping": {
    "x72": "qty", "x100": "unit", "x132": "description",
    "x280": "catalog_number", "x440": "finish", "x500": "mfr"
  },
  "components": [
    {
      "qty": 2,
      "description": "CONTINUOUS HINGE",
      "catalog_number": "224HD",
      "mfr": "PE",
      "finish": "628",
      "notes": null,
      "location": { "page": 1, "bbox": [72.0, 268.08, 510.2, 278.69], "line_range": [13, 13] },
      "confidence": {
        "qty": 1.0, "description": 1.0, "catalog_number": 1.0,
        "mfr": 0.75, "finish": 1.0
      }
    }
  ]
}
```

`set_number`, `description`, `location` and `components[]` are the fields the
challenge specifies. Everything else is additive:

* `location.spans` — one entry per page, so a set that crosses a page break
  reports its full footprint. `location.page` / `location.bbox` still describe
  where the set *starts*.
* `not_used` — the set was found and is marked NOT USED / N/A; `components` is
  legitimately empty.
* `confidence` — per field and per set (see [Bonus features](#bonus-features)).
* `column_mapping` — which component field was assigned to each column position,
  so a field-mapping mistake is diagnosable rather than mysterious.

Note this example: the schedule prints **FINISH left of MFR**, and `PE` is still
correctly read as the manufacturer. Both come from column content, not position.

---

## How it works

```text
PDF
 │
 ├─ 1. Parse            words + bounding boxes, clustered into visual rows
 ├─ 2. Strip furniture  running headers/footers repeated across pages
 ├─ 3. Find sets        header regex over one document-ordered line stream
 ├─ 4. Detect columns   union-gap analysis of word extents
 ├─ 5. Classify columns aggregate column evidence → qty/desc/catalog/mfr/finish/notes
 ├─ 6. Build components cells → schema rows, with wrapped text re-joined
 └─ 7. Normalize        clean values, keep nulls, validate schema
 ↓
HardwareSet[]
```

Four decisions carry most of the weight.

### 1. Column geometry, not text parsing

A column boundary is an x-range that **no word on any row occupies**, wider than
a space. Because that test is computed over the union of every row in the set, it
works identically for a ruled table schedule and a plain indented list — one code
path handles both layout families, rather than a table branch and a list branch
that drift apart.

### 2. Manufacturer vs. finish is a property of the column

This is the challenge's central caveat, and the rule is: **never classify a code
on its own.** Each column is scored from the aggregate of its values, and codes
that genuinely mean both things — `PE`, `NO`, `AL`, `PC`, `BR`, `SP` — are
excluded from the scoring entirely, so a column is decided by its *unambiguous*
members.

The same `PE`, from the same code table, with no per-document configuration:

| Source | Column also contains | `PE` resolves to |
| --- | --- | --- |
| Fixture 01, set 2 | `VON`, `LCN` | **manufacturer** (Pemko) |
| Fixture 02, set 2A | `628`, `BSP`, `US26D` | **finish** (Painted Enamel) |

The same applies to `NO` → Norton when its column holds `HAG`, `SAR`, `IVE`.

Where a schedule prints both in one cell (`MK US26D`), the pair is split by
whichever token is unambiguously typed — so a column of `PE US26D` resolves `PE`
to the manufacturer because `US26D` can only be a finish.

Evidence is used in this order:

1. An abbreviation legend printed on the page (`PE = PEMKO`) — decisive
2. An explicit column header (`MFR`, `FIN`) — strong, but content can override it
   when the header is misaligned
3. The aggregate content of the column
4. The same column position elsewhere in the document, for a set whose own column
   is all-ambiguous

### 3. Multi-page sets fall out of the region model

Sets are cut from a single document-ordered line stream rather than page by page,
so a set that runs past a page break simply keeps collecting lines. There is no
separate stitching pass to get wrong. An explicit `HARDWARE SET 4 (CONT'D)`
header merges into the set already open instead of starting a new one.

### 4. Missing values stay missing

A quantity that is not printed is `null`. The extractor never infers one, and the
optional LLM pass is explicitly forbidden from supplying one.

---

## Handling of the challenge's caveats

| Caveat | Where it is handled | Covered by |
| --- | --- | --- |
| Mfr vs. finish codes | `classification/columns.py`, `classification/vocab.py` | `test_columns.py`, fixtures 01/02/04 |
| Non-obvious set boundaries | `detection/sets.py` | `test_detection.py` |
| NOT USED sets | `normalization/normalize.py` | fixtures 01/02/03/04 |
| Multi-page sets | `detection/sets.py` region model | fixtures 01 (bare) and 03 (`CONT'D`) |
| Inconsistent column layouts | `detect_columns` + aggregate scoring | four different schemas across the fixtures |
| Missing quantities | `_parse_qty`, LLM merge guard | fixtures 01/02/03/04 |
| Location data | `Location.spans` | `test_locations_are_meaningful` |

Also handled: running headers/footers, descriptions wrapped onto a second line,
boilerplate prose between sets, quantity and unit sharing a cell, manufacturer
and finish sharing a column, and set numbers like `3A`.

---

## Accuracy

```text
CORPUS OVERALL ACCURACY: 100.0%  (348/348 assertions)
no failures
```

**Read that number with its caveat.** The challenge specbooks are not
redistributable, so the evaluation corpus is four PDFs written for this
repository to reproduce the layout families and caveats the challenge describes.
100% means the pipeline handles those structures correctly — it is **not** a
measurement against the real corpus.

What makes it more than self-congratulation:

* The goldens were hand-written from the fixture *source*, not from extractor
  output.
* **Fixture 04 was written after the pipeline was finished**, as a deliberate
  generalisation test — merged mfr+finish columns, qty and unit in one cell, a
  set whose manufacturer codes are *all* the ambiguous `PE`, prose between sets,
  a footer instead of a header. It failed in four distinct ways on first run.
  Each was fixed at the root cause, not special-cased, and fixtures 01–03 did not
  regress.

To measure against real documents, drop them in `backend/samples/` and run the
CLI; to add them to the corpus, write the expected JSON into `evals/expected/`.

The metric is defined precisely in `evals/evaluate.py`: the share of individual
assertions that are correct — 3 per expected set (number, description, start
page) and 6 per expected component (all fields). A missed set or component scores
zero for all of its assertions, and **a hallucinated one adds the same number of
failed assertions**, so inventing output is penalised exactly as heavily as
missing it.

---

## Bonus features

**Confidence scores** — every extracted field carries one, derived from how
strongly its column classified and whether the value matches the expected shape
for that field. A value resolved purely from column context (an ambiguous `PE`)
is capped at 0.75, so the fields most worth a human glance surface themselves.

**Spec/catalog code resolution** — abbreviation legends printed on the page
(`MK = MCKINNEY   SCH = SCHLAGE   PE = PEMKO`) are parsed into `legend`, shown in
the UI, and used as the strongest signal when classifying an ambiguous column.

**Feedback UI** — every field is editable in place, edits are highlighted,
a set can be reverted, and corrections are saved with an optional note.

---

## Optional LLM assist

The extractor is **fully deterministic by default** — no API key, no network, no
per-page cost, and evaluation is reproducible.

`--llm` adds a refinement pass that revisits only sets the deterministic pipeline
scored as low-confidence. Model output is treated as untrusted:

* validated against a Pydantic schema;
* every proposed value must appear **verbatim in the source region**, matched at
  token granularity;
* a field the deterministic pass was confident about is never overwritten;
* **a null quantity is never filled in**, under any circumstances;
* a disagreement about component *count* is reported, not applied.

It needs `ANTHROPIC_API_KEY` and the `anthropic` package. Its guard rails are
unit-tested against a fake client; it has **not** been exercised against the live
API in this environment.

---

## Project layout

```text
backend/
├── src/hardware_sets/
│   ├── models.py              # the public schema (Pydantic)
│   ├── pipeline.py            # orchestration, two-pass column hinting
│   ├── parsing/               # PDF → words/lines/boxes; header-footer removal
│   ├── detection/             # set headers, region building, page legends
│   ├── classification/        # column geometry, domain vocabulary, field scoring
│   ├── extraction/            # rows → components
│   ├── normalization/         # cleanup and validation
│   ├── llm.py                 # optional refinement (off by default)
│   ├── cli.py                 # python -m hardware_sets
│   └── api.py                 # FastAPI app for the UI
├── tests/                     # 109 tests
├── evals/
│   ├── generate_fixtures.py   # builds the fixture PDFs
│   ├── parser_comparison.py   # the PyMuPDF vs pdfplumber experiment
│   ├── evaluate.py            # the metric
│   ├── fixtures/ expected/    # the golden corpus
└── samples/                   # drop your own PDFs here

frontend/
├── app/                       # Next.js app router, page + components
├── context/                   # React Context holding extraction + edit state
└── lib/                       # API client and shared types
```

---

## Known limitations

* **Scanned pages are not OCR'd.** A page with no text layer is reported in
  `warnings` rather than processed.
* **Columns separated by less than ~1.6 character widths merge.** The
  manufacturer/finish case has a dedicated splitter; a description overrunning
  into a catalog column does not.
* **Column geometry is pooled across the pages of one set**, which assumes a
  document keeps its columns in the same place. True for every layout tested.
* **The `--llm` path is unit-tested only**, never run against the live API here.

---

# Running the projects

Everything below has been run against this repository. Two terminals: one for the
backend, one for the frontend.

## Prerequisites

* **Python 3.11+** (`python3 --version`)
* **Node.js 18.18+** (`node --version`)

## 1. Clone

```bash
git clone <repository-url> && cd fresco-technical
```

## 2. Backend — terminal 1

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

(`.[dev]` adds the test dependencies. Plain `pip install -e .` is enough to run
the extractor, but not `pytest`.)

On Windows, activate with `.venv\Scripts\activate` instead.

Generate the evaluation fixtures (small sample PDFs used by the tests, evals and
the walkthrough below):

```bash
python evals/generate_fixtures.py
```

Start the API:

```bash
uvicorn hardware_sets.api:app --reload --port 8000
```

Leave it running. Check it with `curl http://localhost:8000/health` — it should
return `{"status":"ok"}`.

## 3. Frontend — terminal 2

```bash
cd frontend && npm install && npm run dev
```

Open **http://localhost:3000** and upload a PDF — for example
`backend/evals/fixtures/fixture_01_table_schedule.pdf`.

If port 3000 is taken, Next.js will offer the next free port; the API already
accepts 3000, 3001 and 3100. For any other port, start the backend with:

```bash
HARDWARE_SETS_CORS_ORIGINS=http://localhost:4000 uvicorn hardware_sets.api:app --port 8000
```

To point the UI at a backend elsewhere, copy `frontend/.env.local.example` to
`frontend/.env.local` and set `NEXT_PUBLIC_API_URL`.

## Using the extractor without the UI

The pipeline is a plain CLI — no server, no frontend, no API key:

```bash
python -m hardware_sets evals/fixtures/fixture_01_table_schedule.pdf --summary
```

```bash
python -m hardware_sets path/to/specbook.pdf --out result.json
```

Other flags: `--compact` (single-line JSON), `--backend pdfplumber` (the
alternate parser), `--llm` (optional refinement — needs `ANTHROPIC_API_KEY`).

As a library:

```python
from hardware_sets.pipeline import extract_hardware_sets

result = extract_hardware_sets("specbook.pdf")
for hardware_set in result.hardware_sets:
    print(hardware_set.set_number, len(hardware_set.components))
```

## Tests and evaluation

From `backend/`, with the virtualenv active:

```bash
pytest
```

```bash
python evals/evaluate.py
```

`evaluate.py` prints per-fixture and per-field accuracy plus any failures grouped
by category; `--json` emits the same data machine-readably. The parser comparison
behind the PyMuPDF decision re-runs with:

```bash
python evals/parser_comparison.py
```

## A three-minute walkthrough

1. Upload `fixture_01_table_schedule.pdf`. Five sets are found. Set 3 is marked
   **not used** and has no components — correctly extracted, not skipped.
2. Open set 2. The schedule prints **FINISH before MFR**, and the fields are
   still mapped correctly, because they are decided by column content rather than
   position. `PE` is read as the **manufacturer**. The last component has no
   printed quantity, and `qty` is `null` rather than a guess.
3. Now upload `fixture_02_list_sections.pdf` — a list format with no column
   header row. In set 2A, `PE` is read as a **finish**. Same code, same code
   table, opposite answer, decided entirely by the company its column keeps. In
   set 1, `NO` is read as **Norton**.
4. Back in fixture 01, open set 4 and look at *Source location*. It spans pages
   2 and 3; switch pages to see its components highlighted on both, with the
   running header and the neighbouring sets correctly outside the box.
5. Upload `fixture_04_merged_columns.pdf` — manufacturer and finish share one
   column, quantity and unit share a cell, and set 8's manufacturer codes are
   *all* the ambiguous `PE`. They still split correctly.
6. Edit any field, add a note, and press **Save corrections**.

## API reference

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `POST` | `/extract` | Upload a PDF (multipart `file`, optional `?llm=true`) |
| `GET` | `/documents/{id}` | Re-fetch a previous extraction |
| `GET` | `/documents/{id}/pages/{n}.png` | Rendered page image for the overlay |
| `POST` | `/documents/{id}/feedback` | Save reviewer corrections |
| `GET` | `/documents/{id}/feedback` | Load saved corrections |
| `DELETE` | `/documents/{id}` | Delete a document and its data |

Interactive docs at `http://localhost:8000/docs` while the server is running.

Uploads and corrections are written under the system temp directory; override
with `HARDWARE_SETS_STORAGE=/some/path`.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `No module named hardware_sets` | The virtualenv isn't active, or `pip install -e .` wasn't run from `backend/` |
| UI shows `Failed to fetch` | The backend isn't running on port 8000, or the UI is on a port not in the CORS list — see step 3 |
| `missing fixture …` from `evaluate.py` | Run `python evals/generate_fixtures.py` first |
| Extraction returns no sets | The PDF may be scanned; check `warnings` in the output |
| `--llm` fails | `ANTHROPIC_API_KEY` is unset, or `pip install anthropic` is missing |

## No secrets in this repository

There are no API keys, tokens or `.env` files committed. The only credential the
project can use is `ANTHROPIC_API_KEY`, read from the environment, and only on
the opt-in `--llm` path.
