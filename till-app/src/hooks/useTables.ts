import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { TableSummary } from "../types";

export function useTables() {
  const [tables, setTables] = useState<TableSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setError(null);
    try {
      const data = await api.listTables();
      setTables(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tables.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { tables, loading, error, refetch };
}
