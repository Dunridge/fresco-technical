"use client";

import { useState } from "react";

import { isEdited, useExtraction } from "@/context/ExtractionContext";
import { COMPONENT_FIELDS, FIELD_LABELS, type ComponentField } from "@/lib/types";
import { confidenceTone } from "./confidence";

export function ComponentTable() {
  const { selectedSet, editedFields, updateComponent, revertSet, save, saveState, hasEdits, result } =
    useExtraction();
  const [note, setNote] = useState("");

  if (!selectedSet) {
    return <p className="muted">Select a hardware set to review its components.</p>;
  }

  const setEdited = [...editedFields].some((key) =>
    key.startsWith(`${selectedSet.set_number}:`),
  );

  return (
    <section className="components">
      <header className="components__header">
        <div>
          <h2>Set {selectedSet.set_number}</h2>
          {selectedSet.description && <p className="muted">{selectedSet.description}</p>}
        </div>
        <div className="components__actions">
          {setEdited && (
            <button type="button" className="ghost" onClick={() => revertSet(selectedSet.set_number)}>
              Revert set
            </button>
          )}
          <button
            type="button"
            onClick={() => void save(note || undefined)}
            disabled={!hasEdits || saveState === "saving"}
          >
            {saveState === "saving"
              ? "Saving…"
              : saveState === "saved"
                ? "Saved"
                : "Save corrections"}
          </button>
        </div>
      </header>

      {selectedSet.not_used ? (
        <p className="notice">
          This set is marked <strong>not used</strong> and correctly has no components.
        </p>
      ) : (
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th className="numcol">#</th>
                {COMPONENT_FIELDS.map((field) => (
                  <th key={field}>{FIELD_LABELS[field]}</th>
                ))}
                <th>Page</th>
              </tr>
            </thead>
            <tbody>
              {selectedSet.components.map((component, index) => (
                <tr key={index}>
                  <td className="numcol">{index + 1}</td>
                  {COMPONENT_FIELDS.map((field) => (
                    <Cell
                      key={field}
                      field={field}
                      value={component[field]}
                      confidence={component.confidence[field]}
                      edited={isEdited(editedFields, selectedSet.set_number, index, field)}
                      onChange={(next) =>
                        updateComponent(selectedSet.set_number, index, field, next)
                      }
                    />
                  ))}
                  <td className="muted">{component.location?.page ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hasEdits && (
        <div className="components__note">
          <label htmlFor="feedback-note">Note for this correction (optional)</label>
          <input
            id="feedback-note"
            type="text"
            value={note}
            placeholder="e.g. the finish column was read as manufacturer on page 3"
            onChange={(event) => setNote(event.target.value)}
          />
        </div>
      )}

      {result && Object.keys(result.legend).length > 0 && (
        <details className="legend">
          <summary>Abbreviations printed on the page ({Object.keys(result.legend).length})</summary>
          <ul>
            {Object.entries(result.legend).map(([code, meaning]) => (
              <li key={code}>
                <code>{code}</code> {meaning}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

interface CellProps {
  field: ComponentField;
  value: string | number | null;
  confidence: number | undefined;
  edited: boolean;
  onChange: (value: string) => void;
}

function Cell({ field, value, confidence, edited, onChange }: CellProps) {
  const tone = confidenceTone(confidence);
  return (
    <td className={`cell cell--${tone} ${edited ? "cell--edited" : ""}`}>
      <input
        aria-label={FIELD_LABELS[field]}
        value={value === null ? "" : String(value)}
        placeholder="null"
        inputMode={field === "qty" ? "numeric" : "text"}
        onChange={(event) => onChange(event.target.value)}
      />
      {confidence !== undefined && (
        <span className="cell__confidence" title={`Confidence ${Math.round(confidence * 100)}%`}>
          {Math.round(confidence * 100)}
        </span>
      )}
    </td>
  );
}
