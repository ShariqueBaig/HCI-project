import { useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronUp, FileText, Plus, Save, Volume2, VolumeX } from 'lucide-react';
import type { NoteItem } from '../../types/aura';

interface DeepDocumentEditorProps {
  notes: NoteItem[];
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  voiceAssist?: boolean;
  onSaveNote: (id: string, title: string, content: string) => Promise<void>;
  onAddNote: (title: string, content: string) => Promise<NoteItem | undefined>;
}

export function DeepDocumentEditor({
  notes,
  collapsible = false,
  defaultCollapsed = false,
  voiceAssist = false,
  onSaveNote,
  onAddNote,
}: DeepDocumentEditorProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const [activeId, setActiveId] = useState<string>(notes[0]?.id ?? '');
  const [title, setTitle] = useState<string>(notes[0]?.title ?? '');
  const [content, setContent] = useState<string>(notes[0]?.content ?? '');
  const [saving, setSaving] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const saveTimerRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    setCollapsed(defaultCollapsed);
  }, [defaultCollapsed]);

  const activeNote = notes.find((n) => n.id === activeId) ?? notes[0];

  useEffect(() => {
    if (activeNote && activeNote.id !== activeId) {
      setActiveId(activeNote.id);
      setTitle(activeNote.title);
      setContent(activeNote.content);
    }
  }, [activeNote, activeId]);

  const selectNote = (note: NoteItem) => {
    setActiveId(note.id);
    setTitle(note.title);
    setContent(note.content);
  };

  const scheduleSave = (id: string, nextTitle: string, nextContent: string) => {
    if (!id) return;
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(async () => {
      setSaving(true);
      try {
        await onSaveNote(id, nextTitle, nextContent);
      } finally {
        setSaving(false);
      }
    }, 450);
  };

  const handleNewNote = async () => {
    const created = await onAddNote('New Working Note', '');
    if (created) {
      setActiveId(created.id);
      setTitle(created.title);
      setContent(created.content);
    }
  };

  const toggleReadAloud = () => {
    if (!('speechSynthesis' in window)) return;
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(`${title}. ${content}`);
    utter.rate = 0.96;
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utter);
  };

  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;

  return (
    <section
      className="flex flex-col rounded-3xl border shadow-sm"
      style={{ backgroundColor: 'var(--aura-panel)', borderColor: 'var(--aura-border)' }}
    >
      <div
        className="flex flex-wrap items-center justify-between gap-2 border-b px-5 py-3.5"
        style={{ borderColor: 'var(--aura-border)' }}
      >
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4" style={{ color: 'var(--aura-accent)' }} />
          <h2 className="text-sm font-bold">Document Studio</h2>
          <span className="font-mono-code text-[11px]" style={{ color: 'var(--aura-muted)' }}>
            {wordCount} words {saving ? '• saving...' : '• synced'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {voiceAssist && (
            <button
              type="button"
              onClick={toggleReadAloud}
              className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-semibold cursor-pointer"
              style={{
                borderColor: speaking ? 'var(--aura-accent)' : 'var(--aura-border)',
                backgroundColor: speaking ? 'var(--aura-accent-soft)' : 'var(--aura-panel-alt)',
                color: speaking ? 'var(--aura-accent)' : 'var(--aura-text)',
              }}
            >
              {speaking ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
              {speaking ? 'Stop Audio' : 'Read Aloud'}
            </button>
          )}
          <button
            type="button"
            onClick={handleNewNote}
            className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-semibold hover:opacity-80 cursor-pointer"
            style={{ borderColor: 'var(--aura-border)', backgroundColor: 'var(--aura-panel-alt)' }}
          >
            <Plus className="h-3.5 w-3.5" /> New Note
          </button>
          {collapsible && (
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-semibold cursor-pointer"
              style={{ borderColor: 'var(--aura-border)' }}
            >
              {collapsed ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
              {collapsed ? 'Expand' : 'Collapse'}
            </button>
          )}
        </div>
      </div>

      {!collapsed && (
        <div className="flex flex-col gap-3 p-5">
          {/* Note Switcher Pills */}
          <div className="flex flex-wrap gap-1.5">
            {notes.map((n) => {
              const selected = n.id === activeId;
              return (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => selectNote(n)}
                  className="rounded-lg px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer"
                  style={{
                    backgroundColor: selected ? 'var(--aura-accent-soft)' : 'var(--aura-panel-alt)',
                    color: selected ? 'var(--aura-accent)' : 'var(--aura-muted)',
                  }}
                >
                  {n.title.slice(0, 32)}
                </button>
              );
            })}
          </div>

          <input
            type="text"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              scheduleSave(activeId, e.target.value, content);
            }}
            placeholder="Document title..."
            className="w-full rounded-xl border px-3 py-2 text-base font-bold outline-none focus:ring-2"
            style={{
              backgroundColor: 'var(--aura-panel-alt)',
              borderColor: 'var(--aura-border)',
              color: 'var(--aura-text)',
            }}
          />

          <textarea
            rows={10}
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              scheduleSave(activeId, title, e.target.value);
            }}
            placeholder="Write research notes, synthesis, or focus reflections..."
            className="aura-readable w-full resize-y rounded-2xl border p-4 outline-none focus:ring-2"
            style={{
              backgroundColor: 'var(--aura-panel-alt)',
              borderColor: 'var(--aura-border)',
              color: 'var(--aura-text)',
            }}
          />

          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => activeId && onSaveNote(activeId, title, content)}
              className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white cursor-pointer"
              style={{ backgroundColor: 'var(--aura-accent)' }}
            >
              <Save className="h-3.5 w-3.5" />
              Save Now
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
