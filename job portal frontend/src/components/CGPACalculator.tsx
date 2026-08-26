"use client";

import { useMemo, useState } from "react";

type Subject = { id: number; name: string; obtained: number; total: number; credits: number };
type Semester = { id: number; name: string; subjects: Subject[] };

let nextId = 10;
const newSubject = (): Subject => ({ id: nextId++, name: "", obtained: 0, total: 4, credits: 3 });

function normalized(subject: Subject) {
  if (subject.total <= 0) return 0;
  return Math.min(4, Math.max(0, (subject.obtained / subject.total) * 4));
}

function semesterGpa(semester: Semester) {
  const weight = semester.subjects.reduce((sum, subject) => sum + Math.max(0, subject.credits), 0);
  return weight ? semester.subjects.reduce((sum, subject) => sum + normalized(subject) * Math.max(0, subject.credits), 0) / weight : 0;
}

export function CGPACalculator() {
  const [semesters, setSemesters] = useState<Semester[]>([
    { id: 1, name: "Semester 1", subjects: [newSubject(), newSubject()] },
  ]);
  const totals = useMemo(() => {
    const subjects = semesters.flatMap((semester) => semester.subjects);
    const credits = subjects.reduce((sum, subject) => sum + Math.max(0, subject.credits), 0);
    const points = subjects.reduce((sum, subject) => sum + normalized(subject) * Math.max(0, subject.credits), 0);
    return { cgpa: credits ? points / credits : 0, credits };
  }, [semesters]);

  function updateSubject(semesterId: number, subjectId: number, field: keyof Subject, value: string | number) {
    setSemesters((current) => current.map((semester) => semester.id === semesterId ? { ...semester, subjects: semester.subjects.map((subject) => subject.id === subjectId ? { ...subject, [field]: value } : subject) } : semester));
  }

  return (
    <div className="calculator-shell cgpa-calculator" data-testid="cgpa-calculator">
      <div className="calculator-intro"><p className="tool-kicker">Pakistan 4.00 scale</p><h2>Build your semester record</h2><p>Add every subject and semester. Credit hours keep the final CGPA properly weighted.</p></div>
      <div className="cgpa-summary"><span>Current CGPA</span><strong>{totals.cgpa.toFixed(2)} <small>/ 4.00</small></strong><em>{totals.credits} credit hours included</em></div>
      <div className="semester-stack">
        {semesters.map((semester, semesterIndex) => (
          <section className="semester-card" key={semester.id}>
            <header><div><p>Semester {semesterIndex + 1}</p><input aria-label={`Semester ${semesterIndex + 1} name`} value={semester.name} onChange={(event) => setSemesters((current) => current.map((item) => item.id === semester.id ? { ...item, name: event.target.value } : item))} /></div><strong>{semesterGpa(semester).toFixed(2)} GPA</strong>{semesters.length > 1 && <button type="button" className="text-button danger" onClick={() => setSemesters((current) => current.filter((item) => item.id !== semester.id))}>Remove semester</button>}</header>
            <div className="subject-table">
              <div className="subject-head"><span>Subject</span><span>Obtained GPA</span><span>Total GPA</span><span>Credit hours</span><span /></div>
              {semester.subjects.map((subject, subjectIndex) => <div className="subject-row" key={subject.id}>
                <label><span className="mobile-only">Subject</span><input aria-label={`Semester ${semesterIndex + 1} subject ${subjectIndex + 1}`} placeholder={`Subject ${subjectIndex + 1}`} value={subject.name} onChange={(event) => updateSubject(semester.id, subject.id, "name", event.target.value)} /></label>
                <label><span className="mobile-only">Obtained GPA</span><input aria-label={`Subject ${subjectIndex + 1} obtained GPA`} type="number" min="0" max={subject.total || 4} step="0.01" value={subject.obtained || ""} onChange={(event) => updateSubject(semester.id, subject.id, "obtained", Math.max(0, Number(event.target.value) || 0))} /></label>
                <label><span className="mobile-only">Total GPA</span><input aria-label={`Subject ${subjectIndex + 1} total GPA`} type="number" min="0.01" step="0.01" value={subject.total} onChange={(event) => updateSubject(semester.id, subject.id, "total", Math.max(0.01, Number(event.target.value) || 4))} /></label>
                <label><span className="mobile-only">Credit hours</span><input aria-label={`Subject ${subjectIndex + 1} credit hours`} type="number" min="0.5" max="12" step="0.5" value={subject.credits} onChange={(event) => updateSubject(semester.id, subject.id, "credits", Math.max(0.5, Number(event.target.value) || 3))} /></label>
                <button type="button" aria-label={`Remove subject ${subjectIndex + 1}`} disabled={semester.subjects.length === 1} onClick={() => setSemesters((current) => current.map((item) => item.id === semester.id ? { ...item, subjects: item.subjects.filter((candidate) => candidate.id !== subject.id) } : item))}>×</button>
              </div>)}
            </div>
            <button type="button" className="btn btn-ghost" onClick={() => setSemesters((current) => current.map((item) => item.id === semester.id ? { ...item, subjects: [...item.subjects, newSubject()] } : item))}>+ Add subject</button>
          </section>
        ))}
      </div>
      <button type="button" className="btn btn-primary" onClick={() => setSemesters((current) => [...current, { id: nextId++, name: `Semester ${current.length + 1}`, subjects: [newSubject()] }])}>+ Add another semester</button>
      <aside className="calculator-note"><strong>How it is calculated:</strong> each subject is normalized to 4.00 from obtained GPA ÷ total GPA, then weighted by credit hours. Confirm your university&apos;s grading policy because some institutions use marks, quality points, repeated-course rules or a different weighting method.</aside>
    </div>
  );
}
