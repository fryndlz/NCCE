"""Native GUI gates with no network or provider requests."""
import importlib.util
from pathlib import Path
import sys
import tkinter as tk
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_writer_quality import setup, fake_candidate, review
from test_writer_pipeline import with_store
spec = importlib.util.spec_from_file_location('quality_gui', ROOT / 'scripts' / 'writer_quality_gui.py')
gui = importlib.util.module_from_spec(spec); spec.loader.exec_module(gui)


def test_native_buttons_enforce_confirmation_review_and_human_gates():
    def check(store):
        flow = setup(store)
        root = tk.Tk(); root.withdraw()
        app = gui.App(root, autoload=False)
        form = 'fighter_memory'
        def render(): app.render(flow.report(), form, flow.inspect(form)); root.update_idletasks()
        try:
            app.busy = True; app.update_buttons(); app.busy = False
            render()
            assert app.listbox.size() == 1 and app.listbox.get(0) == 'Fighter memory'
            assert not app.buttons['generate'].instate(['disabled'])
            assert app.buttons['approve'].instate(['disabled'])
            assert app.buttons['import'].instate(['disabled'])
            assert 'No draft yet' in app.drafts[0].get('1.0', 'end')
            with patch.object(app, 'mutate') as mutation, patch.object(gui.messagebox, 'showinfo') as info:
                app.key.set(''); app.generate()
                assert info.call_count == 1 and mutation.call_count == 0
            with patch.object(app, 'mutate') as mutation, patch.object(gui.messagebox, 'askokcancel', return_value=False):
                app.key.set('not-a-real-key'); app.generate()
                assert mutation.call_count == 0
            with patch.object(gui.writer, 'API_KEY', ''), patch.object(app, 'mutate') as mutation, patch.object(gui.messagebox, 'askokcancel', return_value=True):
                app.generate()
                assert mutation.call_count == 1
                action = mutation.call_args.args[0]
                with patch.object(flow, 'run_pair') as pair:
                    action(flow)
                    assert pair.call_count == 1
            assert flow.state()['forms'][form]['status'] == 'granted'
            flow.run_pair(form, fake_candidate); render()
            assert app.buttons['generate'].instate(['disabled'])
            assert not app.buttons['import'].instate(['disabled'])
            assert 'Sample 0' in app.drafts[0].get('1.0', 'end')
            assert 'Sample 1' in app.drafts[1].get('1.0', 'end')
            flow.review(form, review(flow)); render()
            assert not app.buttons['approve'].instate(['disabled'])
            assert not app.buttons['reject'].instate(['disabled'])
            flow.decide(form, 'human', True, 'Approved'); render()
            assert app.buttons['approve'].instate(['disabled'])
            assert app.buttons['generate'].instate(['disabled'])
            app.busy = True; app.update_buttons()
            assert all(button.instate(['disabled']) for button in app.buttons.values())
        finally: root.destroy()
    with_store(check)


if __name__ == '__main__':
    test_native_buttons_enforce_confirmation_review_and_human_gates()
    print('PASS native GUI: no-key/declined spending denied, two-call action explicit, drafts rendered, review and approval gates, busy controls disabled')
