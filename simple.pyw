#! python3.10
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
import threading
import urllib.parse
import time
import concurrent.futures
import json
import os
import re
import csv
import subprocess
import uuid
import hashlib
import base64

# 【核心替换】引入 requests 库，并强行关闭烦人的 SSL 不安全警告
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from io import StringIO

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# 【新增】丝滑拖拽支持库
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ========================== simple底层防伪配置 ==========================
STUDIO_SECRET_SALT = "T@k3_Y0ur_T1m3_H@Ias3r!#_8a7p6c5_E4e7f2g1h_$%^&*_QWE4O5sI4P_9Q2_6_!"
CONFIG_FILE = "config.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01'
}

def get_machine_id():
    mac_num = hex(uuid.getnode())
    raw_mid = hashlib.md5(mac_num.encode('utf-8')).hexdigest().upper()[:16]
    return re.sub(r'[^A-Z0-9]', '', raw_mid)

def get_expected_key(machine_id):
    clean_mid = re.sub(r'[^A-Z0-9]', '', machine_id.upper())
    raw_str = clean_mid + STUDIO_SECRET_SALT
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest().upper()[:20]

def load_global_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_global_config(data):
    try:
        with open(CONFIG_FILE, "w", encoding='utf-8') as f: json.dump(data, f, indent=4)
    except: pass

