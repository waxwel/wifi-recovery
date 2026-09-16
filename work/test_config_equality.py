from test_desktop_app import module, FakeMonitor
import tempfile
import tkinter as tk
from unittest.mock import patch

with tempfile.TemporaryDirectory() as tmp:
    root=tk.Tk(); root.withdraw()
    monitor=FakeMonitor(tmp); app=module.App(root,monitor,autostart=False)
    original=app.config.copy()
    app.fields['interval'].set('30'); assert app.draft_dirty
    app.fields['interval'].set(str(original['interval'])); assert not app.draft_dirty
    app.fields['interval'].set('0'+str(original['interval'])); assert not app.draft_dirty
    app.fields['interval'].set(''); assert app.draft_dirty
    app.fields['interval'].set(str(original['interval']))
    app.mode.set('共享端'); assert app.draft_dirty
    app.mode.set('使用端'); assert not app.draft_dirty
    app.wifi_profile.set('  '); assert not app.draft_dirty
    app.url_entry.delete(0,'end'); app.url_entry.insert(0,'https://example.com/')
    app.add_url(); assert app.draft_dirty
    app.url_list.selection_clear(0,'end'); app.url_list.selection_set('end')
    app.delete_url(); assert not app.draft_dirty
    with patch.object(module,'save_json',wraps=module.save_json) as write:
        app.save_settings(); assert write.call_count==0 and monitor.wakes==0
        app.fields['interval'].set('30'); app.save_settings()
        assert write.call_count==1 and monitor.wakes==1 and not app.draft_dirty
        app.save_settings(); assert write.call_count==1 and monitor.wakes==1
    root.destroy()
print('PASS: edit/revert, normalized equality, invalid draft, URL add/remove, and no-op save')
