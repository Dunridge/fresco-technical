"use client";

import { ComponentTable } from "./components/ComponentTable";
import { PageViewer } from "./components/PageViewer";
import { SetList } from "./components/SetList";
import { UploadPanel } from "./components/UploadPanel";
import { useExtraction } from "@/context/ExtractionContext";

export default function Home() {
  const { status, error, result } = useExtraction();

  return (
    <main>
      <header className="masthead">
        <h1>Hardware Set Extractor</h1>
        <p>Division 08 specbooks in, structured hardware sets out.</p>
      </header>

      <UploadPanel />

      {status === "error" && error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {result?.warnings.map((warning) => (
        <p className="warning" key={warning}>
          {warning}
        </p>
      ))}

      {status === "ready" && result && (
        <div className="workspace">
          <aside>
            <SetList />
          </aside>
          <div className="workspace__main">
            <ComponentTable />
            <PageViewer />
          </div>
        </div>
      )}

      {status === "idle" && (
        <section className="empty">
          <h2>What this does</h2>
          <ul>
            <li>Finds every hardware set, including ones marked NOT USED.</li>
            <li>Reads each component&rsquo;s quantity, description, catalog number, manufacturer and finish.</li>
            <li>
              Decides manufacturer vs. finish from the column a value sits in, so <code>PE</code> can be
              Pemko on one page and Painted Enamel on another.
            </li>
            <li>Keeps sets together across page breaks and records where each one came from.</li>
            <li>Leaves a missing quantity as null rather than guessing it.</li>
          </ul>
          <p className="muted">
            Every field carries a confidence score, and anything the extractor got wrong can be
            corrected here and saved.
          </p>
        </section>
      )}
    </main>
  );
}
