import os
import json
from gtts import gTTS
import pygame
import time
import customtkinter as ctk
from tkinter import messagebox
from deep_translator import GoogleTranslator
import speech_recognition as sr
from PIL import Image
import cv2
import threading
import requests
import re
# from difflib import get_close_matches
import winsound
import datetime
import subprocess
# import psutil
import sys
import urllib.request
from dotenv import load_dotenv
import traceback
import atexit
import hashlib

# Load environment variables from .env file at the specified path
load_dotenv(dotenv_path=r"C:\\Users\\admin\\Desktop\\Sangrur Court\\src_02\\.env")


# #######################################################################################################
class APIClient:
    BASE_URL = "http://192.168.1.81:8000/search"

    def __init__(self):
        self.session = requests.Session()

    def post(self, endpoint: str, params: dict):
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self.session.post(
                url,
                headers={
                    "accept": "application/json",
                    "Content-Type": "application/json"
                },
                json=params,
                timeout=10
            )
            response_data = response.json()
            return {"status": response.status_code, "data": response_data}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        
    # ================================== Health Check ===================================================
    def check_backend(self) -> bool:
        """Check if the backend server is running and healthy."""
        try:
            health_url = self.BASE_URL.replace("/search", "/health") 
            response = self.session.get(health_url, timeout=5)
            if response.status_code == 200:
                print(f"[INFO] Backend is healthy at {health_url}")
                return True
            else:
                print(f"[ERROR] Backend returned status {response.status_code} at {health_url}")
                return False
        except Exception as e:
            print(f"[ERROR] Backend is not accessible.")
            return False
    
    # =============================== Get API responsee =================================================
    @staticmethod
    def api_response(response) -> str:
        output = []

        if response.get("status") != 200:
            output.append(f"[ERROR] Request failed. Status: {response.get('status')}")
            if "error" in response:
                output.append(f"[DETAIL] {response['error']}")
            return "\n".join(output)

        data = response["data"]
        if isinstance(data, list):
            for i, item in enumerate(data, start=1):
                output.append(f"\n========== Case {i} Details ==========")
                for key, value in item.items():
                    formatted_key = key.replace("_", " ").title()
                    output.append(f"{formatted_key}: {value}")
        else:
            output.append("\n========== Case Details ==========")
            for key, value in data.items():
                formatted_key = key.replace("_", " ").title()
                output.append(f"{formatted_key}: {value}")

        return "\n".join(output)
    
# #######################################################################################################


