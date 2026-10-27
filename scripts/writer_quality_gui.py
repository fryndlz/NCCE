"""Small native desktop front end for the opt-in writing-quality workflow."""
from contextlib import closing
import getpass
import json
import os
from pathlib import Path
import queue
import sqlite3
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import writer_quality as quality
import writer_workshop as workshop
import llm_writer as writer
from store import Store
# Import CLI helpers by file to avoid the similarly named workflow module.
import importlib.util
spec = importlib.util.spec_from_file_location('quality_operator', ROOT / 'scripts' / 'writer_quality.py')
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)

PROJECT = Path(os.environ.get('NCCE_PROJECT_ROOT', r'C:\Codex\NCCE'))
DEFAULT_RUN = PROJECT / '.writing-quality-run'
DEFAULT_SOURCE = PROJECT / 'MCCE-PROJECT-CONTEXT' / 'MCCE-personal-codex-handoff' / 'data' / 'chronicle.db'
LABELS = {form: form.replace('_', ' ').capitalize() for form in quality.contract.BRIEFS}
STATUSES = {'awaiting_grant': 'Ready to try', 'granted': 'Two drafts authorized',
            'running': 'Interrupted — check audit', 'awaiting_review': 'Needs reviewer',
            'escalated': 'Human help needed', 'qualified': 'Ready for your approval',
            'approved': 'Approved', 'disapproved': 'Rejected — discuss next steps'}


def ensure_run(folder, source):
    if (folder / 'snapshot.db').exists():
        return
    if not source.exists():
        raise ValueError('The campaign database was not found. Use Open run to choose an existing review run.')
    # Discover sample coverage read-only; do not migrate or initialize the source.
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        view = object.__new__(Store); view.db = db
        available = {s['form'] for s in workshop.catalog(view)}
    forms = [f for f in quality.contract.BRIEFS if f in available]
    operator.snapshot(source, folder, forms, {}, 3)


def document_text(document):
    parts = []
    composition = document.get('composition') or {}
    for key in ('heading', 'subject'):
        if composition.get(key): parts.append(composition[key])
    def blocks(items):
        for item in items:
            if item.get('text'): parts.append(item['text'])
            # Older documents can store structured rich-text runs.
            elif item.get('runs'): parts.append(''.join(r.get('text', '') for r in item['runs']))
            blocks(item.get('blocks', []))
    blocks(document.get('blocks', []))
    termination = document.get('termination') or {}
    if termination.get('text'): parts.append(termination['text'])
    return '\n\n'.join(parts) or 'No draft yet. Inspect the context, then generate two drafts when you are ready.'


def load(folder, selected=None):
    with operator.opened(folder) as flow:
        state = flow.state()
        form = selected if selected in state['forms'] else next(iter(state['forms']))
        prepared = flow.inspect(form)
        return flow.report(), form, prepared


