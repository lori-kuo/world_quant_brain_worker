import os
import json
import base64
import tkinter as tk
from tkinter import scrolledtext, messagebox, Toplevel
from PIL import Image, ImageTk, ImageGrab
from openai import OpenAI
import threading
import io
import time
import ctypes
import subprocess
import sys

# --- Auto-Install Dependencies ---
def install_dependencies():
    import importlib.util
    import importlib.metadata

    # Mapping of package names to their import names (if different)
    packages = {
        "openai": "openai",
        "Pillow": "PIL",
        "fastembed": "fastembed",
        "chromadb": "chromadb",
        "watchdog": "watchdog",
        "pypdf": "pypdf",
        "python-docx": "docx"
    }
    
    missing = []
    for pkg_name, import_name in packages.items():
        if importlib.util.find_spec(import_name) is None:
            missing.append(pkg_name)
    
    if missing:
        print(f"Missing dependencies: {missing}. Installing...")
        # Try Tsinghua source first
        tsinghua_url = "https://pypi.tuna.tsinghua.edu.cn/simple"
        try:
            print(f"Attempting to install via Tsinghua mirror: {tsinghua_url}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "-i", tsinghua_url])
            print("Dependencies installed successfully via Tsinghua.")
        except Exception as e:
            print(f"Tsinghua mirror failed, falling back to default source: {e}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
                print("Dependencies installed successfully via default source.")
            except Exception as e2:
                print(f"Failed to install dependencies: {e2}")
                messagebox.showwarning("Warning", f"Failed to auto-install some dependencies: {e2}\nPlease run 'pip install -r requirements.txt' manually.")

# Run install check before other imports that might fail
install_dependencies()

# Now import our custom RAG engine
try:
    from rag_engine import KnowledgeBase
except ImportError:
    KnowledgeBase = None
    print("KnowledgeBase module not found or dependencies missing.")

# Set DPI Awareness (Windows) to ensure high-resolution screenshots
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Load Configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
ICON_PATH = os.path.join(os.path.dirname(__file__), 'icon.png')

def load_config():
    if not os.path.exists(CONFIG_PATH):
        messagebox.showerror("Error", "Config file not found!")
        return None
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = load_config()

class BrainConsultantApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BRAIN Consultant Assistant")
        
        # Floating Icon Setup
        self.root.overrideredirect(True)  # Frameless
        self.root.attributes("-topmost", True)  # Always on top
        self.root.geometry("64x64+100+100")  # Small size, initial position
        
        # Transparency setup (Windows only hack)
        transparent_color = '#ff00ff'
        self.root.configure(bg=transparent_color)
        self.root.wm_attributes("-transparentcolor", transparent_color)

        # Load Icon
        self.icon_image = None
        if os.path.exists(ICON_PATH):
            try:
                # Force RGBA to ensure we can handle transparency
                img = Image.open(ICON_PATH).convert("RGBA")
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                
                # Fix for halo effect: Strict binary alpha
                # Any pixel that is not fully opaque becomes fully transparent
                # This removes the semi-transparent edges that blend with the background color
                datas = img.getdata()
                new_data = []
                for item in datas:
                    if item[3] < 200:  # Threshold: if alpha < 200, make it transparent
                        new_data.append((0, 0, 0, 0))
                    else:
                        # Keep original color, force full opacity
                        new_data.append((item[0], item[1], item[2], 255))
                img.putdata(new_data)

                self.icon_image = ImageTk.PhotoImage(img)
                # Set window icon if possible (though frameless windows don't show it usually)
                self.root.iconphoto(False, self.icon_image)
            except Exception as e:
                print(f"Failed to load icon: {e}")
        
        # Create a label as the button
        self.icon_label = tk.Label(root, image=self.icon_image, bg=transparent_color, cursor="hand2")
        if not self.icon_image:
            self.icon_label.config(text="BRAIN", fg="white", font=("Arial", 10, "bold"))
        self.icon_label.pack(fill=tk.BOTH, expand=True)

        # Bind events
        self.icon_label.bind("<Button-3>", self.show_context_menu) # Right click menu
        self.icon_label.bind("<ButtonPress-1>", self.start_move)
        self.icon_label.bind("<ButtonRelease-1>", self.stop_move)
        self.icon_label.bind("<B1-Motion>", self.do_move)

        # Initialize OpenAI Client
        self.client = OpenAI(
            api_key=CONFIG['api_key'],
            base_url=CONFIG['base_url']
        )
        self.model = CONFIG['model']
        self.system_prompt = CONFIG.get('system_prompt', "You are a helpful assistant.")

        # Initialize Knowledge Base
        self.kb = None
        if KnowledgeBase:
            try:
                self.kb = KnowledgeBase()
            except Exception as e:
                print(f"Failed to initialize Knowledge Base: {e}")

        self.knowledge_dir = os.path.join(os.path.dirname(__file__), "knowledge")

        # Last KB retrieval (for UI display)
        self.last_kb_query = ""
        self.last_kb_context = ""
        self.last_kb_hits = []

        self.current_screenshot = None
        self.chat_window = None
        self.history = [{"role": "system", "content": self.system_prompt}]
        
        # Dragging state
        self.x = 0
        self.y = 0
        self.dragging = False

    def start_move(self, event):
        self.x = event.x
        self.y = event.y
        self.dragging = False # Initialize as false, set to true if moved

    def stop_move(self, event):
        if not self.dragging:
            self.start_snip()
        self.dragging = False

    def do_move(self, event):
        self.dragging = True
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def show_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="💬 Chat Only", command=self.open_chat_window)
        menu.add_separator()
        menu.add_command(label="❌ Exit", command=self.root.quit)
        menu.post(event.x_root, event.y_root)

    def start_snip(self):
        """Hides the window and takes a screenshot after a short delay."""
        self.root.withdraw()  # Hide main window
        if self.chat_window and tk.Toplevel.winfo_exists(self.chat_window):
            self.chat_window.withdraw()
        self.root.after(500, self.take_screenshot)

    def take_screenshot(self):
        """Captures the full screen."""
        try:
            # Capture full screen
            screenshot = ImageGrab.grab()
            self.current_screenshot = screenshot
            
            # Show the chat window with the screenshot
            self.open_chat_window(with_screenshot=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to take screenshot: {e}")
            self.root.deiconify()

    def open_chat_window(self, with_screenshot=False):
        """Opens the chat interface."""
        if self.chat_window is None or not tk.Toplevel.winfo_exists(self.chat_window):
            self.chat_window = Toplevel(self.root)
            self.chat_window.title("BRAIN Consultant Assistant - Chat")
            self.chat_window.geometry("600x700")
            self.chat_window.configure(bg="#1e1e1e") # Dark background
            self.chat_window.attributes("-topmost", True)  # Always on top
            self.chat_window.protocol("WM_DELETE_WINDOW", self.on_chat_close)
            
            if self.icon_image:
                self.chat_window.iconphoto(False, self.icon_image)

            # --- Layout Strategy: Pack Bottom-Up ---
            
            # 1. Input Area (Bottom)
            input_frame = tk.Frame(self.chat_window, bg="#1e1e1e")
            input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

            # Button Frame
            btn_frame = tk.Frame(input_frame, bg="#1e1e1e")
            btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

            # Buttons aligned to the right (visual order left→right): Open KB, KB hits, Resnip, Send
            send_btn = tk.Button(
                btn_frame, 
                text="提问", 
                command=self.send_message,
                bg="#007acc", 
                fg="white", 
                font=("Segoe UI", 10, "bold"),
                relief=tk.FLAT,
                padx=15
            )
            send_btn.pack(side=tk.RIGHT, padx=5)

            continue_snip_btn = tk.Button(
                btn_frame, 
                text="📸 重新截屏", 
                command=self.start_snip,
                bg="#3c3c3c", 
                fg="white", 
                font=("Segoe UI", 10),
                relief=tk.FLAT,
                padx=10
            )
            continue_snip_btn.pack(side=tk.RIGHT, padx=5)

            self.kb_hits_btn = tk.Button(
                btn_frame,
                text="📚 命中内容",
                command=self.show_kb_hits,
                bg="#3c3c3c",
                fg="white",
                font=("Segoe UI", 10),
                relief=tk.FLAT,
                padx=10,
                state=tk.DISABLED
            )
            self.kb_hits_btn.pack(side=tk.RIGHT, padx=5)

            open_kb_btn = tk.Button(
                btn_frame,
                text="📂 打开知识库",
                command=self.open_knowledge_folder,
                bg="#3c3c3c",
                fg="white",
                font=("Segoe UI", 10),
                relief=tk.FLAT,
                padx=10
            )
            open_kb_btn.pack(side=tk.RIGHT, padx=5)

            # Text Entry (Multi-line, Full Width)
            self.msg_entry = tk.Text(
                input_frame, 
                height=4, # Slightly taller
                font=("Consolas", 11), 
                bg="#3c3c3c", 
                fg="white", 
                insertbackground="white",
                relief=tk.FLAT,
                padx=5,
                pady=5
            )
            self.msg_entry.pack(side=tk.BOTTOM, fill=tk.X)
            self.msg_entry.bind("<Return>", self.handle_return)
            self.msg_entry.bind("<Shift-Return>", lambda e: None)

            # 2. Screenshot Preview (Above Input)
            self.image_label = tk.Label(self.chat_window, bg="#1e1e1e")
            self.image_label.pack(side=tk.BOTTOM, pady=5)

            # 3. Chat History (Top, fills remaining space)
            chat_frame = tk.Frame(self.chat_window, bg="#252526")
            chat_frame.pack(side=tk.TOP, expand=True, fill='both', padx=10, pady=10)

            # Chat History Display (High-tech style)
            self.chat_display = tk.Text(
                chat_frame, 
                state='disabled', 
                wrap=tk.WORD,
                bg="#252526", 
                fg="#d4d4d4",
                font=("Consolas", 10),
                insertbackground="white",
                relief=tk.FLAT,
                padx=10,
                pady=10
            )
            self.chat_display.pack(side=tk.LEFT, expand=True, fill='both')

            self.chat_display.tag_config("user", foreground="#569cd6", font=("Consolas", 10, "bold")) # Blue
            self.chat_display.tag_config("assistant", foreground="#4ec9b0", font=("Consolas", 10)) # Teal
            self.chat_display.tag_config("system", foreground="#6a9955", font=("Consolas", 9, "italic")) # Green

            # Reset KB hit state for this window
            self.last_kb_query = ""
            self.last_kb_context = ""
            if hasattr(self, "kb_hits_btn"):
                self.kb_hits_btn.config(state=tk.DISABLED)



        # If we just took a screenshot, display it
        if with_screenshot and self.current_screenshot:
            # Resize for preview
            preview_img = self.current_screenshot.copy()
            preview_img.thumbnail((500, 250))
            self.photo = ImageTk.PhotoImage(preview_img)
            self.image_label.config(image=self.photo)
            self.image_label.image = self.photo
            self.append_to_chat("System", "已截屏,顾问助手已准备好帮助您进行Alpha研究", "system")
            
            # Auto-trigger analysis if user wants (optional, but "提问屏幕内容" implies user action)
            # For now, we wait for user input or they can just click send with empty text to trigger analysis?
            # Let's allow empty text to trigger "Analyze this"
            
        elif not with_screenshot:
            self.image_label.config(image='')
            self.current_screenshot = None

        self.chat_window.deiconify()
        self.root.withdraw() # Keep main window hidden while chatting

    def on_chat_close(self):
        self.chat_window.destroy()
        self.chat_window = None
        self.current_screenshot = None
        self.root.deiconify() # Show main window again

    def append_to_chat(self, role, text, tag):
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, f"[{role}]: {text}\n\n", tag)
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')

    def handle_return(self, event):
        # If Shift is pressed, let default behavior happen (newline)
        if event.state & 0x0001: 
            return None
        # Otherwise send message
        self.send_message()
        return "break" # Prevent default newline

    def send_message(self, event=None):
        user_text = self.msg_entry.get("1.0", tk.END).strip()
        user_typed_text = bool(user_text)
        
        # Allow sending if there is a screenshot, even if text is empty (implies "Analyze this")
        if not user_text and not self.current_screenshot:
            return
            
        if not user_text and self.current_screenshot:
            user_text = "Please analyze this screenshot and guide me on the next steps."

        # --- RAG: Query Knowledge Base ---
        context = ""
        hit_details = []
        used_kb = False
        if self.kb and user_typed_text:
            try:
                res = self.kb.query(user_text)
                used_kb = bool(res.get("hit"))
                context = res.get("context", "") if used_kb else ""
                hit_details = res.get("hits", []) or []
            except Exception as e:
                print(f"KB query failed: {e}")
                used_kb = False
                context = ""
                hit_details = []

        # Save last KB retrieval and toggle button
        self.last_kb_query = user_text
        self.last_kb_context = context or ""
        self.last_kb_hits = hit_details
        if hasattr(self, "kb_hits_btn"):
            self.kb_hits_btn.config(state=(tk.NORMAL if used_kb and context else tk.DISABLED))

        # Show user message first
        self.msg_entry.delete("1.0", tk.END)
        self.append_to_chat("User", user_text, "user")

        # Let user know whether KB was used (only when user actually typed text)
        if user_typed_text:
            if self.kb:
                if used_kb:
                    self.append_to_chat("System", "已检索本地知识库：命中相关内容，将结合回答。", "system")
                else:
                    self.append_to_chat("System", "已检索本地知识库：未命中，将直接基于模型回答。", "system")
            else:
                self.append_to_chat("System", "本地知识库未启用（依赖缺失或初始化失败），将直接基于模型回答。", "system")
        
        # Augment user text with context if available
        api_user_text = user_text
        if context:
            api_user_text = f"【参考本地知识库内容】:\n{context}\n\n【用户问题】:\n{user_text}"

        # Prepare messages for API
        messages = list(self.history) # Copy existing history
        
        new_message = {"role": "user", "content": []}
        
        # Add text (using the augmented text for the API, but showing original in UI)
        if api_user_text:
            new_message["content"].append({"type": "text", "text": api_user_text})

        # Add image if it's the FIRST message about this screenshot
        if self.current_screenshot:
            base64_image = self.encode_image(self.current_screenshot)
            new_message["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
            self.current_screenshot = None 
            self.image_label.config(image='') # Hide preview after sending

        # Simplify content if just text
        if len(new_message["content"]) == 1 and new_message["content"][0]["type"] == "text":
             new_message["content"] = api_user_text

        messages.append(new_message)
        
        # Start thread for API call
        threading.Thread(target=self.run_api_call, args=(messages,)).start()

    def open_knowledge_folder(self):
        target_dir = self.knowledge_dir or os.path.join(os.path.dirname(__file__), "knowledge")
        if not os.path.exists(target_dir):
            messagebox.showinfo("知识库", "知识库文件夹不存在。")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(target_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target_dir])
            else:
                subprocess.Popen(["xdg-open", target_dir])
        except Exception as e:
            messagebox.showerror("知识库", f"无法打开知识库文件夹：{e}")

    def show_kb_hits(self):
        """Show the last retrieved KB context in a separate window."""
        if not self.kb:
            messagebox.showinfo("知识库", "本地知识库未启用或初始化失败。")
            return
        if not getattr(self, "last_kb_context", ""):
            messagebox.showinfo("知识库", "本次提问未命中知识库内容。")
            return

        win = Toplevel(self.chat_window if self.chat_window else self.root)
        win.title("知识库命中内容")
        win.geometry("700x500")
        win.configure(bg="#1e1e1e")
        win.attributes("-topmost", True)
        if self.icon_image:
            win.iconphoto(False, self.icon_image)

        header = tk.Label(
            win,
            text=f"查询：{self.last_kb_query}",
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            justify="left",
            padx=10,
            pady=10
        )
        header.pack(side=tk.TOP, fill=tk.X)

        text_box = scrolledtext.ScrolledText(
            win,
            wrap=tk.WORD,
            bg="#252526",
            fg="#d4d4d4",
            insertbackground="white",
            font=("Consolas", 10)
        )
        text_box.pack(side=tk.TOP, expand=True, fill="both", padx=10, pady=(0, 10))

        # Prefer structured hits if available (shows source + score)
        hits = getattr(self, "last_kb_hits", None) or []
        if hits:
            lines = []
            for i, h in enumerate(hits, start=1):
                src = h.get("source", "")
                dist = h.get("distance", None)
                dist_str = f"{dist:.4f}" if isinstance(dist, (int, float)) else "N/A"
                lines.append(f"--- Hit {i} | source={src} | distance={dist_str} ---\n")
                lines.append((h.get("text") or "") + "\n\n")
            text_box.insert(tk.END, "".join(lines).strip())
        else:
            text_box.insert(tk.END, self.last_kb_context)
        text_box.config(state='disabled')

    def run_api_call(self, messages):
        try:
            # Create an empty message for the assistant first
            self.root.after(0, self.append_to_chat, "顾问助手", "", "assistant")
            
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.6,
                stream=True
            )
            
            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    # Update UI with the new chunk
                    self.root.after(0, self.update_last_message, content)
            
            # Update history with full response
            self.history.append(messages[-1]) # User msg
            self.history.append({"role": "assistant", "content": full_response})

        except Exception as e:
            error_msg = str(e)
            self.root.after(0, self.append_to_chat, "Error", error_msg, "system")

    def update_last_message(self, text_chunk):
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, text_chunk, "assistant")
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')

    def encode_image(self, image):
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

if __name__ == "__main__":
    root = tk.Tk()
    app = BrainConsultantApp(root)
    root.mainloop()
