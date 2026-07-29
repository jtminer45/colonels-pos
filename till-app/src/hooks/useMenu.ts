import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Category } from "../types";

// A manager can change a price or add a new item from the dashboard at any
// time and expects the till to reflect it without staff needing to reload
// the page — so the menu polls in the background. Background polls never
// flip `loading` back on: that would blank the item grid staff are looking
// at every time the interval fires, which would be worse than the problem
// this is solving.
const BACKGROUND_POLL_MS = 30_000;

export function useMenu() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isFirstLoad = useRef(true);

  const refetch = useCallback(async () => {
    if (isFirstLoad.current) setLoading(true);
    try {
      const data = await api.getMenu();
      setCategories(data);
      setError(null);
    } catch (e) {
      // Don't clobber an already-loaded menu with an error banner just
      // because one background poll failed — only surface it if we have
      // nothing to show yet.
      if (isFirstLoad.current) {
        setError(e instanceof Error ? e.message : "Failed to load the menu.");
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

  return { categories, loading, error, refetch };
}
