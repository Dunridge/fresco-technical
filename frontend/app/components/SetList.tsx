"use client";

import { useExtraction } from "@/context/ExtractionContext";
import { confidenceTone } from "./confidence";

export function SetList() {
  const { sets, selectedSetNumber, selectSet, reviewedSetNumbers, reviewProgress } =
    useExtraction();

  const complete = reviewProgress.reviewed >= reviewProgress.total && reviewProgress.total > 0;

  return (
    <nav className="setlist" aria-label="Hardware sets">
      <h2>
        Hardware sets <span className="pill">{sets.length}</span>
      </h2>
      <p className={`review-progress ${complete ? "is-complete" : ""}`}>
        {reviewProgress.reviewed} of {reviewProgress.total} checked
        {complete ? " \u2713" : ""}
      </p>
      <ul>
        {sets.map((hardwareSet) => {
          const pages = [...new Set(hardwareSet.location.spans.map((span) => span.page))];
          const selected = hardwareSet.set_number === selectedSetNumber;
          const reviewed = reviewedSetNumbers.has(hardwareSet.set_number);
          return (
            <li key={hardwareSet.set_number}>
              <button
                type="button"
                className={`setlist__item ${selected ? "is-selected" : ""} ${
                  reviewed ? "is-reviewed" : ""
                }`}
                onClick={() => selectSet(hardwareSet.set_number)}
                aria-current={selected}
              >
                <span className="setlist__number">
                  {reviewed && (
                    <span className="setlist__check" aria-label="checked">
                      &#10003;
                    </span>
                  )}
                  SET {hardwareSet.set_number}
                </span>
                <span className="setlist__meta">
                  {hardwareSet.not_used
                    ? "not used"
                    : `${hardwareSet.components.length} component${
                        hardwareSet.components.length === 1 ? "" : "s"
                      }`}
                  {" · "}
                  {pages.length > 1 ? `pages ${pages.join("–")}` : `page ${pages[0] ?? hardwareSet.location.page}`}
                </span>
                {hardwareSet.description && (
                  <span className="setlist__desc">{hardwareSet.description}</span>
                )}
                {hardwareSet.confidence !== null && (
                  <span className={`chip chip--${confidenceTone(hardwareSet.confidence)}`}>
                    {Math.round(hardwareSet.confidence * 100)}%
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
