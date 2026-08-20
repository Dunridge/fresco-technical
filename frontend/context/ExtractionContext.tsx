"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { saveFeedback, uploadPdf } from "@/lib/api";
import type {
  ComponentField,
  ExtractionResult,
  HardwareSet,
} from "@/lib/types";

type Status = "idle" | "uploading" | "ready" | "error";
type SaveState = "idle" | "saving" | "saved" | "error";

/** `sets` is the reviewer's working copy; `result` stays as the extractor produced it. */
interface ExtractionState {
  status: Status;
  saveState: SaveState;
  error: string | null;
  documentId: string | null;
  filename: string | null;
  result: ExtractionResult | null;
  sets: HardwareSet[];
  selectedSetNumber: string | null;
  editedFields: Set<string>;
}

interface ExtractionValue extends ExtractionState {
  selectedSet: HardwareSet | null;
  hasEdits: boolean;
  upload: (file: File, useLlm: boolean) => Promise<void>;
  selectSet: (setNumber: string) => void;
  updateComponent: (
    setNumber: string,
    index: number,
    field: ComponentField,
    value: string,
  ) => void;
  revertSet: (setNumber: string) => void;
  save: (note?: string) => Promise<void>;
  clear: () => void;
}

const INITIAL: ExtractionState = {
  status: "idle",
  saveState: "idle",
  error: null,
  documentId: null,
  filename: null,
  result: null,
  sets: [],
  selectedSetNumber: null,
  editedFields: new Set(),
};

const ExtractionContext = createContext<ExtractionValue | null>(null);

const editKey = (setNumber: string, index: number, field: ComponentField) =>
  `${setNumber}:${index}:${field}`;

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

/** Empty input means "the page does not print this", which the schema stores as null. */
function parseFieldValue(field: ComponentField, raw: string): string | number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  if (field === "qty") {
    const parsed = Number.parseInt(trimmed, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }
  return trimmed;
}

export function ExtractionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ExtractionState>(INITIAL);

  const upload = useCallback(async (file: File, useLlm: boolean) => {
    setState({ ...INITIAL, status: "uploading" });
    try {
      const response = await uploadPdf(file, useLlm);
      setState({
        status: "ready",
        saveState: "idle",
        error: null,
        documentId: response.document_id,
        filename: response.filename,
        result: response.result,
        sets: clone(response.result.hardware_sets),
        selectedSetNumber: response.result.hardware_sets[0]?.set_number ?? null,
        editedFields: new Set(),
      });
    } catch (error) {
      setState({
        ...INITIAL,
        status: "error",
        error: error instanceof Error ? error.message : "Upload failed.",
      });
    }
  }, []);

  const selectSet = useCallback((setNumber: string) => {
    setState((previous) => ({ ...previous, selectedSetNumber: setNumber }));
  }, []);

  const updateComponent = useCallback(
    (setNumber: string, index: number, field: ComponentField, value: string) => {
      setState((previous) => {
        const sets = previous.sets.map((hardwareSet) => {
          if (hardwareSet.set_number !== setNumber) return hardwareSet;
          const components = hardwareSet.components.map((component, position) =>
            position === index
              ? { ...component, [field]: parseFieldValue(field, value) }
              : component,
          );
          return { ...hardwareSet, components };
        });
        const editedFields = new Set(previous.editedFields);
        editedFields.add(editKey(setNumber, index, field));
        return { ...previous, sets, editedFields, saveState: "idle" };
      });
    },
    [],
  );

  const revertSet = useCallback((setNumber: string) => {
    setState((previous) => {
      if (!previous.result) return previous;
      const original = previous.result.hardware_sets.find(
        (hardwareSet) => hardwareSet.set_number === setNumber,
      );
      if (!original) return previous;
      const sets = previous.sets.map((hardwareSet) =>
        hardwareSet.set_number === setNumber ? clone(original) : hardwareSet,
      );
      const editedFields = new Set(
        [...previous.editedFields].filter((key) => !key.startsWith(`${setNumber}:`)),
      );
      return { ...previous, sets, editedFields, saveState: "idle" };
    });
  }, []);

  const save = useCallback(
    async (note?: string) => {
      if (!state.documentId) return;
      setState((previous) => ({ ...previous, saveState: "saving" }));
      try {
        await saveFeedback(state.documentId, state.sets, note);
        setState((previous) => ({ ...previous, saveState: "saved", error: null }));
      } catch (error) {
        setState((previous) => ({
          ...previous,
          saveState: "error",
          error: error instanceof Error ? error.message : "Could not save corrections.",
        }));
      }
    },
    [state.documentId, state.sets],
  );

  const clear = useCallback(() => setState(INITIAL), []);

  const value = useMemo<ExtractionValue>(() => {
    const selectedSet =
      state.sets.find((hardwareSet) => hardwareSet.set_number === state.selectedSetNumber) ?? null;
    return {
      ...state,
      selectedSet,
      hasEdits: state.editedFields.size > 0,
      upload,
      selectSet,
      updateComponent,
      revertSet,
      save,
      clear,
    };
  }, [state, upload, selectSet, updateComponent, revertSet, save, clear]);

  return <ExtractionContext.Provider value={value}>{children}</ExtractionContext.Provider>;
}

export function useExtraction(): ExtractionValue {
  const value = useContext(ExtractionContext);
  if (!value) throw new Error("useExtraction must be used inside <ExtractionProvider>.");
  return value;
}

export function isEdited(
  editedFields: Set<string>,
  setNumber: string,
  index: number,
  field: ComponentField,
): boolean {
  return editedFields.has(editKey(setNumber, index, field));
}