# #######################################################################################################
class HighCourt:
    # =========================================== Constructore ==========================================
    def __init__(self, root):
        # Load paths from environment variables
        self.start_sound = os.getenv("START_SOUND_PATH", "C:\\Windows\\Media\\chimes.wav")
        self.end_sound = os.getenv("END_SOUND_PATH", "C:\\Windows\\Media\\notify.wav")
        self.image_folder = os.getenv("IMAGE_FOLDER_PATH")
        self.auth_json_path = os.getenv("AUTH_JSON_PATH")

        self.client = APIClient()
        self.root = root
        self.root.attributes("-fullscreen", True)
        self.root.title("Court Case Information System")

        try:
            self.root.report_callback_exception = self._tk_report_callback_exception
        except Exception:
            pass

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # low-latency mixer setup
        try:
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
        except Exception:
            pass
        pygame.mixer.init()

        # Initialize caches for speed
        self._translators = {}
        self._translate_cache = {}
        self._tts_cache_dir = os.path.join(os.getcwd(), ".tts_cache")
        try:
            os.makedirs(self._tts_cache_dir, exist_ok=True)
        except Exception:
            pass

        # Initialize the reset_timer before any other method calls
        self.reset_timer = None

        # Load authentication data
        self._load_auth_data()

        # Reset flags after inactivity
        self.reset_flags_after_inactivity(timer=90.0)

        # Flags
        self.camera_pause = False
        self.speak_pause = False
        self.conversation_pause = False
        self.listen_pause = False

        self.chrome_process = None
        self.button_key = None
        self.button_value = None
        self.button_input = False

        self.stop_system = False

        # Create main frame
        self.main_frame = ctk.CTkFrame(root, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True)

        # Add heading above the title
        self.heading_label = ctk.CTkLabel(
            self.main_frame,
            text="ਸੈਸ਼ਨ ਕੋਰਟ ਕੇਸ ਪ੍ਰਬੰਧਨ",
            font=ctk.CTkFont(size=42, weight="bold"),
            text_color="blue",  # Blue color
        )
        self.heading_label.pack(fill="x", pady=10)

        # Face detection variables
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.cap = None
        self.is_camera_running = False
        self.detection_thread = None
        self.face_detected = False
        self.face_detection_cooldown = False
        
        # Create frame for camera feed
        self.image_frame = ctk.CTkFrame(
            self.main_frame,
            width=950,
            height=500,
            fg_color="transparent",
            border_width=3,
            border_color="black",
            corner_radius=10,
        )
        self.image_frame.pack(padx=10, pady=10)
        
        # Create label for camera feed
        self.image_label = ctk.CTkLabel(self.image_frame, text="", width=940, height=490)
        self.image_label.pack(padx=5, pady=5)

        # keep a strong ref to the current CTkImage to prevent GC issues
        self._current_ctk_frame_image = None
        
        self.start_camera()

        # Label for the text input box
        self.text_input_label = ctk.CTkLabel(self.main_frame, 
                                            text="ਖੋਜ", 
                                            font=ctk.CTkFont(size=32, weight="bold"))
        self.text_input_label.pack(padx=10, pady=10)

        # ------------- Create a frame to hold the manual input button and mic button ---------------
        self.input_frame = ctk.CTkFrame(self.main_frame, 
                                        width=900, 
                                        height=150,
                                        fg_color="transparent"
                                        )
        self.input_frame.pack(padx=20, pady=10)
        
        # Load microphone image once
        self.mic_image = self._load_image(os.path.join(self.image_folder, "mic2.png"), (100, 100))
        self.mic_button = ctk.CTkButton(
            self.input_frame,
            command=self._face_button_conversation,
            font=ctk.CTkFont(size=42, weight="bold"),
            fg_color="pink",
            text_color="red",
            height=140,
            width=400,
            border_width=2,
            border_color="black",
            corner_radius=30,
            image=self.mic_image,
            text="Mic Input"
        )
        self.mic_button.pack(side="left", padx=(25, 20), pady=10)

        # Load Manual Input image once
        self.manual_image = self._load_image(os.path.join(self.image_folder, "hand.png"), (100, 100))
        self.manual_button = ctk.CTkButton(
            self.input_frame,
            command=self._manual_conversation,
            font=ctk.CTkFont(size=42, weight="bold"),
            fg_color="pink",
            text_color="red",
            height=140,
            width=400,
            border_width=2,
            border_color="black",
            corner_radius=30,
            image=self.manual_image,
            text="Manual Input"
        )
        self.manual_button.pack(side="right", padx=(25, 20), pady=10)

        # ------------------- Create a frame to hold the text input ---------------------
        self.input_frame = ctk.CTkFrame(self.main_frame, 
                                        width=920, 
                                        height=120,
                                        fg_color="transparent",
                                        border_width=2,
                                        border_color="black",
                                        corner_radius=40)
        self.input_frame.pack(padx=10, pady=20)

        # Text input box
        self.text_input = ctk.CTkEntry(self.input_frame, 
                                    font=ctk.CTkFont(size=26, weight="bold"), 
                                    width=860, 
                                    height=100,
                                    fg_color="transparent", 
                                    placeholder_text="Search for your case details",
                                    border_width=0)
        self.text_input.pack(padx=10, pady=10)

        # --------------- Buttons for speaking in different languages --------------------
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(padx=10, pady=10)

        self.english_button = ctk.CTkButton(
            self.button_frame,
            text="Speak English",
            command=lambda: self._face_button_conversation(lang="en", input_from_button=True),
            font=ctk.CTkFont(size=32, weight="bold"),
            fg_color="#573AC0",
            text_color="white",
            height=100,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=30
        )
        self.english_button.pack(side="left", padx=30, pady=10)

        self.hindi_button = ctk.CTkButton(
            self.button_frame,
            text="हिंदी बोलें",
            command=lambda: self._face_button_conversation(lang="hi", input_from_button=True),
            font=ctk.CTkFont(size=32, weight="bold"),
            fg_color="#573AC0",
            text_color="white",
            height=100,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=30
        )
        self.hindi_button.pack(side="left", padx=30, pady=10)

        self.punjabi_button = ctk.CTkButton(
            self.button_frame,
            text="ਹਿੰਦੀ ਬੋਲੋ",
            command=lambda: self._face_button_conversation(lang="pa", input_from_button=True),
            font=ctk.CTkFont(size=32, weight="bold"),
            fg_color="#573AC0",
            text_color="white",
            height=100,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=30
        )
        self.punjabi_button.pack(side="left", padx=30, pady=10)
        
        # Create a frame for subtitle to act as a solid border
        self.subtitle_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color="white",
            width=940,
            height=480,
            border_width=2,
            border_color="white",
            corner_radius=10
        )
        self.subtitle_frame.pack(pady=20, padx=20)

        # Create a label inside the frame
        self.subtitle_label = ctk.CTkLabel(
            self.subtitle_frame,
            text="ਕੇਸ ਦੇ ਵੇਰਵੇ",
            width=940,
            height=460,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="gray",
            fg_color="white",
            wraplength=530,
            padx=10,
            pady=10
        )
        self.subtitle_label.pack(padx=5, pady=5)

        # Create numeric keypad
        self._create_numeric_keypad()
        
        # --------------- Buttons for stop, close and rese the application --------------------
        self.last_button_frame = ctk.CTkFrame(
            self.main_frame, 
            width=900,
            height=120,
            fg_color="transparent"
            )
        self.last_button_frame.pack(padx=10, pady=10)

        # Stop button
        self.stop_button = ctk.CTkButton(
            self.last_button_frame,
            text="Stop",
            command=self.stop_application,
            font=ctk.CTkFont(size=38, weight="bold"),
            fg_color="red",
            text_color="white",
            height=100,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=40
        )
        self.stop_button.pack(side="left", padx=30, pady=10)
        
        # Close button
        self.close_button = ctk.CTkButton(
            self.last_button_frame,
            text="Close",
            command=self._show_password_popup,
            font=ctk.CTkFont(size=38, weight="bold"),
            fg_color="maroon", 
            text_color="white",
            height=100,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=40
        )
        self.close_button.pack(side="left", padx=30, pady=10)
        
        # Reset button
        self.reset_button = ctk.CTkButton(
            self.last_button_frame,
            text="Reset",
            command=self.reset_application,
            font=ctk.CTkFont(size=38, weight="bold"),
            fg_color="green",
            text_color="white",
            height=100,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=40
        )
        self.reset_button.pack(side="left", padx=30, pady=10)
        
        # Register cleanup function to release camera resources
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        atexit.register(self._safe_exit_cleanup)

        self.case_types = {
            "CWP": "CIVIL WRIT PETITION", "CRM-M": "CRIMINAL MAIN", "CR": "CIVIL REVISION",
            "RSA": "REGULAR SECOND APPEAL", "CRR": "CRIMINAL REVISION", "CRA-S": "CRIMINAL APPEAL SB",
            "FAO": "FIRST APPEAL ORDER", "CM": "CIVIL MISC", "CRM": "CRIMINAL MISCELLANEOUS PETITION",
            "ARB": "ARBITRATION ACT CASE (WEF 15/10/03)", "ARB-DC": "ARBITRATION CASE (DOMESTIC COMMERCIAL)", "ARB-ICA": "ARBITRATION CASE (INTERNATIONAL COMM ARBITRATION)",
            "CA": "CIVIL APPEAL/COMPANY APPLICATION", "CA-CWP": "COMMERCIAL APPEAL (WRIT)", "CA-MISC": "COMMERCIAL APPEAL (MISC)",
            "CACP": "CONTEMPT APPEALS", "CAPP": "COMPANY APPEAL", "CCEC": "CUSTOM CENTRAL EXCISE CASE",
            "CCES": "CCES", "CEA": "CENTRAL EXCISE APPEAL (WEF 10-11-2003)", "CEC": "CENTRAL EXCISE CASE",
            "CEGC": "CENTRAL EXCISE GOLD CASE", "CESR": "CENTRAL EXCISE AND SALT REFERENCE", "CLAIM": "CLAIMS",
            "CM-INCOMP": "Misc Appl. in Incomplete Case", "CMA": "COMPANY MISC. APPLICATION", "CMM": "HMA CASES U/S 24",
            "CO": "CIVIL ORIGINAL", "CO-COM": "CIVIL ORIGINAL (COMMERCIAL)", "COA": "COMPANY APPLICATION",
            "COCP": "CIVIL ORIGINAL CONTEMPT PETITION", "COMM-PET-M": "COMMERCIAL PETITION MAIN", "CP": "COMPANY PETITIONS",
            "CP-MISC": "COMMERCIAL PETITION (MISC)", "CR-COM": "CIVIL REVISION (COMMERCIAL)", "CRA": "CRIMINAL APPEAL",
            "CRA-AD": "CRIMINAL APPEAL ACQUITTAL DB", "CRA-AS": "CRIMINAL APPEAL ACQUITTAL SB", "CRA-D": "CRIMINAL APPEAL DB",
            "CRACP": "CRIMINAL APPEAL CONTEMPT PETITION", "CREF": "CIVIL REFERENCE", "CRM-A": "AGAINST ACQUITTALS",
            "CRM-CLT-OJ": "CRIMINAL COMPLAINT (ORIGINAL SIDE)", "CRM-W": "CRM IN CRWP", "CROCP": "CRIMINAL ORIGINAL CONTEMPT PETITION",
            "CRR(F)": "CRIMINAL REVISION (FAMILY COURT)", "CRREF": "CRIMINAL REFERENCE", "CRWP": "CRIMINAL WRIT PETITION",
            "CS": "CIVIL SUIT", "CS-OS": "CIVIL SUIT-ORIGINAL SIDE", "CUSAP": "CUSTOM APPEAL (WEF 17/7/2004)",
            "CWP-COM": "CIVIL WRIT PETITION (COMMERCIAL)", "CWP-PIL": "CIVIL WRIT PETITION PUBLIC INTEREST LITIGATION", "DP": "DIVORCE PETITION",
            "EA": "EXECUTION APPL", "EDC": "ESTATE DUTY CASE", "EDREF": "ESTATE DUTY REFERENCE",
            "EFA": "EXECUTION FIRST APPEAL", "EFA-COM": "EXECUTION FIRST APPEAL (COMMERCIAL)", "EP": "ELECTION PETITIONS",
            "EP-COM": "EXECUTION PETITION (COMMERCIAL)", "ESA": "EXECUTION SECOND APPEAL", "FAO(FC)": "FAO (FAMILY COURT)",
            "FAO-C": "FAO (CUS AND MTC)", "FAO-CARB": "FIRST APPEAL FROM ORDER (COMMERCIAL ARBITRATION)", "FAO-COM": "FIRST APPEAL FROM ORDER (COMMERCIAL)",
            "FAO-ICA": "FIRST APPEAL FROM ORDER (INTERNATIONAL COMM ARBI.)", "FAO-M": "FIRST APPEAL ORDER-MATRIMONIAL", "FEMA-APPL": "FEMA APPEAL",
            "FORM-8A": "FORM-8A", "GCR": "GOLD CONTROL REFERENCE", "GSTA": "GOODS AND SERVICES TAX APPEAL",
            "GSTR": "GENERAL SALES TAX REFERENCE", "GTA": "GIFT TAX APPEAL", "GTC": "GIFT TAX CASE",
            "GTR": "GIFT TAX REFERENCE", "GVATR": "GENERAL VAT REFERENCES", "INCOMP": "INCOMPLETE OBJECTION CASE",
            "INTTA": "INTEREST TAX APPEAL", "IOIN": "INTERIM ORDER IN", "ITA": "INCOME TAX APPEAL",
            "ITC": "INCOME TAX CASES", "ITR": "INCOME TAX REFERENCE", "LPA": "LATTER PATENT APPEALS",
            "LR": "LIQUIDATOR REPORT", "MATRF": "MATROMONIAL REFERENCE", "MRC": "MURDER REFERENCE CASE",
            "O&M": "ORIGINAL & MISCELLANEOUS", "OLR": "OFFICIAL LIQUIDATOR REPORT", "PBPT-APPL": "PROHIBITION OF BENAMI PROPERTY TRANSACTION APPEAL",
            "PBT": "PROBATE", "PMLA-APPL": "PREVENTION OF MONEY LAUNDERING APPEAL", "PVR": "PB VAT REVISION",
            "RA": "REVIEW APPL", "RA-CA": "REVIEW IN COMPANY APPEAL", "RA-CP": "REVIEW IN COMPANY PETITION",
            "RA-CR": "REVIEW IN CR", "RA-CW": "REVIEW IN CWP", "RA-LP": "REVIEW IN LPA",
            "RA-RF": "REVIEW APPLICATION IN RFA", "RA-RS": "REVIEW IN RSA", "RCRWP": "REVIEW IN CRCWP",
            "RERA-APPL": "RERA APPEAL", "RFA": "REGULAR FIRST APPEAL", "RFA-COM": "REGULAR FIRST APPEAL (COMMERCIAL)",
            "RP": "RECRIMINATION PETITION", "SA": "SERVICE APPEAL", "SAO": "SECOND APPEAL ORDER",
            "SAO(FS)": "SAO FOOD SAFETY", "SDR": "STATE DUTY REFERENCE", "STA": "SALES TAX APPEAL",
            "STC": "SALES TAX CASES", "STR": "SALE TAX REFERENCE", "TA": "TRANSFER APPLICATION",
            "TA-COM": "TRANSFER APPLICATION (COMMERCIAL)", "TC": "TAKENUP CASES", "TCRIM": "TRANSFER CRIMINAL PETITION",
            "TEST": "TEST", "UVA": "UT VAT APPEAL", "UVR": "UT VAT REVISION", "VATAP": "VAT APPEAL",
            "VATCASE": "VALUE ADDED TAX CASE", "VATREF": "VAT REFERENCE",
            "WTA": "WEALTH TAX APPEAL", "WTC": "WEALTH TAX CASES",
            "WTR": "WEALTH TAX REFERENCE", "XOBJ": "CROSS OBJECTION", "XOBJC": "CROSS OBJECTION IN CR",
            "XOBJL": "CROSS OBJECTION IN LPA", "XOBJR": "CROSS OBJECTION IN RFA", "XOBJS": "CROSS OBJECTION IN RSA",
        }
    

        threading.Thread(target=self.monitor_button_input, daemon=True).start()
    
    # ===================================================================================================

    # ========================================= Create Button for GUI ===================================
    def _create_numeric_keypad(self):
        """Create a numeric keypad with 0-9 buttons in a single row."""
        self.on_action_performed()

        # Create a frame for the keypad
        self.keypad_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.keypad_frame.pack(padx=10, pady=10)

        # Define all numeric buttons in one row
        buttons = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']

        # Create and place each button in a single row (row=0)
        for col_idx, key in enumerate(buttons):
            button = ctk.CTkButton(
                self.keypad_frame,
                text=key,
                font=ctk.CTkFont(size=28, weight="bold"),
                width=80,
                height=60,
                fg_color="black",
                text_color="white",
                border_width=2,
                border_color="red",
                corner_radius=20,
                command=lambda k=key: self._get_button_input(k)
            )
            button.grid(row=0, column=col_idx, padx=5, pady=5)

    def _get_button_input(self, key):
        self.on_action_performed()
        print(f"Button pressed: {key}")
        self.button_key = key

        self.button_input = True
        self.stop_system = True
        self.speak_pause = True

        # Stop mixer only if it's running
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            print("[INFO] Pygame mixer stopped but not quit.")
        
        self.speak_text(text='', lang='en')

        self.subtitle_label.configure(text='', text_color="gray")
        self.root.update()
    
    def monitor_button_input(self):
        while True:
            if self.button_key is None:
                time.sleep(0.1)
                continue

            print(f"[INFO] Button input detected: {self.button_key}")
            self.button_value = self.button_key
            self.button_key = None

            self._reset_flags()
            self.stop_system = False

            self.button_input = False

            print("[INFO] monitor_button_input run successfully.")
                
            time.sleep(0.5)

    # ===================================================================================================
    
    # ========================================= Reset Application =======================================
    def reset_flags_after_inactivity(self, timer=30.0):
        if self.reset_timer is not None:
            try:
                self.reset_timer.cancel()
            except Exception:
                pass
        
        self.reset_timer = threading.Timer(timer, self._reset_flags)
        self.reset_timer.daemon = True
        self.reset_timer.start()
     
    def on_action_performed(self, timer=30.0):
        # # Backend health check 
        # if not self.client.check_backend():
        #     self.root.withdraw()
        #     messagebox.showerror("Server Error", "The backend server is not connected.\nPlease start the FastAPI server and try again.")
        # else:
        #     self.root.deiconify()

        self.reset_flags_after_inactivity(timer=timer)
    
    def _reset_flags(self):
        if self._is_chrome_open():
            self.close_chrome()

        if self.camera_pause:
            self.camera_pause = False
        if self.speak_pause or self.conversation_pause or self.listen_pause or self.stop_system:
            self.stop_system = False
            self.speak_pause = False
            self.conversation_pause = False
            self.listen_pause = False
        self.face_detection_cooldown = False

         # ======================= Safe close password popup =======================
        if hasattr(self, "password_window"):
            try:
                if self.password_window and self.password_window.winfo_exists():
                    # Destroy child widgets first
                    for child in self.password_window.winfo_children():
                        if child.winfo_exists():
                            child.destroy()
                    # Destroy the popup itself
                    self.password_window.destroy()
                    print("[INFO] Password popup closed due to 90s reset.")

                # Clear reference to avoid reuse
                self.password_window = None
            except Exception as e:
                print(f"[WARN] Failed to close password popup safely: {e}")

        #  Start mixer only if it's not running
        if not pygame.mixer.get_init():
            pygame.mixer.init()
            print("[INFO] Pygame mixer started.")
    
    def _set_flags_false(self):
        if self.speak_pause or self.conversation_pause or self.listen_pause:
            self.speak_pause = False
            self.conversation_pause = False
            self.listen_pause = False
            self.stop_system = False

    # ===================================================================================================

    # ========================================= face detection ==========================================    
    def start_camera(self):
        """Start the camera and face detection thread"""
        self.on_action_performed()
        self.cap = cv2.VideoCapture(0)  # 0 is usually the built-in webcam
        self.is_camera_running = True
        
        # Start detection in a separate thread
        self.detection_thread = threading.Thread(target=self.detect_faces)
        self.detection_thread.daemon = True
        self.detection_thread.start()

    def detect_faces(self):
        """Thread function for face detection with strict zone and no bounding boxes."""
        self.on_action_performed()
        last_detection_time = 0
        cooldown_period = 10
        min_face_size = (160, 160)
        max_face_size = (250, 250)
        
        while self.is_camera_running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # Convert frame to RGB for GUI
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Draw detection zone regardless of detection pause
            height, width = frame.shape[:2]
            x_start = int(width * 0.3)
            x_end = int(width * 0.7)
            y_start = int(height * 0.2)
            y_end = int(height * 0.8)
            cv2.rectangle(frame_rgb, (x_start, y_start), (x_end, y_end), (0, 255, 0), 2)
            cv2.putText(frame_rgb, "Detection Range", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame_rgb, f"Min: {min_face_size[0]}px", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
            cv2.putText(frame_rgb, f"Max: {max_face_size[0]}px", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

            # Only do face detection if not paused
            if not self.camera_pause:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=4,
                    minSize=min_face_size,
                    maxSize=max_face_size
                )

                face_in_zone = False
                current_time = time.time()

                for (x, y, w, h) in faces:
                    # Check if face is completely within detection zone
                    if (x >= x_start and x + w <= x_end and
                        y >= y_start and y + h <= y_end):
                        face_in_zone = True
                        break  # Only need one full face inside zone

                if face_in_zone and not self.face_detection_cooldown and (current_time - last_detection_time > cooldown_period):
                    self.face_detected = True
                    last_detection_time = current_time
                    self.face_detection_cooldown = True
                    self.root.after(0, self._face_button_conversation)

            # Always update the GUI image (create the CTkImage on the MAIN thread)
            pil_img = Image.fromarray(frame_rgb)

            # Create & set CTkImage on the Tk main thread to avoid "image" errors.
            self.root.after(0, lambda img=pil_img: self._update_camera_image(img))

            time.sleep(0.03)
    
    # ===================================================================================================

    # ========================================= authentication ==========================================
    def _on_closing(self):
        """Release resources and close application."""
        self.is_camera_running = False
        try:
            if self.reset_timer is not None:
                self.reset_timer.cancel()
        except Exception:
            pass
        try:
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _show_password_popup(self):
        """Show a password entry popup with a numeric keypad."""
        self.stop_application()
        self.on_action_performed(timer=10)

        self.password_window = ctk.CTkToplevel(self.root)
        self.password_window.title("Password Verification")
        self.password_window.geometry("360x480") 
        self.password_window.resizable(False, False)

        # Keep the pop-up on top and grab focus
        self.password_window.grab_set()
        self.password_window.focus_force()

        # Label
        ctk.CTkLabel(self.password_window, text="Enter Password:", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)

        # Password Entry Field (Read-Only)
        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(self.password_window, textvariable=self.password_var, font=ctk.CTkFont(size=18), justify="center", show="*")
        self.password_entry.pack(pady=5, padx=20, fill="x")

        # Numeric Keypad Frame
        keypad_frame = ctk.CTkFrame(self.password_window)
        keypad_frame.pack(pady=10)

        # Keypad Buttons for password pop up
        buttons = [
            ('1', '2', '3'),
            ('4', '5', '6'),
            ('7', '8', '9'),
            ('⌫', '0', '✔')
        ]

        for row_idx, row in enumerate(buttons):
            for col_idx, digit in enumerate(row):
                button = ctk.CTkButton(
                    keypad_frame,
                    text=digit,
                    font=ctk.CTkFont(size=24, weight="bold"),
                    width=80,
                    height=60,
                    fg_color="teal",
                    border_width=2,
                    border_color="black",
                    corner_radius=10,
                    command=lambda d=digit: self._handle_keypress(d)
                )
                button.grid(row=row_idx, column=col_idx, padx=5, pady=5)
        
        # Additional buttons frame
        additional_buttons_frame = ctk.CTkFrame(self.password_window)
        additional_buttons_frame.pack(pady=10)
        
        # Reset Button
        reset_button = ctk.CTkButton(
            additional_buttons_frame,
            text="Reset",
            font=ctk.CTkFont(size=24, weight="bold"),
            width=120,
            height=60,
            fg_color="green",
            border_width=2,
            border_color="white",
            corner_radius=10,
            command=self._reset_password
        )
        reset_button.grid(row=0, column=0, padx=10, pady=5)
        
        # Close Button
        close_button = ctk.CTkButton(
            additional_buttons_frame,
            text="Close",
            font=ctk.CTkFont(size=24, weight="bold"),
            width=120,
            height=60,
            fg_color="maroon",
            border_width=2,
            border_color="white",
            corner_radius=10,
            command=self._close_password_window
        )
        close_button.grid(row=0, column=1, padx=10, pady=5)

    def _reset_password(self):
        """Reset the password field."""
        self.on_action_performed()
        self.password_var.set("")

    def _close_password_window(self):
        """Close the password window."""
        self.on_action_performed()
        self.password_window.destroy()

    def _handle_keypress(self, key):
        """Handle keypresses for the numeric keypad."""
        self.on_action_performed(timer=10.0)
        if key == '⌫':  # Backspace
            self.password_var.set(self.password_var.get()[:-1])
        elif key == '✔':  # Enter
            self._verify_password()
        else:
            self.password_var.set(self.password_var.get() + key)

    def _verify_password(self):
        """Verify the entered password and close the app if correct."""
        self.on_action_performed()
        password = self.password_var.get()
        if password:
            for user in self.auth_data:
                if password in user.values():
                    self._on_closing()  # Use _on_closing to properly release camera resources
                    return
            messagebox.showerror("Error", "Incorrect password.")
        else:
            messagebox.showwarning("Warning", "Password cannot be empty.")

    def _load_auth_data(self):
        """Load authentication data from auth.json."""
        self.on_action_performed()
        try:
            with open(self.auth_json_path, "r", encoding="utf-8") as file:
                self.auth_data = json.load(file)
        except FileNotFoundError:
            print("Authentication file not found. Using default passwords.")
            self.auth_data = [
                {"superadmin": "69696969"},
                {"admin": "244466666"}
            ]

    def reset_application(self):
        self.on_action_performed()
        self.stop_application()
        self.reset_flags_after_inactivity(timer=0.5)

        # Clear the subtitle label and text input immediately
        self.subtitle_label.configure(text="🔁 RESET", text_color="green")
        self.root.update()

        self.stop_system = False

    def stop_application(self):
        """Stop all ongoing operations immediately."""
        self.on_action_performed(timer=30.0)

        if self._is_chrome_open():
            self.close_chrome()
        
        self.button_key = None
        self.button_value = None
        
        # Set all pause flags to True to stop operations
        self.stop_system = True
        self.camera_pause = True
        self.speak_pause = True
        self.conversation_pause = True
        self.listen_pause = True
        self.face_detection_cooldown = True
        
        # Stop any ongoing audio playback immediately (do not quit mixer to avoid re-init cost)
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        
        # Clear the subtitle label and text input immediately
        self.subtitle_label.configure(text="🛑 STOP", text_color="red")
        self.root.update()

    def _load_image(self, path, size):
        """Load and resize an image."""
        self.on_action_performed()
        try:
            image = Image.open(path)
            image = image.resize(size, Image.Resampling.LANCZOS)
            return ctk.CTkImage(light_image=image, size=size)
        except Exception as e:
            print(f"Could not load image: {e}")
            return None
        
    # ===================================================================================================
    
    # =============================== open chrome for manual search =====================================
    def check_backend(self):
        """Check if the FastAPI backend is running."""
        self.on_action_performed()
        self.camera_pause = True
        
        url = "http://192.168.1.81:8000/static/index.html"
        try:
            urllib.request.urlopen(url, timeout=5)
            print(f"Backend is running at {url}.")
            return True
        except Exception as e:
            print(f"Backend is not running or inaccessible at {url}: {e}")
            return False

    # def open_chrome(self):
    #     """Open index.html in Chrome browser in full-screen mode."""
    #     self.on_action_performed()
    #     self.camera_pause = True

    #     url = "http://192.168.1.81:8000/static/index.html"

    #     if not self.check_backend():
    #         messagebox.showerror("Backend Unavailable", "Please ensure the FastAPI server is running.\n(e.g., 'uvicorn main:app --reload').")
    #         return

    #     chrome_path = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    #     if not os.path.exists(chrome_path):
    #         messagebox.showerror("Chrome Not Found", "Chrome not found at the specified path. Please ensure Chrome is installed.")
    #         return

    #     try:
    #         self.chrome_process = subprocess.Popen(
    #             [chrome_path, "--start-fullscreen", url],
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.PIPE
    #         )
    #         print(f"Opened {url} in Chrome in full-screen mode (PID: {self.chrome_process.pid}).")

    #         # Start monitoring thread
    #         self.monitor_thread = threading.Thread(target=self._chrome_monitor, daemon=True)
    #         self.monitor_thread.start()

    #     except Exception as e:
    #         messagebox.showerror("Error opening Chrome", str(e))
    #         return

    def open_chrome(self):
        """Open local index.html in Chrome browser in full-screen mode."""
        self.on_action_performed()
        self.camera_pause = True

        # Get the local path of index.html in the same directory as this script
        local_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

        if not os.path.exists(local_html):
            messagebox.showerror(
                "File Not Found",
                f"index.html was not found at:\n{local_html}"
            )
            return

        chrome_path = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        if not os.path.exists(chrome_path):
            messagebox.showerror(
                "Chrome Not Found",
                "Chrome not found at the specified path. Please ensure Chrome is installed."
            )
            return

        try:
            # Convert local path to a file:// URL
            file_url = f"file:///{local_html.replace(os.sep, '/')}"
            
            self.chrome_process = subprocess.Popen(
                [chrome_path, "--start-fullscreen", file_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"Opened {file_url} in Chrome in full-screen mode (PID: {self.chrome_process.pid}).")

            # Start monitoring thread
            self.monitor_thread = threading.Thread(target=self._chrome_monitor, daemon=True)
            self.monitor_thread.start()

        except Exception as e:
            messagebox.showerror("Error opening Chrome", str(e))
            return

    def _is_chrome_open(self):
        """Check if any Chrome browser instances are running."""
        self.on_action_performed()
        self.camera_pause = True
        try:
            if self.chrome_process and self.chrome_process.poll() is None:
                return True
            self.camera_pause = False
            return False
        except Exception as e:
            print(f"Error checking Chrome process: {e}")
            return False
    
    def close_chrome(self):
        """Forcefully close all Chrome browser instances."""
        self.on_action_performed()
        self.camera_pause = True

        try:
            if self.chrome_process and self.chrome_process.poll() is None:
                self.chrome_process.kill()
                print(f"Closed Chrome process (PID: {self.chrome_process.pid}).")
            
        except Exception as e:
            print(f"Error closing Chrome process: {e}")
        finally:
            self.camera_pause = False
    
    def _chrome_monitor(self):
        """Continuously monitor if the specific Chrome instance is still running."""
        while True:
            if self._is_chrome_open():
                time.sleep(1)
            else:
                time.sleep(5)
                self.reset_application()
                break
    
    # ===================================================================================================
    
    #  ================================ language Speak and Translate ====================================
    def translate_text(self, text, source, target):
        """Translate text from source language to target language."""
        self.on_action_performed(timer=30.0)
        if text is None or (source == target):
            return text
        
        self.camera_pause = True
        
        key = (source, target, text)
        if key in self._translate_cache:
            return self._translate_cache[key]

        st_key = (source, target)
        if st_key not in self._translators:
            self._translators[st_key] = GoogleTranslator(source=source, target=target)
        try:
            translated = self._translators[st_key].translate(text)
            # cache result for speed
            if len(text) <= 4000:  # avoid caching huge strings
                self._translate_cache[key] = translated
            return translated
        except Exception as e:
            print(f"Translation error: {e}")
            return text

    def speak_text(self, text, lang="pa"):
        self.on_action_performed(timer=90.0)

        if self.speak_pause or not text or self.conversation_pause or self.stop_system:
            return 

        self.camera_pause = True
        self.listen_pause = True
        
        try:
            # Use cached TTS audio if available to avoid network delay
            key_bytes = (lang + "\0" + text).encode("utf-8", errors="ignore")
            tts_hash = hashlib.sha1(key_bytes).hexdigest()
            cached_mp3 = os.path.join(self._tts_cache_dir, f"{lang}_{tts_hash}.mp3")

            if not os.path.exists(cached_mp3):
                # Generate the speech file using gTTS
                tts = gTTS(text=text, lang=lang)
                tts.save(cached_mp3)

            # Initialize pygame mixer if not already initialized
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            # Load the speech file into pygame mixer
            pygame.mixer.music.load(cached_mp3)
            pygame.mixer.music.play()  # Play the audio

            # Calculate the total duration of the audio
            audio = pygame.mixer.Sound(cached_mp3)
            total_duration = audio.get_length()

            # Split the text into words for real-time display
            words = text.split()
            num_words = len(words)
            duration_per_word = total_duration / max(num_words, 1)  # Avoid division by zero

            # Clear the subtitle label before starting
            if self.root and self.subtitle_label.winfo_exists():
                self.subtitle_label.configure(text="", text_color="gray")
                self.root.update()

            # Start time for tracking word display
            start_time = time.time()

            # Display words in real-time as the audio plays
            for idx, word in enumerate(words):
                # 🔹 Check if speaking was paused/stopped OR audio stopped
                if self.speak_pause or self.stop_system or not pygame.mixer.music.get_busy():
                    self.subtitle_label.configure(text="", text_color="gray")
                    self.root.update()
                    return
                
                if self.root and self.subtitle_label.winfo_exists():
                    current_text = self.subtitle_label.cget("text")
                    self.subtitle_label.configure(
                        text=(current_text + " " + word) if current_text else word, 
                        text_color="gray"
                    )
                    self.root.update()

                # Calculate the elapsed time and sleep accordingly
                elapsed_time = time.time() - start_time
                expected_time = duration_per_word * (idx + 1)
                sleep_time = max(0, expected_time - elapsed_time)
                time.sleep(sleep_time)

            # 🔹 Final wait loop
            while pygame.mixer.music.get_busy():
                if self.speak_pause or self.stop_system:
                    self.subtitle_label.configure(text="", text_color="gray")
                    self.root.update()
                    pygame.mixer.music.stop()  # make sure audio halts
                    return
                pygame.time.Clock().tick(30)  # smoother UI

            # Keep mixer initialized to avoid re-init overhead
            self.listen_pause = False

        except Exception as e:
            print(f"Text-to-speech error: {e}")

    def listen(self, lang="pa", timeout=7):
        self.on_action_performed(timer=60.0)

        if self.listen_pause or self.stop_system:
            return

        self.camera_pause = True
        recognizer = sr.Recognizer()

        attempts = 0
        max_attempts = 3

        while attempts < max_attempts:
            if self.stop_system:
                break

            with sr.Microphone() as source:
                try:
                    # shorter calibration to be faster
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    self.subtitle_label.configure(text="🎙️ MIC INPUT", text_color="blue")
                    self.root.update()
                    audio = recognizer.listen(source, timeout=timeout)
                    recognized_text = recognizer.recognize_google(audio, language='en')
                    winsound.PlaySound(self.end_sound, winsound.SND_FILENAME)
                    return recognized_text

                except sr.UnknownValueError:
                    attempts += 1
                    error_message = self.translate_text(text="Could not understand audio. Retrying...", source='en', target=lang)
                    self.speak_text(text=error_message, lang=lang)

                except sr.RequestError as e:
                    attempts += 1
                    error_message = self.translate_text(text=f"Request error: {e}. Retrying...", source='en', target=lang)
                    self.speak_text(text=error_message, lang=lang)

                except Exception as e:
                    attempts += 1
                    error_message = self.translate_text(text=f"An error occurred: {e}. Retrying...", source='en', target=lang)
                    self.speak_text(text=error_message, lang=lang)


        final_error_message = self.translate_text(text="Failed to listen after all attempts.", source='en', target=lang)
        self.speak_text(text=final_error_message, lang=lang)
        return ""
    
    # ===================================================================================================

    # ======================================= listen case id ============================================
    def _map_spoken_numbers(self, text, lang='en'):
        self.on_action_performed()
        self.punjabi_numbers = {
            "੦": "0", "੧": "1", "੨": "2", "੩": "3", "੪": "4",
            "੫": "5", "੬": "6", "੭": "7", "੮": "8", "੯": "9",
            "ਸਿਫਰ": "0", "ਇੱਕ": "1", "ਦੋ": "2", "ਤਿੰਨ": "3", "ਚਾਰ": "4",
            "ਪੰਜ": "5", "ਛੇ": "6", "ਸੱਤ": "7", "ਅੱਠ": "8", "ਨੌਂ": "9"
        }

        self.hindi_numbers = {
            "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
            "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
            "शून्य": "0", "एक": "1", "दो": "2", "तीन": "3", "चार": "4",
            "पांच": "5", "छह": "6", "सात": "7", "आठ": "8", "नौ": "9"
        }

        self.english_numbers = {
            "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
        }

        if lang == 'pa':
            number_mapping = self.punjabi_numbers
        elif lang == 'hi':
            number_mapping = self.hindi_numbers
        else:
            number_mapping = self.english_numbers

        for word, num in number_mapping.items():
            text = text.replace(word, num)

        return text
       
    def listen_case_number(self, lang='pa', timeout=7):
        self.on_action_performed(timer=60.0)

        if self.listen_pause:
            return

        self.camera_pause = True
        recognizer = sr.Recognizer()
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts:
            with sr.Microphone() as source:
                try:
                    # winsound.PlaySound(self.start_sound, winsound.SND_FILENAME)
                    recognizer.adjust_for_ambient_noise(source, duration=0.8)
                    self.subtitle_label.configure(text="🎙️ MIC INPUT", text_color="blue")
                    self.root.update()
                    audio = recognizer.listen(source, timeout=timeout)
                    recognized_text = recognizer.recognize_google(audio, language=lang)
                    print(f"Recognized case number: {recognized_text}")

                    recognized_text = self._map_spoken_numbers(recognized_text, lang)
                    recognized_text = recognized_text.replace("O", "0").replace("o", "0")
                    recognized_text = recognized_text.replace(" ", "-")
                    winsound.PlaySound(self.end_sound, winsound.SND_FILENAME)

                    parts = recognized_text.split("-")
                    numeric_part = ""
                    alphanumeric_part = ""

                    for part in parts:
                        if part.isdigit():
                            numeric_part = part
                        else:
                            alphanumeric_part = part.upper()

                    if not numeric_part:
                        print(f"Invalid case number: {recognized_text}. Numeric part is missing.")
                        error_message = self.translate_text(text="Invalid case number. Numeric part is missing.", source='en', target=lang)
                        self.speak_text(text=error_message, lang=lang)
                        attempts += 1
                        continue

                    structured_case_number = f"{numeric_part}-{alphanumeric_part}" if alphanumeric_part else numeric_part

                    if re.match(r'^\d+(-\w+)?$', structured_case_number):
                        return structured_case_number
                    else:
                        print(f"Invalid case number: {structured_case_number}. Case number must be in the format 'XXXX-XXX' or 'XXXX'.")
                        error_message = self.translate_text(
                            text="Invalid case number format. It should be like '1234' or '1234-ABC'.", source='en', target=lang
                        )
                        self.speak_text(text=error_message, lang=lang)
                        attempts += 1
                        continue

                except sr.UnknownValueError:
                    attempts += 1
                    error_message = self.translate_text(text="Sorry, I could not understand the audio. Retrying...", source='en', target=lang)
                    self.speak_text(text=error_message, lang=lang)

                except sr.RequestError as e:
                    attempts += 1
                    error_message = self.translate_text(
                        text=f"Could not request results from the speech recognition service; {e}. Retrying...",
                        source='en', target=lang
                    )
                    self.speak_text(text=error_message, lang=lang)

                except Exception as e:
                    attempts += 1
                    error_message = self.translate_text(
                        text=f"An error occurred in listen_case_number: {e}. Retrying...",
                        source='en', target=lang
                    )
                    self.speak_text(text=error_message, lang=lang)
                
                finally:
                    if self.stop_system:
                        break


        # If all attempts fail
        final_error = self.translate_text(
            text="Failed to recognize case number after all attempts.", source='en', target=lang
        )
        self.speak_text(text=final_error, lang=lang)
        return None

    def listen_case_year(self, lang='pa', timeout=7):
        self.on_action_performed(timer=60.0)

        if self.listen_pause:
            return

        self.camera_pause = True
        recognizer = sr.Recognizer()
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts:
            with sr.Microphone() as source:
                try:
                    # winsound.PlaySound(self.start_sound, winsound.SND_FILENAME)
                    recognizer.adjust_for_ambient_noise(source, duration=0.8)
                    self.subtitle_label.configure(text="🎙️ MIC INPUT", text_color="blue")
                    self.root.update()
                    audio = recognizer.listen(source, timeout=timeout)
                    recognized_text = recognizer.recognize_google(audio, language=lang)

                    recognized_text = self._map_spoken_numbers(recognized_text, lang)
                    recognized_text = recognized_text.replace("O", "0").replace("o", "0")
                    winsound.PlaySound(self.end_sound, winsound.SND_FILENAME)

                    if recognized_text.isdigit() and len(recognized_text) == 4:
                        return recognized_text
                    else:
                        translated_text = self.translate_text(
                            text=f"Invalid case year: {recognized_text}. Case year must be a 4-digit number.",
                            source='en', target=lang
                        )
                        self.speak_text(text=translated_text, lang=lang)
                        return None

                except sr.UnknownValueError:
                    attempts += 1
                    error_message = self.translate_text(
                        text="Sorry, I could not understand the audio. Retrying...", source='en', target=lang
                    )
                    self.speak_text(text=error_message, lang=lang)

                except sr.RequestError as e:
                    attempts += 1
                    error_message = self.translate_text(
                        text=f"Could not request results from the speech recognition service; {e}. Retrying...",
                        source='en', target=lang
                    )
                    self.speak_text(text=error_message, lang=lang)

                except Exception as e:
                    attempts += 1
                    error_message = self.translate_text(
                        text=f"An error occurred: {e}. Retrying...", source='en', target=lang
                    )
                    self.speak_text(text=error_message, lang=lang)
                
                finally:
                    if self.stop_system:
                        break

        # If all attempts fail
        final_error = self.translate_text(
            text="Failed to recognize case year after all attempts.", source='en', target=lang
        )
        self.speak_text(text=final_error, lang=lang)
        return None

    # ===================================================================================================
    
    # ====================================== Conversation ===============================================
    def _generate_greeting(self):
        now = datetime.datetime.now()

        # Greeting and time of day
        h, m = now.hour, now.minute
        if 5 <= h < 12:
            greet = "Good Morning"
        elif 12 <= h < 17:
            greet = "Good Afternoon"
        elif 17 <= h < 21:
            greet = "Good Evening"
        else:
            greet = "Good Night"

        # Ordinal date
        d = now.day
        suffix = "th" if 10 <= d % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")

        # Time format
        hour12 = h % 12 or 12

        return (
            f"{greet}, today is {now.strftime('%A')}, {d}{suffix} {now.strftime('%B')} {now.year}, and the current time is {hour12}:{m:02d}."
        )
    
    def _manual_conversation(self):
        "Prompt the user for manual search"
        self.on_action_performed()

        self.stop_application()

        self.open_chrome()

    def _face_button_conversation(self, lang='pa', input_from_button=False):
        """Prompt the user for case number after face detection"""
        self.on_action_performed()
        
        self.camera_pause = True
        self._set_flags_false()

        if input_from_button == True:
            # Stop any ongoing audio playback immediately
            if pygame.mixer.get_init() is not None:
                pygame.mixer.music.stop()
                # keep mixer initialized
            
            # Clear the subtitle label and text input immediately
            self.subtitle_label.configure(text="", text_color="gray")
            self.root.update()

        self.conversation(lang=lang, input_from_button=input_from_button)
    
    def conversation(self, lang="pa", input_from_button=False):
        """Engage in a conversation based on user input."""
        self.on_action_performed(timer=90.0)

        if self.conversation_pause:
            return
        
        try:
            self.camera_pause = True

            self.selected_lang = 'punjabi'
            self.court_establishment = None
            self.search_type = None
            
        # ==================================================== select lang ====================================================== 
            # try:            
            def language_communication():
                try:
                    nonlocal lang

                    if input_from_button:
                        if lang=='en':
                            self.selected_lang = 'english'
                        elif lang=='hi':
                            self.selected_lang = 'hindi'
                        else:
                            self.selected_lang = 'punjabi'
                    else:
                        self.button_key = None
                        self.button_value = None
                        self.button_input = False

                        prompt_message = f"""
                        {self._generate_greeting()}. Kindly select a language. 
                        I could understand three languages, 1. English 2. Hindi and 3. Punjabi. 
                        Speak anyone of them. If you want to make a manual search then press 
                        Manual Input button.
                        """
                        prompt_message = self.translate_text(text=prompt_message, source='en', target=lang)
                        self.speak_text(prompt_message, lang=lang)

                        # ----------------------------------------- language selection manual input ---------------------
                        self.selected_lang = None
                        for i in range(3):
                            if self.button_value is None:
                                break
                            else:
                                self.button_input = True
                                if self.button_value ==  '1':
                                    self.selected_lang = 'english'
                                    lang = 'en'
                                    self.button_value = None
                                    self.button_key = None
                                    break
                                elif self.button_value ==  '2':
                                    self.selected_lang = 'hindi'
                                    lang = 'hi'
                                    self.button_value = None
                                    self.button_key = None
                                    break
                                elif self.button_value ==  '3':
                                    self.selected_lang = 'punjabi'
                                    lang='pa'
                                    self.button_value = None
                                    self.button_key = None
                                    break
                                else: 
                                    self.selected_lang = None
                                    text = self.translate_text(text="Invalid selection please try again.", source='en', target=lang)
                                    self.speak_text(text, lang)
                                    time.sleep(2)
                                    if i==2:
                                        self.button_value = None
                                        self.button_key = None
                        else:
                            self.button_input = False
                            self.button_value = None
                            self.button_key = None
                        # -----------------------------------------------------------------------------------------------

                        # ----------------------------------------- language selction voice input -----------------------
                        if not self.button_input:
                            max_attempts = 3
                            attempt = 0
                            self.selected_lang = None

                            while attempt < max_attempts and self.selected_lang is None:
                                if self.button_input:
                                    break

                                attempt += 1
                                voice_input = self.listen(lang=lang)
                                self.text_input.delete(0, ctk.END)
                                self.text_input.insert(0, str(voice_input))

                                if voice_input is not None:
                                    voice_input_lower = voice_input.lower()

                                    if any(word in voice_input_lower for word in ['1', 'one', 'ek', 'ik', 'english', 'अंग्रेज़ी', 'angrezee', 'ਅੰਗਰੇਜ਼ੀ']):
                                        self.selected_lang = 'english'
                                        lang='en'
                                    elif any(word in voice_input_lower for word in ['2', 'two', 'tu', 'do', 'hindi', 'हिन्दी', 'hindee', 'ਹਿੰਦੀ']):
                                        self.selected_lang = 'hindi'
                                        lang='hi'
                                    elif any(word in voice_input_lower for word in ['3', 'three', 'teen', 'punjabi', 'पंजाबी', 'panjaabee', 'ਪੰਜਾਬੀ']):
                                        self.selected_lang = 'punjabi'
                                        lang='pa'
                                    else:
                                        translated_text = self.translate_text("No valid language type recognized. Please try again.", source='en', target=lang)
                                        self.speak_text(translated_text, lang=lang)
                                else:
                                    translated_text = self.translate_text("I couldn't understand your input. Please try again.", source='en', target=lang)
                                    self.speak_text(translated_text, lang=lang)

                            # After loop ends, if still not valid
                            if self.selected_lang is None:
                                final_error = self.translate_text("Failed to detect valid language type after many attempts. So I am continue with default language.", source='en', target=lang)
                                self.speak_text(final_error, lang=lang)
                                self.selected_lang='punjabi'
                                lang='pa'
                        else:
                            self.button_value = None
                            self.button_key = None
                            self.button_input = False

                        # If we got a valid selected lang
                        if self.selected_lang is not None:
                            prompt_text = self.translate_text(text=f"Ok you have selected {self.selected_lang}.", source='en', target=lang)
                            self.speak_text(prompt_text, lang='en')
                        # -----------------------------------------------------------------------------------------------
                except Exception as e:
                    print("Start commnunication error: ", e)
            language_communication()
            if self.selected_lang is None:
                prompt_text = self.translate_text(text=f"No Valid Language selected.", source='en', target=lang)
                self.speak_text(prompt_text, lang='en')
                return
        
        # ============================================= court establishmet =====================================================
            def court_establishment_communication():
                try:
                    nonlocal lang

                    self.button_key = None
                    self.button_value = None
                    self.button_input = False

                    court_establishment_text = '''
                        Kindly select a court establishment.
                            1. District & Session Court Sangrur
                            2. Criminal Court Sangrur
                            3. Civil Court Sangrur
                        '''
                    court_establishment_text = self.translate_text(court_establishment_text, source='en', target=lang)
                    self.speak_text(court_establishment_text, lang=lang)
                    
                    # ---------------------------------- court establishment button input ------------------------------------------
                    self.court_establishment = None
                    for i in range(3):
                        if self.button_value is None:
                            print(self.button_value)
                            break
                        else:
                            print(self.button_value)
                            self.button_input = True
                            if self.button_value ==  '1':
                                self.court_establishment = 'district & session court sangrur'
                                self.button_value = None
                                self.button_key = None
                                break
                            elif self.button_value ==  '2':
                                self.court_establishment = 'criminal court sangrur'
                                self.button_value = None
                                self.button_key = None
                                break
                            elif self.button_value ==  '3':
                                self.court_establishment = 'civil court sangrur'
                                self.button_value = None
                                self.button_key = None
                                break
                            else: 
                                self.court_establishment = None
                                text = self.translate_text(text="Invalid selection please try again.", source='en', target=lang)
                                self.speak_text(text, lang)
                                time.sleep(2)
                                if i==2:
                                    self.button_value = None
                                    self.button_key = None
                    else:
                        self.button_input = False
                        self.button_value = None
                        self.button_key = None
                    # ---------------------------------------------------------------------------------------------------------------

                    # ---------------------------------- court establishment voice input --------------------------------------------
                    if not self.button_input:
                        max_attempts = 3
                        attempt = 0
                        self.court_establishment = None

                        while attempt < max_attempts and self.court_establishment is None:
                            if self.button_input:
                                break

                            attempt += 1
                            voice_input = self.listen(lang=lang)
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(voice_input))

                            if voice_input is not None:
                                voice_input_lower = voice_input.lower()

                                if any(word in voice_input_lower for word in ['1', 'one', 'ek', 'ik', 'district and session court sangarur', 'district', 'session', 'जिला एवं सत्र न्यायालय संगरूर', 'जिला', 'सत्र', 'ਜ਼ਿਲ੍ਹਾ ਅਤੇ ਸੈਸ਼ਨ ਕੋਰਟ ਸੰਗਰੂਰ', 'ਜ਼ਿਲ੍ਹਾ', 'ਸੈਸ਼ਨ', 'एक', 'ਇੱਕ']):
                                    self.court_establishment = 'district & session court sangrur'
                                elif any(word in voice_input_lower for word in ['2', 'two', 'tu', 'do', 'criminal court sangrur', 'criminal', 'आपराधिक न्यायालय संगरूर', 'आपराधिक', 'ਫੌਜਦਾਰੀ ਅਦਾਲਤ ਸੰਗਰੂਰ', 'ਅਪਰਾਧੀ', 'दो', 'ਦੋ']):
                                    self.court_establishment = 'criminal court sangrur'
                                elif any(word in voice_input_lower for word in ['3', 'three', 'teen', 'civil court sangrur', 'civil', 'सिविल कोर्ट संगरूर', 'सिविल', 'ਸਿਵਲ ਕੋਰਟ ਸੰਗਰੂਰ', 'ਸਿਵਲ', 'तीन', 'ਤਿੰਨ']):
                                    self.court_establishment = 'civil court sangrur'
                                else:
                                    translated_text = self.translate_text("No valid court establishment type recognized. Please try again.", source='en', target=lang)
                                    self.speak_text(translated_text, lang=lang)
                            else:
                                translated_text = self.translate_text("I couldn't understand your input. Please try again.", source='en', target=lang)
                                self.speak_text(translated_text, lang=lang)

                        # After loop ends, if still not valid
                        if self.court_establishment is None:
                            final_error = self.translate_text("Failed to detect valid court type after 3 attempts.", source='en', target=lang)
                            self.speak_text(final_error, lang=lang)
                    else:
                        self.button_value = None
                        self.button_key = None
                        self.button_input = False

                    # If we got a valid court establishment
                    if self.court_establishment is not None:
                        prompt_text = self.translate_text(text=f"Ok you have selected {self.court_establishment}.", source='en', target=lang)
                        self.speak_text(prompt_text, lang='en')
                    # ---------------------------------------------------------------------------------------------------------------
                except Exception as e:
                    print(f"Court Establishment Error: {e}.")
            court_establishment_communication()
            if self.court_establishment is None:
                prompt_text = self.translate_text(text=f"No Valid Court Establishment Type.", source='en', target=lang)
                self.speak_text(prompt_text, lang='en')
                return
        
        # ============================================== search type ===========================================================
            def search_type_communication():
                try:
                    nonlocal lang

                    self.button_key = None
                    self.button_value = None
                    self.button_input = False

                    search_type_text = """What kind of search you want to make.
                                        1. Case Search
                                        2. Advocate
                                        3. Cause List
                                        4. Lok Adalat Report
                                        5. Caveat Search
                                        6. Panel Search
                                        """
                    translated_text = self.translate_text(text=search_type_text, source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)

                    # ---------------------------------------- search type button input --------------------------------------------
                    self.search_type = None
                    for i in range(3):
                        if self.button_value is None:
                            break
                        else:
                            self.button_input = True
                            if self.button_value ==  '1':
                                self.search_type = 'case search'
                                self.button_value = None
                                self.button_key = None
                                break
                            elif self.button_value ==  '2':
                                self.search_type = 'advocate'
                                self.button_value = None
                                self.button_key = None
                                break
                            elif self.button_value ==  '3':
                                self.search_type = 'cause list'
                                self.button_value = None
                                self.button_key = None
                                break
                            elif self.button_value ==  '4':
                                self.search_type = 'lok adalat report'
                                self.button_value = None
                                self.button_key = None
                                break
                            elif self.button_value ==  '5':
                                self.search_type = 'caveat search'
                                self.button_value = None
                                self.button_key = None
                                break
                            elif self.button_value ==  '6':
                                self.search_type = 'panel search'
                                self.button_value = None
                                self.button_key = None
                                break
                            else:
                                self.search_type = None
                                text = self.translate_text(text="Invalid selection please try again.", source='en', target=lang)
                                self.speak_text(text, lang)
                                time.sleep(2)
                                if i==2:
                                    self.button_value = None
                    else:
                        self.button_input = False
                        self.button_value = None
                        self.button_key = None
                    
                    # ----------------------------------------- search type voice input --------------------------------------------
                    if not self.button_input:
                        max_attempts = 3
                        attempt = 0
                        self.search_type = None

                        while attempt < max_attempts and self.search_type is None:
                            if self.button_input:
                                break
                            attempt += 1
                            voice_input = self.listen(lang=lang)
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(voice_input))

                            if voice_input is not None:
                                voice_input_lower = voice_input.lower()

                                if any(word in voice_input_lower for word in ['1', 'one', 'एक', 'ਇੱਕ', 'ek', 'ik', 'case search', 'case', 'मामले की खोज', 'मामला', 'ਕੇਸ ਖੋਜ', 'ਕੇਸ']):
                                    self.search_type = 'case search'
                                elif any(word in voice_input_lower for word in ['2', 'two', 'दो', 'ਦੋ', 'tu', 'do', 'advocate', 'वकील', 'ਵਕੀਲ']):
                                    self.search_type = 'advocate'
                                elif any(word in voice_input_lower for word in ['3', 'three', 'teen', 'तीन', 'ਤਿੰਨ', 'cause list', 'कारण सूची', 'ਕਾਰਨ ਸੂਚੀ', 'cause', 'कारण', 'ਕਾਰਨ', 'list', 'सूची', 'ਸੂਚੀ']):
                                    self.search_type = 'cause list'
                                elif any(word in voice_input_lower for word in ['4', 'four', 'char', 'चार', 'ਚਾਰ', 'lok adalat report', 'लोक अदालत की रिपोर्ट', 'ਲੋਕ ਅਦਾਲਤ ਰਿਪੋਰਟ', 'lok adalat', 'लोक अदालत', 'ਲੋਕ ਅਦਾਲਤ', 'lok report', 'लोक रिपोर्ट', 'ਲੋਕ ਰਿਪੋਰਟ', 'lok', 'लोक', 'ਲੋਕ', 'adalat', 'अदालत', 'ਅਦਾਲਤ', 'report', 'प्रतिवेदन', 'ਰਿਪੋਰਟ']):
                                    self.search_type = 'lok adalat report'
                                elif any(word in voice_input_lower for word in ['5', 'five', 'panch', 'पांच', 'ਪੰਜ', 'caveat search', 'चेतावनी खोज', 'ਚੇਤਾਵਨੀ ਖੋਜ', 'caveat', 'चेतावनी', 'ਚੇਤਾਵਨੀ']):
                                    self.search_type = 'caveat search'
                                elif any(word in voice_input_lower for word in ['6', 'six', 'छह', 'ਛੇ', 'cheh', 'panel search', 'पैनल खोज', 'ਪੈਨਲ ਖੋਜ', 'panel', 'पैनल', 'ਪੈਨਲ']):
                                    self.search_type = 'panel search'
                                else:
                                    translated_text = self.translate_text("No valid search type recognized. Please try again.", source='en', target=lang)
                                    self.speak_text(translated_text, lang=lang)
                            else:
                                translated_text = self.translate_text("I couldn't understand your input. Please try again.", source='en', target=lang)
                                self.speak_text(translated_text, lang=lang)

                        # After loop ends, if still not valid
                        if self.search_type is None:
                            final_error = self.translate_text("Failed to detect valid search type after 3 attempts.", source='en', target=lang)
                            self.speak_text(final_error, lang=lang)
                    else:
                        self.button_value = None
                        self.button_key = None
                        self.button_input = False

                    # If we got a valid search type
                    if self.search_type is not None:
                        prompt_text = self.translate_text(text=f"Ok you have selected {self.search_type}.", source='en', target=lang)
                        self.speak_text(prompt_text, lang='en')
                    # ---------------------------------------------------------------------------------------------------------------
                except Exception as e:
                        print(f"Search Type Error: {e}.")
            search_type_communication()
            if self.search_type is None:
                prompt_text = self.translate_text(text=f"No Valid Search Type.", source='en', target=lang)
                self.speak_text(prompt_text, lang='en')
                return
        
        # ============================================== CASE SEARCH ===========================================================
            if any(word in self.search_type for word in ['1', 'one', 'ek', 'एक', 'ਇੱਕ', 'case search', 'मामले की खोज', 'ਕੇਸ ਖੋਜ']):
                def case_search_communication():
                    try:
                        nonlocal lang

                        self.button_key = None
                        self.button_value = None
                        self.button_input = False

                        case_search_text = """ Please select a case search type.
                                                1. CNR Number
                                                2. Filing Number
                                                3. Registration Number
                                                4. FIR Number
                                                5. Party Name
                                                6. Subordinate Court 
                                            """
                        
                        translated_text = self.translate_text(text=case_search_text, source='en', target=lang)
                        self.speak_text(translated_text, lang=lang)


                        # ---------------------------------------- case search type button input -------------------------------------------
                        case_search_type = None
                        for i in range(3):
                            if self.button_value is None:
                                break
                            else:
                                self.button_input = True
                                if self.button_value ==  '1':
                                    case_search_type = 'cnr number'
                                    self.button_value = None
                                    self.button_key = None
                                    break
                                elif self.button_value == '2':
                                    case_search_type = 'filing number'
                                    self.button_value = None
                                    self.button_key = None
                                    break
                                elif self.button_value == '3':
                                    case_search_type = 'registration number'
                                    self.button_value = None
                                    self.button_key = None
                                    break
                                elif self.button_value == '4':
                                    case_search_type = 'fir number'
                                    self.button_value = None
                                    self.button_key = None
                                    break
                                elif self.button_value == '5':
                                    case_search_type = 'party name'
                                    self.button_value = None
                                    self.button_key = None
                                    break
                                elif self.button_value == '6':
                                    case_search_type = 'subordinate court'
                                    self.button_value = None
                                    self.button_key = None
                                    break
                                else:
                                    case_search_type = None
                                    text = self.translate_text(text="Invalid selection please try again.", source='en', target=lang)
                                    self.speak_text(text, lang)
                                    time.sleep(2)
                                    if i==2:
                                        self.button_value = None
                        else:
                            self.button_input = False
                            self.button_value = None
                            self.button_key = None

                        # ----------------------------------------- case search type voice input --------------------------------------------
                        if not self.button_input:
                            max_attempts = 3
                            attempt = 0
                            case_search_type = None

                            while attempt < max_attempts and case_search_type is None:
                                if self.button_input:
                                    break
                                attempt += 1
                                voice_input = self.listen(lang=lang)
                                self.text_input.delete(0, ctk.END)
                                self.text_input.insert(0, str(voice_input))

                                if voice_input is not None:
                                    voice_input_lower = voice_input.lower()

                                    if any(word in voice_input_lower for word in ['1', 'one', 'ek', 'एक', 'ਇੱਕ', 'cnr', 'cnr number']):
                                        case_search_type = 'cnr number'
                                    elif any(word in voice_input_lower for word in ['2', 'two', 'do', 'दो', 'ਦੋ', 'filing', 'filing number']):
                                        case_search_type = 'filing number'
                                    elif any(word in voice_input_lower for word in ['3', 'three', 'teen', 'तीन', 'ਤਿੰਨ', 'registration', 'registration number']):
                                        case_search_type = 'registration number'
                                    elif any(word in voice_input_lower for word in ['4', 'four', 'char', 'चार', 'ਚਾਰ', 'fir', 'fir number']):
                                        case_search_type = 'fir number'
                                    elif any(word in voice_input_lower for word in ['5', 'five', 'panch', 'पांच', 'ਪੰਜ', 'party', 'party name']):
                                        case_search_type = 'party name'
                                    elif any(word in voice_input_lower for word in ['6', 'six', 'cheh', 'छह', 'ਛੇ', 'subordinate', 'subordinate court']):
                                        case_search_type = 'subordinate court'
                                    else:
                                        translated_text = self.translate_text("No valid case search type recognized. Please try again.", source='en', target=lang)
                                        self.speak_text(translated_text, lang=lang)
                                else:
                                    translated_text = self.translate_text("I couldn't understand your input. Please try again.", source='en', target=lang)
                                    self.speak_text(translated_text, lang=lang)

                            # After loop ends, if still not valid
                            if case_search_type is None:
                                final_error = self.translate_text("Failed to detect valid search type after 3 attempts.", source='en', target=lang)
                                self.speak_text(final_error, lang=lang)
                        else:
                                self.button_value = None
                                self.button_key = None
                                self.button_input = False

                        # If we got a valid search type
                        if case_search_type is not None:
                            prompt_text = self.translate_text(text=f"Ok you have selected {case_search_type}.", source='en', target=lang)
                            self.speak_text(prompt_text, lang='en')
                        elif case_search_type is None:
                            prompt_text = self.translate_text(text=f"No Valid Case Search Type.", source='en', target=lang)
                            self.speak_text(prompt_text, lang='en')
                
                # -----------------------------------------------------------------------------------------------------------------------
                        # CNR Number
                        if any(word in case_search_type for word in ['1', 'one', 'ek', 'एक', 'ਇੱਕ', 'cnr', 'cnr number']):
                            translated_text = self.translate_text(text="Please speak CNR Number.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)

                            cnr_number = self.listen(lang=lang, timeout=10).upper().replace(" ", "")
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(cnr_number))

                            # Make POST request using APIClient instance
                            response = self.client.post("cnr", {"cnr_number": cnr_number})

                            # === Handle API errors ===
                            if response.get("status") != 200:
                                error_text = self.translate_text(
                                    f"Failed to fetch CNR case data. Kindly check the connection.", source='en', target=lang)
                                self.speak_text(error_text, lang=lang)

                            # === Handle empty response data ===
                            elif not response.get("data"):
                                no_data_text = self.translate_text(
                                    "No case found for this CNR number. Please try again.", source='en', target=lang)
                                self.speak_text(no_data_text, lang=lang)

                            # === Handle successful response ===
                            else:
                                result = APIClient.api_response(response)
                                translated_text = self.translate_text(result, source='en', target=lang)
                                self.speak_text(translated_text, lang=lang)

                        # Filing Number
                        elif any(word in case_search_type for word in ['2', 'two', 'do', 'दो', 'ਦੋ', 'filing', 'filing number']):
                            # Step 1: Ask for Filing Number
                            translated_text = self.translate_text("Please speak Filing Number.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            
                            filing_number = self.listen(lang=lang).upper().replace(" ", "/")  # e.g., F/2025/00123
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(filing_number))

                            # Step 2: Ask for Year
                            translated_text = self.translate_text("Please speak year.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)

                            year = str(self.listen_case_year(lang=lang))
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(year))

                            # Step 3: Make API Call
                            response = self.client.post("filing", {
                                "filing_number": filing_number,
                                "year": year
                            })

                            # Step 4: Handle Non-200 Response
                            if response.get("status") != 200:
                                error_text = self.translate_text(
                                    f"Failed to fetch Filing case data. Kindly check the connection.", source='en', target=lang)
                                self.speak_text(error_text, lang=lang)

                            # Step 5: Handle No Data
                            elif not response.get("data"):
                                no_data_text = self.translate_text(
                                    "No case found for this filing number and year. Please try again.", source='en', target=lang)
                                self.speak_text(no_data_text, lang=lang)

                            # Step 6: Success
                            else:
                                result = APIClient.api_response(response)
                                translated_text = self.translate_text(result, source='en', target=lang)
                                self.speak_text(translated_text, lang=lang)

                        # Registration Number
                        elif any(word in case_search_type for word in ['3', 'three', 'teen', 'तीन', 'ਤਿੰਨ', 'registration', 'registration number']):
                            # Step 1: Ask for Case Type
                            translated_text = self.translate_text("Please speak Case Type.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            case_type = self.listen(lang=lang)
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(case_type))

                            # Step 2: Ask for Registration Number
                            translated_text = self.translate_text("Please speak Registration Number.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            registration_number = self.listen(lang=lang).upper().replace(" ", "/")
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(registration_number))

                            # Step 3: Ask for Year
                            translated_text = self.translate_text("Please speak Year.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            year = str(self.listen_case_year(lang=lang))
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(year))

                            # Step 4: Make API Call
                            response = self.client.post("registration", {
                                "case_type": case_type,
                                "registration_number": registration_number,
                                "year": year
                            })

                            # Step 5: Handle API Failure
                            if response.get("status") != 200:
                                error_message = self.translate_text(
                                    f"Failed to fetch Registration case data. Kindly check the connection.", source='en', target=lang)
                                self.speak_text(error_message, lang=lang)

                            # Step 6: Handle No Data
                            elif not response.get("data"):
                                no_data_text = self.translate_text(
                                    "No case found for this registration number. Please try again.", source='en', target=lang)
                                self.speak_text(no_data_text, lang=lang)

                            # Step 7: Success Response
                            else:
                                result = APIClient.api_response(response)
                                translated_text = self.translate_text(result, source='en', target=lang)
                                self.speak_text(translated_text, lang=lang)

                        # FIR Search
                        elif any(word in case_search_type for word in ['4', 'four', 'char', 'चार', 'ਚਾਰ', 'fir', 'fir number']):
                            # Step 1: Ask for State
                            translated_text = self.translate_text("Please speak State name.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            state = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(state))

                            # Step 2: District
                            translated_text = self.translate_text("Please speak District name.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            district = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(district))

                            # Step 3: Police Station
                            translated_text = self.translate_text("Please speak Police Station name.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            police_station = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(police_station))

                            # Step 4: FIR Number
                            translated_text = self.translate_text("Please speak FIR Number.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            fir_number = self.listen(lang=lang).upper().replace(" ", "/")
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(fir_number))

                            # Step 5: Year
                            translated_text = self.translate_text("Please speak case year.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            year = str(self.listen_case_year(lang=lang))
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(year))

                            # Step 6: Case Status
                            translated_text = self.translate_text("Please speak case status.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            status = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(status))

                            # Step 7: API Call
                            response = self.client.post("fir", {
                                "state": state,
                                "district": district,
                                "police_station": police_station,
                                "fir_number": fir_number,
                                "year": year,
                                "status": status
                            })

                            # Step 8: API Error Handling
                            if response.get("status") != 200:
                                error_message = self.translate_text(
                                    f"Failed to fetch FIR case data. Kindly check the connection.", source='en', target=lang)
                                self.speak_text(error_message, lang=lang)

                            # Step 9: No Data Found
                            elif not response.get("data"):
                                no_data_text = self.translate_text(
                                    "No FIR case found for the provided details. Please try again.", source='en', target=lang)
                                self.speak_text(no_data_text, lang=lang)

                            # Step 10: Success
                            else:
                                result = APIClient.api_response(response)
                                translated_text = self.translate_text(result, source='en', target=lang)
                                self.speak_text(translated_text, lang=lang)

                        # Party Search
                        elif any(word in case_search_type for word in ['5', 'five', 'panch', 'पांच', 'ਪੰਜ', 'party', 'party name']):
                            # Step 1: Petitioner Name
                            translated_text = self.translate_text("Please speak Petitioner Name.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            petitioner_name = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(petitioner_name))

                            # Step 2: Respondent Name
                            translated_text = self.translate_text("Please speak Respondent Name.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            respondent_name = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(respondent_name))

                            # Combine both
                            party_name = f"{petitioner_name} vs {respondent_name}"

                            # Step 3: Case Status
                            translated_text = self.translate_text("Please speak case status.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            status = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(status))

                            # Step 4: API Call
                            response = self.client.post("party", {
                                "petitioner_respondent": party_name,
                                "status": status
                            })

                            # Step 5: Error Handling
                            if response.get("status") != 200:
                                error_message = self.translate_text(
                                    f"Failed to fetch Party case data. Kindly check the connection.", source='en', target=lang)
                                self.speak_text(error_message, lang=lang)

                            # Step 6: No Data Found
                            elif not response.get("data"):
                                no_data_text = self.translate_text(
                                    "No party name case found for the provided details. Please try again.", source='en', target=lang)
                                self.speak_text(no_data_text, lang=lang)

                            # Step 7: Success
                            else:
                                result = APIClient.api_response(response)
                                translated_text = self.translate_text(result, source='en', target=lang)
                                self.speak_text(translated_text, lang=lang)

                        # Subordinate Search
                        elif any(word in case_search_type for word in ['6', 'six', 'cheh', 'छह', 'ਛੇ', 'subordinate', 'subordinate court']):
                            # Step 1: Ask for State
                            translated_text = self.translate_text("Please speak state name.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            state = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(state))

                            # Step 2: Ask for District
                            translated_text = self.translate_text("Please speak district name.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            district = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(district))

                            # Step 3: Get court name from selected establishment
                            court_name = self.court_establishment.title()

                            # Step 4: Ask for Judge Name
                            translated_text = self.translate_text("Please speak case judge name.", source='en', target=lang)
                            self.speak_text(translated_text, lang=lang)
                            judge_name = self.listen(lang=lang).title()
                            self.text_input.delete(0, ctk.END)
                            self.text_input.insert(0, str(judge_name))

                            # Step 5: API Call
                            response = self.client.post("subordinate", {
                                "state": state,
                                "district": district,
                                "subordinate_court_name": court_name,
                                "judge_name": judge_name
                            })

                            # Step 6: Error Handling
                            if response.get("status") != 200:
                                error_message = self.translate_text(
                                    f"Failed to fetch Subordinate court case data. Kindly check the connection.", source='en', target=lang)
                                self.speak_text(error_message, lang=lang)

                            # Step 7: No Data Found
                            elif not response.get("data"):
                                no_data_text = self.translate_text(
                                    "No case found for this subordinate court. Please try again.", source='en', target=lang)
                                self.speak_text(no_data_text, lang=lang)

                            # Step 8: Success
                            else:
                                result = APIClient.api_response(response)
                                translated_text = self.translate_text(result, source='en', target=lang)
                                self.speak_text(translated_text, lang=lang)

                        else:
                            retry_text = self.translate_text("No valid case search type recognized. Please try again.", source='en', target=lang)
                            self.speak_text(retry_text, lang=lang)
                    except Exception as e:
                        print("Case search communication error: ", e)
                case_search_communication()
        
        # =============================================== ADVOCATE SEARCH ======================================================
            # Advocate Search
            elif any(word in self.search_type for word in ['2', 'two', 'do', 'दो', 'ਦੋ', 'advocate', 'वकील', 'ਵਕੀਲ']):
                # Step 1: Ask Advocate Name
                translated_text = self.translate_text("Please speak advocate name.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                advocate_name = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(advocate_name))

                # Step 2: Ask Case Status
                translated_text = self.translate_text("Please speak case status.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                status = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(status))

                # Step 3: API Call
                response = self.client.post("advocate", {
                    "advocate_name": advocate_name,
                    "status": status
                })

                # Step 4: Error Handling
                if response.get("status") != 200:
                    error_message = self.translate_text(
                        f"Failed to fetch Advocate case data. Kindly check the connection.", source='en', target=lang)
                    self.speak_text(error_message, lang=lang)

                # Step 5: No Data Found
                elif not response.get("data"):
                    no_data_text = self.translate_text(
                        "No case found for this advocate. Please try again.", source='en', target=lang)
                    self.speak_text(no_data_text, lang=lang)

                # Step 6: Success
                else:
                    result = APIClient.api_response(response)
                    translated_text = self.translate_text(result, source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)

        # =============================================== CAUSE LIST SEARCH ====================================================
            # Cause List Search
            elif any(word in self.search_type for word in ['3', 'three', 'teen', 'तीन', 'ਤਿੰਨ', 'cause list', 'कारण सूची', 'ਕਾਰਨ ਸੂਚੀ']):
                # Step 1: Get Court Name from Selected Establishment
                court_name = self.court_establishment.title()

                # Step 2: Ask Court Type
                translated_text = self.translate_text("Please speak case type.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                court_type = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(court_type))

                # Step 3: API Call
                response = self.client.post("cause_list", {
                    "court_name": court_name,
                    "court_type": court_type
                })

                # Step 4: Handle Invalid HTTP Response
                if response.get("status") != 200:
                    error_message = self.translate_text(
                        f"Failed to fetch Cause list data. Kindly check the connection.", source='en', target=lang)
                    self.speak_text(error_message, lang=lang)

                # Step 5: Handle No Data
                elif not response.get("data"):
                    no_data_text = self.translate_text(
                        "No data found for this cause list. Please try again.", source='en', target=lang)
                    self.speak_text(no_data_text, lang=lang)

                # Step 6: Handle Success
                else:
                    result = APIClient.api_response(response)
                    translated_text = self.translate_text(result, source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)

        # =============================================== LOK ADALAT REPORT ====================================================
            # Lok Adalat Report
            elif any(word in self.search_type for word in ['4', 'four', 'char', 'चार', 'ਚਾਰ', 'lok adalat', 'लोक अदालत', 'ਲੋਕ ਅਦਾਲਤ']):
                # Step 1: Ask for Case Status
                translated_text = self.translate_text(text="Please speak case status.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                status = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(status))
                
                # Step 2: Ask if Lok Adalat
                translated_text = self.translate_text(text="Please speak lok adalat (yes or no).", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                lokadalat_resp = self.listen(lang=lang).lower()
                lokadalat = 'Yes' if any(word in lokadalat_resp for word in ['yes', 'yeah', 'haan', 'ਹਾਂ', 'हाँ']) else 'No'
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(lokadalat))
                
                # Step 3: Ask for Panel
                translated_text = self.translate_text(text="Please speak panel.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                panel = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(panel))
                
                # Step 4: API Call
                response = self.client.post("lokadalat", {
                    "status": status,
                    "lokadalat": lokadalat,
                    "panel": panel
                })

                # Step 5: Error & Empty Handling
                if response.get("status") != 200:
                    error_message = self.translate_text(
                        f"Failed to fetch Lok Adalat data. Kindly check the connection.", source='en', target=lang)
                    self.speak_text(error_message, lang=lang)
                
                elif not response.get("data"):
                    no_data_text = self.translate_text(
                        "No data found for this Lok Adalat query. Please try again.", source='en', target=lang)
                    self.speak_text(no_data_text, lang=lang)

                else:
                    result = APIClient.api_response(response)
                    translated_text = self.translate_text(result, source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)

        # =============================================== CAVEAT SEARCH ========================================================
            # Caveat Search
            elif any(word in self.search_type for word in ['5', 'five', 'panch', 'पांच', 'ਪੰਜ', 'caveat', 'कैविएट', 'ਕੇਵੀਅਟ']):
                # Step 1: Ask for Caveat Type
                translated_text = self.translate_text(text="Please speak caveat type.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                caveat_type = self.listen(lang=lang).title().strip()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, caveat_type)
                
                # Step 2: Ask for Caveator Name
                translated_text = self.translate_text(text="Please speak caveator name.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                caveator_name = self.listen(lang=lang).title().strip()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, caveator_name)
                
                # Step 3: Ask for Caveatee Name
                translated_text = self.translate_text(text="Please speak caveatee name.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                caveatee_name = self.listen(lang=lang).title().strip()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, caveatee_name)
                
                # Step 4: Make API Call
                response = self.client.post("caveat", {
                    "caveat_type": caveat_type,
                    "caveator_name": caveator_name,
                    "caveatee_name": caveatee_name
                })

                # Step 5: Response Handling
                if response.get("status") != 200:
                    error_message = self.translate_text(f"Failed to fetch Caveat data. Kindly check the connection.", source='en', target=lang)
                    self.speak_text(error_message, lang=lang)
                elif not response.get("data"):
                    no_data_text = self.translate_text("No data found for this Caveat query. Please try again.", source='en', target=lang)
                    self.speak_text(no_data_text, lang=lang)
                else:
                    result = APIClient.api_response(response)
                    translated_text = self.translate_text(result, source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)

        # =============================================== PANEL SEARCH =========================================================
            # Panel Search
            elif any(word in self.search_type for word in ['6', 'six', 'cheh', 'छह', 'ਛੇ', 'panel', 'पैनल', 'ਪੈਨਲ']):
                # Step 1: Ask for Police Station
                translated_text = self.translate_text(text="Please tell me police station name.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                police_station = self.listen(lang=lang).title().strip()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, police_station)
                
                # Step 2: Ask for FIR Type (e.g., IPC 420/506)
                translated_text = self.translate_text(text="Please tell me FIR Type.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                fir_type = self.listen(lang=lang).upper().strip()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, fir_type)

                # Step 3: Ask for FIR Number
                translated_text = self.translate_text(text="Please speak FIR number.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                fir_number = self.listen(lang=lang).upper().replace(" ", "/").strip()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, fir_number)

                # Step 4: Ask for Case Year
                translated_text = self.translate_text(text="Please speak case year.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                year = str(self.listen_case_year(lang=lang)).strip()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, year)

                # Step 5: Send Data to API
                response = self.client.post("pre_panel", {
                    "police_station": police_station,
                    "fir_type": fir_type,
                    "fir_number": fir_number,
                    "year": year
                })

                # Step 6: Handle Response
                if response.get("status") != 200:
                    error_text = self.translate_text("Failed to fetch FIR Panel data. Kindly check the connection.", source='en', target=lang)
                    self.speak_text(error_text, lang=lang)
                elif not response.get("data"):
                    no_data_text = self.translate_text("No data found for this FIR panel query.", source='en', target=lang)
                    self.speak_text(no_data_text, lang=lang)
                else:
                    result = APIClient.api_response(response)
                    translated_text = self.translate_text(result, source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
        
        # ======================================================================================================================

            else:
                retry_text = self.translate_text("No valid search type recognized. Please try again.", source='en', target=lang)
                self.speak_text(retry_text, lang=lang)

            self.stop_system = False
            self.camera_pause = False
            self.listen_pause = False
            self.speak_pause = False
            self.button_input = False
    
        except Exception as e:
            print(f"Conversation Error: {e}.")
            traceback.print_exc()
    
    # ===================================================================================================

    # ======================================== Destructor ===============================================
    def __del__(self):
        try:
            if os.path.exists("speech.mp3"):
                try:
                    os.remove("speech.mp3")
                except Exception:
                    pass
            if self.reset_timer is not None:
                try:
                    self.reset_timer.cancel()
                    if hasattr(self.reset_timer, "is_alive") and self.reset_timer.is_alive():
                        self.reset_timer.join(timeout=0.5)
                except Exception:
                    pass
        except Exception:
            pass
    
    # ===================================================================================================

    # =============================== helpers added for robustness & performance ========================
    def _update_camera_image(self, pil_img: Image.Image):
        """
        Create CTkImage and update the label on the MAIN thread.
        Keeps a strong reference to prevent Tk image GC issues.
        """
        try:
            ctk_img = ctk.CTkImage(light_image=pil_img, size=(920, 460))
            self._current_ctk_frame_image = ctk_img  # keep a reference!
            self.image_label.configure(image=ctk_img)
            self.image_label.image = ctk_img
        except Exception as e:
            print(f"[ERROR] Could not update camera frame in UI: {e}")

    def _tk_report_callback_exception(self, exc, val, tb):
        """Capture Tkinter callback errors without crashing."""
        print("\n[Tkinter callback error]", file=sys.stderr)
        traceback.print_exception(exc, val, tb)

    def _safe_exit_cleanup(self):
        """Ensure resources are freed on unexpected interpreter exit."""
        try:
            self.is_camera_running = False
            if self.cap is not None:
                self.cap.release()
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.quit()
        except Exception:
            pass

# #######################################################################################################

if __name__ == "__main__":
    root = ctk.CTk()
    tts = HighCourt(root)
    root.mainloop()

