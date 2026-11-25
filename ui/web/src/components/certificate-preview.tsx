/** Compact visual thumbnails for Classic / Modern / Formal — used on publish. */

type Props = {
  templateId: string;
  /** Course title shown on the mini cert (falls back to a sample). */
  courseTitle?: string;
  selected?: boolean;
};

export function CertificatePreviewThumb({ templateId, courseTitle, selected }: Props) {
  const title = courseTitle?.trim() || "Patient recruitment induction";
  const shell = `overflow-hidden rounded-lg border bg-white text-[7px] leading-tight text-stone-800 shadow-none dark:bg-stone-950 dark:text-stone-100 ${
    selected ? "ring-2 ring-brand-600" : ""
  }`;

  if (templateId === "modern") {
    return (
      <div className={shell} aria-hidden>
        <div className="bg-stone-900 px-2 py-1.5 text-white">
          <p className="text-[6px] uppercase tracking-wider text-stone-400">Certificate</p>
          <p className="mt-0.5 truncate text-[8px] font-semibold">Alex Trainee</p>
        </div>
        <div className="space-y-1 px-2 py-2">
          <p className="text-stone-500 dark:text-stone-400">completed</p>
          <p className="truncate font-semibold">{title}</p>
          <div className="mt-1 grid grid-cols-2 gap-1 border-t border-stone-200 pt-1 dark:border-stone-700">
            <span>70%</span>
            <span>v1</span>
          </div>
        </div>
      </div>
    );
  }

  if (templateId === "formal") {
    return (
      <div className={`border border-amber-700/50 p-0.5 ${selected ? "ring-2 ring-brand-600" : ""}`} aria-hidden>
        <div className="rounded border border-amber-700/30 bg-white px-2 py-2 text-center font-serif dark:bg-stone-950">
          <p className="text-[6px] uppercase tracking-wider text-amber-800 dark:text-amber-400">Certificate</p>
          <p className="mt-1 text-[8px] italic text-stone-500">This certifies that</p>
          <p className="mt-0.5 text-[9px] font-semibold">Alex Trainee</p>
          <p className="mt-1 truncate text-[7px] font-semibold">{title}</p>
          <div className="mx-auto mt-1.5 grid max-w-[90%] grid-cols-2 gap-1 border-y border-amber-700/20 py-1 text-stone-600 dark:text-stone-300">
            <span>70%</span>
            <span>Issued</span>
          </div>
        </div>
      </div>
    );
  }

  // classic (default)
  return (
    <div className={shell} aria-hidden>
      <div className="h-1 bg-brand-600" />
      <div className="space-y-1 px-2 py-2 text-center">
        <div className="mx-auto size-4 rounded bg-brand-600" />
        <p className="text-[6px] font-semibold uppercase tracking-wider text-brand-700 dark:text-brand-300">Certificate</p>
        <p className="text-[7px] text-stone-500">This certifies that</p>
        <p className="text-[9px] font-semibold">Alex Trainee</p>
        <p className="truncate text-[7px] font-semibold">{title}</p>
        <div className="mx-auto mt-1 grid max-w-[90%] grid-cols-2 gap-1 border-t border-stone-200 pt-1 text-stone-600 dark:border-stone-700 dark:text-stone-300">
          <span>70%</span>
          <span>v1</span>
        </div>
      </div>
    </div>
  );
}
