// Generates the app icons from one SVG (the pill mark from the header, on the brand colour).
// Run from frontend/: node scripts/generate-icons.mjs
import { mkdir, writeFile } from "node:fs/promises";
import sharp from "sharp";

const BRAND = "#007565"; // --primary, oklch(0.5 0.1 180)

// Lucide "pill" (24x24, stroked), scaled to `size` and centred; `scale` is the mark's share of the canvas.
function svg({ size, scale, rounded }) {
  const mark = size * scale;
  const offset = (size - mark) / 2;
  const radius = rounded ? size * 0.22 : 0;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" rx="${radius}" fill="${BRAND}"/>
  <g transform="translate(${offset} ${offset}) scale(${mark / 24})" fill="none" stroke="#ffffff"
     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/>
    <path d="m8.5 8.5 7 7"/>
  </g>
</svg>`;
}

const png = (options, file) => sharp(Buffer.from(svg(options))).png().toFile(file);

await mkdir("public/icons", { recursive: true });
await Promise.all([
  png({ size: 192, scale: 0.6, rounded: true }, "public/icons/icon-192.png"),
  png({ size: 512, scale: 0.6, rounded: true }, "public/icons/icon-512.png"),
  // Maskable: full-bleed background, mark inside the 80% safe zone so any mask shape keeps it whole.
  png({ size: 512, scale: 0.5, rounded: false }, "public/icons/maskable-512.png"),
  // iOS home screen (iOS rounds the corners itself).
  png({ size: 180, scale: 0.6, rounded: false }, "src/app/apple-icon.png"),
]);
await writeFile("src/app/icon.svg", svg({ size: 32, scale: 0.7, rounded: true }));
console.log("icons written");
