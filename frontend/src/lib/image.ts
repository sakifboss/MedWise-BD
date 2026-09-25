const MAX_SIDE = 2000;
const JPEG_QUALITY = 0.85;

/**
 * Downscales a photo to at most 2000px on its longest side and re-encodes it as JPEG.
 * Phone photos shrink from several MB to a few hundred KB, which keeps uploads fast.
 * Falls back to the original file if the browser cannot decode it (e.g. HEIC on Chrome).
 */
export async function prepareImage(file: File): Promise<{ blob: Blob; filename: string }> {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas not supported");
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
    );
    if (!blob || blob.size >= file.size) return { blob: file, filename: file.name };
    return { blob, filename: "prescription.jpg" };
  } catch {
    return { blob: file, filename: file.name };
  }
}
