import io
import os
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, font, messagebox

from src.lexer import Lexer, LexerError
from src.parser.reader import PlannerReader, ParseError
from src.interpreter import PlannerInterpreter, PlannerRuntimeError


THEME = {
    "bg":          "#1e1e2e",
    "bg_panel":    "#181825",
    "bg_toolbar":  "#313244",
    "fg":          "#cdd6f4",
    "fg_dim":      "#6c7086",
    "accent":      "#89b4fa",
    "green":       "#a6e3a1",
    "red":         "#f38ba8",
    "yellow":      "#f9e2af",
    "orange":      "#fab387",
    "purple":      "#cba6f7",
    "pink":        "#f5c2e7",
    "teal":        "#94e2d5",
    "selection":   "#45475a",
    "cursor":      "#f5e0dc",
    "output_form": "#89dceb",
    "output_val":  "#a6e3a1",
}

RUN_KEY = "<F5>"
RUN_KEY_LABEL = "F5"

KEYWORDS = (
    "DEFINE", "LAMBDA", "COND", "PROG", "RETURN", "GO",
    "SET", "CSET", "QUOTE", "AND", "OR", "NOT",
    "COND", "IF", "WHILE", "FOR",
    "LENGTH", "ELEM", "REST", "HEAD", "LAST", "APPEND", "CONS", "CAR", "CDR",
    "LIST", "ATOM", "NUM", "EMPTY", "EQ", "EQUAL",
    "LT", "GT", "LE", "GE", "NE",
    "PRINT", "MPRINT", "READ",
    "SUBR", "FSUBR",
)

_HIGHLIGHT_RULES: list[tuple[str, str]] = [
    # Комментарии — строки, начинающиеся с «*» (с возможными пробелами)
    ("comment",  r"(?m)^[ \t]*\*[^\n]*"),
    # Ключевые слова (целые токены в верхнем регистре)
    ("keyword",  r"\b(?:" + "|".join(KEYWORDS) + r")\b"),
    # Ссылки на переменные: .X  *X  :X  !.X  !*X  !:X
    ("varref",   r"[!]?[.*:][A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9\-+×÷]*"),
    # Числа: целые, вещественные, с возможным знаком
    ("number",   r"(?<![A-Za-zА-Яа-яЁё_])[-+]?\d+(?:\.\d*)?(?![A-Za-zА-Яа-яЁё_0-9])"),
    # Шкалы: *3704
    ("scale",    r"\*[0-7]+"),
    # Скобки P-списков: [ ]
    ("p_bracket", r"[\[\]]"),
    # Скобки L-списков: ( )
    ("l_bracket", r"[()]"),
    # Скобки S-списков: < >
    ("s_bracket", r"[<>]"),
]


