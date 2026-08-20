export type ComponentField =
  | "qty"
  | "description"
  | "catalog_number"
  | "mfr"
  | "finish"
  | "notes";

export const COMPONENT_FIELDS: ComponentField[] = [
  "qty",
  "description",
  "catalog_number",
  "mfr",
  "finish",
  "notes",
];

export const FIELD_LABELS: Record<ComponentField, string> = {
  qty: "Qty",
  description: "Description",
  catalog_number: "Catalog number",
  mfr: "Mfr",
  finish: "Finish",
  notes: "Notes",
};

export interface Span {
  page: number;
  bbox: [number, number, number, number];
  line_range: [number, number] | null;
}

export interface Location {
  page: number;
  bbox: [number, number, number, number] | null;
  line_range: [number, number] | null;
  spans: Span[];
}

export interface HardwareComponent {
  qty: number | null;
  description: string | null;
  catalog_number: string | null;
  mfr: string | null;
  finish: string | null;
  notes: string | null;
  location: Span | null;
  confidence: Partial<Record<ComponentField, number>>;
}

export interface HardwareSet {
  set_number: string;
  description: string | null;
  location: Location;
  components: HardwareComponent[];
  not_used: boolean;
  confidence: number | null;
  column_mapping: Record<string, string>;
}

export interface PageInfo {
  page: number;
  width: number;
  height: number;
  has_text: boolean;
}

export interface ExtractionResult {
  source: string;
  page_count: number;
  pages: PageInfo[];
  hardware_sets: HardwareSet[];
  legend: Record<string, string>;
  warnings: string[];
}

export interface ExtractionResponse {
  document_id: string;
  filename: string;
  result: ExtractionResult;
}