# ========================== 核心应用程序 ==========================
class LinkOpenerApp:
    def __init__(self, root, config_data):
        self.root = root
        self.root.title("simple - Studio Authorized Edition")
        
        self.root.geometry("1350x850")
        self.root.minsize(1300, 800)
        self.is_zoomed = False

        self.config_data = config_data
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.stop_scan = False
        self.is_animating = False
        self.stop_fofa_batch_flag = False

        self.style = ttk.Style()
        if 'clam' in self.style.theme_names():
            self.style.theme_use('clam')
            
        self.style.configure("TNotebook", background="#F5F5F7", borderwidth=0)
        self.style.configure("TNotebook.Tab", font=('Microsoft YaHei', 9), padding=[15, 5])
        self.style.map("TNotebook.Tab", background=[("selected", "#007AFF")], foreground=[("selected", "white")])
        self.style.configure("Treeview", rowheight=30, font=('Microsoft YaHei', 9), borderwidth=0)
        self.style.configure("Treeview.Heading", font=('Microsoft YaHei', 9, 'bold'), background="#F2F2F7")
        self.style.map('Treeview', background=[('selected', '#007AFF')], foreground=[('selected', 'white')])

        self.setup_status_bar()

        self.paned = ttk.PanedWindow(root, orient=tk.VERTICAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        self.top_frame = tk.Frame(self.paned, bg="white", highlightthickness=1, highlightbackground="#D1D1D6")
        self.paned.add(self.top_frame, weight=3)

        self.bottom_frame = tk.Frame(self.paned, bg="#F5F5F7")
        self.paned.add(self.bottom_frame, weight=2)

        self.setup_table_area()
        self.setup_bottom_area()

        self.root.bind("<Control-v>", self.paste_links_from_shortcut)
        self.update_sys_info()
        
        if not HAS_DND:
            self.root.after(1500, lambda: self.log("⚠️ 检测到未安装拖拽支持库！如需开启【文件拖拽】功能，请在CMD执行: pip install tkinterdnd2"))

    def toggle_window_mode(self):
        if not self.is_zoomed:
            self.root.resizable(True, True)
            if os.name == 'nt':
                self.root.state('zoomed')
            else:
                self.root.attributes('-zoomed', True)
            self.root.resizable(False, False)
            self.is_zoomed = True
            self.btn_window_mode.config(text="🪟   切换为缩小模式", bg="#FF9500")
        else:
            self.root.resizable(True, True)
            if os.name == 'nt':
                self.root.state('normal')
            else:
                self.root.attributes('-zoomed', False)
            self.root.geometry("1350x850")
            self.root.resizable(False, False)
            self.is_zoomed = False
            self.btn_window_mode.config(text="🖥️   切换为全屏模式", bg="#007AFF")

    def enable_drag_drop(self, widget, expected_type):
        if HAS_DND:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, widget, expected_type))

    def on_drop(self, event, widget, expected_type):
        path = event.data
        if path.startswith('{') and path.endswith('}'):
            path = path[1:-1]
        path = path.strip()

        if expected_type == 'table':
            if os.path.isfile(path) and path.lower().endswith(('.txt', '.csv')):
                self.import_data_to_table_smart(path)
            else:
                messagebox.showwarning("格式错误", "🚫 无法识别！\n\n请将包含资产数据的【.txt】或【.csv】文件拖入表格区域。")
                
        elif expected_type == 'txt':
            if os.path.isfile(path) and path.lower().endswith('.txt'):
                widget.delete(0, tk.END)
                widget.insert(0, path)
                self.save_app_config(silent=True)
                self.log(f"✅ 成功拖入并识别TXT文件: {os.path.basename(path)}")
            else:
                messagebox.showwarning("文件格式错误", "🚫 拒绝载入！\n\n该输入框仅支持【.txt】格式的文本文件。")
        
        elif expected_type == 'dir':
            if os.path.isdir(path):
                widget.delete(0, tk.END)
                widget.insert(0, path)
                self.save_app_config(silent=True)
                self.log(f"✅ 成功拖入并识别文件夹: {path}")
            else:
                messagebox.showwarning("格式错误", "🚫 拒绝载入！\n\n该输入框仅支持【文件夹目录】。")
                
        elif expected_type == 'wav':
            if os.path.isfile(path) and path.lower().endswith('.wav'):
                widget.delete(0, tk.END)
                widget.insert(0, path)
                self.save_app_config(silent=True)
                self.log(f"✅ 成功拖入并识别音频文件: {os.path.basename(path)}")
            else:
                messagebox.showwarning("格式错误", "🚫 拒绝载入！\n\n请拖入【.wav】格式的音频文件。")

    def import_data_to_table_smart(self, path):
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().strip()
            if not content:
                self.log(f"⚠️ 文件 {os.path.basename(path)} 为空！")
                return
                
            lines = content.split('\n')
            count = 0
            start_idx = len(self.tree.get_children()) + 1
            
            self.log(f"🔄 正在智能分析文件 {os.path.basename(path)} 的数据结构...")

            first_line = lines[0].lower()
            if ',' in first_line and any(k in first_line for k in ['url', 'host', 'ip', 'title', 'domain']):
                self.log("✅ 嗅探到表头特征，启用 [结构化精准映射模式]")
                reader = csv.DictReader(StringIO(content))
                for row in reader:
                    row_lower = {k.lower().strip(): v for k, v in row.items() if k}
                    
                    url = row_lower.get('url', row_lower.get('host', row_lower.get('ip', row_lower.get('domain', ''))))
                    if not url: continue
                    if not url.startswith('http') and '://' not in url:
                        port = row_lower.get('port', '')
                        if port and not url.endswith(':'+port): url = f"http://{url}:{port}"
                        else: url = f"http://{url}"
                            
                    title = row_lower.get('title', '-')
                    country = row_lower.get('country_name', row_lower.get('country', '-'))
                    icp = row_lower.get('icp', '-')
                    product = row_lower.get('product', row_lower.get('server', row_lower.get('component', '-')))
                    status = row_lower.get('status_code', row_lower.get('status', '待测'))
                    
                    i = start_idx + count
                    tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                    self.tree.insert("", "end", values=("☐", i, country, icp, title, url, "-", status, product), tags=(tag,))
                    count += 1
            else:
                self.log("✅ 未检测到表头，启用 [AI正则模糊提取模式]")
                for line in lines:
                    line = line.strip()
                    if not line: continue
                    
                    url, title, status = "", "-", "待测"
                    
                    url_match = re.search(r'(https?://[^\s,"]+|[\w\.-]+:\d+)', line)
                    if url_match:
                        url = url_match.group(1)
                        if not url.startswith('http'): url = "http://" + url
                            
                        remain = line.replace(url_match.group(0), '').strip()
                        if remain:
                            status_match = re.search(r'\[(\d{3})\]|\b(\d{3})\b', remain)
                            if status_match:
                                status = status_match.group(1) or status_match.group(2)
                                remain = remain.replace(status_match.group(0), '').strip()
                            
                            clean_title = re.sub(r'^[,\s\[\]\|"\'\-]+|[,\s\[\]\|"\'-]+$', '', remain)
                            if clean_title: title = clean_title
                    else:
                        parts = line.split()
                        url = "http://" + parts[0]
                        if len(parts) > 1: title = " ".join(parts[1:])
                            
                    i = start_idx + count
                    tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                    self.tree.insert("", "end", values=("☐", i, "-", "-", title, url, "-", status, "-"), tags=(tag,))
                    count += 1
                    
            self.update_range_end()
            self.log(f"🎉 智能解析完毕！成功将 {count} 条资产解剖并对号入座填入表格！")
            if count > 0 and HAS_WINSOUND: winsound.MessageBeep(winsound.MB_OK)
                
        except Exception as e:
            self.log(f"❌ 导入解析失败: {str(e)}")
            messagebox.showerror("解析错误", f"无法识别该文件的数据结构：\n{e}")

    def setup_status_bar(self):
        status_frame = tk.Frame(self.root, bg="#F5F5F7")
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=5)
        self.lbl_info = tk.Label(status_frame, text="RAM: -% | CPU: -%", bg="#F5F5F7", font=("Arial", 8), fg="#8E8E93")
        self.lbl_info.pack(side=tk.LEFT)
        self.lbl_auth = tk.Label(status_frame, text=f"授权设备: {get_machine_id()}", bg="#F5F5F7", font=("Microsoft YaHei", 8), fg="#34C759")
        self.lbl_auth.pack(side=tk.RIGHT, padx=20)
        self.lbl_count = tk.Label(status_frame, text="资产总计: 0  |  已勾选: 0", bg="#F5F5F7", font=("Microsoft YaHei", 9, "bold"), fg="#007AFF")
        self.lbl_count.pack(side=tk.RIGHT)

    def update_sys_info(self):
        try:
            total = len(self.tree.get_children())
            checked = len([i for i in self.tree.get_children() if self.tree.item(i, 'values')[0] == "☑"])
            self.lbl_count.config(text=f"资产总计: {total}  |  已勾选: {checked}")
        except: pass
        if HAS_PSUTIL:
            try:
                cpu = psutil.cpu_percent()
                mem = psutil.virtual_memory().percent
                self.lbl_info.config(text=f"RAM: {mem}% | CPU: {cpu}%")
            except: pass
        self.root.after(500, self.update_sys_info)

    def setup_table_area(self):
        scroll_y = ttk.Scrollbar(self.top_frame)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        columns = ("check", "id", "country", "icp", "title", "url", "length", "status", "product")
        self.tree = ttk.Treeview(self.top_frame, columns=columns, show="headings", yscrollcommand=scroll_y.set)
        scroll_y.config(command=self.tree.yview)
        
        self.all_checked = False
        
        self.headings_text = {
            "check": "1.☐ 选",
            "id": "2.ID",
            "country": "3.国家",
            "icp": "4.备案",
            "title": "5.标题",
            "url": "6.资产链接",
            "length": "7.长度",
            "status": "8.状态",
            "product": "9.指纹"
        }
        self.sort_states = {c: 0 for c in self.headings_text}
        
        headings = [("check",60), ("id",50), ("country",80), ("icp",100), ("title",180), ("url",260), ("length",60), ("status",60), ("product",130)]
        for col, width in headings:
            self.tree.heading(col, text=self.headings_text[col], command=lambda c=col: self.sort_column(c))
            self.tree.column(col, width=width, anchor=tk.CENTER if col in ("check","id","status") else tk.W)
            
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.tag_configure('oddrow', background='#FFFFFF')
        self.tree.tag_configure('evenrow', background='#F9F9FB')
        self.tree.tag_configure('alive', foreground='#34C759', font=('Microsoft YaHei', 9, 'bold'))
        self.tree.tag_configure('dead', foreground='#FF3B30')
        
        self.tree.bind('<ButtonRelease-1>', self.toggle_checkbox)
        self.tree.bind('<Double-1>', lambda e: self.open_selected_links())

        self.enable_drag_drop(self.tree, 'table')

        self.menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei", 9))
        self.menu.add_command(label="🚀 浏览器打开选中", command=self.open_selected_links)
        self.menu.add_separator()
        self.menu.add_command(label="📋 复制 URL", command=lambda: self.copy_to_clip(5))
        self.menu.add_command(label="📋 复制 IP:Port", command=lambda: self.copy_to_clip(5, strip_http=True))
        self.menu.add_separator()
        self.menu.add_command(label="➖ 动态删除选中资产", command=self.delete_highlighted_rows)
        self.tree.bind("<Button-3>", self.show_context_menu)

    def sort_column(self, col):
        if col == "check":
            self.all_checked = not self.all_checked
            new_state = "☑" if self.all_checked else "☐"
            self.headings_text["check"] = f"1.{new_state} 选"
            self.tree.heading("check", text=self.headings_text["check"])
            for item in self.tree.get_children():
                vals = list(self.tree.item(item, 'values'))
                if vals[0] != new_state:
                    vals[0] = new_state
                    self.tree.item(item, values=vals)
            return

        next_state = (self.sort_states[col] + 1) % 3
        for c in self.headings_text:
            if c != "check":
                self.sort_states[c] = 0
                self.tree.heading(c, text=self.headings_text[c])
        self.sort_states[col] = next_state
        if next_state == 0:
            sort_col = 'id'
            reverse = False
            self.tree.heading(col, text=self.headings_text[col])
        else:
            sort_col = col
            reverse = (next_state == 2)
            arrow = " ▲" if next_state == 1 else " ▼"
            self.tree.heading(col, text=self.headings_text[col] + arrow)
            
        col_idx = self.tree['columns'].index(sort_col)
        data = []
        for item in self.tree.get_children(''):
            val = self.tree.item(item, 'values')[col_idx]
            data.append((val, item))
            
        def convert(val):
            if sort_col in ('id', 'length', 'status'):
                try: return float(val)
                except ValueError: return float('inf') if not reverse else float('-inf')
            return str(val).lower()
            
        data.sort(key=lambda x: convert(x[0]), reverse=reverse)
        for index, (val, item) in enumerate(data):
            self.tree.move(item, '', index)
        for index, item in enumerate(self.tree.get_children('')):
            tag = 'evenrow' if (index + 1) % 2 == 0 else 'oddrow'
            current_tags = list(self.tree.item(item, 'tags'))
            new_tags = [t for t in current_tags if t not in ('oddrow', 'evenrow')]
            new_tags.insert(0, tag)
            self.tree.item(item, tags=tuple(new_tags))

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
            self.menu.tk_popup(event.x_root, event.y_root)

    def copy_to_clip(self, col_index, strip_http=False):
        selected = self.tree.selection()
        if not selected: return
        results = []
        for item in selected:
            val = str(self.tree.item(item, 'values')[col_index])
            if strip_http: val = val.replace("http://", "").replace("https://", "").split("/")[0]
            results.append(val)
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(results))
        self.log(f"已复制 {len(results)} 条数据到剪贴板。")

    def get_target_col(self):
        try:
            col = int(self.entry_col_index.get().strip()) - 1
            if 0 <= col <= 8:
                return col
            else:
                messagebox.showwarning("错误", "列号必须在 1 到 9 之间！\n(1=勾选 2=ID 3=国家 4=备案 5=标题 6=链接 7=长度 8=状态 9=指纹)")
                return None
        except:
            messagebox.showwarning("错误", "请输入正确的列号数字！")
            return None

    def mark_contains(self):
        col = self.get_target_col()
        if col is None: return
        keyword = self.entry_mark_keyword.get().strip()
        if not keyword:
            messagebox.showinfo("提示", "请输入需要包含的关键词！")
            return
        
        count = 0
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, 'values'))
            if keyword in str(vals[col]):
                if vals[0] != "☑":
                    vals[0] = "☑"
                    self.tree.item(item, values=vals)
                    count += 1
        self.log(f"🎯 已成功勾选 {count} 条第 {col+1} 列包含 '{keyword}' 的数据。")

    def mark_duplicates(self):
        col = self.get_target_col()
        if col is None: return
        
        count = 0
        if col == 5:
            # === 针对第6列（资产链接）的特殊清洗与查重逻辑 ===
            seen = set()
            for item in self.tree.get_children():
                vals = list(self.tree.item(item, 'values'))
                val = str(vals[col])
                
                if val not in ("-", "", "待测", "Error", "Timeout"):
                    try:
                        # 解析URL，精准剥离端口号及后续路径内容
                        parsed = urllib.parse.urlparse(val)
                        if parsed.scheme and parsed.hostname:
                            hostname = f"[{parsed.hostname}]" if ':' in parsed.hostname else parsed.hostname
                            clean_val = f"{parsed.scheme}://{hostname}"
                            vals[col] = clean_val
                            val = clean_val
                    except Exception:
                        pass
                        
                    # 查重逻辑：首次出现的保留，后续重复的打勾
                    if val in seen:
                        if vals[0] != "☑":
                            vals[0] = "☑"
                            count += 1
                    else:
                        seen.add(val)
                        
                # 将清洗结果和勾选状态更新回表格
                self.tree.item(item, values=vals)
                
            self.log(f"👯 链接查重清洗完毕：已剥离端口及后缀，并勾选 {count} 条重复链接（保留唯一根地址）。")
            
        else:
            # === 其他列的原有查重逻辑：无差别全部勾选 ===
            val_counts = {}
            for item in self.tree.get_children():
                val = str(self.tree.item(item, 'values')[col])
                if val in ("-", "", "待测", "Error", "Timeout"):
                    continue
                val_counts[val] = val_counts.get(val, 0) + 1
                
            for item in self.tree.get_children():
                vals = list(self.tree.item(item, 'values'))
                val = str(vals[col])
                if val in val_counts and val_counts[val] > 1:
                    if vals[0] != "☑":
                        vals[0] = "☑"
                        self.tree.item(item, values=vals)
                        count += 1
                        
            self.log(f"👯 目标列查重完毕：已无差别勾选 {count} 条存在重复的数据。")

    def copy_column_all(self):
        col = self.get_target_col()
        if col is None: return
        
        results = []
        for item in self.tree.get_children():
            val = str(self.tree.item(item, 'values')[col])
            if val not in ("-", "", "待测"):
                results.append(val)
            
        if results:
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(results))
            self.log(f"📋 已成功提取第 {col+1} 列的 {len(results)} 条有效数据到剪贴板。")
        else:
            self.log("📋 目标列没有可提取的有效数据。")

    def setup_bottom_area(self):
        btn_frame = tk.Frame(self.bottom_frame, bg="#F5F5F7")
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=15, pady=10)
        
        btn_opt = {"font": ("Microsoft YaHei", 9, "bold"), "width": 16, "bd": 0, "pady": 6, "anchor": "w", "padx": 15}
        
        top_btn_group = tk.Frame(btn_frame, bg="#F5F5F7")
        top_btn_group.pack(side=tk.TOP, fill=tk.X)
        
        self.btn_window_mode = tk.Button(top_btn_group, text="🖥️   切换为全屏模式", bg="#007AFF", fg="white", **btn_opt, command=self.toggle_window_mode)
        self.btn_window_mode.pack(pady=(0, 10))
        
        tk.Button(top_btn_group, text="💾   保存全局配置", bg="#34C759", fg="white", **btn_opt, command=self.save_app_config).pack(pady=5)
        tk.Button(top_btn_group, text="🗑️   动态清空表格", bg="#8E8E93", fg="white", **btn_opt, command=self.clear_table).pack(pady=5)
        tk.Button(top_btn_group, text="➖   动态删除勾选行", bg="#FF3B30", fg="white", **btn_opt, command=self.delete_checked_rows).pack(pady=5)

        self.btn_bp = tk.Button(btn_frame, text="🕷️\nBP 启动\n(右键重设路径)", bg="#5856D6", fg="white", font=("Microsoft YaHei", 11, "bold"), width=13, height=3, bd=0, command=self.start_bp)
        self.btn_bp.pack(side=tk.BOTTOM, pady=10)
        self.btn_bp.bind("<Button-3>", self.reconfigure_bp)

        nb_frame = tk.Frame(self.bottom_frame, bg="#F5F5F7")
        nb_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.notebook = ttk.Notebook(nb_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_fofa = tk.Frame(self.notebook, bg="white")
        self.tab_check = tk.Frame(self.notebook, bg="white")
        self.tab_pentest = tk.Frame(self.notebook, bg="white")
        self.tab_text_dedup = tk.Frame(self.notebook, bg="white")
        
        self.notebook.add(self.tab_fofa, text=" 1. FOFA 采集 ")
        self.notebook.add(self.tab_check, text=" 2. 资产管理与测活 ")
        self.notebook.add(self.tab_pentest, text=" 3. 自动化 Payload ")
        self.notebook.add(self.tab_text_dedup, text=" 4. 文本去重清洗 ")

        self.setup_fofa_tab()
        self.setup_check_tab()
        self.setup_pentest_tab()
        self.setup_text_dedup_tab()

        log_frame = tk.LabelFrame(self.bottom_frame, text="实战日志", bg="#F5F5F7", font=("Microsoft YaHei", 9, "bold"))
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        self.text_log = tk.Text(log_frame, bg="white", fg="#1C1C1E", font=("Courier New", 9), bd=0)
        self.text_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log("系统核心加载完毕，当前设备已永久绑定并授权...")

    def setup_text_dedup_tab(self):
        t = tk.Frame(self.tab_text_dedup, bg="white", padx=15, pady=15)
        t.pack(fill=tk.BOTH, expand=True)
        
        f_main = tk.Frame(t, bg="white")
        f_main.pack(fill=tk.X, pady=5)
        tk.Label(f_main, text="主文本完全路径:", bg="#F2F2F7", font=("Microsoft YaHei", 9, "bold"), width=16, anchor="e").pack(side=tk.LEFT, ipady=3, padx=(0, 5))
        self.entry_dedup_main = tk.Entry(f_main, bg="#F2F2F7", bd=0)
        self.entry_dedup_main.insert(0, self.config_data.get("dedup_main_txt", ""))
        self.entry_dedup_main.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(f_main, text="浏览", bg="#E5E5EA", bd=0, padx=10, command=lambda: self.browse_txt_for_entry(self.entry_dedup_main, "dedup_main_txt")).pack(side=tk.LEFT, padx=(5, 0))
        tk.Button(f_main, text="主文本自去重 覆盖更新", bg="#E5E5EA", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=10, command=lambda: self.self_dedup_file(self.entry_dedup_main)).pack(side=tk.LEFT, padx=(5, 0))
        self.enable_drag_drop(self.entry_dedup_main, 'txt')

        f_sub = tk.Frame(t, bg="white")
        f_sub.pack(fill=tk.X, pady=5)
        tk.Label(f_sub, text="副文本完全路径:", bg="#F2F2F7", font=("Microsoft YaHei", 9, "bold"), width=16, anchor="e").pack(side=tk.LEFT, ipady=3, padx=(0, 5))
        self.entry_dedup_sub = tk.Entry(f_sub, bg="#F2F2F7", bd=0)
        self.entry_dedup_sub.insert(0, self.config_data.get("dedup_sub_txt", ""))
        self.entry_dedup_sub.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(f_sub, text="浏览", bg="#E5E5EA", bd=0, padx=10, command=lambda: self.browse_txt_for_entry(self.entry_dedup_sub, "dedup_sub_txt")).pack(side=tk.LEFT, padx=(5, 0))
        tk.Button(f_sub, text="副文本自去重 覆盖更新", bg="#E5E5EA", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=10, command=lambda: self.self_dedup_file(self.entry_dedup_sub)).pack(side=tk.LEFT, padx=(5, 0))
        self.enable_drag_drop(self.entry_dedup_sub, 'txt')

        f_cross = tk.Frame(t, bg="white")
        f_cross.pack(fill=tk.X, pady=15)
        
        btn_cross = tk.Button(f_cross, text="文本去重 主文本更新累加保存 > 提取未重复新内容 > 显示至列表及覆盖至副文本", 
                              bg="#E1F5FE", fg="#0277BD", font=("Microsoft YaHei", 10, "bold"), bd=0, pady=10, command=self.cross_deduplicate)
        btn_cross.pack(fill=tk.X)

        ttk.Separator(t, orient='horizontal').pack(fill=tk.X, pady=5)

        f_del = tk.Frame(t, bg="white")
        f_del.pack(fill=tk.X, pady=10)
        tk.Label(f_del, text="主文本操作内容:", bg="#F2F2F7", font=("Microsoft YaHei", 9, "bold"), width=16, anchor="e").pack(side=tk.LEFT, ipady=3, padx=(0, 5))
        self.entry_del_target = tk.Entry(f_del, width=20, bg="#FFF0E0", bd=0)
        self.entry_del_target.pack(side=tk.LEFT, ipady=3, padx=5)
        
        tk.Button(f_del, text="✂️ 删除自身及右边", bg="#FF9500", fg="white", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=15, command=self.delete_self_and_right).pack(side=tk.LEFT, padx=5)
        tk.Label(f_del, text="(输入需要剔除的尾部特征，如 '?' 或 '/'，将直接修改主文本文件)", bg="white", font=("Arial", 8), fg="#8E8E93").pack(side=tk.LEFT, padx=5)

        # ====== 新增：提取表格 URL 并用逗号连接功能 ======
        ttk.Separator(t, orient='horizontal').pack(fill=tk.X, pady=10)
        
        f_join = tk.Frame(t, bg="white")
        f_join.pack(fill=tk.X, pady=5)
        tk.Label(f_join, text="表格资产提取:", bg="#F2F2F7", font=("Microsoft YaHei", 9, "bold"), width=16, anchor="e").pack(side=tk.LEFT, ipady=3, padx=(0, 5))
        
        btn_join = tk.Button(f_join, text="🔗 将URL使用英文逗号连接并复制", bg="#5856D6", fg="white", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=15, command=self.join_urls_with_comma)
        btn_join.pack(side=tk.LEFT, padx=5)
        tk.Label(f_join, text="(一键提取上方表格中的所有URL，用英文逗号拼接并自动存入剪贴板)", bg="white", font=("Arial", 8), fg="#8E8E93").pack(side=tk.LEFT, padx=5)

    def join_urls_with_comma(self):
        urls = []
        for item in self.tree.get_children():
            # 表格第6列（资产链接）的索引是5
            val = str(self.tree.item(item, 'values')[5])
            if val and val not in ("-", "", "待测"):
                urls.append(val)
                
        if not urls:
            messagebox.showwarning("提示", "上方表格中没有任何有效的 URL 可供提取！")
            return
            
        result_str = ",".join(urls)
        
        # 写入剪贴板
        self.root.clipboard_clear()
        self.root.clipboard_append(result_str)
        self.log(f"🔗 成功提取了 {len(urls)} 条 URL，已用逗号连接并自动复制到了剪贴板！")
        messagebox.showinfo("提取成功", f"处理完成！\n\n成功将上方表格内的 {len(urls)} 条 URL 拼接，并已复制到您的剪贴板。")

    def browse_txt_for_entry(self, entry_widget, config_key):
        path = filedialog.askopenfilename(title="选择TXT文件", filetypes=[("TXT 文本文件", "*.txt")])
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)
            self.config_data[config_key] = path
            save_global_config(self.config_data)

    def self_dedup_file(self, entry_widget):
        path = entry_widget.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("错误", "请先填入有效的文本路径！")
            return
            
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            original_len = len(lines)
            unique_lines = list(dict.fromkeys(line.strip() for line in lines if line.strip()))
            new_len = len(unique_lines)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(unique_lines) + '\n')
                
            self.log(f"✅ 文件自去重完毕: {os.path.basename(path)} | 剔除 {original_len - new_len} 条重复数据。")
        except Exception as e:
            self.log(f"❌ 自去重失败: {str(e)}")

    def cross_deduplicate(self):
        main_path = self.entry_dedup_main.get().strip()
        sub_path = self.entry_dedup_sub.get().strip()
        
        if not os.path.isfile(main_path):
            messagebox.showwarning("错误", "主文本路径为空或文件不存在！")
            return
        if not os.path.isfile(sub_path):
            try: open(sub_path, 'a').close()
            except: pass
            
        try:
            with open(main_path, 'r', encoding='utf-8', errors='ignore') as f:
                main_lines = [l.strip() for l in f.readlines() if l.strip()]
            with open(sub_path, 'r', encoding='utf-8', errors='ignore') as f:
                sub_lines = [l.strip() for l in f.readlines() if l.strip()]
                
            sub_set = set(sub_lines)
            new_unique_lines = []
            
            for line in main_lines:
                if line not in sub_set:
                    new_unique_lines.append(line)
                    sub_set.add(line)
                    
            if not new_unique_lines:
                self.log("ℹ️ 交叉比对完成，主文本中没有发现任何新内容。")
                return
                
            with open(sub_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_unique_lines) + '\n')
                
            self.clear_table()
            start_idx = 1
            for i, url in enumerate(new_unique_lines, start_idx):
                link = url if url.startswith("http") else "http://" + url
                tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                self.tree.insert("", "end", values=("☐", i, "-", "-", "-", link, "-", "待测", "-"), tags=(tag,))
            self.update_range_end()
            
            self.log(f"🌟 交叉去重完毕！发现 {len(new_unique_lines)} 条新资产，已覆盖保存至副文本，并成功载入表格准备测活！")
            if HAS_WINSOUND: winsound.MessageBeep(winsound.MB_OK)
        except Exception as e:
            self.log(f"❌ 交叉去重失败: {str(e)}")

    def delete_self_and_right(self):
        path = self.entry_dedup_main.get().strip()
        target = self.entry_del_target.get()
        
        if not os.path.isfile(path):
            messagebox.showwarning("错误", "请先填入有效的主文本路径！")
            return
        if not target:
            messagebox.showwarning("提示", "请输入要删除的特征字符（例如 ? 或 /）！")
            return
            
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            new_lines = []
            mod_count = 0
            for line in lines:
                line = line.strip()
                if not line: continue
                
                if target in line:
                    new_lines.append(line.split(target)[0])
                    mod_count += 1
                else:
                    new_lines.append(line)
                    
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines) + '\n')
                
            self.log(f"✂️ 截断清洗完毕: 成功切断了 {mod_count} 条包含 '{target}' 的尾巴脏数据。")
        except Exception as e:
            self.log(f"❌ 截断处理失败: {str(e)}")

    def setup_fofa_tab(self):
        f = tk.Frame(self.tab_fofa, bg="white", padx=15, pady=15)
        f.pack(fill=tk.BOTH, expand=True)
        
        lbl_single = tk.Label(f, text="【单条语法查询】", bg="white", font=("Microsoft YaHei", 9, "bold"), fg="#007AFF")
        lbl_single.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        tk.Label(f, text="FOFA Key:", bg="white").grid(row=1, column=0, sticky="w")
        self.entry_fofa_key = tk.Entry(f, width=40, bg="#F2F2F7", bd=0)
        self.entry_fofa_key.insert(0, self.config_data.get("fofa_key",""))
        self.entry_fofa_key.grid(row=1, column=1, pady=5, padx=5, ipady=3, sticky="w")

        tk.Label(f, text="查询语法:", bg="white").grid(row=2, column=0, sticky="w")
        self.entry_fofa_query = tk.Entry(f, width=40, bg="#F2F2F7", bd=0)
        self.entry_fofa_query.insert(0, self.config_data.get("fofa_query",""))
        self.entry_fofa_query.grid(row=2, column=1, sticky="w", pady=5, padx=5, ipady=3)

        tk.Label(f, text="获取数量:", bg="white").grid(row=2, column=2, sticky="e", padx=5)
        self.entry_fofa_size = tk.Entry(f, width=8, bg="#F2F2F7", bd=0)
        self.entry_fofa_size.insert(0, self.config_data.get("fofa_size", "100"))
        self.entry_fofa_size.grid(row=2, column=3, pady=5, padx=5, ipady=3)

        self.btn_fofa_search = tk.Button(f, text="🔍 开始拉取数据", bg="#007AFF", fg="white", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=20, command=self.start_fofa_search)
        self.btn_fofa_search.grid(row=3, column=1, pady=10, sticky="w")

        ttk.Separator(f, orient='horizontal').grid(row=4, column=0, columnspan=4, sticky="ew", pady=15)

        lbl_batch = tk.Label(f, text="【批量指纹查询 (涡轮并发版)】", bg="white", font=("Microsoft YaHei", 9, "bold"), fg="#FF9500")
        lbl_batch.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 5))

        tk.Label(f, text="指纹TXT路径:", bg="white").grid(row=6, column=0, sticky="w")
        self.entry_fofa_txt_path = tk.Entry(f, width=40, bg="#F2F2F7", bd=0)
        self.entry_fofa_txt_path.insert(0, self.config_data.get("fofa_txt_path", ""))
        self.entry_fofa_txt_path.grid(row=6, column=1, pady=5, padx=5, ipady=3, sticky="w")
        tk.Button(f, text="浏览", bg="#E5E5EA", bd=0, padx=10, command=self.select_fofa_txt_file).grid(row=6, column=2, padx=5, sticky="w")
        self.enable_drag_drop(self.entry_fofa_txt_path, 'txt')

        tk.Label(f, text="资产TXT路径:", bg="white").grid(row=7, column=0, sticky="w")
        self.entry_fofa_asset_txt = tk.Entry(f, width=40, bg="#F2F2F7", bd=0)
        self.entry_fofa_asset_txt.insert(0, self.config_data.get("fofa_asset_txt", ""))
        self.entry_fofa_asset_txt.grid(row=7, column=1, pady=5, padx=5, ipady=3, sticky="w")
        tk.Button(f, text="浏览", bg="#E5E5EA", bd=0, padx=10, command=self.select_fofa_asset_txt).grid(row=7, column=2, padx=5, sticky="w")
        tk.Label(f, text="(支持异常熔断保护与安全断点续传)", bg="white", font=("Arial", 8), fg="#8E8E93").grid(row=7, column=3, sticky="w")
        self.enable_drag_drop(self.entry_fofa_asset_txt, 'txt')

        tk.Label(f, text="阈值/并发:", bg="white").grid(row=8, column=0, sticky="w")
        f_thres = tk.Frame(f, bg="white")
        f_thres.grid(row=8, column=1, columnspan=2, sticky="w", pady=5, padx=5)
        
        tk.Label(f_thres, text="淘汰阈值", bg="white", font=("Arial", 9)).pack(side=tk.LEFT)
        self.entry_min_count = tk.Entry(f_thres, width=5, justify="center", bg="#F2F2F7", bd=0)
        self.entry_min_count.insert(0, self.config_data.get("fofa_threshold", "10"))
        self.entry_min_count.pack(side=tk.LEFT, ipady=3, padx=(2, 15))
        
        tk.Label(f_thres, text="并发线程", bg="white", font=("Arial", 9, "bold"), fg="#FF9500").pack(side=tk.LEFT)
        self.entry_fofa_threads = tk.Entry(f_thres, width=5, justify="center", bg="#FFF0E0", bd=0, fg="#FF9500")
        self.entry_fofa_threads.insert(0, self.config_data.get("fofa_threads", "3"))
        self.entry_fofa_threads.pack(side=tk.LEFT, ipady=3, padx=(2, 10))

        f_btn_batch = tk.Frame(f, bg="white")
        f_btn_batch.grid(row=9, column=1, columnspan=3, pady=10, sticky="w")
        self.btn_fofa_batch = tk.Button(f_btn_batch, text="🔍 FOFA指纹TXT查询", bg="#FF9500", fg="white", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=20, command=self.batch_fofa_from_txt)
        self.btn_fofa_batch.pack(side=tk.LEFT)
        self.btn_stop_batch = tk.Button(f_btn_batch, text="⏹ 查询完当前资产停止", bg="#E5E5EA", fg="#A1A1A6", disabledforeground="#A1A1A6", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=15, state="disabled", command=self.stop_fofa_batch)
        self.btn_stop_batch.pack(side=tk.LEFT, padx=10)

    def stop_fofa_batch(self):
        self.stop_fofa_batch_flag = True
        if hasattr(self, 'btn_stop_batch'):
            self.btn_stop_batch.config(state="disabled", text="正在等待当前轮次跑完...")
        self.log("⚠️ 已触发优雅停止指令！程序将在正在跑的资产检索完毕后安全退出...")

    def setup_check_tab(self):
        c = tk.Frame(self.tab_check, bg="white", padx=15, pady=5)
        c.pack(fill=tk.BOTH, expand=True)

        r1 = tk.Frame(c, bg="white"); r1.pack(fill=tk.X, pady=2)
        tk.Button(r1, text="📋 粘贴剪贴板链接", bg="#F2F2F7", bd=0, command=self.paste_links).pack(side=tk.LEFT, padx=5)
        tk.Button(r1, text="✂️ 动态去重(链接)", bg="#F2F2F7", bd=0, command=self.remove_duplicates).pack(side=tk.LEFT, padx=5)
        tk.Button(r1, text="🔄 反选所有复选框", bg="#F2F2F7", bd=0, command=self.invert_selection).pack(side=tk.LEFT, padx=5)

        r_mark = tk.Frame(c, bg="white"); r_mark.pack(fill=tk.X, pady=5)
        tk.Label(r_mark, text="目标列号(1-9):", bg="white", font=("Microsoft YaHei", 9, "bold"), fg="#5856D6").pack(side=tk.LEFT)
        self.entry_col_index = tk.Entry(r_mark, width=4, justify="center", bg="#F2F2F7", bd=0)
        self.entry_col_index.insert(0, "5")
        self.entry_col_index.pack(side=tk.LEFT, padx=5, ipady=2)
        
        tk.Label(r_mark, text="包含关键词:", bg="white").pack(side=tk.LEFT, padx=(10, 2))
        self.entry_mark_keyword = tk.Entry(r_mark, width=15, bg="#F2F2F7", bd=0)
        self.entry_mark_keyword.pack(side=tk.LEFT, padx=5, ipady=2)
        
        tk.Button(r_mark, text="🎯 标记包含项", bg="#E5E5EA", bd=0, command=self.mark_contains).pack(side=tk.LEFT, padx=5)
        tk.Button(r_mark, text="👯 目标列全部查重", bg="#E5E5EA", fg="#FF3B30", bd=0, command=self.mark_duplicates).pack(side=tk.LEFT, padx=5)
        tk.Button(r_mark, text="📋 目标列全部复制", bg="#E5E5EA", bd=0, command=self.copy_column_all).pack(side=tk.LEFT, padx=5)

        r_range = tk.Frame(c, bg="white"); r_range.pack(fill=tk.X, pady=5)
        tk.Label(r_range, text="操作范围(序号):", bg="white", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT)
        self.entry_range_start = tk.Entry(r_range, width=6, justify="center", bg="#F2F2F7", bd=0)
        self.entry_range_start.insert(0, "1")
        self.entry_range_start.pack(side=tk.LEFT, padx=5, ipady=2)
        tk.Label(r_range, text="到", bg="white").pack(side=tk.LEFT)
        self.entry_range_end = tk.Entry(r_range, width=6, justify="center", bg="#F2F2F7", bd=0)
        self.entry_range_end.insert(0, "0")
        self.entry_range_end.pack(side=tk.LEFT, padx=5, ipady=2)
        
        self.entry_range_start.bind("<KeyRelease>", self.dynamic_check_range)
        self.entry_range_end.bind("<KeyRelease>", self.dynamic_check_range)
        tk.Label(r_range, text="*(输入数字动态勾选)", font=("Arial", 8), fg="#8E8E93", bg="white").pack(side=tk.LEFT, padx=(5, 10))
        
        tk.Button(r_range, text="🚀 默认浏览器打开所选链接", bg="#E5E5EA", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=10, command=self.open_checked_links).pack(side=tk.LEFT, padx=5)

        r2 = tk.Frame(c, bg="white"); r2.pack(fill=tk.X, pady=5)
        tk.Label(r2, text="并发线程:", bg="white", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT)
        self.entry_threads = tk.Entry(r2, width=5, justify="center", bg="#F2F2F7", bd=0)
        self.entry_threads.insert(0, self.config_data.get("threads", "200"))
        self.entry_threads.pack(side=tk.LEFT, padx=5, ipady=2)
        
        tk.Label(r2, text="超时(秒):", bg="white", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT, padx=(10, 0))
        self.entry_timeout = tk.Entry(r2, width=5, justify="center", bg="#F2F2F7", bd=0)
        self.entry_timeout.insert(0, self.config_data.get("timeout", "3"))
        self.entry_timeout.pack(side=tk.LEFT, padx=5, ipady=2)

        tk.Label(r2, text="存活状态码:", bg="white", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT, padx=(10, 0))
        self.entry_status = tk.Entry(r2, width=5, justify="center", bg="#F2F2F7", bd=0)
        self.entry_status.insert(0, self.config_data.get("status_code", "200"))
        self.entry_status.pack(side=tk.LEFT, padx=5, ipady=2)
        
        self.btn_check = tk.Button(r2, text="⚡ 对【已勾选】资产极速测活", bg="#34C759", fg="white", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=15, command=self.start_health_check)
        self.btn_check.pack(side=tk.LEFT, padx=15)
        self.btn_pause = tk.Button(r2, text="⏸ 暂停", bg="#E5E5EA", fg="#A1A1A6", disabledforeground="#A1A1A6", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=10, state="disabled", command=self.pause_health_check)
        self.btn_pause.pack(side=tk.LEFT, padx=5)
        self.btn_stop = tk.Button(r2, text="⏹ 停止", bg="#E5E5EA", fg="#A1A1A6", disabledforeground="#A1A1A6", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=10, state="disabled", command=self.stop_health_check)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        path_frame = tk.Frame(c, bg="white")
        path_frame.pack(fill=tk.X, pady=8)

        f_imp = tk.Frame(path_frame, bg="white")
        f_imp.pack(fill=tk.X, pady=2)
        lbl_imp = tk.Label(f_imp, text="直连资产txt路径:", bg="#F2F2F7", font=("Microsoft YaHei", 9, "bold"), width=16, anchor="e")
        lbl_imp.pack(side=tk.LEFT, ipady=3, padx=(0, 5))
        self.entry_import_path = tk.Entry(f_imp, bg="#F2F2F7", bd=0)
        self.entry_import_path.insert(0, self.config_data.get("import_path", ""))
        self.entry_import_path.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(f_imp, text="浏览", bg="#E5E5EA", bd=0, padx=10, command=self.select_import_file).pack(side=tk.LEFT, padx=(5, 0))
        tk.Button(f_imp, text="📥 导入为直连资产", bg="#5856D6", fg="white", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=10, command=self.import_txt_data).pack(side=tk.LEFT, padx=(5, 0))
        self.enable_drag_drop(self.entry_import_path, 'txt')
        
        f_exp = tk.Frame(path_frame, bg="white")
        f_exp.pack(fill=tk.X, pady=2)
        lbl_exp = tk.Label(f_exp, text="导出资产文件夹:", bg="#F2F2F7", font=("Microsoft YaHei", 9, "bold"), width=16, anchor="e")
        lbl_exp.pack(side=tk.LEFT, ipady=3, padx=(0, 5))
        self.entry_export_dir = tk.Entry(f_exp, bg="#F2F2F7", bd=0)
        self.entry_export_dir.insert(0, self.config_data.get("export_dir", ""))
        self.entry_export_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(f_exp, text="浏览", bg="#E5E5EA", bd=0, padx=10, command=self.select_export_dir).pack(side=tk.LEFT, padx=(5, 0))
        tk.Button(f_exp, text="📁 一键导出", bg="#007AFF", fg="white", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=10, command=self.export_txt_data).pack(side=tk.LEFT, padx=(5, 0))
        self.enable_drag_drop(self.entry_export_dir, 'dir')

        r4 = tk.Frame(c, bg="white"); r4.pack(fill=tk.X, pady=5)
        tk.Label(r4, text="完成提示音(WAV):", bg="white", font=("Microsoft YaHei", 9, "bold"), fg="#007AFF").pack(side=tk.LEFT)
        self.entry_sound_path = tk.Entry(r4, width=30, bg="#F2F2F7", bd=0)
        self.entry_sound_path.insert(0, self.config_data.get("sound_path", ""))
        self.entry_sound_path.pack(side=tk.LEFT, padx=5, ipady=2)
        tk.Button(r4, text="浏览音频", bg="#E5E5EA", bd=0, command=self.select_sound).pack(side=tk.LEFT)
        tk.Label(r4, text="(留空默认'叮'声)", bg="white", font=("Arial", 8), fg="#8E8E93").pack(side=tk.LEFT, padx=5)
        self.enable_drag_drop(self.entry_sound_path, 'wav')

        self.var_auto_shutdown = tk.BooleanVar(value=False)
        tk.Checkbutton(r4, text="测试完成后自动保存并关机", variable=self.var_auto_shutdown, bg="white", font=("Microsoft YaHei", 9, "bold"), fg="#FF3B30").pack(side=tk.RIGHT, padx=5)

    def setup_pentest_tab(self):
        p = tk.Frame(self.tab_pentest, bg="white", padx=15, pady=15)
        p.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(p, text="拼接路径 (URI):", bg="white", font=("Microsoft YaHei", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.entry_uri = tk.Entry(p, width=45, bg="#F2F2F7", bd=0)
        self.entry_uri.insert(0, self.config_data.get("pentest_uri", "/admin/login.php"))
        self.entry_uri.grid(row=0, column=1, columnspan=2, pady=5, padx=5, ipady=3, sticky="w")
        
        tk.Label(p, text="基础 POST 数据:", bg="white", font=("Microsoft YaHei", 9, "bold")).grid(row=1, column=0, sticky="w")
        self.entry_post = tk.Entry(p, width=45, bg="#F2F2F7", bd=0)
        self.entry_post.insert(0, self.config_data.get("pentest_post", "user=admin&pass=123456"))
        self.entry_post.grid(row=1, column=1, columnspan=2, pady=5, padx=5, ipady=3, sticky="w")
        tk.Label(p, text="(留空则发起 GET 请求)", font=("Arial", 8), fg="#8E8E93", bg="white").grid(row=1, column=3, sticky="w")

        f_token = tk.Frame(p, bg="white")
        f_token.grid(row=2, column=0, columnspan=4, sticky="w", pady=10)

        self.var_enable_token = tk.BooleanVar(value=self.config_data.get("enable_token", False))
        tk.Checkbutton(f_token, text="启用 Token 爆破/提取", variable=self.var_enable_token, bg="white", font=("Microsoft YaHei", 9, "bold"), fg="#5856D6").pack(side=tk.LEFT)

        tk.Label(f_token, text="左特征:", bg="white").pack(side=tk.LEFT, padx=(10, 2))
        self.entry_token_left = tk.Entry(f_token, width=20, bg="#F2F2F7", bd=0)
        self.entry_token_left.insert(0, self.config_data.get("token_left", 'name="token" value="'))
        self.entry_token_left.pack(side=tk.LEFT, ipady=3)

        tk.Label(f_token, text="拼接参数名:", bg="white").pack(side=tk.LEFT, padx=(10, 2))
        self.entry_token_param = tk.Entry(f_token, width=10, bg="#F2F2F7", bd=0)
        self.entry_token_param.insert(0, self.config_data.get("token_param", "token"))
        self.entry_token_param.pack(side=tk.LEFT, ipady=3)

        tk.Label(f_token, text="右特征:", bg="white").pack(side=tk.LEFT, padx=(10, 2))
        self.entry_token_right = tk.Entry(f_token, width=8, bg="#F2F2F7", bd=0)
        self.entry_token_right.insert(0, self.config_data.get("token_right", '">'))
        self.entry_token_right.pack(side=tk.LEFT, ipady=3)

        self.var_enable_cors = tk.BooleanVar(value=self.config_data.get("enable_cors", False))
        tk.Checkbutton(f_token, text="CORS跨域漏洞", variable=self.var_enable_cors, bg="white", font=("Microsoft YaHei", 9, "bold"), fg="#34C759").pack(side=tk.LEFT, padx=15)

        self.btn_pentest = tk.Button(p, text="🔥 运行 Payload 极速探测", bg="#FF9500", fg="white", font=("Microsoft YaHei", 9, "bold"), bd=0, padx=15, pady=5, command=self.start_pentest_scan)
        self.btn_pentest.grid(row=3, column=1, pady=15, sticky="w")
        
    def log(self, msg):
        t = time.strftime("%H:%M:%S")
        self.text_log.config(state="normal")
        self.text_log.insert(tk.END, f"[{t}] {msg}\n")
        self.text_log.see(tk.END)
        self.text_log.config(state="disabled")

    def save_app_config(self, silent=False):
        self.config_data["status_code"] = self.entry_status.get().strip() if hasattr(self, 'entry_status') else "200"
        self.config_data["threads"] = self.entry_threads.get().strip() if hasattr(self, 'entry_threads') else "200"
        self.config_data["timeout"] = self.entry_timeout.get().strip() if hasattr(self, 'entry_timeout') else "3"
        self.config_data["fofa_key"] = self.entry_fofa_key.get().strip() if hasattr(self, 'entry_fofa_key') else ""
        self.config_data["fofa_query"] = self.entry_fofa_query.get().strip() if hasattr(self, 'entry_fofa_query') else ""
        self.config_data["fofa_size"] = self.entry_fofa_size.get().strip() if hasattr(self, 'entry_fofa_size') else "100"
        self.config_data["import_path"] = self.entry_import_path.get().strip() if hasattr(self, 'entry_import_path') else ""
        self.config_data["export_dir"] = self.entry_export_dir.get().strip() if hasattr(self, 'entry_export_dir') else ""
        self.config_data["sound_path"] = self.entry_sound_path.get().strip() if hasattr(self, 'entry_sound_path') else ""
        self.config_data["fofa_threshold"] = self.entry_min_count.get().strip() if hasattr(self, 'entry_min_count') else "10"
        self.config_data["fofa_txt_path"] = self.entry_fofa_txt_path.get().strip() if hasattr(self, 'entry_fofa_txt_path') else ""
        self.config_data["fofa_asset_txt"] = self.entry_fofa_asset_txt.get().strip() if hasattr(self, 'entry_fofa_asset_txt') else ""
        self.config_data["fofa_threads"] = self.entry_fofa_threads.get().strip() if hasattr(self, 'entry_fofa_threads') else "3"
        
        if hasattr(self, 'entry_dedup_main'):
            self.config_data["dedup_main_txt"] = self.entry_dedup_main.get().strip()
        if hasattr(self, 'entry_dedup_sub'):
            self.config_data["dedup_sub_txt"] = self.entry_dedup_sub.get().strip()

        if hasattr(self, 'entry_uri'): self.config_data["pentest_uri"] = self.entry_uri.get().strip()
        if hasattr(self, 'entry_post'): self.config_data["pentest_post"] = self.entry_post.get().strip()
        if hasattr(self, 'var_enable_token'): self.config_data["enable_token"] = self.var_enable_token.get()
        if hasattr(self, 'entry_token_left'): self.config_data["token_left"] = self.entry_token_left.get()
        if hasattr(self, 'entry_token_param'): self.config_data["token_param"] = self.entry_token_param.get().strip()
        if hasattr(self, 'entry_token_right'): self.config_data["token_right"] = self.entry_token_right.get()
        if hasattr(self, 'var_enable_cors'): self.config_data["enable_cors"] = self.var_enable_cors.get()
            
        save_global_config(self.config_data)
        
        if not silent:
            messagebox.showinfo("Success", "全局配置已保存！")
            
    def dynamic_check_range(self, event=None):
        try:
            s_str = self.entry_range_start.get().strip()
            e_str = self.entry_range_end.get().strip()
            if not s_str or not e_str: return
            s, e = int(s_str), int(e_str)

            for i, item in enumerate(self.tree.get_children(), 1):
                target_state = "☑" if s <= i <= e else "☐"
                vals = list(self.tree.item(item, 'values'))
                if vals[0] != target_state:  
                    vals[0] = target_state
                    self.tree.item(item, values=vals)
            
            self.all_checked = False
            self.headings_text["check"] = "1.☐ 选"
            self.tree.heading("check", text=self.headings_text["check"])
        except ValueError:
            pass 

    def animate_delete(self, items_to_del, msg=None, chunk_size=1):
        if not items_to_del:
            self.reindex_table()
            self.all_checked = False
            self.headings_text["check"] = "1.☐ 选"
            self.tree.heading("check", text=self.headings_text["check"])
            self.is_animating = False
            if msg: self.log(msg)
            return
            
        for _ in range(min(chunk_size, len(items_to_del))):
            item = items_to_del.pop(0)
            if self.tree.exists(item):
                self.tree.delete(item)
                
        remain = len(items_to_del)
        if remain > 500: next_chunk, delay = 20, 10
        elif remain > 100: next_chunk, delay = 10, 20
        elif remain > 30: next_chunk, delay = 5, 20
        else: next_chunk, delay = 1, 30
            
        self.root.after(delay, lambda: self.animate_delete(items_to_del, msg, next_chunk))

    def delete_checked_rows(self):
        if self.is_animating: return
        items_to_del = [item for item in self.tree.get_children() if self.tree.item(item, 'values')[0] == "☑"]
        if not items_to_del:
            messagebox.showwarning("提示", "请先在表格第一列【勾选】要删除的行！")
            return
        self.is_animating = True
        self.log(f"开始动态清理 {len(items_to_del)} 条已勾选的记录...")
        self.animate_delete(items_to_del, msg="勾选清理完成。")

    def delete_highlighted_rows(self):
        if self.is_animating: return
        selected = list(self.tree.selection())
        if not selected:
            messagebox.showwarning("提示", "请先在表格中【点击高亮】要删除的行。")
            return
        self.is_animating = True
        self.log(f"开始动态清理 {len(selected)} 条高亮选中的记录...")
        self.animate_delete(selected, msg="高亮清理完成。")

    def clear_table(self):
        if self.is_animating: return
        items = list(self.tree.get_children())
        if not items: return
        self.is_animating = True
        self.log("启动销毁程序，正在动态清空表格数据...")
        self.animate_delete(items, msg="表格已彻底清空。")

    def remove_duplicates(self):
        if self.is_animating: return
        seen, to_del = set(), []
        for item in self.tree.get_children():
            url = self.tree.item(item, 'values')[5]
            if url in seen: to_del.append(item)
            else: seen.add(url)
        if not to_del:
            self.log("没有发现重复的资产记录。")
            return
        self.is_animating = True
        self.log(f"开始动态剥离 {len(to_del)} 条重复记录...")
        self.animate_delete(to_del, msg="去重工作已完成。")

    def select_sound(self):
        path = filedialog.askopenfilename(title="选择完成提示音 (WAV格式)", filetypes=[("WAV 音频文件", "*.wav")])
        if path:
            self.entry_sound_path.delete(0, tk.END)
            self.entry_sound_path.insert(0, path)
            self.save_app_config(silent=True)

    def play_finish_sound(self):
        if not HAS_WINSOUND: return
        sound_path = self.entry_sound_path.get().strip()
        if sound_path and os.path.exists(sound_path) and sound_path.lower().endswith('.wav'):
            try:
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)

    def reconfigure_bp(self, event):
        path = filedialog.askopenfilename(title="重新配置 Burp Suite 路径", filetypes=[("可执行文件/JAR/脚本", "*.jar *.exe *.bat *.vbs *.cmd"), ("所有文件", "*.*")])
        if path:
            self.config_data["bp_path"] = path
            save_global_config(self.config_data)
            self.log(f"[*] BP 启动路径已更新并保存。")
            messagebox.showinfo("配置成功", f"BP路径已重新配置！\n现在可以直接左键点击启动了。")

    def start_bp(self):
        bp_path = self.config_data.get("bp_path", "")
        if not bp_path or not os.path.exists(bp_path):
            messagebox.showinfo("初始化配置", "未检测到 Burp Suite 路径。\n请选择您的 Burp Suite 启动文件。")
            bp_path = filedialog.askopenfilename(title="选择 Burp Suite", filetypes=[("可执行文件/JAR/脚本", "*.jar *.exe *.bat *.vbs *.cmd"), ("所有文件", "*.*")])
            if not bp_path: return 
            self.config_data["bp_path"] = bp_path
            save_global_config(self.config_data)
            
        self.log(f"正在唤醒 Burp Suite: {os.path.basename(bp_path)}")
        try:
            bp_dir = os.path.dirname(bp_path)
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            if bp_path.lower().endswith('.jar'):
                subprocess.Popen(['java', '-jar', bp_path], cwd=bp_dir, creationflags=flags)
            elif bp_path.lower().endswith('.vbs'):
                subprocess.Popen(['wscript', bp_path], cwd=bp_dir, creationflags=flags)
            else:
                subprocess.Popen(f'"{bp_path}"', shell=True, cwd=bp_dir, creationflags=flags)
            self.log("[-] 蜘蛛已释放！BP 启动命令发送成功。")
        except Exception as e:
            self.log(f"启动 BP 失败: {str(e)}")
            messagebox.showerror("启动失败", f"无法启动，可能文件有误或未安装Java。\n\n解决办法：右键点击『BP启动』按钮，重新选择！\n\n报错详情: {str(e)}")

    def update_range_end(self):
        try:
            total = len(self.tree.get_children())
            self.entry_range_end.delete(0, tk.END)
            self.entry_range_end.insert(0, str(total))
        except: pass

    def toggle_checkbox(self, event):
        if self.tree.identify_column(event.x) == '#1':
            item = self.tree.identify_row(event.y)
            if item:
                v = list(self.tree.item(item, 'values'))
                v[0] = "☑" if v[0] == "☐" else "☐"
                self.tree.item(item, values=v)
                self.update_sys_info()

    def invert_selection(self):
        for item in self.tree.get_children():
            v = list(self.tree.item(item, 'values'))
            v[0] = "☐" if v[0] == "☑" else "☑"
            self.tree.item(item, values=v)
        self.all_checked = False
        self.headings_text["check"] = "1.☐ 选"
        self.tree.heading("check", text=self.headings_text["check"])
        self.log("完成反选。")

    def open_selected_links(self):
        for item in self.tree.selection():
            webbrowser.open(self.tree.item(item, 'values')[5])

    def open_checked_links(self):
        opened = 0
        for item in self.tree.get_children():
            vals = self.tree.item(item, 'values')
            if vals[0] == "☑":  
                url = vals[5]   
                try: webbrowser.open(url)
                except: pass
                opened += 1
        if opened == 0:
            messagebox.showinfo("提示", "没有找到已勾选的链接！请先在第一列勾选 ☑。")
        else:
            self.log(f"已在默认浏览器中触发打开 {opened} 个链接。")

    def paste_links_from_shortcut(self, event):
        self.paste_links()

    def paste_links(self):
        try:
            raw = self.root.clipboard_get()
            links = re.findall(r'(https?://[^\s,]+|[\w.-]+:\d+)', raw)
            for i, l in enumerate(links, len(self.tree.get_children())+1):
                url = l if l.startswith("http") else "http://" + l
                tag = 'evenrow' if i%2==0 else 'oddrow'
                self.tree.insert("","end", values=("☐",i,"-","-","-",url,"-","待测","-"), tags=(tag,))
            self.update_range_end()
            self.log(f"手动粘贴导入 {len(links)} 条资产")
        except: pass

    def select_fofa_txt_file(self):
        path = filedialog.askopenfilename(title="选择指纹TXT", filetypes=[("TXT 文本文件", "*.txt")])
        if path:
            self.entry_fofa_txt_path.delete(0, tk.END)
            self.entry_fofa_txt_path.insert(0, path)
            self.save_app_config(silent=True)

    def select_fofa_asset_txt(self):
        path = filedialog.askopenfilename(title="选择资产TXT", filetypes=[("TXT 文本文件", "*.txt")])
        if path:
            self.entry_fofa_asset_txt.delete(0, tk.END)
            self.entry_fofa_asset_txt.insert(0, path)
            self.save_app_config(silent=True)

    def select_import_file(self):
        path = filedialog.askopenfilename(title="选择直连资产TXT", filetypes=[("TXT 文本文件", "*.txt")])
        if path:
            self.entry_import_path.delete(0, tk.END)
            self.entry_import_path.insert(0, path)
            self.save_app_config(silent=True)

    def import_txt_data(self):
        path = self.entry_import_path.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("提示", "导入失败！\n请先点击【浏览】按钮或拖入一个真实存在的 TXT 文件。")
            return
            
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            count = 0
            start_idx = len(self.tree.get_children()) + 1
            for i, line in enumerate(lines, start_idx):
                url = line if line.startswith("http") else "http://" + line
                tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                self.tree.insert("", "end", values=("☐", i, "-", "-", "-", url, "-", "待测", "-"), tags=(tag,))
                count += 1
            self.update_range_end()
            self.log(f"成功从 {os.path.basename(path)} 导入 {count} 条资产。")
        except Exception as e:
            self.log(f"导入失败: {str(e)}")
            
    def select_export_dir(self):
        path = filedialog.askdirectory(title="选择导出资产文件夹")
        if path:
            self.entry_export_dir.delete(0, tk.END)
            self.entry_export_dir.insert(0, path)
            self.save_app_config(silent=True)

    def export_txt_data(self, auto_path=None):
        items = self.tree.get_children()
        if not items:
            self.log("表格为空，无数据可导出！")
            return
            
        if auto_path:
            path = auto_path
        else:
            folder = self.entry_export_dir.get().strip()
            if not folder or not os.path.isdir(folder):
                messagebox.showwarning("提示", "未指定导出文件夹！请先拖入或【浏览】选择保存位置。")
                self.select_export_dir()
                folder = self.entry_export_dir.get().strip()
                if not folder: return 
            
            filename = f"资产导出_{time.strftime('%Y%m%d_%H%M%S')}.txt"
            path = os.path.join(folder, filename)

        try:
            with open(path, 'w', encoding='utf-8') as f:
                for item in items:
                    url = self.tree.item(item, 'values')[5]
                    f.write(f"{url}\n")
            self.log(f"成功将 {len(items)} 条资产导出至文件夹: {os.path.dirname(path)}")
            if not auto_path:
                messagebox.showinfo("导出成功", f"资产已打包生成：\n{filename}\n\n保存于：{os.path.dirname(path)}")
        except Exception as e:
            self.log(f"导出失败: {str(e)}")

    def auto_save_and_shutdown(self):
        self.log("触发自动保存并关机...")
        export_folder = self.entry_export_dir.get().strip()
        if not export_folder or not os.path.isdir(export_folder):
            export_folder = os.getcwd() 
            
        filename = f"AutoSave_Assets_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        export_path = os.path.join(export_folder, filename)

        self.export_txt_data(auto_path=export_path)
        self.log(f"⚠️ 系统将在 60 秒后关机！如需取消，请在 cmd 输入 shutdown -a")
        os.system("shutdown -s -t 60")

    def reindex_table(self):
        for i, item in enumerate(self.tree.get_children(), 1):
            vals = list(self.tree.item(item, 'values'))
            vals[1] = str(i)
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.tree.item(item, values=vals, tags=(tag,))
        self.update_range_end()

    def pause_health_check(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.btn_pause.config(text="▶ 继续", bg="#34C759", fg="white")
            self.log("⚠️ 测活已被暂停...")
        else:
            self.pause_event.set()
            self.btn_pause.config(text="⏸ 暂停", bg="#FF9500", fg="white")
            self.log("▶ 测活恢复继续...")

    def stop_health_check(self):
        self.stop_scan = True
        self.pause_event.set() 
        self.log("⏹ 正在停止测活，等待当前线程退出...")
        self.btn_pause.config(state="disabled", bg="#E5E5EA", fg="#A1A1A6")
        self.btn_stop.config(state="disabled", bg="#E5E5EA", fg="#A1A1A6")

    # ========================== 【核心重构：FOFA批量查询引擎 (无限制并发版)】 ==========================
    def batch_fofa_from_txt(self):
        fofa_key = self.entry_fofa_key.get().strip()
        size_val = self.entry_fofa_size.get().strip()
        fp_path = self.entry_fofa_txt_path.get().strip()
        asset_path = self.entry_fofa_asset_txt.get().strip()
        
        if not fofa_key:
            messagebox.showwarning("提示", "请先在上方填写您的 FOFA Key！")
            return
        if not fp_path or not os.path.isfile(fp_path):
            messagebox.showwarning("提示", "请先拖入或选择一个包含指纹语法的 TXT 文件！")
            return
            
        try: threshold = int(self.entry_min_count.get().strip())
        except: threshold = 10
        try: fofa_threads = int(self.entry_fofa_threads.get().strip())
        except: fofa_threads = 3 # 默认多线程
        
        export_folder = self.entry_export_dir.get().strip()
        if not export_folder or not os.path.isdir(export_folder):
            export_folder = os.path.join(os.getcwd(), "FOFA_自动分拣结果")
            os.makedirs(export_folder, exist_ok=True)
            self.entry_export_dir.delete(0, tk.END)
            self.entry_export_dir.insert(0, export_folder)
            self.save_app_config(silent=True) 

        self.stop_fofa_batch_flag = False
        self.btn_fofa_batch.config(state="disabled", text="批量查询中...")
        self.btn_stop_batch.config(state="normal", bg="#FF3B30", fg="white", text="⏹ 查询完当前资产停止")
        self.log(f"正在准备启动 FOFA 多线程涡轮并发引擎 (当前设置 {fofa_threads} 线程全开)...")
        
        def _task():
            try:
                with open(fp_path, 'r', encoding='utf-8', errors='ignore') as f:
                    fp_lines = [line.strip() for line in f.readlines() if line.strip()]
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"指纹TXT读取失败: {e}"))
                self.root.after(0, lambda: self.btn_fofa_batch.config(state="normal", text="🔍 FOFA指纹TXT查询"))
                self.root.after(0, lambda: self.btn_stop_batch.config(state="disabled", bg="#E5E5EA", fg="#A1A1A6", text="⏹ 查询完当前资产停止"))
                return
                
            asset_lines = []
            if asset_path and os.path.isfile(asset_path):
                try:
                    with open(asset_path, 'r', encoding='utf-8', errors='ignore') as f:
                        asset_lines = [line.strip() for line in f.readlines() if line.strip()]
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("错误", f"资产TXT读取失败: {e}"))
                    self.root.after(0, lambda: self.btn_fofa_batch.config(state="normal", text="🔍 FOFA指纹TXT查询"))
                    self.root.after(0, lambda: self.btn_stop_batch.config(state="disabled", bg="#E5E5EA", fg="#A1A1A6", text="⏹ 查询完当前资产停止"))
                    return

            all_to_del_ids = []
            file_lock = threading.Lock()

            def _process_single_asset(asset):
                if self.stop_fofa_batch_flag: return
                self.root.after(0, lambda a=asset: self.log(f"\n--- 🎯 [线程启动] 锁定资产: {a} ---"))
                
                asset_all_success = True 
                
                for fp in fp_lines:
                    if self.stop_fofa_batch_flag: break
                    self.root.after(0, lambda f=fp, a=asset: self.log(f"[{a}] 正在注入指纹: {f}"))
                    
                    if '""' in fp: query = fp.replace('""', f'"{asset}"')
                    elif '{}' in fp: query = fp.replace('{}', asset)
                    else: query = f'({fp}) && host="{asset}"'
                        
                    qbase64 = base64.b64encode(query.encode('utf-8')).decode('utf-8')
                    fields_str = "host,ip,port,country_name,title,product,icp"
                    params = {"key": fofa_key, "qbase64": qbase64, "size": size_val, "fields": fields_str}
                    url = "https://fofa.icu/api/v1/search/all"
                    
                    try:
                        r = requests.get(url, params=params, headers=HEADERS, timeout=60, verify=False)
                        data = r.json()
                        
                        if not data.get("error"):
                            res = data.get("results", [])
                            
                            if res:
                                is_under_threshold = len(res) < threshold
                                
                                def _gui_insert_async(data_list=res, under=is_under_threshold):
                                    local_inserted_ids = []
                                    for item_data in data_list:
                                        host = str(item_data[0]) if len(item_data) > 0 else ""
                                        country = str(item_data[3]) if len(item_data) > 3 else "-"
                                        title = str(item_data[4]) if len(item_data) > 4 else "-"
                                        product = str(item_data[5]) if len(item_data) > 5 else "-"
                                        icp = str(item_data[6]) if len(item_data) > 6 else "-"
                                        
                                        link = host if host.startswith("http") else "http://" + host
                                        tag = 'evenrow' if (len(self.tree.get_children()) + 1) % 2 == 0 else 'oddrow'
                                        v = ("☐", len(self.tree.get_children()) + 1, country, icp, title, link, "-", "待测", product)
                                        iid = self.tree.insert("", "end", values=v, tags=(tag,))
                                        local_inserted_ids.append(iid)
                                    self.update_range_end()
                                    if under:
                                        all_to_del_ids.extend(local_inserted_ids)
                                self.root.after(0, _gui_insert_async)
                        
                                if not is_under_threshold:
                                    safe_asset_name = re.sub(r'[\\/:*?"<>|]', '_', asset)
                                    save_path = os.path.join(export_folder, f"{safe_asset_name}.txt")
                                    with file_lock:
                                        try:
                                            with open(save_path, 'a', encoding='utf-8') as sf:
                                                sf.write(f"\n{'='*40}\n")
                                                sf.write(f"[+] 使用指纹: {fp}\n")
                                                sf.write(f"[-] 实际执行: {query}\n")
                                                sf.write(f"[-] 共查到 {len(res)} 个结果\n")
                                                sf.write(f"{'='*40}\n")
                                                for item_data in res:
                                                    host = str(item_data[0]) if len(item_data) > 0 else ""
                                                    link = host if host.startswith("http") else "http://" + host
                                                    sf.write(f"{link}\n")
                                        except Exception: pass
                                    self.root.after(0, lambda a=asset, cnt=len(res), d=export_folder: self.log(f"{a}查询完成，共{cnt}条记录，已保存到{d}"))
                                else:
                                    self.root.after(0, lambda a=asset, cnt=len(res): self.log(f"{a}查询完成，共{cnt}条记录 (未达阈值，拒绝入库)"))
                            else:
                                self.root.after(0, lambda a=asset: self.log(f"{a}查询完成，共0条记录"))

                        else:
                            err_msg = data.get("errmsg", "未知API接口错误")
                            self.root.after(0, lambda a=asset, err=err_msg: self.log(f"[{a}] 遭FOFA拦截/报错: {err}"))
                            asset_all_success = False 
                            
                    except requests.exceptions.RequestException as e:
                        self.root.after(0, lambda a=asset, err=str(e): self.log(f"[{a}] 查询请求失败: {err}"))
                        asset_all_success = False 
                    except Exception as e:
                        self.root.after(0, lambda a=asset, err=str(e): self.log(f"[{a}] 查询异常: {err}"))
                        asset_all_success = False 
                        
                    if not asset_all_success:
                        self.root.after(0, lambda a=asset: self.log(f"⚠️ [{a}] 触发异常保护，放弃剩余指纹，跳至下一资产..."))
                        break 

                if not self.stop_fofa_batch_flag:
                    if asset_all_success:
                        with file_lock:
                            try:
                                with open(asset_path, 'r', encoding='utf-8', errors='ignore') as f_read:
                                    current_lines = [l.strip() for l in f_read.readlines() if l.strip()]
                                
                                if asset in current_lines:
                                    current_lines.remove(asset)
                                    with open(asset_path, 'w', encoding='utf-8') as f_write:
                                        for cl in current_lines:
                                            f_write.write(f"{cl}\n")
                                    self.root.after(0, lambda a=asset: self.log(f"✅ 资产 {a} 探测完毕，已安全物理抹除！"))
                            except Exception:
                                pass
                    else:
                        self.root.after(0, lambda a=asset: self.log(f"⏸️ 资产 {a} 存在报错，未彻底查完，已保留在TXT中防丢失！"))

            def _process_single_fp(fp):
                if self.stop_fofa_batch_flag: return
                self.root.after(0, lambda q=fp: self.log(f"正在查询指纹: {q}"))
                
                qbase64 = base64.b64encode(fp.encode('utf-8')).decode('utf-8')
                fields_str = "host,ip,port,country_name,title,product,icp"
                params = {"key": fofa_key, "qbase64": qbase64, "size": size_val, "fields": fields_str}
                url = "https://fofa.icu/api/v1/search/all"
                
                try:
                    r = requests.get(url, params=params, headers=HEADERS, timeout=60, verify=False)
                    data = r.json()
                    
                    if not data.get("error"):
                        res = data.get("results", [])
                        
                        if res:
                            is_under_threshold = len(res) < threshold
                            def _gui_insert_async(data_list=res, under=is_under_threshold):
                                local_inserted_ids = []
                                for item_data in data_list:
                                    host = str(item_data[0]) if len(item_data) > 0 else ""
                                    country = str(item_data[3]) if len(item_data) > 3 else "-"
                                    title = str(item_data[4]) if len(item_data) > 4 else "-"
                                    product = str(item_data[5]) if len(item_data) > 5 else "-"
                                    icp = str(item_data[6]) if len(item_data) > 6 else "-"
                                    
                                    link = host if host.startswith("http") else "http://" + host
                                    tag = 'evenrow' if (len(self.tree.get_children()) + 1) % 2 == 0 else 'oddrow'
                                    v = ("☐", len(self.tree.get_children()) + 1, country, icp, title, link, "-", "待测", product)
                                    iid = self.tree.insert("", "end", values=v, tags=(tag,))
                                    local_inserted_ids.append(iid)
                                self.update_range_end()
                                if under:
                                    all_to_del_ids.extend(local_inserted_ids)
                            self.root.after(0, _gui_insert_async)
                
                            if not is_under_threshold:
                                safe_fp_name = re.sub(r'[\\/:*?"<>|]', '_', fp)[:50] 
                                save_path = os.path.join(export_folder, f"指纹查询_{safe_fp_name}.txt")
                                with file_lock:
                                    try:
                                        with open(save_path, 'a', encoding='utf-8') as sf:
                                            sf.write(f"\n{'='*40}\n")
                                            sf.write(f"[+] 查询指纹: {fp}\n")
                                            sf.write(f"[-] 共查到 {len(res)} 个结果\n")
                                            sf.write(f"{'='*40}\n")
                                            for item_data in res:
                                                host = str(item_data[0]) if len(item_data) > 0 else ""
                                                link = host if host.startswith("http") else "http://" + host
                                                sf.write(f"{link}\n")
                                    except Exception: pass
                            self.root.after(0, lambda q=fp, cnt=len(res), d=export_folder: self.log(f"{q} 查询完成，共{cnt}条记录，已保存到{d}"))
                        else:
                            self.root.after(0, lambda q=fp, cnt=len(res): self.log(f"{q} 查询完成，共{cnt}条记录 (未达阈值，拒绝入库)"))
                    else:
                        self.root.after(0, lambda q=fp: self.log(f"{q} 查询完成，共0条记录"))
                        
                except requests.exceptions.RequestException as e:
                    self.root.after(0, lambda q=fp, err=str(e): self.log(f"[{q}] 查询请求失败: {err}"))
                except Exception as e:
                    self.root.after(0, lambda q=fp, err=str(e): self.log(f"[{q}] 查询异常: {err}"))

            if asset_lines:
                self.root.after(0, lambda: self.log(f"⚡ 启动并发引擎队列 (已解除全局锁，{fofa_threads} 线程全速并发)，开始交叉探测..."))
                with concurrent.futures.ThreadPoolExecutor(max_workers=fofa_threads) as executor:
                    futures = [executor.submit(_process_single_asset, a) for a in asset_lines]
                    concurrent.futures.wait(futures) 
            else:
                self.root.after(0, lambda: self.log(f"⚡ 启动并发引擎队列 (已解除全局锁，{fofa_threads} 线程全速并发)，开始批量采集指纹！"))
                with concurrent.futures.ThreadPoolExecutor(max_workers=fofa_threads) as executor:
                    futures = [executor.submit(_process_single_fp, fp) for fp in fp_lines]
                    concurrent.futures.wait(futures)

            self.root.after(0, lambda: self.log("=" * 30))
            if self.stop_fofa_batch_flag:
                self.root.after(0, lambda: self.log("🛑 所有正在执行的资产均已处理完毕并断点保存，任务已安全终止！"))
            else:
                self.root.after(0, lambda: self.log("✅ 批量引擎任务彻底执行完毕！"))
            
            self.root.after(0, lambda: self.btn_fofa_batch.config(state="normal", text="🔍 FOFA指纹TXT查询"))
            self.root.after(0, lambda: self.btn_stop_batch.config(state="disabled", bg="#E5E5EA", fg="#A1A1A6", text="⏹ 查询完当前资产停止"))
            
            if all_to_del_ids:
                self.root.after(0, lambda: self.log(f"⚠️ 识别到存在 {len(all_to_del_ids)} 条界面记录不满足阈值({threshold})。"))
                self.root.after(1000, lambda: self.log("即将开始动态淘汰界面上的劣质资产..."))
                self.is_animating = True
                self.root.after(2000, lambda: self.animate_delete(all_to_del_ids, msg=f"已成功清理界面上的非标准资产。"))
                
        threading.Thread(target=_task, daemon=True).start()

    # ========================== 【核心重构：FOFA单点查询】 ==========================
    def start_fofa_search(self):
        key, query, size = self.entry_fofa_key.get(), self.entry_fofa_query.get(), self.entry_fofa_size.get()
        if not key or not query: return
        self.btn_fofa_search.config(state="disabled", text="检索中...")
        self.log(f"向 FOFA 请求单条语法: {query}")
        
        def _task():
            qbase64 = base64.b64encode(query.encode('utf-8')).decode('utf-8')
            fields_str = "host,ip,port,country_name,title,product,icp"
            params = {"key": key, "qbase64": qbase64, "size": size, "fields": fields_str}
            url = "https://fofa.icu/api/v1/search/all"
            
            try:
                # 【核心替换】使用 requests 绕过 TLS 指纹墙
                r = requests.get(url, params=params, headers=HEADERS, timeout=60, verify=False)
                data = r.json()
                    
                if not data.get("error"):
                    res = data.get("results", [])
                    for i, item in enumerate(res, len(self.tree.get_children())+1):
                        host = str(item[0]) if len(item) > 0 else ""
                        country = str(item[3]) if len(item) > 3 else "-"
                        title = str(item[4]) if len(item) > 4 else "-"
                        product = str(item[5]) if len(item) > 5 else "-"
                        icp = str(item[6]) if len(item) > 6 else "-"
                        
                        link = host if host.startswith("http") else "http://" + host
                        tag = 'evenrow' if i%2==0 else 'oddrow'
                        v = ("☐", i, country, icp, title, link, "-", "待测", product)
                        self.root.after(0, lambda val=v, t=tag: self.tree.insert("", "end", values=val, tags=(t,)))
                    self.log(f"成功导入 {len(res)} 条资产")
                    self.root.after(200, self.update_range_end) 
                else:
                    err_msg = data.get("errmsg", "未知接口错误")
                    self.log(f"获取失败，原因: {err_msg}")
            except Exception as e: self.log(f"请求崩溃或网络错误: {str(e)}")
            finally: self.root.after(0, lambda: self.btn_fofa_search.config(state="normal", text="🔍 开始拉取数据"))
        
        threading.Thread(target=_task, daemon=True).start()

    # ========================== 【核心重构：资产测活 (高可用穿透版)】 ==========================
    def start_health_check(self):
        items = [i for i in self.tree.get_children() if self.tree.item(i, 'values')[0] == "☑"]
        if not items:
            messagebox.showwarning("提示", "没有勾选的资产！")
            return
        
        try: threads = int(self.entry_threads.get().strip())
        except: threads = 200
        try: timeout_val = float(self.entry_timeout.get().strip())
        except: timeout_val = 3.0
        
        # 【增强】支持多状态码识别。实战中 403, 301, 302 往往也是存活的Web服务
        # 用户可以在界面输入框填 "200,403,302"
        target_codes = [c.strip() for c in self.entry_status.get().strip().replace('，', ',').split(',')]
        if not target_codes or target_codes == ['']:
            target_codes = ["200"]

        self.stop_scan = False
        self.pause_event.set()
        
        self.btn_check.config(state="disabled", text="测活中...")
        self.btn_pause.config(state="normal", text="⏸ 暂停", bg="#FF9500", fg="white")
        self.btn_stop.config(state="normal", bg="#FF3B30", fg="white")
        
        self.log(f"启动涡轮测活: 目标 {len(items)} 条 | 并发: {threads} | 超时: {timeout_val}s | 匹配状态码: {target_codes}")
        
        # 【核心】全套高匿请求头，伪装成真实 Chrome 浏览器，规避基础 WAF 和 CDN 拦截
        enh_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        def _scan():
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                for item_id in items:
                    def _proc(it=item_id):
                        if self.stop_scan: return
                        self.pause_event.wait() 
                        
                        if not self.tree.exists(it): return
                        vals = list(self.tree.item(it, 'values'))
                        url = vals[5]
                        code, length = "Error", "-"
                        
                        # 【核心】增加 1 次容错重试机制，防止高并发时短暂的网络波动导致误杀
                        max_retries = 1
                        for attempt in range(max_retries + 1):
                            try:
                                # 【核心】allow_redirects=True 允许跟随跳转，解决访问 http 强转 https 导致的误判
                                r = requests.get(url, headers=enh_headers, timeout=timeout_val, verify=False, allow_redirects=True)
                                code, length = str(r.status_code), str(len(r.content))
                                break  # 成功则跳出重试循环
                            except requests.exceptions.RequestException as e:
                                if hasattr(e, 'response') and e.response is not None: 
                                    code = str(e.response.status_code)
                                    break
                            except Exception:
                                pass
                        
                        def _gui():
                            if self.stop_scan or not self.tree.exists(it): return
                            # 如果最终状态码在用户允许的列表里，则判定存活
                            if code in target_codes:
                                vals[7], vals[6] = code, length
                                row_tag = 'evenrow' if int(vals[1])%2==0 else 'oddrow'
                                self.tree.item(it, values=vals, tags=(row_tag, 'alive'))
                            else:
                                self.tree.delete(it)
                        self.root.after(0, _gui)
                    executor.submit(_proc)
            
            self.root.after(0, self.reindex_table)
            self.root.after(0, lambda: self.btn_check.config(state="normal", text="⚡ 对【已勾选】资产极速测活"))
            self.root.after(0, lambda: self.btn_pause.config(state="disabled", bg="#E5E5EA", fg="#A1A1A6", text="⏸ 暂停"))
            self.root.after(0, lambda: self.btn_stop.config(state="disabled", bg="#E5E5EA", fg="#A1A1A6"))
            
            if not self.stop_scan:
                self.root.after(0, lambda: self.log("极速测活完成！失效死链已动态剔除。"))
                self.root.after(0, self.play_finish_sound)
                if self.var_auto_shutdown.get():
                    self.root.after(0, self.auto_save_and_shutdown)
            else:
                self.root.after(0, lambda: self.log("测活已被用户手动终止。"))
            
        threading.Thread(target=_scan, daemon=True).start()

    # ========================== 【核心重构：自动化 Payload】 ==========================
    def start_pentest_scan(self):
        enable_cors = self.var_enable_cors.get()
        fake_origin = "https://evil-cors-test.com"
        items = [i for i in self.tree.get_children() if self.tree.item(i, 'values')[0] == "☑"]
        if not items:
            messagebox.showwarning("提示", "请先在表格中勾选资产！")
            return
        
        uri = self.entry_uri.get().strip()
        base_post_data = self.entry_post.get().strip()
        
        try: threads = int(self.entry_threads.get().strip())
        except: threads = 200
        try: timeout_val = float(self.entry_timeout.get().strip())
        except: timeout_val = 3.0

        enable_token = self.var_enable_token.get()
        t_left = self.entry_token_left.get()
        t_param = self.entry_token_param.get().strip()
        t_right = self.entry_token_right.get()

        self.btn_pentest.config(state="disabled", text="探测攻击中...")
        self.log(f"--- Payload探测: 目标 {len(items)} | 并发: {threads} | 超时: {timeout_val}s ---")
        if enable_token:
            self.log(f"[*] 已开启令牌动态绕过，参数名: {t_param}")
        
        def _scan():
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                for item_id in items:
                    def _proc(it=item_id):
                        if not self.tree.exists(it): return
                        vals = list(self.tree.item(it, 'values'))
                        target = vals[5].rstrip('/') + uri
                        code, length = "Error", "-"
                        final_post_data = base_post_data

                        try:
                            # 【核心替换】二次握手 Token 提取使用 requests
                            if enable_token and t_left and t_right and t_param:
                                r_get = requests.get(target, headers={'User-Agent': 'Mozilla/5.0'}, timeout=timeout_val, verify=False)
                                html = r_get.text
                                
                                token_val = ""
                                if t_left in html:
                                    parts = html.split(t_left, 1)
                                    if len(parts) > 1 and t_right in parts[1]:
                                        token_val = parts[1].split(t_right, 1)[0]
                                
                                if token_val:
                                    encoded_token = urllib.parse.quote(token_val)
                                    if final_post_data:
                                        final_post_data += f"&{t_param}={encoded_token}"
                                    else:
                                        final_post_data = f"{t_param}={encoded_token}"
                                else:
                                    self.root.after(0, lambda t=target: self.log(f"[-] {t} 页面未匹配到左/右特征，Token提取失败"))

                            req_headers = {'User-Agent': 'Mozilla/5.0'}
                            if enable_cors:
                                req_headers['Origin'] = fake_origin 

                            # 【核心替换】Payload 发送使用 requests
                            if final_post_data:
                                req_headers['Content-Type'] = 'application/x-www-form-urlencoded'
                                r = requests.post(target, data=final_post_data, headers=req_headers, timeout=timeout_val, verify=False)
                            else:
                                r = requests.get(target, headers=req_headers, timeout=timeout_val, verify=False)
                                
                            code, length = str(r.status_code), str(len(r.content))
                            
                            if enable_cors:
                                acao = r.headers.get('Access-Control-Allow-Origin')
                                acac = r.headers.get('Access-Control-Allow-Credentials')
                                
                                if acao == fake_origin:
                                    if acac == 'true':
                                        self.root.after(0, lambda t=target: self.log(f"[!!!] 发现高危 CORS 漏洞: {t} (信任恶意Origin且允许凭证)"))
                                    else:
                                        self.root.after(0, lambda t=target: self.log(f"[!] 发现普通 CORS 缺陷: {t} (信任恶意Origin但未允许凭证)"))                                
                        except requests.exceptions.RequestException as e:
                            if hasattr(e.response, 'status_code') and e.response is not None:
                                code = str(e.response.status_code)
                        except: code = "Timeout"
                        
                        def _gui():
                            if not self.tree.exists(it): return
                            vals[7], vals[6] = code, length
                            tag = ('alive',) if code == "200" else ('dead',)
                            row_tag = 'evenrow' if int(vals[1])%2==0 else 'oddrow'
                            self.tree.item(it, values=vals, tags=(row_tag,) + tag)
                            if code == "200": self.log(f"[+] 渗透突破口: {target} (状态:{code})")
                        self.root.after(0, _gui)
                    executor.submit(_proc)
                    
            self.root.after(0, lambda: self.log("Payload 探测任务执行完毕！"))
            self.root.after(0, self.play_finish_sound)
            self.root.after(0, lambda: self.btn_pentest.config(state="normal", text="🔥 运行 Payload 极速探测"))
            
        threading.Thread(target=_scan, daemon=True).start()

    def mark_duplicates(self):
        col = self.get_target_col()
        if col is None: return
        
        count = 0
        if col == 5:
            # === 针对第6列（资产链接）的特殊清洗与查重逻辑 ===
            seen = set()
            for item in self.tree.get_children():
                vals = list(self.tree.item(item, 'values'))
                val = str(vals[col])
                
                if val not in ("-", "", "待测", "Error", "Timeout"):
                    try:
                        # 解析URL，精准剥离端口号及后续路径内容
                        parsed = urllib.parse.urlparse(val)
                        if parsed.scheme and parsed.hostname:
                            hostname = f"[{parsed.hostname}]" if ':' in parsed.hostname else parsed.hostname
                            clean_val = f"{parsed.scheme}://{hostname}"
                            vals[col] = clean_val
                            val = clean_val
                    except Exception:
                        pass
                        
                    # 查重逻辑：首次出现的保留，后续重复的打勾
                    if val in seen:
                        if vals[0] != "☑":
                            vals[0] = "☑"
                            count += 1
                    else:
                        seen.add(val)
                        
                # 将清洗结果和勾选状态更新回表格
                self.tree.item(item, values=vals)
                
            self.log(f"👯 链接查重清洗完毕：已剥离端口及后缀，并勾选 {count} 条重复链接（保留唯一根地址）。")
            
        else:
            # === 其他列的原有查重逻辑：无差别全部勾选 ===
            val_counts = {}
            for item in self.tree.get_children():
                val = str(self.tree.item(item, 'values')[col])
                if val in ("-", "", "待测", "Error", "Timeout"):
                    continue
                val_counts[val] = val_counts.get(val, 0) + 1
                
            for item in self.tree.get_children():
                vals = list(self.tree.item(item, 'values'))
                val = str(vals[col])
                if val in val_counts and val_counts[val] > 1:
                    if vals[0] != "☑":
                        vals[0] = "☑"
                        self.tree.item(item, values=vals)
                        count += 1
                        
            self.log(f"👯 目标列查重完毕：已无差别勾选 {count} 条存在重复的数据。")


