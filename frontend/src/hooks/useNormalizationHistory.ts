import { useState, useEffect, useCallback } from 'react';
import type { HistoryItem } from '../types';

export const HISTORY_STORAGE_KEY = 'vietnorm:normalization-history';
export const MAX_HISTORY_ITEMS = 10;

function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `hist_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function loadInitialHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    const validItems: HistoryItem[] = [];
    for (const item of parsed) {
      if (
        typeof item === 'object' &&
        item !== null &&
        typeof item.id === 'string' &&
        typeof item.input === 'string' &&
        typeof item.output === 'string' &&
        typeof item.createdAt === 'string'
      ) {
        validItems.push({
          id: item.id,
          input: item.input,
          output: item.output,
          createdAt: item.createdAt,
        });
      }
    }
    return validItems.slice(0, MAX_HISTORY_ITEMS);
  } catch {
    // Return empty list if localStorage parsing or access fails
    return [];
  }
}

function saveHistoryToStorage(items: HistoryItem[]): void {
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(items));
  } catch {
    // Fail silently if localStorage quota is exceeded or storage is disabled
  }
}

export function useNormalizationHistory() {
  const [history, setHistory] = useState<HistoryItem[]>(() => loadInitialHistory());

  // Keep localStorage in sync whenever history state updates
  useEffect(() => {
    saveHistoryToStorage(history);
  }, [history]);

  const addHistoryItem = useCallback((input: string, output: string) => {
    const trimmedInput = input.trim();
    const trimmedOutput = output.trim();
    if (!trimmedInput || !trimmedOutput) return;

    setHistory((prev) => {
      // Prevent consecutive identical duplicate entry
      if (prev.length > 0) {
        const latest = prev[0];
        if (latest.input === input && latest.output === output) {
          return prev;
        }
      }

      const newItem: HistoryItem = {
        id: generateId(),
        input,
        output,
        createdAt: new Date().toISOString(),
      };

      return [newItem, ...prev].slice(0, MAX_HISTORY_ITEMS);
    });
  }, []);

  const removeHistoryItem = useCallback((id: string) => {
    setHistory((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
    try {
      localStorage.removeItem(HISTORY_STORAGE_KEY);
    } catch {
      // Fail silently
    }
  }, []);

  return {
    history,
    addHistoryItem,
    removeHistoryItem,
    clearHistory,
  };
}