class PlannerIDE(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Плэннер — интерпретатор")
        self.geometry("1100x700")
        self.minsize(700, 400)
        self.configure(bg=THEME["bg"])

        self._current_file: str | None = None
        self._highlight_job: str | None = None
        self._result_queue: queue.Queue = queue.Queue()

        self._setup_fonts()
        self._build_menu()
        self._build_toolbar()
        self._build_panes()
        self._build_statusbar()
        self._apply_highlight_tags()

        self.bind_all(RUN_KEY, lambda e: self.run_program())

    def _setup_fonts(self) -> None:
        self._mono = font.Font(family="Courier", size=13)
        self._mono_bold = font.Font(
            family=self._mono.actual("family"), size=13, weight="bold"
        )
        self._ui_font = font.Font(family="Helvetica", size=12)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self, bg=THEME["bg_toolbar"], fg=THEME["fg"],
                          activebackground=THEME["selection"],
                          activeforeground=THEME["fg"], relief="flat")

        file_menu = tk.Menu(menubar, tearoff=False,
                            bg=THEME["bg_toolbar"], fg=THEME["fg"],
                            activebackground=THEME["accent"],
                            activeforeground=THEME["bg"])
        file_menu.add_command(label="Открыть...   Ctrl+O",
                              command=self.open_file)
        file_menu.add_command(label="Сохранить    Ctrl+S",
                              command=self.save_file)
        file_menu.add_command(label="Сохранить как...",
                              command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.destroy)

        run_menu = tk.Menu(menubar, tearoff=False,
                           bg=THEME["bg_toolbar"], fg=THEME["fg"],
                           activebackground=THEME["accent"],
                           activeforeground=THEME["bg"])
        run_menu.add_command(label=f"Выполнить   {RUN_KEY_LABEL}",
                             command=self.run_program)
        run_menu.add_command(label="Очистить вывод",
                             command=self.clear_output)

        menubar.add_cascade(label="Файл", menu=file_menu)
        menubar.add_cascade(label="Выполнить", menu=run_menu)
        self.config(menu=menubar)

        self.bind_all("<Control-o>", lambda e: self.open_file())
        self.bind_all("<Control-s>", lambda e: self.save_file())

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self, bg=THEME["bg_toolbar"], pady=4)
        bar.pack(side="top", fill="x")

        btn_cfg = dict(
            font=self._ui_font,
            bg=THEME["bg_toolbar"],
            fg=THEME["fg"],
            activebackground=THEME["selection"],
            activeforeground=THEME["fg"],
            relief="flat",
            padx=10,
            pady=2,
            cursor="hand2",
            bd=0,
        )

        tk.Button(bar, text="Открыть", command=self.open_file, **btn_cfg).pack(side="left", padx=(6, 2))
        tk.Button(bar, text="Сохранить", command=self.save_file, **btn_cfg).pack(side="left", padx=2)
        run_cfg = {**btn_cfg, "fg": THEME["green"]}
        tk.Button(bar, text=f"▶  Выполнить  [{RUN_KEY_LABEL}]",
                  command=self.run_program,
                  **run_cfg).pack(side="left", padx=(10, 2))
        dim_cfg = {**btn_cfg, "fg": THEME["fg_dim"]}
        tk.Button(bar, text="Очистить вывод", command=self.clear_output,
                  **dim_cfg).pack(side="left", padx=2)
        tk.Button(bar, text="Выход", command=self.destroy, **dim_cfg).pack(side="left", padx=2)

    def _build_panes(self) -> None:
        paned = tk.PanedWindow(self, orient="horizontal",
                               bg=THEME["bg"], sashwidth=5,
                               sashrelief="flat", sashpad=2)
        paned.pack(fill="both", expand=True, padx=0, pady=0)

        left = tk.Frame(paned, bg=THEME["bg_panel"])
        paned.add(left, minsize=300, stretch="always")

        _lbl(left, "Редактор").pack(anchor="w", padx=8, pady=(4, 0))

        editor_frame = tk.Frame(left, bg=THEME["bg_panel"])
        editor_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.editor = tk.Text(
            editor_frame,
            font=self._mono,
            bg=THEME["bg"],
            fg=THEME["fg"],
            insertbackground=THEME["cursor"],
            selectbackground=THEME["selection"],
            selectforeground=THEME["fg"],
            relief="flat",
            wrap="none",
            undo=True,
            tabs=("2c",),
            padx=8, pady=6,
        )
        ed_scroll_y = tk.Scrollbar(editor_frame, command=self.editor.yview,
                                   bg=THEME["bg_toolbar"])
        ed_scroll_x = tk.Scrollbar(editor_frame, orient="horizontal",
                                   command=self.editor.xview,
                                   bg=THEME["bg_toolbar"])
        self.editor.configure(yscrollcommand=ed_scroll_y.set,
                              xscrollcommand=ed_scroll_x.set)

        ed_scroll_y.pack(side="right", fill="y")
        ed_scroll_x.pack(side="bottom", fill="x")
        self.editor.pack(fill="both", expand=True)

        self.editor.bind("<<Modified>>", self._on_editor_modified)

        right = tk.Frame(paned, bg=THEME["bg_panel"])
        paned.add(right, minsize=250, stretch="always")

        _lbl(right, "Вывод").pack(anchor="w", padx=8, pady=(4, 0))

        out_frame = tk.Frame(right, bg=THEME["bg_panel"])
        out_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.output = tk.Text(
            out_frame,
            font=self._mono,
            bg=THEME["bg"],
            fg=THEME["output_val"],
            insertbackground=THEME["cursor"],
            selectbackground=THEME["selection"],
            selectforeground=THEME["fg"],
            relief="flat",
            wrap="none",
            state="disabled",
            padx=8, pady=6,
        )
        out_scroll_y = tk.Scrollbar(out_frame, command=self.output.yview,
                                    bg=THEME["bg_toolbar"])
        out_scroll_x = tk.Scrollbar(out_frame, orient="horizontal",
                                    command=self.output.xview,
                                    bg=THEME["bg_toolbar"])
        self.output.configure(yscrollcommand=out_scroll_y.set,
                              xscrollcommand=out_scroll_x.set)

        out_scroll_y.pack(side="right", fill="y")
        out_scroll_x.pack(side="bottom", fill="x")
        self.output.pack(fill="both", expand=True)

        self.output.tag_configure("form",  foreground=THEME["output_form"])
        self.output.tag_configure("value", foreground=THEME["output_val"])
        self.output.tag_configure("error", foreground=THEME["red"])
        self.output.tag_configure("sep",   foreground=THEME["fg_dim"])

        self.after(100, lambda: paned.sash_place(0, 560, 0))

    def _build_statusbar(self) -> None:
        bar = tk.Frame(self, bg=THEME["bg_toolbar"], pady=3)
        bar.pack(side="bottom", fill="x")
        self._status_var = tk.StringVar(value="Готово")
        tk.Label(
            bar,
            textvariable=self._status_var,
            font=font.Font(family="Helvetica", size=11),
            bg=THEME["bg_toolbar"],
            fg=THEME["fg_dim"],
            anchor="w",
        ).pack(side="left", padx=8)

    def _apply_highlight_tags(self) -> None:
        ed = self.editor
        ed.tag_configure("comment",   foreground=THEME["fg_dim"],   font=self._mono)
        ed.tag_configure("keyword",   foreground=THEME["accent"],   font=self._mono_bold)
        ed.tag_configure("varref",    foreground=THEME["pink"])
        ed.tag_configure("number",    foreground=THEME["purple"])
        ed.tag_configure("scale",     foreground=THEME["orange"])
        ed.tag_configure("p_bracket", foreground=THEME["yellow"])
        ed.tag_configure("l_bracket", foreground=THEME["teal"])
        ed.tag_configure("s_bracket", foreground=THEME["green"])

    def _on_editor_modified(self, _event: tk.Event | None = None) -> None:
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            if self._highlight_job:
                self.after_cancel(self._highlight_job)
            self._highlight_job = self.after(120, self._highlight)

    def _highlight(self) -> None:
        ed = self.editor
        text = ed.get("1.0", "end-1c")
        for tag, _ in _HIGHLIGHT_RULES:
            ed.tag_remove(tag, "1.0", "end")
        for tag, pattern in _HIGHLIGHT_RULES:
            for m in re.finditer(pattern, text):
                start = f"1.0 + {m.start()} chars"
                end_   = f"1.0 + {m.end()} chars"
                ed.tag_add(tag, start, end_)

    def run_program(self) -> None:
        source = self.editor.get("1.0", "end-1c").strip()
        if not source:
            self._set_status("Редактор пуст — нечего выполнять.")
            return

        self.clear_output()
        self._set_status("Выполняется...")
        self.update_idletasks()

        threading.Thread(
            target=self._interpret_worker,
            args=(source,),
            daemon=True,
        ).start()
        self.after(50, self._poll_result)

    def _interpret_worker(self, source: str) -> None:
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        error_msg: str | None = None
        try:
            token_groups = Lexer(source).tokenize()
            reader = PlannerReader()
            program = reader.read(token_groups)
            interpreter = PlannerInterpreter()
            interpreter.run(program)
        except LexerError as e:
            error_msg = f"Лексическая ошибка: {e}"
        except ParseError as e:
            error_msg = f"Синтаксическая ошибка: {e}"
        except PlannerRuntimeError as e:
            error_msg = f"Ошибка выполнения: {e}"
        except Exception as e:
            error_msg = f"Внутренняя ошибка: {type(e).__name__}: {e}"
        finally:
            sys.stdout = old_stdout
        self._result_queue.put((buf.getvalue(), error_msg))

    def _poll_result(self) -> None:
        try:
            raw_output, error_msg = self._result_queue.get_nowait()
        except queue.Empty:
            self.after(50, self._poll_result)
            return

        out = self.output
        out.configure(state="normal")

        if raw_output:
            lines = raw_output.splitlines(keepends=True)
            for i, line in enumerate(lines):
                tag = "form" if i % 2 == 0 else "value"
                out.insert("end", line, tag)

        if error_msg:
            if raw_output:
                out.insert("end", "\n", "sep")
            out.insert("end", error_msg + "\n", "error")
            self._set_status(error_msg, error=True)
        else:
            self._set_status("Готово.")

        out.configure(state="disabled")
        out.see("end")

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Открыть программу Плэннер",
            filetypes=[("Planner files", "*.pl"), ("All files", "*.*")],
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}")
            return
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", content)
        self._current_file = path
        self.title(f"Плэннер — {os.path.basename(path)}")
        self._set_status(f"Открыт: {path}")
        self._highlight()

    def save_file(self) -> None:
        if self._current_file:
            self._write_file(self._current_file)
        else:
            self.save_file_as()

    def save_file_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Сохранить программу Плэннер",
            defaultextension=".pl",
            filetypes=[("Planner files", "*.pl"), ("All files", "*.*")],
        )
        if path:
            self._write_file(path)

    def _write_file(self, path: str) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.get("1.0", "end-1c"))
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")
            return
        self._current_file = path
        self.title(f"Плэннер — {os.path.basename(path)}")
        self._set_status(f"Сохранено: {path}")

    def clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _set_status(self, msg: str, error: bool = False) -> None:
        self._status_var.set(msg)
        # Меняем цвет статусной строки
        color = THEME["red"] if error else THEME["fg_dim"]
        for w in self.winfo_children():
            if isinstance(w, tk.Frame) and w.cget("bg") == THEME["bg_toolbar"]:
                for lbl in w.winfo_children():
                    if isinstance(lbl, tk.Label):
                        lbl.configure(fg=color)
                break


def _lbl(parent: tk.Widget, text: str) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        font=font.Font(family="Helvetica", size=10),
        bg=THEME["bg_panel"],
        fg=THEME["fg_dim"],
    )


if __name__ == "__main__":
    app = PlannerIDE()
    app.mainloop()
