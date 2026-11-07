/* Applied before the app hydrates so the first paint already has the right
   theme — no light flash on a dark visit. Mirrors lib/theme.ts. Served from
   /public so next/script can load it in <head> instead of inlining a script
   tag inside React, which React warns about. */
(function () {
  try {
    var t = localStorage.getItem("pl-theme");
    if (t !== "light" && t !== "dark") {
      t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    if (t === "dark") document.documentElement.classList.add("dark");
  } catch (e) { /* private mode: stay light, the toggle still works per visit */ }
})();
