import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Category } from "../types";

export function useMenu() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMenu();
      setCategories(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load the menu.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { categories, loading, error, refetch };
}
