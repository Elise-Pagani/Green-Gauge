"""The mock mic button: drawing and animation frames only.

It is drawn with plain canvas shapes (no emoji). There is no microphone on
the Pi, so the button only SIMULATES voice input; what a tap does is decided
elsewhere. Its colors come from color() directly, so draw() must be called
again after a theme change.
"""
import tkinter as tk

from theme import color, mix, paint

MIC_SIZE = 60


class MicButton:
    def __init__(self, parent):
        self.canvas = tk.Canvas(parent, width=MIC_SIZE, height=MIC_SIZE,
                                highlightthickness=0, bd=0, cursor="hand2")
        paint(self.canvas, bg="CARD")

    def bind(self, callback):
        self.canvas.bind("<Button-1>", callback)

    def draw(self, mode="idle", frame=0):
        """mode: idle | listening | heard | thinking; frame: animation step."""
        canvas, c = self.canvas, MIC_SIZE / 2
        canvas.delete("all")
        canvas.create_rectangle(0, 0, MIC_SIZE - 1, MIC_SIZE - 1,
                                outline=color("CONTROL_BORDER"))
        if mode == "listening":
            for k in range(3):   # three rings expanding outward and fading
                p = (frame / 16 + k / 3) % 1
                r = 19 + p * 10
                canvas.create_oval(c - r, c - r, c + r, c + r, width=2,
                                   outline=mix(color("ACCENT"), color("CARD"), p))
        elif mode == "thinking":   # a spinning arc
            canvas.create_arc(c - 25, c - 25, c + 25, c + 25, start=-frame * 12,
                              extent=100, style="arc", width=3,
                              outline=color("ACCENT"))
        canvas.create_oval(c - 19, c - 19, c + 19, c + 19,
                           fill=color("ACCENT"), outline=color("ACCENT"))
        ink = color("ON_ACCENT")
        canvas.create_line(c, c - 9, c, c + 1, width=8, capstyle="round", fill=ink)
        canvas.create_arc(c - 9, c - 11, c + 9, c + 7, start=180, extent=180,
                          style="arc", width=2, outline=ink)
        canvas.create_line(c, c + 7, c, c + 11, width=2, fill=ink)
        canvas.create_line(c - 5, c + 11, c + 5, c + 11, width=2, fill=ink)
