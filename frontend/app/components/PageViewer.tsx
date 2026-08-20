"use client";

import { useEffect, useState } from "react";

import { useExtraction } from "@/context/ExtractionContext";
import { pageImageUrl } from "@/lib/api";

/**
 * Draws the page image with the set's bounding boxes on top. Boxes are placed
 * as percentages of the page's PDF dimensions, so the overlay stays aligned at
 * any rendered image size.
 */
export function PageViewer() {
  const { documentId, result, selectedSet } = useExtraction();
  const [page, setPage] = useState<number | null>(null);

  const spanPages = selectedSet
    ? [...new Set(selectedSet.location.spans.map((span) => span.page))]
    : [];

  useEffect(() => {
    setPage(spanPages[0] ?? selectedSet?.location.page ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSet?.set_number]);

  if (!documentId || !result || !selectedSet || page === null) {
    return <p className="muted">The source page appears here once a set is selected.</p>;
  }

  const pageInfo = result.pages.find((candidate) => candidate.page === page);
  if (!pageInfo) return <p className="muted">Page {page} is not in this document.</p>;

  const toStyle = (bbox: [number, number, number, number]) => ({
    left: `${(bbox[0] / pageInfo.width) * 100}%`,
    top: `${(bbox[1] / pageInfo.height) * 100}%`,
    width: `${((bbox[2] - bbox[0]) / pageInfo.width) * 100}%`,
    height: `${((bbox[3] - bbox[1]) / pageInfo.height) * 100}%`,
  });

  const setSpan = selectedSet.location.spans.find((span) => span.page === page);
  const componentSpans = selectedSet.components
    .map((component) => component.location)
    .filter((span): span is NonNullable<typeof span> => !!span && span.page === page);

  return (
    <section className="viewer">
      <header className="viewer__header">
        <h2>Source location</h2>
        {spanPages.length > 1 && (
          <div className="viewer__pages">
            {spanPages.map((candidate) => (
              <button
                key={candidate}
                type="button"
                className={candidate === page ? "is-selected" : ""}
                onClick={() => setPage(candidate)}
              >
                page {candidate}
              </button>
            ))}
          </div>
        )}
      </header>

      <div className="viewer__stage">
        {/* Plain <img>: the API returns a rendered PNG, so Next's optimizer adds nothing. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={pageImageUrl(documentId, page)} alt={`Page ${page} of ${result.source}`} />
        <div className="viewer__overlay">
          {setSpan && <span className="box box--set" style={toStyle(setSpan.bbox)} />}
          {componentSpans.map((span, index) => (
            <span key={index} className="box box--component" style={toStyle(span.bbox)} />
          ))}
        </div>
      </div>

      <p className="muted small">
        The outer box is the set&rsquo;s footprint on this page; the inner boxes are its components.
      </p>
    </section>
  );
}
