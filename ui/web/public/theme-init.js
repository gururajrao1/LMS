/* Applied before the app hydrates so the first paint already has the right
   theme — no light flash on a dark visit. Mirrors lib/theme.ts. Served from
   /public and loaded with a plain blocking <script> in <head> (see layout.tsx),
   since next/script renders outside <head> and trips a hydration warning. */
(function () {
  try {
    var t = localStorage.getItem("pl-theme");
    if (t !== "light" && t !== "dark") {
      t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    if (t === "dark") document.documentElement.classList.add("dark");
  } catch { /* private mode: stay light, the toggle still works per visit */ }
})();
