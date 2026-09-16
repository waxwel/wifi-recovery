from test_desktop_app import module,FakeMonitor
from unittest.mock import patch
import tempfile,tkinter as tk
with tempfile.TemporaryDirectory() as tmp:
 r=tk.Tk();r.withdraw()
 with patch.object(module.wifi_ui.system_theme,'prefers_dark',return_value=False) as read:
  a=module.App(r,FakeMonitor(tmp),autostart=False)
  assert read.call_count==1
  a.apply_system_theme(True);a.apply_system_theme(False)
  assert read.call_count==1 and a.theme_choice.get()=='明亮'
  callbacks=[str(r.tk.call('after','info',i)) for i in r.tk.call('after','info')]
  assert not any('poll' in c for c in callbacks)
 r.destroy()
print('PASS: system theme read once; manual switching does not query system; no polling timer')
