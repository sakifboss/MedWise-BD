"use client";

import { useEffect } from "react";

/**
 * Old links (e.g. /alternatives/22, by database id) show the page as it is, then the address bar
 * is changed to the stable URL (/alternatives/BR00022) without loading the page again, so what the
 * person bookmarks or shares from here keeps working after a deploy.
 */
export function CanonicalUrl({ path }: { path: string }) {
  useEffect(() => {
    if (window.location.pathname !== path) {
      window.history.replaceState(window.history.state, "", `${path}${window.location.search}${window.location.hash}`);
    }
  }, [path]);
  return null;
}