# ========================== 工作室一机一码验证锁 ==========================
class AuthWindow:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.machine_id = get_machine_id()
        
        self.auth_root = tk.Toplevel(root)
        self.auth_root.title("安全验证 - 工作室内部工具")
        self.auth_root.geometry("420x280")
        self.auth_root.configure(bg="#F5F5F7")
        self.auth_root.resizable(False, False)
        
        self.auth_root.update_idletasks()
        x = (self.auth_root.winfo_screenwidth() // 2) - (420 // 2)
        y = (self.auth_root.winfo_screenheight() // 2) - (280 // 2)
        self.auth_root.geometry(f'+{x}+{y}')
        
        self.auth_root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        tk.Label(self.auth_root, text="simple", font=("Microsoft YaHei", 14, "bold"), bg="#F5F5F7", fg="#1C1C1E").pack(pady=(20, 5))
        tk.Label(self.auth_root, text="首次运行需要进行设备绑定，请联系管理员获取激活码", font=("Microsoft YaHei", 9), bg="#F5F5F7", fg="#8E8E93").pack(pady=(0, 15))
        
        f1 = tk.Frame(self.auth_root, bg="#F5F5F7")
        f1.pack(fill=tk.X, padx=40, pady=5)
        tk.Label(f1, text="您的专属机器码：", font=("Microsoft YaHei", 9, "bold"), bg="#F5F5F7").pack(anchor="w")
        
        f1_sub = tk.Frame(f1, bg="#F5F5F7")
        f1_sub.pack(fill=tk.X)
        self.entry_mid = tk.Entry(f1_sub, font=("Consolas", 11, "bold"), fg="#FF3B30", bg="#E5E5EA", bd=0, justify="center")
        self.entry_mid.insert(0, self.machine_id)
        self.entry_mid.config(state="readonly")
        self.entry_mid.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        tk.Button(f1_sub, text="复制", bg="#D1D1D6", bd=0, command=self.copy_mid).pack(side=tk.LEFT, padx=(5,0), ipady=2)

        f2 = tk.Frame(self.auth_root, bg="#F5F5F7")
        f2.pack(fill=tk.X, padx=40, pady=10)
        tk.Label(f2, text="请输入激活密钥：", font=("Microsoft YaHei", 9, "bold"), bg="#F5F5F7").pack(anchor="w")
        self.entry_key = tk.Entry(f2, font=("Consolas", 11), justify="center", bd=0, highlightthickness=1, highlightbackground="#D1D1D6")
        self.entry_key.pack(fill=tk.X, ipady=4)
        self.entry_key.bind('<Return>', lambda e: self.verify_key())
        
        tk.Button(self.auth_root, text="🔓 验证并永久绑定本设备", font=("Microsoft YaHei", 10, "bold"), bg="#007AFF", fg="white", bd=0, width=25, pady=6, command=self.verify_key).pack(pady=5)
        self.entry_key.focus_set()

    def copy_mid(self):
        self.auth_root.clipboard_clear()
        self.auth_root.clipboard_append(self.machine_id)
        messagebox.showinfo("复制成功", "机器码已复制，请发给管理员索要激活码！", parent=self.auth_root)

    def verify_key(self):
        user_input = re.sub(r'[^A-Z0-9]', '', self.entry_key.get().strip().upper())
        expected_key = get_expected_key(self.machine_id)
        
        if user_input == expected_key:
            self.config["auth_key"] = user_input
            save_global_config(self.config)
            messagebox.showinfo("激活成功", "设备绑定成功！欢迎使用simple工具。", parent=self.auth_root)
            self.auth_root.destroy()
            if HAS_DND:
                self.root.deiconify() 
                app = LinkOpenerApp(self.root, self.config)
            else:
                self.root.deiconify()
                app = LinkOpenerApp(self.root, self.config)
        else:
            messagebox.showerror("验证失败", "激活密钥错误或不匹配本机！\n未经授权禁止使用本工作室工具。", parent=self.auth_root)
            self.entry_key.delete(0, tk.END)

    def on_close(self):
        self.root.destroy()

# ========================== 程序入口 ==========================
if __name__ == "__main__":
    global_config = load_global_config()
    current_machine_id = get_machine_id()
    expected_key = get_expected_key(current_machine_id)
    
    if HAS_DND:
        main_root = TkinterDnD.Tk()
    else:
        main_root = tk.Tk()
        
    main_root.withdraw() 
    
    if global_config.get("auth_key") == expected_key:
        main_root.deiconify()
        app = LinkOpenerApp(main_root, global_config)
    else:
        auth_app = AuthWindow(main_root, global_config)
        
    main_root.mainloop()
