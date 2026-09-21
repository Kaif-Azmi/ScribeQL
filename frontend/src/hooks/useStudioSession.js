import { useCallback, useEffect, useState } from "react";
import { createSession, getSession } from "../api/scribeql.js";

const inflight = new Map();

async function bootstrapSession(mode) {
  const existing = await getSession(mode);
  if (existing.ok) {
    return existing.data;
  }
  if (existing.status === 404) {
    const created = await createSession(mode);
    if (!created.ok) {
      throw created.error;
    }
    return created.data;
  }
  throw existing.error;
}

function loadSession(mode) {
  let pending = inflight.get(mode);
  if (!pending) {
    pending = bootstrapSession(mode).finally(() => {
      inflight.delete(mode);
    });
    inflight.set(mode, pending);
  }
  return pending;
}

export default function useStudioSession(mode) {
  const [session, setSession] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(
    async (opts = {}) => {
      const { keepQuestion } = opts;
      void keepQuestion;
      setLoading(true);
      setError(null);
      try {
        const data = await loadSession(mode);
        setSession(data);
        return data;
      } catch (err) {
        setError(err);
        setSession(null);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [mode]
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadSession(mode)
      .then((data) => {
        if (!cancelled) {
          setSession(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err);
          setSession(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [mode]);

  const replaceSession = useCallback(async () => {
    inflight.delete(mode);
    const created = await createSession(mode);
    if (!created.ok) {
      throw created.error;
    }
    setSession(created.data);
    return created.data;
  }, [mode]);

  return { session, setSession, loading, error, refresh, replaceSession };
}
