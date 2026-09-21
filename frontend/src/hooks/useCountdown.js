import { useEffect, useState } from "react";

export default function useCountdown(untilMs) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!untilMs) return undefined;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [untilMs]);

  if (!untilMs) return 0;
  return Math.max(0, Math.ceil((untilMs - now) / 1000));
}
