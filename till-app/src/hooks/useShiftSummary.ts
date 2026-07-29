import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { ShiftSummary } from "../types";

export function useShiftSummary() {
  const [summary, setSummary] = useState<ShiftSummary | null>(null);

  const refetch = useCallback(async () => {
    try {
      const data = await api.shiftSummary();
      setSummary(data);
    } catch {
      // Non-critical display — leave the last known value on screen rather
      // than showing an error banner for a background refresh failure.
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { summary, refetch };
}
