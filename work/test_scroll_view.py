from test_desktop_app import module, FakeMonitor
from unittest.mock import patch
from types import SimpleNamespace
import tempfile
import tkinter as tk

for factor in (1, 1.5, 2, 2.5, 3):
    with tempfile.TemporaryDirectory() as tmp:
        root=tk.Tk()
        root.tk.call('tk','scaling',factor*96/72)
        with patch.object(module.wifi_ui.system_theme, 'prefers_dark', return_value=False):
            app=module.App(root,FakeMonitor(tmp),autostart=False)
        root.geometry('640x480+0+0')
        root.update()
        view=app.viewport
        assert view.vertical.winfo_ismapped() and view.horizontal.winfo_ismapped()
        for page in range(3):
            app.tabs.select(page); root.update()
            view.canvas.yview_moveto(1); view.canvas.xview_moveto(1); root.update()
            assert view.canvas.yview()[1] > .99
            assert view.canvas.xview()[1] > .99
        app.tabs.select(1); root.update()
        view.canvas.yview_moveto(0)
        view.wheel(SimpleNamespace(delta=-120,state=0,widget=app.settings_note))
        assert view.canvas.yview()[0] > 0
        view.canvas.yview_moveto(0)
        view.focus_visible(SimpleNamespace(widget=app.url_entry)); root.update()
        top=app.url_entry.winfo_rooty()-view.canvas.winfo_rooty()
        assert -1 <= top < view.canvas.winfo_height(), (factor,top)
        app.apply_system_theme(True); app.apply_system_theme(False); root.update()
        assert view.canvas.cget('background') == module.wifi_ui.BG
        if factor == 1:
            root.geometry('1200x1000+0+0'); root.update()
            assert not view.vertical.winfo_ismapped()
            assert not view.horizontal.winfo_ismapped()
        for callback in root.tk.call('after','info'):
            root.after_cancel(callback)
        root.destroy()
        print(f'PASS {factor*100:g}%: pages reachable, both axes, wheel, keyboard focus and themes')
