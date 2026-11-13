/** The prescription QR code as SVG markup: error correction M, printed 5 cm wide (R4). */
export async function makeQrSvg(link: string): Promise<string> {
  const QRCode = (await import("qrcode")).default;
  return QRCode.toString(link, { type: "svg", margin: 1, errorCorrectionLevel: "M" });
}
