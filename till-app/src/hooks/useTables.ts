import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { TableSummary } from "../types";

// Same reasoning as useMenu's polling: another staff member (or the
// manager updating a price) can change what this screen should show, so it
// refreshes itself in the background rather than only on manual action.
const BACKGROUND_POLL_MS = 15_000;

export function useTables() {
  const [tables, setTables] = useState<TableSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isFirstLoad = useRef(true);

  const refetch = useCallback(async () => {
    if (isFirstLoad.current) setLoading(true);
    try {
      const data = await api.listTables();
      setTables(data);
      setError(null);
    } catch (e) {
      if (isFirstLoad.current) {
        setError(e instanceof Error ? e.message : "Failed to load tables.");
      }
    } finally {
      isFirstLoad.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
    const interval = setInterval(refetch, BACKGROUND_POLL_MS);
    return () => clearInterval(interval);
  }, [refetch]);

  return { tables, loading, error, refetch };
}
