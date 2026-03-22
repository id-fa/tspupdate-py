"""TSPUPDATE - タイムスタンプ同期ツール (Python版)"""

import locale
import os
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
from tkinterdnd2 import TkinterDnD, DND_FILES
import tkinter as tk
from tkinter import messagebox

VERSION = "0.1"
APP_TITLE = f"TSPUPDATE (id-fa私家版) {VERSION}"

# --- i18n ---
_MESSAGES = {
    "ja": {
        "drop_targets": "変換するファイルをドラッグアンドドロップしてください",
        "delete": "削除",
        "clear": "クリア",
        "drop_ref": "参照ファイルをドラッグアンドドロップしてください",
        "sync_creation": "作成日時も参照ファイルに同期",
        "execute": "変更",
        "cancel": "キャンセル",
        "error": "エラー",
        "warning": "警告",
        "done": "完了",
        "err_no_ref": "参照ファイルが指定されていないか、存在しません。",
        "warn_no_targets": "変換対象のファイルがありません。",
        "err_not_found": "ファイルが見つかりません",
        "warn_partial": "一部のファイルで失敗しました:\n",
        "done_msg": "{count} 個のファイルのタイムスタンプを変更しました。",
    },
    "en": {
        "drop_targets": "Drag and drop files to convert",
        "delete": "Delete",
        "clear": "Clear",
        "drop_ref": "Drag and drop a reference file",
        "sync_creation": "Sync creation time from reference file",
        "execute": "Apply",
        "cancel": "Cancel",
        "error": "Error",
        "warning": "Warning",
        "done": "Done",
        "err_no_ref": "No reference file specified or file does not exist.",
        "warn_no_targets": "No target files to convert.",
        "err_not_found": "File not found",
        "warn_partial": "Some files failed:\n",
        "done_msg": "Timestamps updated for {count} file(s).",
    },
}

def _get_lang():
    lang, _ = locale.getdefaultlocale()
    if lang and lang.startswith("ja"):
        return "ja"
    return "en"

MSG = _MESSAGES[_get_lang()]

# Windows API for setting creation time
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CreateFileW = kernel32.CreateFileW
CreateFileW.restype = wintypes.HANDLE
CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]

SetFileTime = kernel32.SetFileTime
SetFileTime.restype = wintypes.BOOL
SetFileTime.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPVOID, wintypes.LPVOID]

CloseHandle = kernel32.CloseHandle
CloseHandle.restype = wintypes.BOOL
CloseHandle.argtypes = [wintypes.HANDLE]

GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000  # Required for directories
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


def timestamp_to_filetime(ts):
    """Unix timestamp to Windows FILETIME."""
    # FILETIME epoch: 1601-01-01, units: 100ns
    EPOCH_DIFF = 116444736000000000
    ft_val = int(ts * 10000000) + EPOCH_DIFF
    ft = FILETIME()
    ft.dwLowDateTime = ft_val & 0xFFFFFFFF
    ft.dwHighDateTime = ft_val >> 32
    return ft


