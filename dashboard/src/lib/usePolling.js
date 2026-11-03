/**
 * Fetch now and then again every `ms` milliseconds, while the tab is visible.
 * This is what makes the monitor "live": no websockets, just a short poll.
 *
 *   const { data, error, loading, refresh, updatedAt } = usePolling(() => api.stats(), 3000, []);
 *
 * `deps` restart the poll (for example when a filter changes), like useEffect deps.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export function usePolling(fetcher, ms, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true, updatedAt: null });
  const latest = useRef(fetcher);
  latest.current = fetcher;
  const run = useRef(0); // ignore answers that arrive after a newer request started

  const load = useCallback(async () => {
    const id = ++run.current;
    try {
      const data = await latest.current();
      if (id === run.current) setState({ data, error: null, loading: false, updatedAt: new Date() });
    } catch (error) {
      if (id === run.current) setState((s) => ({ ...s, error, loading: false }));
    }
  }, []);

  useEffect(() => {
    setState((s) => ({ ...s, loading: true }));
    load();
    const timer = ms
      ? setInterval(() => {
          if (!document.hidden) load();
        }, ms)
      : null;
    return () => {
      run.current++;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, load, ...deps]);

  return { ...state, refresh: load };
}
