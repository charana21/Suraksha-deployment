import { useEffect } from "react";
import { ArrowLeft, ExternalLink, Globe } from "lucide-react";
import { Link } from "react-router-dom";

const DIGITAL_TWIN_URL = "https://sec-dt-dev.tride.live/";

export default function DigitalTwinPge() {
  useEffect(() => {
    const opened = window.open(DIGITAL_TWIN_URL, "_blank", "noopener,noreferrer");

    if (opened) {
      opened.focus();
    }
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 text-slate-100">
      <div className="w-full max-w-xl rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl shadow-black/40">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-cyan-300/80">
          <Globe className="h-4 w-4" />
          Digital Twin
        </div>

        <h1 className="mt-4 text-2xl font-semibold text-foreground">
          Opening the Digital Twin in a new tab
        </h1>

        <p className="mt-2 text-sm leading-6 text-slate-400">
          If the new tab did not open, your browser may have blocked pop-ups. Use the button below to launch it manually.
        </p>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <a
            href={DIGITAL_TWIN_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-medium text-slate-950 transition-colors hover:bg-cyan-400"
          >
            Open Digital Twin
            <ExternalLink className="h-4 w-4" />
          </a>

          <Link
            to="/"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
