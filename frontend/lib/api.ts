import type { ExtractionResponse, HardwareSet } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* the error body was not JSON; keep the status line */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function uploadPdf(file: File, useLlm = false): Promise<ExtractionResponse> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${API_URL}/extract?llm=${useLlm}`, { method: "POST", body });
  return unwrap<ExtractionResponse>(response);
}

export async function saveFeedback(
  documentId: string,
  hardwareSets: HardwareSet[],
  note?: string,
  reviewedSetNumbers: string[] = [],
): Promise<{ saved: boolean }> {
  const response = await fetch(`${API_URL}/documents/${documentId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      hardware_sets: hardwareSets,
      note: note ?? null,
      reviewed_set_numbers: reviewedSetNumbers,
    }),
  });
  return unwrap<{ saved: boolean }>(response);
}

export function pageImageUrl(documentId: string, page: number): string {
  return `${API_URL}/documents/${documentId}/pages/${page}.png`;
}

export async function checkApi(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}