def set_creation_time(path, creation_ts):
    """Set the creation time of a file or folder on Windows."""
    flags = FILE_FLAG_BACKUP_SEMANTICS if os.path.isdir(path) else 0
    handle = CreateFileW(
        path, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, flags, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        ft = timestamp_to_filetime(creation_ts)
        if not SetFileTime(handle, ctypes.byref(ft), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        CloseHandle(handle)


def parse_dropped_paths(data):
    """Parse drag-and-drop data into a list of file paths."""
    paths = []
    raw = data.strip()
    # tkdnd wraps paths containing spaces in {}
    i = 0
    while i < len(raw):
        if raw[i] == "{":
            end = raw.index("}", i)
            paths.append(raw[i + 1 : end])
            i = end + 2  # skip } and space
        else:
            end = raw.find(" ", i)
            if end == -1:
                paths.append(raw[i:])
                break
            paths.append(raw[i:end])
            i = end + 1
    return [p for p in paths if p]


class App:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("600x480")
        self.root.resizable(True, True)
        self._build_ui()

    def _build_ui(self):
        root = self.root

        # --- Target files area ---
        top_frame = tk.Frame(root)
        top_frame.pack(fill=tk.X, padx=8, pady=(8, 0))

        tk.Label(top_frame, text=MSG["drop_targets"]).pack(side=tk.LEFT)

        btn_frame = tk.Frame(top_frame)
        btn_frame.pack(side=tk.RIGHT)
        tk.Button(btn_frame, text=MSG["delete"], width=6, command=self._delete_selected).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text=MSG["clear"], width=6, command=self._clear_list).pack(side=tk.LEFT, padx=2)

        list_frame = tk.Frame(root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_frame, selectmode=tk.EXTENDED,
            yscrollcommand=scrollbar.set,
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # Enable drag-and-drop on listbox
        self.listbox.drop_target_register(DND_FILES)
        self.listbox.dnd_bind("<<Drop>>", self._on_drop_targets)

        # Delete key to remove selected
        self.listbox.bind("<Delete>", lambda e: self._delete_selected())

        # --- Reference file area ---
        tk.Label(root, text=MSG["drop_ref"]).pack(
            anchor=tk.W, padx=8, pady=(8, 0)
        )

        self.ref_var = tk.StringVar()
        self.ref_entry = tk.Entry(root, textvariable=self.ref_var, state="readonly")
        self.ref_entry.pack(fill=tk.X, padx=8, pady=4)

        self.ref_entry.drop_target_register(DND_FILES)
        self.ref_entry.dnd_bind("<<Drop>>", self._on_drop_ref)

        # --- Bottom controls ---
        bottom_frame = tk.Frame(root)
        bottom_frame.pack(fill=tk.X, padx=8, pady=(4, 8))

        self.sync_creation = tk.BooleanVar(value=False)
        tk.Checkbutton(
            bottom_frame, text=MSG["sync_creation"], variable=self.sync_creation,
        ).pack(side=tk.LEFT, expand=True, anchor=tk.E)

        tk.Button(bottom_frame, text=MSG["execute"], width=10, command=self._execute).pack(side=tk.LEFT, padx=(16, 4))
        tk.Button(bottom_frame, text=MSG["cancel"], width=10, command=root.destroy).pack(side=tk.LEFT, padx=4)

    def _on_drop_targets(self, event):
        paths = parse_dropped_paths(event.data)
        existing = set(self.listbox.get(0, tk.END))
        for p in paths:
            if p not in existing:
                self.listbox.insert(tk.END, p)

    def _on_drop_ref(self, event):
        paths = parse_dropped_paths(event.data)
        if paths:
            self.ref_var.set(paths[0])

    def _delete_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)

    def _clear_list(self):
        self.listbox.delete(0, tk.END)

    def _execute(self):
        ref_path = self.ref_var.get()
        if not ref_path or not os.path.exists(ref_path):
            messagebox.showerror(MSG["error"], MSG["err_no_ref"])
            return

        targets = list(self.listbox.get(0, tk.END))
        if not targets:
            messagebox.showwarning(MSG["warning"], MSG["warn_no_targets"])
            return

        # Get reference file timestamps
        ref_stat = os.stat(ref_path)
        ref_mtime = ref_stat.st_mtime
        ref_ctime = ref_stat.st_ctime  # On Windows, this is creation time

        errors = []
        for path in targets:
            try:
                if not os.path.exists(path):
                    errors.append(f"{path}: {MSG['err_not_found']}")
                    continue
                # Set modification time (and access time)
                os.utime(path, (ref_mtime, ref_mtime))
                # Set creation time if checked
                if self.sync_creation.get():
                    set_creation_time(path, ref_ctime)
            except Exception as e:
                errors.append(f"{path}: {e}")

        if errors:
            messagebox.showwarning(MSG["warning"], MSG["warn_partial"] + "\n".join(errors))
        else:
            messagebox.showinfo(MSG["done"], MSG["done_msg"].format(count=len(targets)))

        # Clear the list after conversion
        self._clear_list()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
