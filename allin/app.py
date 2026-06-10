#!/usr/bin/env python3
"""
指数加仓提醒 - 桌面应用 (Tkinter GUI)

双击 app.bat 启动（推荐），或在终端执行: python app.py
"""

import sys
import os
import threading
from datetime import datetime

# 确保能找到 src 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core import load_config, fetch_all_indices, generate_report

import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont


# ══════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════

class IndexMonitorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("指数加仓提醒")
        self.root.geometry("820x720")
        self.root.minsize(640, 500)

        # 主题色
        self.COLORS = {
            "bg":           "#f5f5f5",
            "header_bg":    "#2c3e50",
            "header_fg":    "#ecf0f1",
            "btn_bg":       "#3498db",
            "btn_fg":       "#ffffff",
            "btn_hover":    "#2980b9",
            "trigger_red":  "#e74c3c",
            "green":        "#27ae60",
            "text_bg":      "#ffffff",
            "text_fg":      "#2c3e50",
            "section":      "#8e44ad",
            "warn":         "#e67e22",
            "orange":       "#e67e22",
            "muted":        "#95a5a6",
        }

        self.config = None
        self.results = None
        self._fetching = False

        self._build_ui()
        self._trigger_refresh()

        # 窗口置顶
        self.root.lift()
        self.root.focus_force()

    # ── Build UI ────────────────────────────────────────────

    def _build_ui(self):
        self.root.configure(bg=self.COLORS["bg"])

        # ---- 顶部标题栏 ----
        header = tk.Frame(self.root, bg=self.COLORS["header_bg"], height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title_font = tkfont.Font(family="Microsoft YaHei", size=18, weight="bold")
        lbl_title = tk.Label(
            header, text="📊 指数加仓提醒",
            font=title_font,
            bg=self.COLORS["header_bg"], fg=self.COLORS["header_fg"],
        )
        lbl_title.pack(side=tk.LEFT, padx=20, pady=14)

        self.lbl_time = tk.Label(
            header, text="",
            font=("Consolas", 10),
            bg=self.COLORS["header_bg"], fg=self.COLORS["muted"],
        )
        self.lbl_time.pack(side=tk.RIGHT, padx=20, pady=14)

        # ---- 操作栏 ----
        toolbar = tk.Frame(self.root, bg=self.COLORS["bg"])
        toolbar.pack(fill=tk.X, padx=16, pady=(12, 4))

        self.btn_refresh = tk.Button(
            toolbar, text="🔄 刷新数据", font=("Microsoft YaHei", 11, "bold"),
            bg=self.COLORS["btn_bg"], fg=self.COLORS["btn_fg"],
            activebackground=self.COLORS["btn_hover"], activeforeground="#fff",
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2",
            command=self._trigger_refresh,
        )
        self.btn_refresh.pack(side=tk.LEFT)

        self.lbl_status = tk.Label(
            toolbar, text="就绪",
            font=("Microsoft YaHei", 10), bg=self.COLORS["bg"], fg=self.COLORS["muted"],
        )
        self.lbl_status.pack(side=tk.LEFT, padx=16)

        # 分隔线
        sep = tk.Frame(self.root, height=2, bg="#dcdde1")
        sep.pack(fill=tk.X, padx=16)

        # ---- 报告区域 ----
        report_frame = tk.Frame(self.root, bg=self.COLORS["text_bg"])
        report_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        self.text = tk.Text(
            report_frame,
            font=("Consolas", 10),
            bg=self.COLORS["text_bg"],
            fg=self.COLORS["text_fg"],
            wrap=tk.NONE,
            relief=tk.FLAT,
            padx=20, pady=16,
            state=tk.DISABLED,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 滚动条
        scroll_y = ttk.Scrollbar(report_frame, orient=tk.VERTICAL, command=self.text.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=scroll_y.set)

        # 定义文本样式标签
        self.text.tag_configure("title", font=("Consolas", 13, "bold"), foreground="#2c3e50")
        self.text.tag_configure("section", font=("Microsoft YaHei", 12, "bold"), foreground="#8e44ad", spacing1=12, spacing3=4)
        self.text.tag_configure("index_name", font=("Microsoft YaHei", 10, "bold"), foreground="#2c3e50")
        self.text.tag_configure("red", foreground="#e74c3c")
        self.text.tag_configure("green", foreground="#27ae60")
        self.text.tag_configure("orange", foreground="#e67e22")
        self.text.tag_configure("muted", foreground="#95a5a6")
        self.text.tag_configure("trigger", foreground="#e74c3c", font=("Consolas", 10, "bold"))
        self.text.tag_configure("summary", font=("Microsoft YaHei", 11, "bold"), foreground="#2c3e50", spacing1=8)
        self.text.tag_configure("sep", foreground="#bdc3c7")
        self.text.tag_configure("cell_trigger", foreground="#e74c3c", font=("Consolas", 10, "bold"))

    # ── Data fetching (threaded) ────────────────────────────

    def _trigger_refresh(self):
        if self._fetching:
            return
        self._fetching = True
        self.btn_refresh.config(state=tk.DISABLED, text="⏳ 正在获取数据...")
        self.lbl_status.config(text="正在拉取指数数据...", fg=self.COLORS["orange"])
        self._set_text("正在获取数据，请稍候...\n", clear=True)
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def _do_fetch(self):
        try:
            self.config = load_config()
            self.results = fetch_all_indices(self.config)
            self.root.after(0, self._on_fetch_done)
        except Exception as e:
            self.root.after(0, lambda: self._on_fetch_error(str(e)))

    def _on_fetch_done(self):
        self._fetching = False
        self.btn_refresh.config(state=tk.NORMAL, text="🔄 刷新数据")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.lbl_time.config(text=now)
        self.lbl_status.config(text=f"上次更新: {now}", fg=self.COLORS["muted"])

        if self.config and self.results:
            report = generate_report(self.results, self.config)
            self._render_report(report)

    def _on_fetch_error(self, err_msg: str):
        self._fetching = False
        self.btn_refresh.config(state=tk.NORMAL, text="🔄 重试")
        self.lbl_status.config(text="获取数据失败", fg=self.COLORS["trigger_red"])
        self._set_text(f"❌ 数据获取失败\n\n{err_msg}\n\n请检查网络连接后重试。", clear=True)
        messagebox.showerror("错误", f"数据获取失败:\n{err_msg}")

    # ── Report rendering ────────────────────────────────────

    def _set_text(self, content: str, clear: bool = False):
        self.text.config(state=tk.NORMAL)
        if clear:
            self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, content)
        self.text.config(state=tk.DISABLED)

    def _render_report(self, report: str):
        """先写入全部文本，再按行搜索打标签"""
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        self.text.insert(tk.END, report)

        # 全文搜索、逐行打标签
        line_idx = 1
        in_table = False
        in_section3 = False

        for line in report.split("\n"):
            start = f"{line_idx}.0"
            end   = f"{line_idx}.end"

            # 日期标题行
            if line.startswith("[20") and "指数加仓检查报告" in line:
                self.text.tag_add("title", start, end)

            # 大节标题
            elif line.startswith("一、") or line.startswith("二、") or line.startswith("三、"):
                in_section3 = ("三、" in line)
                in_table = False
                self.text.tag_add("section", start, end)

            # 表格分隔线
            elif line.startswith("+") and "-" in line:
                self.text.tag_add("sep", start, end)
                in_table = "|" not in line  # 纯分隔线
            elif line.startswith("|"):
                in_table = True
                if "⚠" in line:
                    self.text.tag_add("trigger", start, end)
                elif "否" in line:
                    self.text.tag_add("green", start, end)

            # 指数名称行
            elif line.startswith("■"):
                self.text.tag_add("index_name", start, end)
                in_table = False

            # 触发条件行
            elif ("已触发" in line or "已达" in line or
                  ("⚠" in line and in_section3)):
                self.text.tag_add("trigger", start, end)

            # 一句话总结
            elif line.startswith("一句话总结"):
                self.text.tag_add("summary", start, end)

            # 建议正文
            elif "建议" in line and in_section3:
                self.text.tag_add("orange", start, end)

            # 回撤行 —— 数值部分变色
            elif "回撤" in line and "%" in line:
                # 找到百分号位置，只标后半段
                pct_pos = line.rfind("%")
                if pct_pos > 0:
                    # 往回找数字开始
                    i = pct_pos - 1
                    while i >= 0 and line[i] in "0123456789.-":
                        i -= 1
                    num_start = f"{line_idx}.{i + 1}"
                    num_end = f"{line_idx}.{pct_pos + 1}"
                    self.text.tag_add("red", num_start, num_end)

            # 展望点位行
            elif "需回撤达" in line:
                self.text.tag_add("muted", start, end)

            # 分隔线
            elif line.startswith("=="):
                self.text.tag_add("sep", start, end)

            line_idx += 1

        self.text.config(state=tk.DISABLED)
        self.text.see("1.0")


# ══════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()

    # 尝试设置 Windows 字体
    try:
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Microsoft YaHei", size=10)
    except Exception:
        pass

    # 窗口图标 (可选)
    try:
        root.iconbitmap(default="")
    except Exception:
        pass

    app = IndexMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
