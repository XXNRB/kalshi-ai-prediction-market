"use client";

import { useEffect, useRef, useState } from "react";
import { getMarket } from "./api";
import type { Market } from "./types";

export function useLiveMarket(ticker: string, initialMarket: Market, intervalMs = 15000): Market {
  const [market, setMarket] = useState(initialMarket);
  const tickerRef = useRef(ticker);
  tickerRef.current = ticker;

  useEffect(() => {
    setMarket(initialMarket);
  }, [ticker, initialMarket]);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const latest = await getMarket(tickerRef.current);
        if (!cancelled) setMarket(latest);
      } catch {
        // transient fetch failure — keep showing the last known market
      }
    };

    const id = setInterval(poll, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return market;
}