class App:
    def __init__(self, root, folder=DEFAULT_RUN, source=DEFAULT_SOURCE, autoload=True):
        self.root = root; self.folder = Path(folder); self.source = Path(source)
        self.busy = False; self.report = None; self.form = None; self.forms = []
        self.events = queue.Queue(); self.buttons = {}
        root.title('NCCE — Writing Lab'); root.geometry('1220x820'); root.minsize(1000, 680)
        root.configure(bg='#eef1f5'); root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(root); style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('TFrame', background='#eef1f5')
        style.configure('TLabel', background='#eef1f5', foreground='#233047')
        style.configure('Title.TLabel', font=('Segoe UI', 22, 'bold'))
        style.configure('Subtitle.TLabel', foreground='#59667a')
        style.configure('TButton', padding=(12, 8))
        style.configure('Primary.TButton', background='#245cc4', foreground='white')
        outer = ttk.Frame(root, padding=20); outer.pack(fill='both', expand=True)
        header = ttk.Frame(outer); header.pack(fill='x')
        ttk.Label(header, text='Writing Lab', style='Title.TLabel').pack(side='left')
        self.button(header, 'open', 'Open run…', self.open_run).pack(side='right')
        self.button(header, 'refresh', 'Refresh', self.refresh).pack(side='right', padx=8)
        ttk.Label(outer, text='Try two drafts. Review the writing. Decide what is good enough.', style='Subtitle.TLabel').pack(anchor='w', pady=(3, 14))
        credentials = ttk.Frame(outer); credentials.pack(fill='x', pady=(0, 12))
        ttk.Label(credentials, text='OpenAI API key').pack(side='left')
        self.key = tk.StringVar(value=writer.API_KEY)
        self.key_entry = ttk.Entry(credentials, textvariable=self.key, show='●', width=42)
        self.key_entry.pack(side='left', padx=10)
        ttk.Label(credentials, text='Held in memory only • ' + writer.MODEL + ' / ' + writer.DEFAULT_REASONING_EFFORT,
                  style='Subtitle.TLabel').pack(side='left')
        self.notice = tk.StringVar(value='Opening your private review copy…')
        self.notice_label = ttk.Label(outer, textvariable=self.notice, wraplength=1120)
        self.notice_label.pack(fill='x', pady=(0, 12))
        body = ttk.Panedwindow(outer, orient='horizontal'); body.pack(fill='both', expand=True)
        left = ttk.Frame(body, padding=(0, 0, 15, 0)); body.add(left, weight=1)
        ttk.Label(left, text='PROSE FORMS', style='Subtitle.TLabel').pack(anchor='w', pady=(0, 7))
        self.listbox = tk.Listbox(left, width=29, height=18, font=('Segoe UI', 10),
                                 borderwidth=0, highlightthickness=0, background='#ffffff',
                                 selectbackground='#dce8ff', selectforeground='#173665', exportselection=False)
        self.listbox.pack(fill='both', expand=True); self.listbox.bind('<<ListboxSelect>>', self.select)
        self.coverage = tk.StringVar()
        ttk.Label(left, textvariable=self.coverage, wraplength=230, style='Subtitle.TLabel').pack(anchor='w', pady=12)
        right = ttk.Frame(body); body.add(right, weight=5)
        self.subject = tk.StringVar(value='Choose a prose form')
        ttk.Label(right, textvariable=self.subject, font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        self.state_label = tk.StringVar()
        ttk.Label(right, textvariable=self.state_label, style='Subtitle.TLabel').pack(anchor='w', pady=(3, 10))
        controls = ttk.Frame(right); controls.pack(fill='x', pady=(0, 10))
        self.button(controls, 'generate', 'Generate two drafts', self.generate, primary=True).pack(side='left')
        self.button(controls, 'export', 'Export for reviewer…', self.export_review).pack(side='left', padx=7)
        self.button(controls, 'import', 'Import review…', self.import_review).pack(side='left')
        self.tabs = ttk.Notebook(right); self.tabs.pack(fill='both', expand=True)
        drafts = ttk.Frame(self.tabs, padding=10); self.tabs.add(drafts, text='  Drafts  ')
        drafts.columnconfigure(0, weight=1); drafts.columnconfigure(1, weight=1); drafts.rowconfigure(1, weight=1)
        self.drafts = []
        for i in range(2):
            ttk.Label(drafts, text='DRAFT ' + ('A' if i == 0 else 'B'), font=('Segoe UI', 10, 'bold')).grid(row=0, column=i, sticky='w', pady=(0, 8), padx=5)
            area = self.textbox(drafts); area.grid(row=1, column=i, sticky='nsew', padx=5)
            self.drafts.append(area)
        self.context = self.tab('Context & instructions')
        self.review_text = self.tab('Review & history')
        bottom = ttk.Frame(right); bottom.pack(fill='x', pady=(12, 0))
        self.button(bottom, 'approve', 'Approve this form', lambda: self.decide(True)).pack(side='left')
        self.button(bottom, 'reject', 'Reject this form', lambda: self.decide(False)).pack(side='left', padx=7)
        self.button(bottom, 'resolve', 'Resolve stop…', self.resolve).pack(side='left')
        self.button(bottom, 'report', 'Save report…', self.save_report).pack(side='right')
        ttk.Label(outer, text='Private development copy • Existing campaign prose stays unchanged • Reviewer handoff is currently manual',
                  style='Subtitle.TLabel').pack(anchor='w', pady=(14, 0))
        self.update_buttons()
        root.after(100, self.poll)
        if autoload:
            self.work(lambda: (ensure_run(self.folder, self.source), load(self.folder))[1], 'Loading your review workspace…')

    def button(self, parent, key, label, action, primary=False):
        b = ttk.Button(parent, text=label, command=action, style='Primary.TButton' if primary else 'TButton')
        self.buttons[key] = b; return b

    @staticmethod
    def textbox(parent):
        return ScrolledText(parent, wrap='word', font=('Segoe UI', 11), background='white',
                            foreground='#233047', relief='flat', padx=12, pady=10, state='disabled', width=20, height=12)

    def tab(self, label):
        frame = ttk.Frame(self.tabs, padding=10); self.tabs.add(frame, text='  ' + label + '  ')
        text = self.textbox(frame); text.pack(fill='both', expand=True); return text

    @staticmethod
    def put(widget, content):
        widget.configure(state='normal'); widget.delete('1.0', 'end'); widget.insert('1.0', content); widget.configure(state='disabled')

    def work(self, job, notice):
        if self.busy: return
        self.busy = True; self.notice.set(notice); self.update_buttons()
        def worker():
            try: self.events.put(('ok', job()))
            except Exception as exc:
                text = str(exc)
                if writer.API_KEY: text = text.replace(writer.API_KEY, '[redacted]')
                self.events.put(('error', text))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            kind, result = self.events.get_nowait()
            self.busy = False
            if kind == 'ok': self.render(*result)
            else:
                self.notice.set('Stopped: ' + result)
                messagebox.showerror('Writing Lab', result, parent=self.root)
            self.update_buttons()
        except queue.Empty: pass
        self.root.after(100, self.poll)

    def render(self, report, form, prepared):
        self.report = report; self.form = form; self.forms = list(report['run']['forms'])
        self.listbox.configure(state='normal')
        self.listbox.delete(0, 'end')
        for name in self.forms: self.listbox.insert('end', LABELS[name])
        self.listbox.selection_set(self.forms.index(form))
        f = report['run']['forms'][form]; rounds = f['rounds']; pair = rounds[-1] if rounds else {}
        self.subject.set(LABELS[form]); self.state_label.set(STATUSES[f['status']] + ' • ' + prepared['label'])
        for index, area in enumerate(self.drafts):
            candidates = pair.get('candidates', [])
            content = document_text(candidates[index].get('document', {})) if index < len(candidates) else document_text({})
            if index < len(candidates) and candidates[index].get('error'): content += '\n\nStopped: ' + candidates[index]['error']
            self.put(area, content)
        self.put(self.context, 'WRITING INSTRUCTIONS\n\n' + prepared['instructions'] + '\n\nSOURCE CONTEXT\n\n' + json.dumps(prepared['packet'], ensure_ascii=False, indent=2))
        assessment = pair.get('review')
        history = 'JKSimmons review\n\n' + (json.dumps(assessment, ensure_ascii=False, indent=2) if assessment else 'No review yet. After generation, export the review bundle and bring back the filled review.')
        history += '\n\nStoryTechMan\n\n' + report['storytechman_report'] + '\n\nACTIVITY\n'
        history += '\n'.join(e['at'] + ' — ' + e['role'] + ': ' + e['note'] for e in report['run']['events']) or '\nNo activity yet.'
        self.put(self.review_text, history)
        missing = [LABELS[x] for x in LABELS if x not in self.forms]
        self.coverage.set(str(len(self.forms)) + '/14 forms available' + ('\nMissing: ' + ', '.join(missing) if missing else ''))
        if f['status'] in ('escalated', 'running'):
            notice = 'Stopped for human input. Read Review & history before resolving this stop.'
        elif f['status'] == 'awaiting_review':
            notice = 'Both drafts are ready. Export them for JKSimmons, then import the completed review.'
        else:
            notice = 'Ready. Generation makes at most two paid requests after your confirmation.'
        self.notice.set(notice); self.update_buttons()

    def update_buttons(self):
        for button in self.buttons.values(): button.configure(state='disabled' if self.busy else 'normal')
        self.listbox.configure(state='disabled' if self.busy else 'normal')
        self.key_entry.configure(state='disabled' if self.busy else 'normal')
        if self.busy: return
        status = self.report['run']['forms'][self.form]['status'] if self.report else None
        stopped = self.report and any(f['status'] in ('running', 'escalated') for f in self.report['run']['forms'].values())
        allowed = {'generate': status in ('awaiting_grant', 'granted') and not stopped,
                   'export': status == 'awaiting_review', 'import': status == 'awaiting_review' and not stopped,
                   'approve': status == 'qualified' and not stopped, 'reject': status == 'qualified' and not stopped,
                   'resolve': status in ('running', 'escalated'), 'report': self.report is not None}
        for key, enabled in allowed.items(): self.buttons[key].configure(state='normal' if enabled else 'disabled')

    def select(self, _event=None):
        selection = self.listbox.curselection()
        if not self.busy and selection and self.forms[selection[0]] != self.form:
            selected = self.forms[selection[0]]
            self.work(lambda: load(self.folder, selected), 'Opening sample…')

    def refresh(self): self.work(lambda: load(self.folder, self.form), 'Refreshing…')

    def open_run(self):
        path = filedialog.askdirectory(title='Choose a Writing Lab run folder', parent=self.root)
        if path:
            folder = Path(path)
            # Change workspace only after successfully opening it.
            def job():
                result = load(folder); self.folder = folder; return result
            self.work(job, 'Opening review run…')

    def mutate(self, action, notice):
        folder, form = self.folder, self.form
        def job():
            with operator.opened(folder) as flow: action(flow)
            return load(folder, form)
        self.work(job, notice)

    def generate(self):
        key = self.key.get().strip()
        if not key:
            messagebox.showinfo('API key needed', 'Enter your OpenAI API key in the masked field at the top. It is kept only for this session.', parent=self.root); return
        if not messagebox.askokcancel('Generate two drafts?', 'Allow up to two paid OpenAI writing requests for ' + LABELS[self.form].lower() + '?\n\nThe drafts stay in your private review copy. The loop stops for review afterward.', parent=self.root): return
        form = self.form
        def action(flow):
            writer.API_KEY = key
            if flow.state()['forms'][form]['status'] == 'awaiting_grant': flow.grant(form, getpass.getuser())
            if flow.state()['forms'][form]['status'] == 'granted': flow.run_pair(form)
        self.mutate(action, 'Writing two alternatives… Please keep this window open.')

    def export_review(self):
        path = filedialog.asksaveasfilename(title='Export for JKSimmons', defaultextension='.json', initialfile=self.form + '-review-bundle.json', parent=self.root)
        if path:
            form = self.form
            self.mutate(lambda flow: Path(path).write_text(json.dumps(flow.bundle(form), ensure_ascii=False, indent=2), encoding='utf-8'), 'Exporting review bundle…')

    def import_review(self):
        path = filedialog.askopenfilename(title='Choose the completed JKSimmons review', filetypes=[('JSON review', '*.json')], parent=self.root)
        if path:
            form = self.form
            self.mutate(lambda flow: flow.review(form, operator.read_json(path)), 'Checking reviewer scores and escalation gates…')

    def decide(self, approve):
        note = simpledialog.askstring('Approve writing' if approve else 'Reject writing', 'Your note:', parent=self.root)
        if note and note.strip():
            form = self.form
            self.mutate(lambda flow: flow.decide(form, getpass.getuser(), approve, note), 'Saving your decision…')

    def resolve(self):
        note = simpledialog.askstring('Resolve human stop', 'What did you investigate and decide?\nThis requires a fresh generation grant; it does not replay old calls.', parent=self.root)
        if note and note.strip():
            form = self.form
            self.mutate(lambda flow: flow.resolve(form, getpass.getuser(), note), 'Saving resolution…')

    def save_report(self):
        path = filedialog.asksaveasfilename(title='Save complete run report', initialfile='ncce-writing-report.json', defaultextension='.json', parent=self.root)
        if path: self.mutate(lambda flow: Path(path).write_text(json.dumps(flow.report(), ensure_ascii=False, indent=2), encoding='utf-8'), 'Saving report…')

    def close(self):
        if self.busy:
            messagebox.showinfo('Work in progress', 'Please wait for the current operation to finish before closing.', parent=self.root); return
        self.key.set(''); writer.API_KEY = ''; self.root.destroy()


def main():
    root = tk.Tk(); App(root); root.mainloop()


if __name__ == '__main__': main()
