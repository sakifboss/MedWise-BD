import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "MedWise BD",
    short_name: "MedWise BD",
    description:
      "Quality-first medicine alternatives for Bangladesh: same generic, same strength, ranked by manufacturer quality and price.",
    lang: "en",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#007565",
    categories: ["health", "medical"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Scan a prescription", short_name: "Scan", url: "/prescription" },
      { name: "Interaction checker", short_name: "Interactions", url: "/interactions" },
      { name: "Manufacturers", short_name: "Companies", url: "/manufacturers" },
    ],
  };
}
