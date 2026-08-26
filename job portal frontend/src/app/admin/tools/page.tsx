"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { RichTextEditor } from "@/components/RichTextEditor";
import { YoastSEOPanel, type YoastSEOValue } from "@/components/YoastSEOPanel";
import {
  API_BASE,
  adminDeleteToolCategory,
  adminDeleteToolPage,
  adminListTools,
  adminSaveToolCategory,
  adminSaveToolPage,
} from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { ToolAdminResponse, ToolCategory, ToolKind, ToolPage } from "@/lib/types";

type EditorMode = "category" | "tool";

const blankSeo = (): YoastSEOValue => ({ focus_keyword: "", meta_title: "", meta_description: "", meta_keywords: "" });
const slugify = (value: string) => value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 100);

export default function AdminToolsPage() {
  const { token } = useAdminAuth();
  const [data, setData] = useState<ToolAdminResponse>({ categories: [], tools: [] });
  const [mode, setMode] = useState<EditorMode>("category");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [categoryForm, setCategoryForm] = useState({ title: "", slug: "", content: "", icon_key: "sparkles", sort_order: 0, is_published: true });
  const [toolForm, setToolForm] = useState({ title: "", slug: "", content: "", category_id: "", tool_kind: "content" as ToolKind, sort_order: 0, is_published: true });
  const [seo, setSeo] = useState<YoastSEOValue>(blankSeo());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slugTouched, setSlugTouched] = useState(false);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try { setData(await adminListTools(token)); }
    catch (err) { setError(err instanceof Error ? err.message : "Tools could not be loaded"); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function loadSeo(entityType: "tool_category" | "tool", id: string) {
    const response = await fetch(`${API_BASE}/api/seo/${entityType}/${id}`);
    if (!response.ok) return setSeo(blankSeo());
    const value = await response.json();
    setSeo({ focus_keyword: value.focus_keyword || "", meta_title: value.meta_title || "", meta_description: value.meta_description || "", meta_keywords: value.meta_keywords || "" });
  }

  function newCategory() {
    setMode("category"); setSelectedId(null); setSlugTouched(false); setSeo(blankSeo()); setError(null); setMessage(null);
    setCategoryForm({ title: "", slug: "", content: "", icon_key: "sparkles", sort_order: data.categories.length, is_published: true });
  }

  function newTool() {
    setMode("tool"); setSelectedId(null); setSlugTouched(false); setSeo(blankSeo()); setError(null); setMessage(null);
    setToolForm({ title: "", slug: "", content: "", category_id: data.categories[0]?.id || "", tool_kind: "content", sort_order: data.tools.length, is_published: true });
  }

  function editCategory(category: ToolCategory) {
    setMode("category"); setSelectedId(category.id); setSlugTouched(true); setError(null); setMessage(null);
    setCategoryForm({ title: category.title, slug: category.slug, content: category.content, icon_key: category.icon_key, sort_order: category.sort_order, is_published: category.is_published });
    loadSeo("tool_category", category.id);
  }

  function editTool(tool: ToolPage) {
    setMode("tool"); setSelectedId(tool.id); setSlugTouched(true); setError(null); setMessage(null);
    setToolForm({ title: tool.title, slug: tool.slug, content: tool.content, category_id: tool.category_id, tool_kind: tool.tool_kind, sort_order: tool.sort_order, is_published: tool.is_published });
    loadSeo("tool", tool.id);
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSaving(true); setError(null); setMessage(null);
    try {
      if (mode === "category") {
        const saved = await adminSaveToolCategory(token, { id: selectedId || undefined, ...categoryForm, seo });
        setSelectedId(saved.id); setSlugTouched(true); setMessage("Tool category saved. Its branch color is managed automatically.");
      } else {
        const saved = await adminSaveToolPage(token, { id: selectedId || undefined, ...toolForm, seo });
        setSelectedId(saved.id); setSlugTouched(true); setMessage("Tool page saved.");
      }
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Save failed"); }
    finally { setSaving(false); }
  }

  async function removeCategory(category: ToolCategory) {
    if (!token || !window.confirm(`Delete ${category.title}? Categories containing tools cannot be deleted.`)) return;
    try { await adminDeleteToolCategory(token, category.id); newCategory(); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Delete failed"); }
  }

  async function removeTool(tool: ToolPage) {
    if (!token || !window.confirm(`Delete ${tool.title}?`)) return;
    try { await adminDeleteToolPage(token, tool.id); newTool(); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Delete failed"); }
  }

  const editorTitle = mode === "category" ? categoryForm.title : toolForm.title;
  const editorContent = mode === "category" ? categoryForm.content : toolForm.content;
  const editorSlug = mode === "category" ? categoryForm.slug : toolForm.slug;
  const publicPath = mode === "category" ? `/tools/categories/${editorSlug}` : `/tools/${editorSlug}`;
  const normalizedQuery = query.trim().toLowerCase();
  const visibleCategories = data.categories
    .map((category) => ({
      ...category,
      tools: normalizedQuery
        ? category.tools.filter((tool) => tool.title.toLowerCase().includes(normalizedQuery))
        : category.tools,
    }))
    .filter((category) => !normalizedQuery
      || category.title.toLowerCase().includes(normalizedQuery)
      || category.tools.length > 0);

  return <AdminShell>
    <div className="admin-tools-page">
      <section className="card-panel admin-tools-hero">
        <div>
          <p className="admin-eyebrow">Dynamic tools hub</p>
          <h2>Other Tools</h2>
          <p>Organize tool categories, configure interactive experiences, and manage every public tool page from one workspace.</p>
        </div>
        <div className="admin-tools-summary" aria-label="Tools summary">
          <span><strong>{data.categories.length}</strong> Categories</span>
          <span><strong>{data.tools.length}</strong> Tools</span>
        </div>
        <div className="admin-tools-actions">
          <button className="btn btn-ghost" type="button" onClick={newCategory}>+ New category</button>
          <button className="btn btn-primary" type="button" onClick={newTool} disabled={!data.categories.length}>+ New tool</button>
        </div>
      </section>

      <div className="admin-tools-layout">
        <section className="card-panel admin-tools-list">
          <header>
            <div><p className="admin-eyebrow">Directory</p><h3>Categories & tools</h3></div>
            <span>{data.tools.filter((tool) => tool.is_published).length} live</span>
          </header>
          <label className="admin-tools-search">
            <span aria-hidden="true">⌕</span>
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a category or tool…" aria-label="Find a category or tool" />
          </label>
          {loading ? <p className="p-5 text-sm text-[var(--muted)]">Loading tools…</p> : <div className="admin-tool-tree">
            {visibleCategories.map((category) => <article className={`admin-tool-group${mode === "category" && selectedId === category.id ? " is-active" : ""}`} key={category.id}>
              <div className="admin-tool-group-title">
                <button type="button" className="admin-tool-group-main" onClick={() => editCategory(category)}>
                  <i style={{ background: `hsl(${(category.color_index * 137.508 + 252) % 360} 88% 58%)` }} />
                  <span><strong>{category.title}</strong><small>{category.tools.length} {category.tools.length === 1 ? "tool" : "tools"}</small></span>
                </button>
                <span className={`admin-tool-status ${category.is_published ? "is-live" : ""}`}>{category.is_published ? "Live" : "Draft"}</span>
                <button className="admin-tool-delete" type="button" aria-label={`Delete ${category.title}`} title={`Delete ${category.title}`} onClick={() => removeCategory(category)}>×</button>
              </div>
              <div className="admin-tool-children">
                {category.tools.map((tool) => <div className={`admin-tool-child${mode === "tool" && selectedId === tool.id ? " is-active" : ""}`} key={tool.id}>
                  <button type="button" className="admin-tool-child-main" onClick={() => editTool(tool)}><span aria-hidden="true">↳</span><span>{tool.title}</span><small>{tool.is_published ? "Live" : "Draft"}</small></button>
                  <button className="admin-tool-delete" type="button" aria-label={`Delete ${tool.title}`} title={`Delete ${tool.title}`} onClick={() => removeTool(tool)}>×</button>
                </div>)}
                {!category.tools.length && <p>No tools in this category yet.</p>}
              </div>
            </article>)}
            {!visibleCategories.length && <div className="admin-tools-empty"><strong>No matches</strong><span>Try another category or tool name.</span></div>}
          </div>}
        </section>

        <form className="card-panel admin-tool-editor" onSubmit={save}>
          <header className="admin-tool-editor-header">
            <div><p className="admin-eyebrow">{selectedId ? "Editing" : "Creating"}</p><h2>{mode === "category" ? "Tool category" : "Tool page"}</h2><p>{selectedId ? editorTitle || "Untitled item" : `Add a new ${mode} to the public tools directory.`}</p></div>
            <div className="admin-tool-editor-actions">
              {selectedId && editorSlug && <a className="btn btn-ghost" href={publicPath} target="_blank" rel="noreferrer">View page ↗</a>}
              <button className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
            </div>
          </header>
          {error && <p className="field-error">{error}</p>}{message && <p className="admin-tool-success">{message}</p>}

          <section className="admin-tool-form-section">
            <div className="admin-tool-section-heading"><span>01</span><div><h3>Basic information</h3><p>Name the page and choose where it appears.</p></div></div>
            <div className="admin-tool-form-grid">
              <div className="admin-tool-field-full"><label className="field-label" htmlFor="tool-title">Name *</label><input id="tool-title" className="input" required value={editorTitle} onChange={(event) => { const title = event.target.value; if (mode === "category") setCategoryForm((current) => ({ ...current, title, slug: slugTouched ? current.slug : slugify(title) })); else setToolForm((current) => ({ ...current, title, slug: slugTouched ? current.slug : slugify(title) })); }} /></div>
              <div className="admin-tool-field-full"><label className="field-label" htmlFor="tool-slug">Slug *</label><div className="admin-slug-field"><span>{mode === "category" ? "/tools/categories/" : "/tools/"}</span><input id="tool-slug" className="input" required value={editorSlug} onChange={(event) => { setSlugTouched(true); const slug = slugify(event.target.value); if (mode === "category") setCategoryForm((current) => ({ ...current, slug })); else setToolForm((current) => ({ ...current, slug })); }} /></div></div>
              {mode === "category" ? <>
                <div><label className="field-label" htmlFor="category-icon">Icon</label><select id="category-icon" className="input" value={categoryForm.icon_key} onChange={(event) => setCategoryForm({ ...categoryForm, icon_key: event.target.value })}><option value="coins">Coins</option><option value="graduation">Graduation</option><option value="image">Image</option><option value="document">Document</option><option value="calculator">Calculator</option><option value="sparkles">Sparkles</option></select></div>
                <div><label className="field-label" htmlFor="category-order">Display order</label><input id="category-order" className="input" type="number" value={categoryForm.sort_order} onChange={(event) => setCategoryForm({ ...categoryForm, sort_order: Number(event.target.value) || 0 })} /></div>
                <p className="admin-color-note admin-tool-field-full">A unique shiny branch colour is assigned automatically when this category is first saved.</p>
              </> : <>
                <div><label className="field-label" htmlFor="tool-category">Category</label><select id="tool-category" className="input" required value={toolForm.category_id} onChange={(event) => setToolForm({ ...toolForm, category_id: event.target.value })}>{data.categories.map((category) => <option key={category.id} value={category.id}>{category.title}</option>)}</select></div>
                <div><label className="field-label" htmlFor="tool-order">Display order</label><input id="tool-order" className="input" type="number" value={toolForm.sort_order} onChange={(event) => setToolForm({ ...toolForm, sort_order: Number(event.target.value) || 0 })} /></div>
                <p className="admin-color-note admin-tool-field-full">{toolForm.tool_kind === "content" ? "New tools are created as fully editable content pages. Their name, content, slug, SEO, category and publishing status are managed here." : "This tool already has a built-in interactive calculator. Its calculator experience is preserved automatically while you edit its page content and SEO."}</p>
              </>}
            </div>
          </section>

          <section className="admin-tool-form-section">
            <div className="admin-tool-section-heading"><span>02</span><div><h3>Page content</h3><p>Add guidance, sources, examples, or supporting copy.</p></div></div>
            <RichTextEditor key={`${mode}-${selectedId || "new"}`} value={editorContent} onChange={(content) => mode === "category" ? setCategoryForm((current) => ({ ...current, content })) : setToolForm((current) => ({ ...current, content }))} placeholder="Write introduction, guidance, sources or supporting content…" />
          </section>

          <section className="admin-tool-form-section admin-tool-publish-section">
            <div><strong>Publishing status</strong><span>Control whether this page appears on the public tools hub.</span></div>
            <label className="admin-tool-switch"><input type="checkbox" checked={mode === "category" ? categoryForm.is_published : toolForm.is_published} onChange={(event) => mode === "category" ? setCategoryForm({ ...categoryForm, is_published: event.target.checked }) : setToolForm({ ...toolForm, is_published: event.target.checked })} /><span aria-hidden="true" /><b>{(mode === "category" ? categoryForm.is_published : toolForm.is_published) ? "Published" : "Draft"}</b></label>
          </section>

          <section className="admin-tool-form-section">
            <div className="admin-tool-section-heading"><span>03</span><div><h3>Search appearance</h3><p>Configure how this page appears in search engines.</p></div></div>
            <YoastSEOPanel title={editorTitle} content={editorContent} slug={editorSlug} value={seo} onChange={setSeo} />
          </section>

          <div className="admin-tool-editor-footer"><span>{selectedId ? "Changes are applied after saving." : `This will create a new ${mode}.`}</span><button className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : `Save ${mode}`}</button></div>
        </form>
      </div>
    </div>
  </AdminShell>;
}
