/**
 * Minimal typing for the browser Web Speech API (Chrome, Edge, Safari). Audio is turned into text
 * by the browser itself; nothing is sent to the MedWise backend.
 */

export type SpeechErrorCode = "not-allowed" | "service-not-allowed" | "no-speech" | "audio-capture" | string;

type SpeechResultList = ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;

export interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous: boolean;
  onresult: ((event: { results: SpeechResultList }) => void) | null;
  onerror: ((event: { error: SpeechErrorCode }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function recognitionClass(): SpeechRecognitionConstructor | undefined {
  if (typeof window === "undefined") return undefined;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

export function isSpeechSupported(): boolean {
  return recognitionClass() !== undefined;
}

export function createRecognition(lang: string): SpeechRecognitionLike | null {
  const Recognition = recognitionClass();
  if (!Recognition) return null;
  const recognition = new Recognition();
  recognition.lang = lang;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  recognition.continuous = false;
  return recognition;
}

/** Joins the best transcript of every result so far; `final` is true once speech has ended. */
export function readTranscript(results: SpeechResultList): { text: string; final: boolean } {
  let text = "";
  let final = results.length > 0;
  for (let i = 0; i < results.length; i++) {
    text += results[i][0]?.transcript ?? "";
    final &&= results[i].isFinal;
  }
  return { text: text.trim(), final };
}
