"use client";

export default function JobEditorError({ reset }: { reset: () => void }) {
  return (
    <div className="card-panel p-6 space-y-3">
      <h2 className="text-lg font-semibold text-[var(--navy-100)]">
        The job editor could not be loaded
      </h2>
      <p className="field-error">
        The post may contain legacy data that the editor could not read. Refresh the editor and
        try again.
      </p>
      <button type="button" className="btn btn-primary" onClick={reset}>
        Reload editor
      </button>
    </div>
  );
}
