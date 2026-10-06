from __future__ import annotations
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
import json
import queue
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from core import Models, Session, export_text, list_sources
from deepseek_translation import DeepSeekTranslator
from credentials import CredentialError, load_api_key
from runtime import VERSION, resolve_model_root, missing_model_files

BG, PANEL, INK, MUTED, ACCENT = '#101827', '#182438', '#edf4ff', '#9bacbf', '#66e0bf'


class App:
    def __init__(self, root):
        self.root = root
        root.title(f'会议翻译 {VERSION} · 英语 → 中文')
        root.geometry('1000x810')
        root.minsize(780, 660)
        root.configure(bg=BG)
        self.events = queue.Queue()
        self.session = None
        self.generation = 0
        self.captions = []
        self.overlay = None
        self.closing = False
        self.device_choices = {'system': '', 'microphone': ''}
        self.displayed_kind = 'system'
        credential_error = ''
        try:
            self.api_key = load_api_key()
        except CredentialError as exc:
            self.api_key = ''
            credential_error = str(exc)
        self.models = Models(resolve_model_root())
        self.status = tk.StringVar(value='准备就绪 · 点击开始后才采集声音')
        self.warning = tk.StringVar(value=credential_error or '选中与会议软件相同的耳机或扬声器。')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=('Microsoft YaHei UI', 11), padding=(15, 10))
        style.configure('TCombobox', font=('Microsoft YaHei UI', 11), padding=6)
        style.configure('Horizontal.TProgressbar', background=ACCENT, troughcolor=PANEL)
        page = tk.Frame(root, bg=BG, padx=28, pady=24)
        page.pack(fill='both', expand=True)
        tk.Label(page, text='听懂每一句', font=('Microsoft YaHei UI', 27, 'bold'), bg=BG, fg=INK).pack(anchor='w')
        tk.Label(page, text='会议实时字幕  /  EN → 中文  /  本地识别 · 可选 DeepSeek 翻译',
                 font=('Microsoft YaHei UI', 11), bg=BG, fg=MUTED).pack(anchor='w', pady=(3, 20))
        controls = tk.Frame(page, bg=BG)
        controls.pack(fill='x')
        source_row = tk.Frame(controls, bg=BG)
        source_row.pack(fill='x', pady=(0, 8))
        tk.Label(source_row, text='声音输入', font=('Microsoft YaHei UI', 11), bg=BG, fg=INK).pack(side='left', padx=(0, 12))
        self.input_source = ttk.Combobox(source_row, state='readonly', width=24,
                                        values=['电脑会议声音', '麦克风（现场英语）'])
        self.input_source.current(0)
        self.input_source.pack(side='left')
        self.input_source.bind('<<ComboboxSelected>>', self.change_input_source)
        self.input_hint = tk.StringVar(value='翻译电脑播放的会议或视频声音')
        tk.Label(source_row, textvariable=self.input_hint, bg=BG, fg=MUTED,
                 font=('Microsoft YaHei UI', 9)).pack(side='left', padx=12)
        device_row = tk.Frame(controls, bg=BG)
        device_row.pack(fill='x', pady=(7, 12))
        self.device = ttk.Combobox(device_row, state='readonly')
        self.device.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.refresh_button = ttk.Button(device_row, text='刷新设备', command=self.refresh)
        self.refresh_button.pack(side='right')
        mode_row = tk.Frame(controls, bg=BG)
        mode_row.pack(fill='x', pady=(0, 10))
        self.mode = ttk.Combobox(mode_row, state='readonly', width=25,
                                values=['DeepSeek 增强翻译', '本地翻译（免费）'])
        self.mode.current(1)
        self.mode.pack(side='left', padx=(0, 8))
        self.key_button = ttk.Button(mode_row, text='设置 API 密钥', command=self.configure_key)
        self.key_button.pack(side='left')
        self.privacy = tk.StringVar()
        tk.Label(mode_row, textvariable=self.privacy, bg=BG, fg=MUTED,
                 font=('Microsoft YaHei UI', 9)).pack(side='left', padx=10)
        self.mode.bind('<<ComboboxSelected>>', lambda _: self.update_mode_hint())
        self.update_mode_hint()
        actions = tk.Frame(controls, bg=BG)
        actions.pack(fill='x')
        self.start_button = ttk.Button(actions, text='开始翻译', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(actions, text='停止', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        ttk.Button(actions, text='悬浮字幕', command=self.toggle_overlay).pack(side='left')
        ttk.Button(actions, text='导出记录', command=self.export).pack(side='right')
        ttk.Button(actions, text='清空', command=self.clear).pack(side='right', padx=8)
        tk.Label(page, textvariable=self.status, font=('Microsoft YaHei UI', 11, 'bold'),
                 bg=BG, fg=ACCENT, anchor='w').pack(fill='x', pady=(18, 7))
        self.level = ttk.Progressbar(page, maximum=1)
        self.level.pack(fill='x')
        tk.Label(page, textvariable=self.warning, font=('Microsoft YaHei UI', 10),
                 bg=BG, fg=MUTED, anchor='w', wraplength=880).pack(fill='x', pady=(6, 14))
        text_frame = tk.Frame(page, bg=PANEL)
        text_frame.pack(fill='both', expand=True)
        self.text = tk.Text(text_frame, bg=PANEL, fg=INK, relief='flat', wrap='word',
                            padx=20, pady=18, height=8, font=('Microsoft YaHei UI', 13), state='disabled')
        scroll = ttk.Scrollbar(text_frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.text.pack(side='left', fill='both', expand=True)
        self.text.tag_configure('time', foreground=MUTED, font=('Microsoft YaHei UI', 9))
        self.text.tag_configure('en', foreground='#b4c4d8', spacing3=5)
        self.text.tag_configure('zh', foreground=INK, font=('Microsoft YaHei UI', 17), spacing3=20)
        self.placeholder()
        tk.Label(page, text='停顿后显示译文；连续讲话最多 12 秒分段。仅手动导出时保存文字，不保存音频。',
                 bg=BG, fg=MUTED, font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=(12, 0))
        self.refresh()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(80, self.poll)

    def placeholder(self):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('end', '字幕将在这里出现\n\n', 'zh')
        instructions = ('选择麦克风 → 开始翻译 → 让对方用英语说话\n\n靠近说话人，停顿后显示中文字幕。'
                        if self.input_kind() == 'microphone' else
                        '打开会议 → 选择播放设备 → 开始翻译\n\n戴耳机也能使用，不需要打开麦克风。')
        self.text.insert('end', instructions, 'en')
        self.text.configure(state='disabled')

    def input_kind(self):
        return 'microphone' if self.input_source.current() == 1 else 'system'

    def change_input_source(self, _=None):
        if self.session:
            return
        self.device_choices[self.displayed_kind] = self.device.get()
        self.refresh()
        if not self.captions:
            self.placeholder()

    def refresh(self):
        kind = self.input_kind()
        old = self.device.get() if kind == self.displayed_kind else self.device_choices[kind]
        try:
            devices, default = list_sources(kind)
            names = [d['name'] for d in devices]
            self.device['values'] = names
            self.device.set(old if old in names else default if default in names else names[0] if names else '')
            self.displayed_kind = kind
            self.device_choices[kind] = self.device.get()
            self.input_hint.set('翻译身边说话人的英语' if kind == 'microphone' else '翻译电脑播放的会议或视频声音')
            if not names:
                self.warning.set('没有找到麦克风。请连接后刷新。' if kind == 'microphone' else
                                 '没有找到播放设备。请接好耳机或扬声器后刷新。')
            elif self.api_key:
                self.warning.set('请确认麦克风未静音，并靠近说话人。' if kind == 'microphone' else
                                 '选中与会议软件相同的耳机或扬声器。')
            self.start_button.configure(state='normal' if names else 'disabled')
        except Exception as exc:
            self.warning.set(f'读取设备失败：{exc}')
            self.start_button.configure(state='disabled')

    def start(self):
        if self.session or not self.device.get():
            return
        if missing_model_files(self.models.root):
            self.warning.set('本地模型不完整。请完整解压下载包，保留 models 文件夹后重新打开。')
            return
        translator = None
        if self.mode.current() == 0:
            if not self.api_key:
                self.warning.set('请先点击“设置 API 密钥”，或选择本地翻译。')
                return
            translator = DeepSeekTranslator(self.api_key)
        self.generation += 1
        generation = self.generation
        self.session = Session(self.models, self.device.get(),
                               lambda kind, data: self.events.put((generation, kind, data)), translator=translator,
                               input_kind=self.input_kind())
        self.start_button.configure(state='disabled')
        self.refresh_button.configure(state='disabled')
        self.device.configure(state='disabled')
        self.input_source.configure(state='disabled')
        self.mode.configure(state='disabled')
        self.key_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.warning.set('正在使用麦克风：请靠近说话人，并核对人名、数字和专业词汇。'
                         if self.input_kind() == 'microphone' else
                         '请核对人名、数字和专业词汇。此处只采集所选设备播放的声音。')
        self.status.set('正在启动…')
        self.session.start()

    def update_mode_hint(self):
        if self.mode.current() == 0:
            self.privacy.set('文字发送至 DeepSeek · API 单独计费' + (' · 已配置' if self.api_key else ' · 未配置'))
        else:
            self.privacy.set('音频与文字均在本机处理')

    def configure_key(self):
        value = simpledialog.askstring('DeepSeek API 密钥',
            '请在此输入密钥（无需发到聊天）。\n仅保留在本次程序内存中，关闭后清除。',
            parent=self.root, show='•')
        if value and value.strip():
            self.api_key = value.strip()
            self.update_mode_hint()

    def stop(self):
        if self.session:
            self.session.stop()
            self.stop_button.configure(state='disabled')
            self.status.set('正在停止…')

    def add_caption(self, caption):
        self.text.configure(state='normal')
        if not self.captions:
            self.text.delete('1.0', 'end')
        self.captions.append(caption)
        self.text.insert('end', f'{caption.timestamp}  ·  {caption.audio_source}  ·  {caption.translation_source}  ·  处理 {caption.processing_seconds:.1f} 秒\n', 'time')
        self.text.insert('end', caption.original + '\n', 'en')
        self.text.insert('end', caption.translated + '\n\n', 'zh')
        self.text.configure(state='disabled')
        self.text.see('end')
        if self.overlay and self.overlay.winfo_exists():
            self.overlay_en.set(caption.original)
            self.overlay_zh.set(caption.translated)

    def poll(self):
        for _ in range(300):
            try:
                generation, kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if generation != self.generation:
                continue
            if kind == 'level':
                self.level['value'] = data
            elif kind == 'caption':
                if self.session and not self.session.stop_event.is_set():
                    self.add_caption(data)
            elif kind == 'status':
                if self.session and not self.session.stop_event.is_set():
                    self.status.set(data)
            elif kind in ('warning', 'hint', 'error'):
                self.warning.set(data)
            elif kind == 'stopped':
                self.session = None
                self.status.set('已停止 · 可以重新选择设备并开始')
                self.level['value'] = 0
                self.start_button.configure(state='normal')
                self.refresh_button.configure(state='normal')
                self.device.configure(state='readonly')
                self.input_source.configure(state='readonly')
                self.mode.configure(state='readonly')
                self.key_button.configure(state='normal')
                self.stop_button.configure(state='disabled')
        if self.closing and self.session is None:
            self.root.destroy()
            return
        self.root.after(80, self.poll)

    def toggle_overlay(self):
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.destroy()
            self.overlay = None
            return
        window = self.overlay = tk.Toplevel(self.root)
        window.title('悬浮字幕 · 可拖动与调整大小')
        window.configure(bg=BG)
        window.geometry(f'880x220+100+{max(40, self.root.winfo_screenheight()-330)}')
        window.minsize(500, 170)
        window.attributes('-topmost', True)
        self.overlay_zh = tk.StringVar(value=self.captions[-1].translated if self.captions else '等待翻译…')
        self.overlay_en = tk.StringVar(value=self.captions[-1].original if self.captions else '点击主窗口的“开始翻译”')
        zh = tk.Label(window, textvariable=self.overlay_zh, bg=BG, fg=INK,
                      font=('Microsoft YaHei UI', 23, 'bold'), wraplength=820)
        zh.pack(fill='both', expand=True, padx=20, pady=(14, 5))
        en = tk.Label(window, textvariable=self.overlay_en, bg=BG, fg=MUTED,
                      font=('Microsoft YaHei UI', 12), wraplength=820)
        en.pack(fill='both', expand=True, padx=20, pady=(0, 14))
        window.bind('<Configure>', lambda e: (zh.configure(wraplength=max(300, window.winfo_width()-40)),
                                              en.configure(wraplength=max(300, window.winfo_width()-40))))

    def export(self):
        if not self.captions:
            messagebox.showinfo('导出记录', '还没有可导出的字幕。')
            return
        from datetime import datetime
        path = filedialog.asksaveasfilename(title='保存会议翻译', defaultextension='.txt',
                  initialfile=f'会议翻译_{datetime.now():%Y-%m-%d_%H%M%S}.txt', filetypes=[('文字记录', '*.txt')])
        if path:
            try:
                Path(path).write_text(export_text(self.captions), encoding='utf-8-sig')
                self.warning.set('翻译记录已保存。')
            except OSError as exc:
                messagebox.showerror('保存失败', str(exc))

    def clear(self):
        if self.session:
            messagebox.showinfo('清空记录', '请先停止翻译，再清空记录。')
            return
        if self.captions and not messagebox.askyesno('清空记录', '清空当前记录？尚未导出的文字将丢失。'):
            return
        self.captions.clear()
        self.placeholder()
        if self.overlay and self.overlay.winfo_exists():
            self.overlay_zh.set('等待翻译…')
            self.overlay_en.set('')

    def close(self):
        if self.captions and not messagebox.askyesno('关闭', '关闭工具？需要的文字请先导出保存。'):
            return
        self.closing = True
        if self.session:
            self.stop()
        else:
            self.root.destroy()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='会议翻译 · 本地英语识别与中文字幕')
    parser.add_argument('--self-test', metavar='REPORT_JSON', help='检查下载包并保存诊断报告，不启动录音')
    parser.add_argument('--audio', help='自检时识别指定的测试音频')
    args = parser.parse_args()
    if args.self_test:
        from diagnostics import run_self_test
        sys.exit(run_self_test(args.self_test, audio_path=args.audio))
    try:
        root = tk.Tk()
        App(root)
        root.mainloop()
    except Exception:
        messagebox.showerror('无法启动', '程序未能启动。请完整解压下载包后重试，或使用下载包自检功能检查。')
        sys.exit(1)
