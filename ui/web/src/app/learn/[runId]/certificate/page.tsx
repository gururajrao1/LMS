"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, BookOpen, Printer, ShieldCheck } from "lucide-react";
import { AppShell, Loading } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Certificate, getJson } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function CertificatePage() {
  const { runId } = useParams<{ runId: string }>();
  const user = useSession(["msl", "hcp"]);
  const [certificate, setCertificate] = useState<Certificate | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    getJson<Certificate>(`/api/learn/${user.id}/${runId}/certificate`).then(setCertificate)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Certificate not available yet."));
  }, [user, runId]);

  if (!user) return <AppShell><Loading /></AppShell>;
  if (!certificate) {
    return (
      <AppShell user={user}>
        <div className="mx-auto max-w-lg py-16 text-center">
          <p className="text-stone-600">{error || "Loading your certificate…"}</p>
          <Button nativeButton={false} render={<Link href={`/learn/${runId}`} />} className="mt-6 bg-brand-600 hover:bg-brand-800">Back to the course</Button>
        </div>
      </AppShell>
    );
  }

  const day = (value?: string) => value ? new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "–";
  const issued = day(certificate.issued_at);
  const expires = day(certificate.expires_at);

  return (
    <AppShell user={user}>
      <div className="mx-auto max-w-3xl">
        <div className="mb-5 flex items-center justify-between print:hidden">
          <Link href={`/learn/${runId}`} className="inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:text-brand-700"><ArrowLeft size={16} /> Back to the course</Link>
          <Button onClick={() => window.print()} className="bg-brand-600 hover:bg-brand-800"><Printer /> Print or save as PDF</Button>
        </div>

        <Card className="overflow-hidden p-0 print:ring-0">
          <div className="h-2 bg-brand-600" />
          <CardContent className="px-8 py-12 text-center sm:px-16">
            <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-brand-600 text-white"><BookOpen size={26} /></span>
            <p className="mt-6 text-sm font-semibold uppercase tracking-[.2em] text-brand-700">Certificate of completion</p>
            <p className="mt-8 text-sm text-stone-600">This certifies that</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight">{certificate.learner_name}</h1>
            {certificate.learner_title && <p className="mt-1 text-stone-600">{certificate.learner_title}</p>}
            <p className="mt-8 text-sm text-stone-600">has successfully completed the training course</p>
            <h2 className="mt-2 text-2xl font-semibold">{certificate.drug?.brand} · {user.role.toUpperCase()} track</h2>
            {certificate.course_title && <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-stone-600">{certificate.course_title}</p>}

            <div className="mx-auto mt-10 grid max-w-2xl grid-cols-2 gap-6 border-t pt-8 text-sm sm:grid-cols-4">
              <div><p className="text-xl font-semibold tabular-nums text-brand-700">{certificate.score}%</p><p className="mt-1 text-stone-600">Final score</p></div>
              <div><p className="text-xl font-semibold tabular-nums">v{certificate.course_version}</p><p className="mt-1 text-stone-600">Course version</p></div>
              <div><p className="text-xl font-semibold tabular-nums">{issued}</p><p className="mt-1 text-stone-600">Issued</p></div>
              <div><p className="text-xl font-semibold tabular-nums">{expires}</p><p className="mt-1 text-stone-600">Valid through</p></div>
            </div>

            {certificate.approved_by?.length ? (
              <div className="mx-auto mt-8 max-w-2xl border-t pt-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-stone-600">Course content approved by</p>
                <div className="mt-3 flex flex-wrap justify-center gap-x-10 gap-y-3">
                  {certificate.approved_by.map((approver) => (
                    <div key={approver.name}>
                      <p className="font-medium">{approver.name}</p>
                      <p className="text-xs text-stone-600">{approver.title}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <p className="mt-10 flex items-center justify-center gap-2 text-xs text-stone-600">
              <ShieldCheck size={14} /> Verification code {certificate.code}
            </p>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
