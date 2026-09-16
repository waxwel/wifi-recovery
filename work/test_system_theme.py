from test_desktop_app import module,FakeMonitor
import tempfile,tkinter as tk
from tkinter import ttk
with tempfile.TemporaryDirectory() as tmp:
 r=tk.Tk();r.withdraw();a=module.App(r,FakeMonitor(tmp),autostart=False)
 a.fields['interval'].set('45');draft=a.wifi_profile.get();images=tuple(map(id,r._rounded_images))
 for dark in (True,False,True,False):
  a.apply_system_theme(dark)
  assert r.cget('background')==('#141b26' if dark else '#edf2f9')
  assert a.url_list.cget('background')==('#192330' if dark else '#f8faff')
  assert a.fields['interval'].get()=='45' and a.draft_dirty
  assert tuple(map(id,r._rounded_images))==images
 r.destroy()
print('PASS: repeated light/dark switches reuse images, preserve draft, and recolour widgets')
