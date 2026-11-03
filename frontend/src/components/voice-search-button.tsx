"use client";

import { Mic, MicOff } from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { useDict } from "@/i18n/client";
import { createRecognition, isSpeechSupported, readTranscript, type SpeechRecognitionLike } from "@/lib/speech";
import { cn } from "@/lib/utils";

const noopSubscribe = () => () => {};

/** Speech language: Bangla UI listens for Bangla (bn-BD), English UI for English. */
const SPEECH_LANG = { bn: "bn-BD", en: "en-US" } as const;

/**
 * Mic button that fills a search field with what the user says. Renders nothing when the
 * browser has no speech recognition (e.g. Firefox), so the page never shows a dead button.
 */
export function VoiceSearchButton({
  onTranscript,
  onMessage,
  className,
}: {
  /** Called with interim text while listening and with the final text at the end. */
  onTranscript: (text: string, final: boolean) => void;
  /** Status or error text to show near the field; null clears it. */
  onMessage: (message: string | null) => void;
  className?: string;
}) {
  const t = useDict();
  const supported = useSyncExternalStore(noopSubscribe, isSpeechSupported, () => false);
  const [listening, setListening] = useState(false);
  const recognition = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => () => recognition.current?.abort(), []);

  if (!supported) return null;

  function stop() {
    recognition.current?.stop();
  }

  function start() {
    const r = createRecognition(SPEECH_LANG[t.lang]);
    if (!r) return;
    recognition.current = r;
    let errored = false;
    r.onresult = (event) => {
      const { text, final } = readTranscript(event.results);
      if (text) onTranscript(text, final);
    };
    r.onerror = (event) => {
      errored = event.error !== "aborted";
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        onMessage(t.voice.denied);
      } else if (event.error === "no-speech") {
        onMessage(t.voice.noSpeech);
      } else if (event.error !== "aborted") {
        onMessage(t.voice.failed);
      }
    };
    r.onend = () => {
      setListening(false);
      recognition.current = null;
      if (!errored) onMessage(null); // keep an error visible, clear "listening…"
    };
    onMessage(t.voice.listening);
    setListening(true);
    try {
      r.start();
    } catch {
      setListening(false);
      onMessage(t.voice.failed);
    }
  }

  return (
    <button
      type="button"
      onClick={listening ? stop : start}
      aria-label={listening ? t.voice.stop : t.voice.start}
      aria-pressed={listening}
      title={listening ? t.voice.stop : t.voice.start}
      className={cn(
        "flex size-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
        listening && "animate-pulse bg-primary/10 text-primary",
        className,
      )}
    >
      {listening ? <MicOff aria-hidden className="size-5" /> : <Mic aria-hidden className="size-5" />}
    </button>
  );
}
