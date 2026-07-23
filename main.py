"""Windows 11 photo converter GUI."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

APP_AUTHOR = "sidebhit"
APP_VERSION = "1.0.0"


class PhotoConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Photo Converter — {APP_AUTHOR}")
        self.minsize(520, 340)
        self.resizable(True, False)

        self.selected_dir = tk.StringVar()
        self.text_size = tk.IntVar(value=48)
        self.text_color = tk.StringVar(value="#333333")
        self.background_color = tk.StringVar(value="#FFFFFF")
        self.status_text = tk.StringVar(value="Select a folder containing photos.")
        self._busy = False
        self._stop_event = threading.Event()

        self._build_ui()

    def _build_ui(self) -> None:
        padding = {"padx": 12, "pady": 6}

        main = ttk.Frame(self, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        dir_frame = ttk.LabelFrame(main, text="Source folder", padding=10)
        dir_frame.pack(fill=tk.X, **padding)

        ttk.Entry(dir_frame, textvariable=self.selected_dir).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        ttk.Button(dir_frame, text="Browse…", command=self._browse).pack(side=tk.RIGHT)

        options = ttk.LabelFrame(main, text="Date label", padding=10)
        options.pack(fill=tk.X, **padding)

        size_row = ttk.Frame(options)
        size_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(size_row, text="Text size").pack(side=tk.LEFT)
        ttk.Spinbox(
            size_row,
            from_=12,
            to=200,
            textvariable=self.text_size,
            width=6,
        ).pack(side=tk.RIGHT)

        color_row = ttk.Frame(options)
        color_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(color_row, text="Text color").pack(side=tk.LEFT)
        self.color_preview = tk.Label(
            color_row,
            width=4,
            background=self.text_color.get(),
            relief=tk.SUNKEN,
            borderwidth=1,
        )
        self.color_preview.pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(color_row, text="Choose…", command=self._choose_color).pack(side=tk.RIGHT)

        bg_row = ttk.Frame(options)
        bg_row.pack(fill=tk.X)
        ttk.Label(bg_row, text="Background color").pack(side=tk.LEFT)
        self.bg_preview = tk.Label(
            bg_row,
            width=4,
            background=self.background_color.get(),
            relief=tk.SUNKEN,
            borderwidth=1,
        )
        self.bg_preview.pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(bg_row, text="Choose…", command=self._choose_background_color).pack(
            side=tk.RIGHT
        )

        info = ttk.Label(
            main,
            text=(
                "4:3 landscape → 1800×1200, date strip on the right.\n"
                "16:9 and wider → 1800×1200, date strip on the bottom (horizontal text).\n"
                "3:4 portrait → 1200×1800, date strip on the bottom.\n"
                "9:16 and taller → 1200×1800, date strip on the right."
            ),
            justify=tk.LEFT,
            wraplength=480,
        )
        info.pack(fill=tk.X, **padding)

        action_row = ttk.Frame(main)
        action_row.pack(fill=tk.X, **padding)

        self.progress = ttk.Progressbar(action_row, mode="determinate", length=220)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

        button_col = ttk.Frame(action_row)
        button_col.pack(side=tk.RIGHT)

        self.convert_btn = ttk.Button(
            button_col, text="Convert", command=self._start_convert, width=12
        )
        self.convert_btn.pack(fill=tk.X)

        self.stop_btn = ttk.Button(
            button_col, text="Stop", command=self._stop_convert, width=12, state=tk.DISABLED
        )
        self.stop_btn.pack(fill=tk.X, pady=(6, 0))

        ttk.Label(main, textvariable=self.status_text, wraplength=480).pack(
            fill=tk.X, **padding
        )

        ttk.Label(
            main,
            text=f"Version {APP_VERSION} · {APP_AUTHOR}",
            foreground="gray",
        ).pack(fill=tk.X, padx=12, pady=(0, 4))

    def _browse(self) -> None:
        directory = filedialog.askdirectory(title="Select photo folder")
        if directory:
            self.selected_dir.set(directory)
            self.status_text.set(f"Ready to convert photos in:\n{directory}")

    def _choose_color(self) -> None:
        color = colorchooser.askcolor(
            color=self.text_color.get(),
            title="Choose date text color",
        )
        if color and color[1]:
            self.text_color.set(color[1])
            self.color_preview.configure(background=color[1])

    def _choose_background_color(self) -> None:
        color = colorchooser.askcolor(
            color=self.background_color.get(),
            title="Choose padding background color",
        )
        if color and color[1]:
            self.background_color.set(color[1])
            self.bg_preview.configure(background=color[1])

    def _set_converting(self, active: bool) -> None:
        self._busy = active
        self.convert_btn.configure(state=tk.DISABLED if active else tk.NORMAL)
        self.stop_btn.configure(state=tk.NORMAL if active else tk.DISABLED)

    def _start_convert(self) -> None:
        if self._busy:
            return

        directory = self.selected_dir.get().strip()
        if not directory:
            messagebox.showwarning("No folder", "Please select a source folder first.")
            return

        source_dir = Path(directory)
        if not source_dir.is_dir():
            messagebox.showerror("Invalid folder", "The selected path is not a folder.")
            return

        try:
            text_size = int(self.text_size.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Invalid size", "Text size must be a number.")
            return

        if text_size < 8 or text_size > 300:
            messagebox.showerror("Invalid size", "Text size must be between 8 and 300.")
            return

        from converter import ConversionSettings

        settings = ConversionSettings(
            text_size=text_size,
            text_color=self.text_color.get(),
            background_color=self.background_color.get(),
        )

        self._stop_event.clear()
        self._set_converting(True)
        self.progress.configure(value=0, maximum=1)
        self.status_text.set("Converting…")

        thread = threading.Thread(
            target=self._run_convert,
            args=(source_dir, settings),
            daemon=True,
        )
        thread.start()

    def _stop_convert(self) -> None:
        if self._busy:
            self._stop_event.set()
            self.stop_btn.configure(state=tk.DISABLED)
            self.status_text.set("Stopping after the current photo…")

    def _run_convert(self, source_dir: Path, settings) -> None:
        try:
            from converter import convert_directory

            def on_progress(done: int, total: int, filename: str) -> None:
                self.after(0, lambda: self._update_progress(done, total, filename))

            count, output_dir, failures, stopped = convert_directory(
                source_dir,
                settings,
                on_progress,
                self._stop_event,
            )
            self.after(
                0, lambda: self._on_complete(count, output_dir, failures, stopped)
            )
        except Exception as exc:
            self.after(0, lambda: self._on_error(str(exc)))

    def _update_progress(self, done: int, total: int, filename: str) -> None:
        self.progress.configure(maximum=max(total, 1), value=done)
        self.status_text.set(f"Converting ({done}/{total}): {filename}")

    def _on_complete(
        self,
        count: int,
        output_dir: Path,
        failures: list[str],
        stopped: bool,
    ) -> None:
        self._set_converting(False)

        if stopped:
            self.status_text.set(
                f"Stopped — {count} photo(s) saved before cancel.\n{output_dir}"
            )
            messagebox.showinfo(
                "Conversion stopped",
                f"Stopped after converting {count} photo(s).\n\nOutput folder:\n{output_dir}",
            )
            return

        if count == 0 and not failures:
            self.status_text.set("No supported images were found in the selected folder.")
            messagebox.showinfo(
                "Nothing to convert",
                "No supported image files were found.\n\n"
                "Supported formats: JPG, PNG, TIFF, BMP, WEBP",
            )
            return

        if failures:
            preview = "\n".join(failures[:5])
            if len(failures) > 5:
                preview += f"\n...and {len(failures) - 5} more"
            self.status_text.set(
                f"Done with warnings — {count} converted, {len(failures)} failed.\n{output_dir}"
            )
            messagebox.showwarning(
                "Conversion finished with errors",
                f"Converted {count} photo(s).\n"
                f"Failed: {len(failures)}\n\n"
                f"Output folder:\n{output_dir}\n\n"
                f"Errors:\n{preview}",
            )
            return

        self.status_text.set(f"Done — {count} photo(s) saved to:\n{output_dir}")
        messagebox.showinfo(
            "Conversion complete",
            f"Converted {count} photo(s).\n\nOutput folder:\n{output_dir}",
        )

    def _on_error(self, message: str) -> None:
        self._set_converting(False)
        self.status_text.set("Conversion failed.")
        messagebox.showerror("Error", message)


def main() -> None:
    app = PhotoConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
