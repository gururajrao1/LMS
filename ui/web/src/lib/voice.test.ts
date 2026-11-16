import { describe, expect, it } from "vitest";
import { loadVoices, resolveVoice } from "./voice";

describe("resolveVoice", () => {
  const voices = [
    { voiceURI: "a", name: "A", lang: "en-US" },
    { voiceURI: "b", name: "B", lang: "en-GB" },
  ];

  it("uses the system default when nothing is stored", () => {
    expect(resolveVoice(voices, null)).toBeNull();
  });

  it("returns the stored voice when it exists", () => {
    expect(resolveVoice(voices, "b")).toEqual(voices[1]);
  });

  it("falls back to the default when the stored voice is gone", () => {
    expect(resolveVoice(voices, "gone")).toBeNull();
  });
});

describe("loadVoices", () => {
  it("resolves empty where speech synthesis does not exist", async () => {
    await expect(loadVoices()).resolves.toEqual([]);
  });
});
