"""Scrollable application viewport with nested scrolling and focus visibility."""
import math
import tkinter as tk
from tkinter import ttk


class ScrollView(ttk.Frame):
    def __init__(self, root, background):
        super().__init__(root)
        self.pack(fill='both', expand=True)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, width=1, height=1, highlightthickness=0,
                                borderwidth=0, background=background)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.vertical = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.horizontal = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set)
        self.content = ttk.Frame(self.canvas, padding=(24,18,24,12))
        self.item = self.canvas.create_window(0, 0, window=self.content, anchor='nw')
        self.pending = None
        self.minimum_width = 900
        self.canvas.bind('<Configure>', self.schedule)
        self.content.bind('<Configure>', self.schedule)
        self.bind('<Destroy>', self.cleanup)

    def cleanup(self, event):
        if event.widget is self and self.pending is not None:
            self.after_cancel(self.pending)
            self.pending = None

    def schedule(self, _=None):
        if self.pending is None:
            self.pending = self.after_idle(self.layout)

    def layout(self):
        self.pending = None
        width = max(self.minimum_width, self.content.winfo_reqwidth())
        height = self.content.winfo_reqheight()
        # Decide both axes together: one scrollbar can make the other necessary.
        total_w, total_h = self.winfo_width(), self.winfo_height()
        show_x = show_y = False
        for _ in range(3):
            avail_w = total_w - (self.vertical.winfo_reqwidth() if show_y else 0)
            avail_h = total_h - (self.horizontal.winfo_reqheight() if show_x else 0)
            show_x, show_y = width > avail_w, height > avail_h
        for bar, show, row, col, sticky in (
                (self.vertical, show_y, 0, 1, 'ns'),
                (self.horizontal, show_x, 1, 0, 'ew')):
            if show and not bar.winfo_manager():
                bar.grid(row=row, column=col, sticky=sticky)
            elif not show and bar.winfo_manager():
                bar.grid_remove()
        width = max(width, total_w - (self.vertical.winfo_reqwidth() if show_y else 0))
        height = max(height, total_h - (self.horizontal.winfo_reqheight() if show_x else 0))
        self.canvas.itemconfigure(self.item, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        if not show_x:
            self.canvas.xview_moveto(0)
        if not show_y:
            self.canvas.yview_moveto(0)

    def enable_input(self, scale):
        self.minimum_width = round(900 * scale)
        self.canvas.configure(xscrollincrement=max(1, round(24*scale)),
                              yscrollincrement=max(1, round(24*scale)))
        tag = 'ViewportWheel' + str(id(self))
        self.bind_class(tag, '<MouseWheel>', self.wheel)
        def visit(widget):
            widget.bindtags((tag, *widget.bindtags()))
            widget.bind('<FocusIn>', self.focus_visible, add='+')
            for child in widget.winfo_children():
                visit(child)
        visit(self.content)
        self.schedule()

    def wheel(self, event):
        if not event.delta:
            return
        axis = 'x' if event.state & 1 else 'y'
        direction = -1 if event.delta > 0 else 1
        widget = event.widget
        # Lists, logs and tables keep their native scroll until their boundary.
        if isinstance(widget, (tk.Listbox, tk.Text, ttk.Treeview)):
            first, last = getattr(widget, axis+'view')()
            if (direction < 0 and first > 0) or (direction > 0 and last < 1):
                return
        getattr(self.canvas, axis+'view_scroll')(
            direction * max(1, math.ceil(abs(event.delta)/120)) * 3, 'units')
        return 'break'

    def focus_visible(self, event):
        widget = event.widget
        # Never scroll for programmatic focus on page containers.
        if not isinstance(widget, (ttk.Entry, ttk.Button, ttk.Radiobutton, tk.Listbox, tk.Text)):
            return
        self.update_idletasks()
        for axis, origin, size, visible in (
                ('x', widget.winfo_rootx()-self.content.winfo_rootx(), widget.winfo_width(), self.canvas.winfo_width()),
                ('y', widget.winfo_rooty()-self.content.winfo_rooty(), widget.winfo_height(), self.canvas.winfo_height())):
            total = self.content.winfo_width() if axis == 'x' else self.content.winfo_height()
            start = getattr(self.canvas, axis+'view')()[0] * total
            target = origin - 8 if origin < start else origin + size + 8 - visible if origin + size > start + visible else start
            if target != start:
                getattr(self.canvas, axis+'view_moveto')(max(0, target)/max(1, total))
