/** Shared voice preference for the read-aloud buttons.
 *
 * Speech synthesis voices come from the device (OS/browser), so the list
 * differs per machine and often arrives late — hence the loader below.
 * The choice persists on this device only.
 */

const STORAGE_KEY = "pl-voice-uri";

export type VoiceOption = { voiceURI: string; name: string; lang: string };

/** Pure pick: preferred voice when it exists, otherwise null (system default). */
export function resolveVoice(voices: VoiceOption[], preferredURI: string | null): VoiceOption | null {
  if (!preferredURI) return null;
  return voices.find((voice) => voice.voiceURI === preferredURI) ?? null;
}

export function getPreferredVoiceURI(): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setPreferredVoiceURI(uri: string | null) {
  try {
    if (typeof window === "undefined") return;
    if (uri) window.localStorage.setItem(STORAGE_KEY, uri);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* private mode: fall back to the default voice */
  }
}

/** Voices may load after first paint; waits for them (with a timeout). */
export function loadVoices(timeoutMs = 2000): Promise<VoiceOption[]> {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return Promise.resolve([]);
  const synth = window.speechSynthesis;
  const snapshot = (): VoiceOption[] =>
    synth.getVoices().map((voice) => ({ voiceURI: voice.voiceURI, name: voice.name, lang: voice.lang }));
  const ready = snapshot();
  if (ready.length) return Promise.resolve(ready);
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      synth.removeEventListener?.("voiceschanged", finish);
      resolve(snapshot());
    };
    synth.addEventListener?.("voiceschanged", finish);
    window.setTimeout(finish, timeoutMs);
  });
}

/** Apply the stored preference to an utterance, if that voice exists. */
export function applyPreferredVoice(utterance: SpeechSynthesisUtterance) {
  try {
    const uri = getPreferredVoiceURI();
    if (!uri) return;
    const match = window.speechSynthesis.getVoices().find((voice) => voice.voiceURI === uri);
    if (match) utterance.voice = match;
  } catch {
    /* keep the default voice */
  }
}
