"""Optional LLM refinement pass.

The deterministic pipeline is the system: it runs, and is evaluated, with no
model access at all. This layer is opt-in (`--llm`) and only revisits sets the
deterministic pass is *not* confident about, because sending every page to a
model would be slower, costlier and no more accurate on the layouts the column
model already handles.

Model output is treated as untrusted: it is schema-validated, then every value
is checked to appear verbatim in the source region before it is accepted. That
guard is what keeps the "never guess" rule intact - a model cannot invent a
quantity that is not printed on the page.
"""

from __future__ import annotations

import os
import re

from pydantic import BaseModel, Field

from .models import Component, ExtractionResult, HardwareSet
from .parsing.layout import Document, Line

DEFAULT_MODEL = "claude-opus-5"
MAX_TOKENS = 16000
REFINE_BELOW_CONFIDENCE = 0.85
FIELD_ACCEPT_BELOW_CONFIDENCE = 0.8
CHAR_WIDTH = 5.0


class LLMComponent(BaseModel):
    qty: int | None = None
    description: str | None = None
    catalog_number: str | None = None
    mfr: str | None = None
    finish: str | None = None
    notes: str | None = None


class LLMHardwareSet(BaseModel):
    set_number: str
    description: str | None = None
    components: list[LLMComponent] = Field(default_factory=list)


SYSTEM_PROMPT = """\
You read door-hardware schedules from Division 08 construction specbooks.

You are given one hardware set exactly as it is printed, with the original
column spacing preserved. Return its components as structured data.

Rules:
- Copy values verbatim from the text. Never normalise, expand or invent them.
- If a field is not printed for a component, return null. Never infer a
  quantity from what the component usually needs.
- Manufacturer and finish are decided by the column a value sits in, not by the
  value itself. Some codes are used for both: PE is Pemko in a column of
  manufacturers and Painted Enamel in a column of finishes; NO is Norton beside
  LCN and SARGENT. Read the whole column before deciding.
- Sets marked NOT USED or N/A have no components. Return an empty list.
"""


class LLMUnavailable(RuntimeError):
    pass


def refine_with_llm(
    result: ExtractionResult,
    document: Document,
    model: str | None = None,
    client=None,
) -> ExtractionResult:
    """Revisit low-confidence sets with a model and merge only safe corrections."""
    targets = [s for s in result.hardware_sets if _needs_refinement(s)]
    if not targets:
        result.warnings.append("LLM refinement skipped: every set was extracted confidently.")
        return result

    client = client or _build_client()
    model = model or os.environ.get("HARDWARE_SETS_LLM_MODEL", DEFAULT_MODEL)

    for hardware_set in targets:
        region_text = render_region(document, hardware_set)
        if not region_text.strip():
            continue
        try:
            proposal = _ask_model(client, model, region_text)
        except Exception as exc:  # pragma: no cover - network failure path
            result.warnings.append(f"LLM refinement failed for set {hardware_set.set_number}: {exc}")
            continue
        if proposal is None:
            result.warnings.append(
                f"LLM declined to answer for set {hardware_set.set_number}; deterministic output kept."
            )
            continue
        merged = _merge(hardware_set, proposal, region_text)
        if merged:
            result.warnings.append(
                f"LLM refined set {hardware_set.set_number}: {', '.join(merged)}"
            )
    return result


def _build_client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise LLMUnavailable("The `anthropic` package is required for --llm.") from exc
    return anthropic.Anthropic()


def _needs_refinement(hardware_set: HardwareSet) -> bool:
    if hardware_set.not_used:
        return False
    if hardware_set.confidence is not None and hardware_set.confidence < REFINE_BELOW_CONFIDENCE:
        return True
    return any(
        value < FIELD_ACCEPT_BELOW_CONFIDENCE
        for component in hardware_set.components
        for value in component.confidence.values()
    )


def _ask_model(client, model: str, region_text: str) -> LLMHardwareSet | None:
    response = client.messages.parse(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"<hardware_set>\n{region_text}\n</hardware_set>",
            }
        ],
        output_format=LLMHardwareSet,
    )
    if getattr(response, "stop_reason", None) == "refusal":
        return None
    return response.parsed_output


def render_region(document: Document, hardware_set: HardwareSet) -> str:
    """Re-render the set's lines with their original column spacing intact.

    Collapsing the region to plain text would destroy exactly the evidence the
    manufacturer/finish decision depends on, so spacing is reconstructed from
    the word coordinates.
    """
    chunks: list[str] = []
    for span in hardware_set.location.spans or []:
        page = next((p for p in document.pages if p.number == span.page), None)
        if page is None or span.line_range is None:
            continue
        low, high = span.line_range
        lines = [ln for ln in page.content_lines if low <= ln.index <= high]
        if not lines:
            continue
        chunks.append(f"[page {span.page}]")
        chunks.extend(_render_line(line) for line in lines)
    return "\n".join(chunks)


def _render_line(line: Line) -> str:
    rendered = ""
    for word in line.words:
        column = max(int(word.x0 / CHAR_WIDTH), len(rendered))
        rendered = rendered.ljust(column) + word.text
    return rendered.rstrip()


def _normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _source_tokens(region_text: str) -> set[str]:
    return {_normalize(token) for token in region_text.split() if _normalize(token)}


def _appears_in_source(value, source_tokens: set[str], source_normalized: str) -> bool:
    """Require the value to be printed on the page, at token granularity.

    A single token must match a whole token in the source. Matching against the
    whole concatenated page would let `1` pass because `315CN` contains a "1".
    """
    if value is None:
        return True
    parts = [_normalize(part) for part in str(value).split()]
    parts = [part for part in parts if part]
    if not parts:
        return False
    if len(parts) == 1:
        return parts[0] in source_tokens
    return "".join(parts) in source_normalized


def _merge(hardware_set: HardwareSet, proposal: LLMHardwareSet, region_text: str) -> list[str]:
    """Accept a model value only where deterministic confidence was low.

    A high-confidence deterministic field is never overwritten, and no value is
    accepted unless it is present in the source text.
    """
    source_normalized = _normalize(region_text)
    source_tokens = _source_tokens(region_text)
    changes: list[str] = []

    if len(proposal.components) != len(hardware_set.components):
        # A disagreement about component count is a signal, not a correction:
        # silently reshaping the set would lose the traceable line locations.
        return changes

    for index, (current, suggested) in enumerate(
        zip(hardware_set.components, proposal.components)
    ):
        for name in ("qty", "description", "catalog_number", "mfr", "finish", "notes"):
            suggested_value = getattr(suggested, name)
            current_value = getattr(current, name)
            if suggested_value is None or suggested_value == current_value:
                continue
            if name == "qty" and current_value is None:
                # A quantity that the page does not print stays null. The model
                # is never allowed to supply one.
                continue
            if current.confidence.get(name, 0.0) >= FIELD_ACCEPT_BELOW_CONFIDENCE:
                continue
            if not _appears_in_source(suggested_value, source_tokens, source_normalized):
                continue
            setattr(current, name, suggested_value)
            current.confidence[name] = 0.7
            changes.append(f"component {index + 1} {name}")
    return changes


def component_from_llm(source: LLMComponent) -> Component:
    return Component(**source.model_dump())
