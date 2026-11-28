"use client";
import { useEffect, useState } from "react";
import { fallbackVitals } from "../../lib/host-vitals.mjs";
export function useObservatory({
  traffic = true,
  server = true,
  fallback = true,
  minutes = 60,
} = {}) {
  const [state, setState] = useState({
    traffic: null,
    resources: null,
    loading: true,
    errors: {},
  });
  useEffect(() => {
    let alive = true,
      inFlight = false,
      fallbackAt = 0;
    const controller = new AbortController();
    async function load() {
      if (document.hidden || inFlight) return;
      inFlight = true;
      const errors = {};
      const endpoints = [
        ...(traffic ? [["traffic", `/api/traffic?minutes=${minutes}`]] : []),
        ...(server ? [["resources", "/api/server/resources"]] : []),
      ];
      const changes = {};
      await Promise.all(
        endpoints.map(async ([key, url]) => {
          try {
            const response = await fetch(url, {
              cache: "no-store",
              signal: AbortSignal.any([
                controller.signal,
                AbortSignal.timeout(12000),
              ]),
            });
            if (!response.ok) throw Error("Unavailable");
            changes[key] = await response.json();
          } catch {
            errors[key] = "Unavailable";
          }
        }),
      );
      if (
        server &&
        fallback &&
        !changes.resources?.available &&
        Date.now() - fallbackAt > 30000
      ) {
        fallbackAt = Date.now();
        try {
          const response = await fetch("/api/server/snapshot", {
            cache: "no-store",
            signal: controller.signal,
          });
          if (response.ok)
            changes.resources = fallbackVitals(await response.json());
        } catch {}
      }
      if (alive)
        setState((old) => {
          if (
            server &&
            !changes.resources?.available &&
            old.resources?.approximate
          )
            changes.resources = {
              ...old.resources,
              stale: Date.now() - Date.parse(old.resources.observedAt) > 45000,
            };
          return {
            ...old,
            ...changes,
            loading: false,
            errors,
            refreshedAt: new Date().toISOString(),
          };
        });
      inFlight = false;
    }
    load();
    const timer = setInterval(load, 5000);
    const visible = () => {
      if (!document.hidden) load();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      alive = false;
      controller.abort();
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [traffic, server, minutes, fallback]);
  return state;
}
