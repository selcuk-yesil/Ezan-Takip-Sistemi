"""
Masaüstü Ezan Vakti Takip ve Hatırlatıcı
Python ile geliştirilmiş, sistem tepsisi entegrasyonlu bildirim uygulaması.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import threading
import time
import requests
import urllib3
import os
import json
from plyer import notification 
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import ctypes 

# --- GELİŞTİRİCİ AYARLARI ---
SEHIR = "Konya"
ULKE = "Turkey"
API_METODU = 13 # Diyanet İşleri Başkanlığı Metodu
API_URL = f"https://api.aladhan.com/v1/timingsByCity?city={SEHIR}&country={ULKE}&method={API_METODU}"

# SSL uyarılarını kapat (Bağlantı kararlılığı için)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- HIZLI EMOJİ SEÇİMİ ---
EMOJILER = {
    "🎮": ["oyun"], "🏋️": ["spor"], "💻": ["kod"], "📚": ["kitap"], 
    "🍽️": ["yemek"], "☕": ["mola"], "😴": ["uyku"], "🚗": ["araba"], 
    "🦇": ["yarasa"], "🔥": ["ateş"], "✨": ["yıldız"], "✅": ["onay"],
    "💪": ["güç"], "🚀": ["hız"], "⚡": ["enerji"], "💧": ["su"]
}

VERI_DOSYASI = "programlar.json"
calisiyor = True
guncel_vakitler = None

def verileri_yukle():
    if os.path.exists(VERI_DOSYASI):
        try:
            with open(VERI_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {"19:34": "Oyun Bitiş 🎮"}

def verileri_kaydet(data):
    with open(VERI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class AsistanUygulaması:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True) # Kenarlıkları kaldır
        self.root.attributes("-topmost", True, "-alpha", 0.95)
        self.root.geometry("340x320+1540+660") 
        
        self.karanlik_mod_uygula()
        self.root.configure(bg="#0F0F0F", highlightthickness=1, highlightbackground="#000000")
        
        self.hatirlaticilar = verileri_yukle()

        # Arayüz Stili
        stil = ttk.Style()
        stil.theme_use('clam')
        stil.configure("TNotebook", background="#0F0F0F", borderwidth=0, highlightthickness=0)
        stil.configure("TNotebook.Tab", background="#1A1A1A", foreground="#AAAAAA", padding=[10, 2], font=("Segoe UI", 9))
        stil.map("TNotebook.Tab", background=[("selected", "#00FFCC")], foreground=[("selected", "#000000")], font=[("selected", ("Segoe UI", 11, "bold"))])

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True)
        self.nb.bind("<<NotebookTabChanged>>", self.sekme_degisti)
        
        self.tab1 = tk.Frame(self.nb, bg="#121212", highlightthickness=0, bd=0)
        self.tab2 = tk.Frame(self.nb, bg="#121212", highlightthickness=0, bd=0)
        self.nb.add(self.tab1, text=" KAÇ DAKİKA? ")
        self.nb.add(self.tab2, text=" PROGRAMLARIM ")

        self.canli_gorunum_kur()
        self.program_gorunumu_kur()

        # Çıkış Butonu
        tk.Button(self.root, text="✕", command=self.pencereyi_gizle, bg="#0F0F0F", fg="#666", bd=0, activebackground="#0F0F0F").place(x=315, y=2)
        
        # Sürükleme Bağlantıları
        for widget in [self.root, self.tab1, self.tab2, self.nb]:
            widget.bind("<Button-1>", self.tiklama_olayi)
            widget.bind("<B1-Motion>", self.surukleme_olayi)

        self.ana_dongu()

    def karanlik_mod_uygula(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            karanlik = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(karanlik), ctypes.sizeof(karanlik))
        except: pass

    def sekme_degisti(self, event):
        if hasattr(self, 'emoji_penceresi'): 
            if self.emoji_penceresi.winfo_viewable():
                self.emoji_penceresi.pack_forget()

    def canli_gorunum_kur(self):
        tk.Label(self.tab1, text=f"{SEHIR.upper()} / {ULKE.upper()}", fg="#00FFCC", bg="#121212", font=("Segoe UI", 10, "bold")).pack(pady=10)
        self.lbl_vakit_ad = tk.Label(self.tab1, text="...", fg="#888", bg="#121212", font=("Segoe UI", 9))
        self.lbl_vakit_ad.pack()
        self.lbl_sayac = tk.Label(self.tab1, text="00:00:00", fg="#FFFFFF", bg="#121212", font=("Segoe UI Semibold", 32))
        self.lbl_sayac.pack(expand=True, pady=10)

    def program_gorunumu_kur(self):
        self.ust_cerceve = tk.Frame(self.tab2, bg="#121212")
        self.ust_cerceve.pack(pady=5, padx=5, fill="x")

        ayar = {"bg": "#1E1E1E", "fg": "#00FFCC", "bd": 0, "width": 3, "font": ("Segoe UI", 11, "bold"), "wrap": True}
        self.sp_saat = tk.Spinbox(self.ust_cerceve, from_=0, to=23, format="%02.0f", **ayar)
        self.sp_saat.pack(side="left", padx=1)
        self.sp_dakika = tk.Spinbox(self.ust_cerceve, from_=