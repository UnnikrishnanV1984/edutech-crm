export interface DataEnvelope<T> {
  data: T;
  meta: { request_id: string };
}

export interface CollectionEnvelope<T> {
  data: T[];
  meta: { request_id: string; page: number; page_size: number; total: number };
}
