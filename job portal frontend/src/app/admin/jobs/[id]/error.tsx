"use client";

export default function JobEditorError() {
  return (
    <div className="card-panel p-6 space-y-3">
      <h2 className="text-lg font-semibold text-[var(--navy-100)]">
        The job editor could not be loaded
      </h2>
      <p className="field-error">
        A frontend module or job-data request failed temporarily. Reload the page to retrieve a
        fresh editor and the latest saved data.
      </p>
      <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
        Reload editor
      </button>
    </div>
  );
}
