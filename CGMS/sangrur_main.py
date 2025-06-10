import os
import json
from gtts import gTTS
import pygame
import time
import customtkinter as ctk
from tkinter import messagebox, ttk
from deep_translator import GoogleTranslator
import speech_recognition as sr
from PIL import Image
import cv2
import threading
import requests
import re
from difflib import get_close_matches
import winsound
import datetime
import subprocess
import psutil
import sys
import urllib.request


class APIClient:
    BASE_URL = "http://192.168.1.81:8000/search"

    def __init__(self):
        self.session = requests.Session()

    def post(self, endpoint: str, params: dict):
        encoded_params = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}/{endpoint}?{encoded_params}"
        try:
            response = self.session.post(url, headers={"accept": "application/json"})
            print(f"\n[INFO] URL: {url}")
            print(f"[INFO] Status Code: {response.status_code}")
            print(f"[INFO] Response: {response.json()}")
        except Exception as e:
            print(f"[ERROR] Failed to connect to {url}")
            print(f"[ERROR] {str(e)}")

class HighCourt:
    # =========================================== Constructore ==========================================
    def __init__(self, root):
        self.start_sound = "C:\\Windows\\Media\\chimes.wav"
        self.end_sound = "C:\\Windows\\Media\\notify.wav"

        self.client = APIClient()
        self.root = root
        self.root.attributes("-fullscreen", True)
        self.root.title("Court Case Information System")

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        pygame.mixer.init()

        # Initialize the reset_timer before any other method calls
        self.reset_timer = None

        # Load authentication data
        self.load_auth_data()

        # Reset flags after inactivity
        self.reset_flags_after_inactivity()

        # Flags
        self.camera_pause = False
        self.speak_pause = False
        self.conversation_pause = False
        self.listen_pause = False

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
        self.is_running = False
        self.detection_thread = None
        self.face_detected = False
        self.face_detection_cooldown = False
        
        # Create frame for camera feed
        self.image_frame = ctk.CTkFrame(
            self.main_frame,
            width=950,
            height=530,
            fg_color="transparent",
            border_width=3,
            border_color="black",
            corner_radius=10,
        )
        self.image_frame.pack(padx=10, pady=10)
        
        # Create label for camera feed
        self.image_label = ctk.CTkLabel(self.image_frame, text="", width=940, height=520)
        self.image_label.pack(padx=5, pady=5)
        
        self.start_camera()

        # Label for the text input box
        self.text_input_label = ctk.CTkLabel(self.main_frame, 
                                            text="ਖੋਜ", 
                                            font=ctk.CTkFont(size=32, weight="bold"))
        self.text_input_label.pack(padx=10, pady=10)

        # ------------- Create a frame to hold the manual input button and mic button ---------------
        self.input_frame = ctk.CTkFrame(self.main_frame, 
                                        width=900, 
                                        height=200,
                                        fg_color="transparent"
                                        )
        self.input_frame.pack(padx=20, pady=10)
        
        # Load microphone image once
        self.mic_image = self.load_image("images/mic2.png", (100, 100))
        self.mic_button = ctk.CTkButton(
            self.input_frame,
            command=self.face_mic_conversation,
            font=ctk.CTkFont(size=38, weight="bold"),
            fg_color="pink",
            text_color="red",
            height=200,
            width=430,
            border_width=2,
            border_color="black",
            corner_radius=30,
            image=self.mic_image,
            text="Mic Input"
        )
        self.mic_button.pack(side="left", padx=(25, 20), pady=10)

        # Load Manual Input image once
        self.manual_image = self.load_image("images/hand.png", (100, 100))
        self.manual_button = ctk.CTkButton(
            self.input_frame,
            command=self.manual_conversation,
            font=ctk.CTkFont(size=38, weight="bold"),
            fg_color="pink",
            text_color="red",
            height=200,
            width=430,
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
                                    font=ctk.CTkFont(size=24, weight="bold"), 
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
            command=lambda: self.process_case_details(case_id=None, lang="en", input_from_button=True),
            font=ctk.CTkFont(size=24, weight="bold"),
            fg_color="#573AC0",
            text_color="white",
            height=125,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=30
        )
        self.english_button.pack(side="left", padx=30, pady=10)

        self.hindi_button = ctk.CTkButton(
            self.button_frame,
            text="हिंदी बोलें",
            command=lambda: self.process_case_details(case_id=None, lang="hi", input_from_button=True),
            font=ctk.CTkFont(size=24, weight="bold"),
            fg_color="#573AC0",
            text_color="white",
            height=125,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=30
        )
        self.hindi_button.pack(side="left", padx=30, pady=10)

        self.punjabi_button = ctk.CTkButton(
            self.button_frame,
            text="ਹਿੰਦੀ ਬੋਲੋ",
            command=lambda: self.process_case_details(case_id=None, lang="pa", input_from_button=True),
            font=ctk.CTkFont(size=24, weight="bold"),
            fg_color="#573AC0",
            text_color="white",
            height=125,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=30
        )
        self.punjabi_button.pack(side="left", padx=30, pady=10)
        
        # Create a frame to act as a solid border
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
            height=480,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="gray",
            fg_color="white",
            wraplength=530,
            padx=10,
            pady=10
        )
        self.subtitle_label.pack(padx=5, pady=5)

        # Initialize translators
        self._translators = {}
        
        # --------------- Buttons for stop, close and rese the application --------------------
        self.last_button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.last_button_frame.pack(padx=10, pady=10)

        # Stop button
        self.stop_button = ctk.CTkButton(
            self.last_button_frame,
            text="Stop",
            command=self.stop_application,
            font=ctk.CTkFont(size=38, weight="bold"),
            fg_color="olive",
            text_color="white",
            height=150,
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
            command=self.show_password_popup,
            font=ctk.CTkFont(size=38, weight="bold"),
            fg_color="maroon", 
            text_color="white",
            height=150,
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
            height=150,
            width=250,
            border_width=2,
            border_color="black",
            corner_radius=40
        )
        self.reset_button.pack(side="left", padx=30, pady=10)
        
        # Register cleanup function to release camera resources
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

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
    
    # ===================================================================================================

    # ========================================= Reset Application =======================================
    def reset_flags_after_inactivity(self):
        if self.reset_timer is not None:
            self.reset_timer.cancel()
        
        self.reset_timer = threading.Timer(90.0, self.reset_flags)
        self.reset_timer.start()
     
    def on_action_performed(self):
        self.reset_flags_after_inactivity()
    
    def reset_flags(self):
        if self.is_chrome_open:
            self.close_chrome()

        if self.camera_pause:
            self.camera_pause = False
        if self.speak_pause or self.conversation_pause or self.listen_pause:
            self.speak_pause = False
            self.conversation_pause = False
            self.listen_pause = False
        self.face_detection_cooldown = False
    
    def false_flags(self):
        if self.speak_pause or self.conversation_pause or self.listen_pause:
            self.speak_pause = False
            self.conversation_pause = False
            self.listen_pause = False
    
    # ===================================================================================================

    # ========================================= face detection ==========================================    
    def start_camera(self):
        """Start the camera and face detection thread"""
        self.on_action_performed()
        self.cap = cv2.VideoCapture(0)  # 0 is usually the built-in webcam
        self.is_running = True
        
        # Start detection in a separate thread
        self.detection_thread = threading.Thread(target=self.detect_faces)
        self.detection_thread.daemon = True
        self.detection_thread.start()
    
    def detect_faces(self):
        """Thread function for face detection with minimum and maximum range control"""
        self.on_action_performed()
        last_detection_time = 0
        cooldown_period = 10
        min_face_size = (160, 160) 
        max_face_size = (250, 250)
        
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret or self.camera_pause:
                time.sleep(0.1)
                continue
                
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces with min/max size constraints
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=min_face_size,
                maxSize=max_face_size
            )
            
            # Convert frame to PIL format for displaying
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Draw detection zone (center 60% of the frame)
            height, width = frame.shape[:2]
            x_start = int(width * 0.3)
            x_end = int(width * 0.7)
            y_start = int(height * 0.2)
            y_end = int(height * 0.8)
            
            # Draw detection zone rectangle
            cv2.rectangle(frame_rgb, (x_start, y_start), (x_end, y_end), (0, 255, 0), 2)
            
            # Add text indicators for range
            cv2.putText(frame_rgb, "Detection Range", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame_rgb, "Min: " + str(min_face_size[0]) + "px", (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
            cv2.putText(frame_rgb, "Max: " + str(max_face_size[0]) + "px", (10, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
            
            face_in_zone = False

            # Draw rectangle around the faces with distance indication
            for (x, y, w, h) in faces:
                if self.camera_pause:
                    break

                face_size = max(w, h)
                
                # Determine if face is in optimal range
                in_range = min_face_size[0] <= face_size <= max_face_size[0]
                
                # Check if face is in detection zone
                face_center_x = x + w // 2
                face_center_y = y + h // 2
                
                if (x_start < face_center_x < x_end and 
                    y_start < face_center_y < y_end and in_range):
                    # Face is in detection zone and optimal range - draw blue rectangle
                    cv2.rectangle(frame_rgb, (x, y), (x+w, y+h), (255, 0, 0), 3)
                    face_in_zone = True
                elif (x_start < face_center_x < x_end and y_start < face_center_y < y_end):
                    # Face is in zone but not in optimal range - draw yellow rectangle
                    cv2.rectangle(frame_rgb, (x, y), (x+w, y+h), (0, 255, 255), 2)
                else:
                    # Face is outside detection zone - draw green rectangle
                    cv2.rectangle(frame_rgb, (x, y), (x+w, y+h), (0, 255, 0), 2)

            # Check if we should trigger case number
            current_time = time.time()

            if face_in_zone and not self.face_detection_cooldown and (current_time - last_detection_time > cooldown_period):
                self.face_detected = True
                last_detection_time = current_time
                self.face_detection_cooldown = True
                
                self.root.after(0, self.face_mic_conversation)
            
            # Convert the image to PIL format for CTkLabel
            pil_img = Image.fromarray(frame_rgb)
            ctk_img = ctk.CTkImage(light_image=pil_img, size=(920, 480))
            
            # Update the label with the new image (in the main thread)
            self.root.after(0, lambda: self.image_label.configure(image=ctk_img))
            
            # Small delay to reduce CPU usage
            time.sleep(0.03)  # ~30 FPS

    # ===================================================================================================

    # ========================================= authentication ==========================================
    def on_closing(self):
        """Release resources and close application."""
        self.is_running = False
        if self.reset_timer is not None:
            self.reset_timer.cancel()  # Cancel the timer
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()
        if pygame.mixer.get_init() is not None:
            pygame.mixer.quit()
        self.root.destroy()

    def show_password_popup(self):
        """Show a password entry popup with a numeric keypad."""
        self.on_action_performed()
        self.password_window = ctk.CTkToplevel(self.root)
        self.password_window.title("Password Verification")
        self.password_window.geometry("360x480")  # Increased height to accommodate new buttons
        self.password_window.resizable(False, False)

        # Keep the pop-up on top and grab focus
        self.password_window.grab_set()  # Prevents clicking outside the window
        self.password_window.focus_force()  # Forces focus on the pop-up

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
                    command=lambda d=digit: self.handle_keypress(d)
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
            command=self.reset_password
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
            command=self.close_password_window
        )
        close_button.grid(row=0, column=1, padx=10, pady=5)

    def reset_password(self):
        """Reset the password field."""
        self.on_action_performed()
        self.password_var.set("")

    def close_password_window(self):
        """Close the password window."""
        self.on_action_performed()
        self.password_window.destroy()

    def handle_keypress(self, key):
        """Handle keypresses for the numeric keypad."""
        self.on_action_performed()
        if key == '⌫':  # Backspace
            self.password_var.set(self.password_var.get()[:-1])
        elif key == '✔':  # Enter
            self.verify_password()
        else:
            self.password_var.set(self.password_var.get() + key)

    def verify_password(self):
        """Verify the entered password and close the app if correct."""
        self.on_action_performed()
        password = self.password_var.get()
        if password:
            for user in self.auth_data:
                if password in user.values():
                    self.on_closing()  # Use on_closing to properly release camera resources
                    return
            messagebox.showerror("Error", "Incorrect password.")
        else:
            messagebox.showwarning("Warning", "Password cannot be empty.")

    def load_auth_data(self):
        """Load authentication data from auth.json."""
        self.on_action_performed()
        try:
            with open("auth.json", "r", encoding="utf-8") as file:
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
        
        self.reset_timer = threading.Timer(0.5, self.reset_flags)
        self.reset_timer.start()

    def stop_application(self):
        """Stop all ongoing operations immediately."""
        self.on_action_performed()

        if self.is_chrome_open():
            self.close_chrome()
        
        # Set all pause flags to True to stop operations
        self.camera_pause = True
        self.speak_pause = True
        self.conversation_pause = True
        self.listen_pause = True
        self.face_detection_cooldown = True
        
        # Stop any ongoing audio playback immediately
        if pygame.mixer.get_init() is not None:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        
        # Clear the subtitle label and text input immediately
        self.subtitle_label.configure(text="")
        
        # Force UI update
        self.root.update()

    def load_image(self, path, size):
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

    def open_chrome(self):
        """Open index.html in Chrome browser in full-screen mode."""
        self.on_action_performed()
        self.camera_pause = True

        url = "http://192.168.1.81:8000/static/index.html"
        
        # Check if backend is running
        if not self.check_backend():
            print("Please ensure the FastAPI server is running (e.g., 'uvicorn main:app --reload').")
            sys.exit(1)
        
        # Path to Chrome executable
        chrome_path = r"C:\\Program Files\\Google\\Chrome\Application\\chrome.exe"
        if not os.path.exists(chrome_path):
            print("Chrome not found at the specified path. Please ensure Chrome is installed.")
            sys.exit(1)
        
        try:
            # Open Chrome in full-screen mode
            process = subprocess.Popen([chrome_path, "--start-fullscreen", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"Opened {url} in Chrome in full-screen mode (PID: {process.pid}).")
        except Exception as e:
            print(f"Error opening Chrome: {e}")
            sys.exit(1)

    def is_chrome_open(self):
        """Check if any Chrome browser instances are running."""
        self.on_action_performed()
        try:
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'].lower() == 'chrome.exe':
                    return True
            return False
        except Exception as e:
            print(f"Error checking for Chrome processes: {e}")
            return False

    def close_chrome(self):
        """Forcefully close all Chrome browser instances."""
        self.on_action_performed()
        self.camera_pause = True

        try:
            closed = False
            # Iterate through all running processes
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'].lower() == 'chrome.exe':
                    try:
                        proc.kill()  # Forcefully terminate the process
                        print(f"Closed Chrome process (PID: {proc.info['pid']}).")
                        closed = True
                    except psutil.NoSuchProcess:
                        pass  # Process already terminated
                    except Exception as e:
                        print(f"Error closing Chrome process (PID: {proc.info['pid']}): {e}")
            
            if not closed:
                pass
        except Exception as e:
            print(f"Error closing Chrome processes: {e}")
    
    # ===================================================================================================
    
    # ==================================== process case details =========================================
    def process_case_details(self, case_id=None, lang="pa", input_from_button=False):
        self.on_action_performed()
        if (case_id==None or case_id=='') and input_from_button:
            self.false_flags()
            self.conversation(lang=lang, input_from_button=input_from_button)
            return
        
        self.camera_pause=True
        self.listen_pause = True
        self.speak_pause = False
        self.conversation_pause = False
        
        BASE_URL = "http://192.168.41.196:8000/cases/"

        # Check if the case details are already cached
        if hasattr(self, 'case_cache') and case_id in self.case_cache:
            case_details = self.case_cache[case_id]
        else:
            def get_case_details(case_id):
                try:
                    response = requests.get(f"{BASE_URL}/{case_id}", timeout=5)
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return None
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching case details: {e}")
                    return None

            case_details = get_case_details(case_id)
            if case_details:
                # Cache the case details
                if not hasattr(self, 'case_cache'):
                    self.case_cache = {}
                self.case_cache[case_id] = case_details

        if case_details:
            case_details_sentence = f"""
            Your case details are as follows: Case Type - {case_details['case_type']}, Case Number - {case_details['case_no']}, and Filing Year - {case_details['case_year']}. 
            The petitioner in this case is {case_details['petitioner_name']}, while the respondent is {case_details['respondent_name']}. 
            The case is being represented by Advocate {case_details['advocate_name']}. Currently, the case status is {case_details['status']}. 
            The next hearing is scheduled for {case_details['next_date']}. Thank you.
            """
            case_details_sentence = self.translate_text(text=case_details_sentence, source='en', target=lang)
            self.speak_text(text=case_details_sentence, lang=lang)
            # ==============================================================================================================================
        else:
            error_message = self.translate_text(text="Case not found.", source='en', target=lang)
            self.speak_text(text=error_message, lang=lang)

        self.listen_pause = False
        
    # ===================================================================================================

    #  ================================ language Speak and Translate ====================================
    def translate_text(self, text, source, target):
        """Translate text from source language to target language."""
        self.on_action_performed()
        if text is None or (source=='en' and target=='en'):
            return text
        
        self.camera_pause = True
        
        key = (source, target)
        if key not in self._translators:
            self._translators[key] = GoogleTranslator(source=source, target=target)
        try:
            return self._translators[key].translate(text)
        except Exception as e:
            print(f"Translation error: {e}")
            return text

    def speak_text(self, text, lang="pa"):
        self.on_action_performed()

        if self.speak_pause or text=='' or text is None or self.conversation_pause:
            return 
        
        self.camera_pause = True
        self.listen_pause = True
        
        try:
            # Remove the existing file if it exists
            if os.path.exists("speech.mp3"):
                os.remove("speech.mp3")

            # Generate the speech file using gTTS
            tts = gTTS(text=text, lang=lang)
            tts.save("speech.mp3")

            # Initialize pygame mixer if not already initialized
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            # Load the speech file into pygame mixer
            pygame.mixer.music.load("speech.mp3")
            pygame.mixer.music.play() # Play the audio

            # Calculate the total duration of the audio
            audio = pygame.mixer.Sound("speech.mp3")
            total_duration = audio.get_length()

            # Split the text into words for real-time display
            words = text.split()
            num_words = len(words)
            duration_per_word = total_duration / max(num_words, 1)  # Avoid division by zero

            # Clear the subtitle label before starting
            if self.root and self.subtitle_label.winfo_exists():
                self.subtitle_label.configure(text="")
                self.root.update()

            # Start time for tracking word display
            start_time = time.time()

            # Display words in real-time as the audio plays
            for word in words:
                if self.speak_pause:
                    return
                
                if self.root and self.subtitle_label.winfo_exists():
                    current_text = self.subtitle_label.cget("text")
                    self.subtitle_label.configure(text=current_text + " " + word)
                    self.root.update()

                # Calculate the elapsed time and sleep accordingly
                elapsed_time = time.time() - start_time
                expected_time = duration_per_word * (words.index(word) + 1)
                sleep_time = max(0, expected_time - elapsed_time)
                time.sleep(sleep_time)

            # Wait for the audio to finish playing
            while pygame.mixer.music.get_busy():
                if self.speak_pause:
                    return
                pygame.time.Clock().tick(10)  # Limit the loop to 10 FPS to reduce CPU usage

            # Clean up pygame mixer
            pygame.mixer.quit()

            self.listen_pause = False

        except Exception as e:
            print(f"Text-to-speech error: {e}")

    def listen(self, lang="pa"):
        self.on_action_performed()

        if self.listen_pause:
            return
        
        self.camera_pause = True

        recognizer = sr.Recognizer()

        with sr.Microphone() as source:
            try:
                winsound.PlaySound(self.start_sound, winsound.SND_FILENAME)
                recognizer.adjust_for_ambient_noise(source)
                status_text = self.translate_text(text="Listening...", source='en', target=lang)
                self.subtitle_label.configure(text=status_text)
                self.root.update()

                # Reduce listening time to 5 seconds
                audio = recognizer.listen(source, timeout=5)
                recognized_text = recognizer.recognize_google(audio, language='en')
                winsound.PlaySound(self.end_sound, winsound.SND_FILENAME)
                return recognized_text

            except sr.UnknownValueError:
                error_message = self.translate_text(text=f"Error, Could not understand audio.", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)
            except sr.RequestError as e:
                error_message = self.translate_text(text=f"Error, Could not request results; {e}", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)
            except Exception as e:
                error_message = self.translate_text(text=f"Error, An error occurred: {e}", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)

            return ""
    
    # ===================================================================================================

    # ======================================= listen case id ============================================
    def number_to_words(self, text):
        self.on_action_performed()
        self.number_words = {
            "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
            "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"
        }
        for num, word in self.number_words.items():
            text = text.replace(num, word)
        return text

    def map_spoken_numbers(self, text, lang='en'):
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

    def listen_case_type(self, lang='pa'):
        self.on_action_performed()

        if self.listen_pause:
            return
        
        self.camera_pause = True

        recognizer = sr.Recognizer()

        with sr.Microphone() as source:
            winsound.PlaySound(self.start_sound, winsound.SND_FILENAME)
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source)

            try:
                recognized_text = recognizer.recognize_google(audio)
                recognized_text = recognized_text.upper()
                print(f"Recognized case type: {recognized_text}")

                words = recognized_text.split()
                for word in reversed(words):
                    if word in self.case_types.keys():
                        return word

                closest_match = get_close_matches(recognized_text, self.case_types.keys(), n=1, cutoff=0.7)
                winsound.PlaySound(self.end_sound, winsound.SND_FILENAME)
                
                if closest_match:
                    return closest_match[0]
                else:
                    for key, value in self.case_types.items():
                        if recognized_text == value.upper():
                            return key
                    
                    status_text = self.translate_text(text=f"Invalid case type: {recognized_text}", source='en', target=lang)
                    self.speak_text(text=status_text, lang=lang)
                    print(f"Invalid case type: {recognized_text}. Valid case types are: {list(self.case_types.keys())}")
                    return None

            except sr.UnknownValueError:
                error_message = self.translate_text(text="Sorry, I could not understand the audio.", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)
            except sr.RequestError as e:
                error_message = self.translate_text(text=f"Could not request results from the speech recognition service; {e}", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)
            except Exception as e:
                error_message = self.translate_text(text=f"An error occurred in listen_case_type: {e}", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)

            return None

    def listen_case_number(self, lang='pa'):
        self.on_action_performed()

        if self.listen_pause:
            return
        
        self.camera_pause = True

        recognizer = sr.Recognizer()

        with sr.Microphone() as source:
            winsound.PlaySound(self.start_sound, winsound.SND_FILENAME)
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source)

            try:
                recognized_text = recognizer.recognize_google(audio, language=lang)
                print(f"Recognized case number: {recognized_text}")

                recognized_text = self.map_spoken_numbers(recognized_text, lang)
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
                    return None

                structured_case_number = f"{numeric_part}-{alphanumeric_part}" if alphanumeric_part else numeric_part

                if re.match(r'^\d+(-\w+)?$', structured_case_number):
                    return structured_case_number
                else:
                    print(f"Invalid case number: {structured_case_number}. Case number must be in the format 'XXXX-XXX' or 'XXXX'.")
                    return None

            except sr.UnknownValueError:
                error_message = self.translate_text(text="Sorry, I could not understand the audio.", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)
            except sr.RequestError as e:
                error_message = self.translate_text(text="Could not request results from the speech recognition service; {e}""Could not request results from the speech recognition service; {e}", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)
            except Exception as e:
                error_message = self.translate_text(text=f"An error occurred in listen_case_number: {e}", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)
            
            return None

    def listen_case_year(self, lang='pa'):
        self.on_action_performed()

        if self.listen_pause:
            return
        
        self.camera_pause = True

        recognizer = sr.Recognizer()

        with sr.Microphone() as source:
            winsound.PlaySound(self.start_sound, winsound.SND_FILENAME)
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source)

            try:
                recognized_text = recognizer.recognize_google(audio, language=lang)
                recognized_text = self.map_spoken_numbers(recognized_text, lang)
                recognized_text = recognized_text.replace("O", "0").replace("o", "0")
                
                winsound.PlaySound(self.end_sound, winsound.SND_FILENAME)

                if recognized_text.isdigit() and len(recognized_text) == 4:
                    return recognized_text
                else:
                    translated_text = self.translate_text(text=f"Invalid case year: {recognized_text}. Case year must be a 4-digit number.", source='en', target=lang)
                    self.speak_text(text=translated_text, lang=lang)
                    return None

            except sr.UnknownValueError:
                error_message = self.translate_text(text="Sorry, I could not understand the audio.", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)
            except sr.RequestError as e:
                error_message = self.translate_text(text=f"Could not request results from the speech recognition service; {e}", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)
            except Exception as e:
                error_message = self.translate_text(text=f"An error occurred: {e}", source='en', target=lang)
                self.speak_text(text=error_message, lang=lang)

            return None

    def listen_case_id(self, lang='pa'):
        self.on_action_performed()

        if self.listen_pause:
            return
        
        self.camera_pause = True

        try:
            status_text = self.translate_text(text="Listening Case Type...", source='en', target=lang)
            self.subtitle_label.configure(text=status_text)
            self.root.update()
            case_type = self.listen_case_type(lang=lang)
            if case_type == None:
                return


            status_text = self.translate_text(text="Listening Case Number...", source='en', target=lang)
            self.subtitle_label.configure(text=status_text)
            self.root.update()
            case_number = self.listen_case_number(lang=lang)
            
            status_text = self.translate_text(text="Listening Case Year...", source='en', target=lang)
            self.subtitle_label.configure(text=status_text)
            self.root.update()
            case_year = self.listen_case_year(lang=lang)

            case_id = f"{case_type}-{case_number}-{case_year}"
            status_text = self.translate_text(text=f"Valid Case ID: {case_id}", source='en', target=lang)
            self.subtitle_label.configure(text=status_text)
            print(f"Valid Case ID: {case_id}")

            return case_id

        except Exception as e:
            print(f"Listen Case Id Error: {e}")    
    
    # ===================================================================================================
    
    # ====================================== Conversation ===============================================
    def generate_greeting(self):
        now = datetime.datetime.now()

        # Greeting and time of day
        h, m = now.hour, now.minute
        if 5 <= h < 12:
            greet, part = "Good Morning", "morning"
        elif 12 <= h < 17:
            greet, part = "Good Afternoon", "afternoon"
        elif 17 <= h < 21:
            greet, part = "Good Evening", "evening"
        else:
            greet, part = "Good Night", "night"

        # Ordinal date
        d = now.day
        suffix = "th" if 10 <= d % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")

        # Time format
        hour12 = h % 12 or 12
        ampm = "am" if h < 12 else "pm"

        return (
            f"{greet}, today is {now.strftime('%A')}, {d}{suffix} {now.strftime('%B')} {now.year}, and the current time is {hour12}:{m:02d}."
        )
    
    def manual_conversation(self):
        "Prompt the user for manual search"
        self.on_action_performed()

        self.stop_application()

        self.open_chrome()

    def face_mic_conversation(self):
        """Prompt the user for case number after face detection"""
        self.on_action_performed()
        
        self.camera_pause = True
        self.false_flags()

        self.conversation(lang='pa', input_from_button=False)
    
    def conversation(self, lang="pa", input_from_button=False):
        """Engage in a conversation based on user input."""
        self.on_action_performed()

        if self.conversation_pause:
            return
        try:
            self.camera_pause = True
            
            if input_from_button:
                if lang=='en':
                    selected_lang = 'english'
                elif lang=='hi':
                    selected_lang = 'hindi'
                else:
                    selected_lang = 'punjabi'
            else:
                prompt_message = f"""
                {self.generate_greeting()}. Kindly select a language. I could understand three languages, Punjabi, English and Hindi. 
                Speak anyone of them. If you want to make a manual search then press Manual Input button.
                """
                prompt_message = self.translate_text(text=prompt_message, source='en', target=lang)
                self.speak_text(prompt_message, lang=lang)
                selected_lang = self.listen(lang=lang)
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(selected_lang))

            # ----------------------------------- Listen language selected_lang --------------------------------------
            if selected_lang is None:
                translated_text = self.translate_text("I couldn't understand your language selection. Please try again.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                return
            
            court_type_text = """
                    Congrats you have selected your language.
                    Kindly tell me court establishment.
                    1. District & Session Court Sangrur
                    2. Criminal Court Sangrur
                    3. Civil Court Sangrur
                """

            if 'english' in selected_lang.lower() and not self.conversation_pause:
                self.speak_text(court_type_text, lang='en')
                lang='en'
            elif 'punjabi' in selected_lang.lower() and not self.conversation_pause:
                translated_prompt = self.translate_text(court_type_text, source="en", target='pa')
                self.speak_text(translated_prompt, lang='pa')
                lang='pa'
            elif 'hindi' in selected_lang.lower() and not self.conversation_pause:
                translated_prompt = self.translate_text(court_type_text, source="en", target='hi')
                self.speak_text(translated_prompt, lang='hi')
                lang='hi'
            else:
                court_type_text = """
                    Congrats you want to continuue with current language.
                    Kindly tell me court establishment.
                    1. District & Session Court Sangrur
                    2. Criminal Court Sangrur
                    3. Civil Court Sangrur
                """
                translated_prompt = self.translate_text(court_type_text, source="en", target='pa')
                self.speak_text(translated_prompt, lang='pa')
                lang='pa'

            
            if not self.conversation_pause:
                court_establishment = self.listen(lang=lang)
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(court_establishment))
            else:
                return

            # ----------------------------------- Listen the court type ------------------------------------
            if court_establishment is not None:
                if any(str(word) in court_establishment.lower() for word in ['1', 'one', 'ek', 'ik', 'district and session court sangarur', 'district', 'session', 'जिला एवं सत्र न्यायालय संगरूर', 'जिला', 'सत्र', 'ਜ਼ਿਲ੍ਹਾ ਅਤੇ ਸੈਸ਼ਨ ਕੋਰਟ ਸੰਗਰੂਰ', 'ਜ਼ਿਲ੍ਹਾ', 'ਸੈਸ਼ਨ', 'एक', 'ਇੱਕ']):
                    court_establishment = 'district & session court sangrur'
                elif any(str(word) in court_establishment.lower() for word in ['2', 'two', 'tu', 'do', 'criminal court sangrur', 'criminal', 'आपराधिक न्यायालय संगरूर', 'आपराधिक', 'ਫੌਜਦਾਰੀ ਅਦਾਲਤ ਸੰਗਰੂਰ', 'ਅਪਰਾਧੀ', 'दो', 'ਦੋ']):
                    court_establishment = 'criminal court sangrur'
                elif any(str(word) in court_establishment.lower() for word in ['3', 'three', 'teen', 'civil court sangrur', 'civil', 'सिविल कोर्ट संगरूर', 'सिविल', 'ਸਿਵਲ ਕੋਰਟ ਸੰਗਰੂਰ', 'ਸਿਵਲ', 'तीन', 'ਤਿੰਨ']):
                    court_establishment = 'civil court sangrur'
                else:
                    translated_text = self.translate_text("No valid court type recognized. Please try again.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    return  
            else:
                translated_text = self.translate_text("I couldn't understand your input. Please try again.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                return

            # ---------------------------------------- Type of Search ---------------------------------------
             # Type of Search Speak
            search_type_text = """What kind of search you want to make.
                                1. Case Search
                                2. Advocate
                                3. Cause List
                                4. Lok Adalat Report
                                5. Search Caveat
                                6. Panel Search
                                """
            translated_text = self.translate_text(text=search_type_text, source='en', target=lang)
            self.speak_text(translated_text, lang=lang)

            if not self.conversation_pause:
                search_type = self.listen(lang=lang)
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(search_type))
            else:
                return

            # Api's comes in under these search types are here.
            # A. Case Search
            search_type = search_type.lower()

            if any(word in search_type for word in ['1', 'one', 'ek', 'एक', 'ਇੱਕ', 'case search', 'मामले की खोज', 'ਕੇਸ ਖੋਜ']):
                # Route to Case Search APIs
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

                if not self.conversation_pause:
                    case_search = self.listen(lang=lang)
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(case_search))
                else:
                    return

                case_search = case_search.lower()

                # CNR Number
                if any(word in case_search for word in ['1', 'one', 'ek', 'एक', 'ਇੱਕ', 'cnr', 'cnr number']):
                    translated_text = self.translate_text(text="Please speak CNR Number.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    cnr_number = self.listen(lang=lang).upper()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(cnr_number))
                    
                    self.client.post("cnr", {"cnr_number": cnr_number})
                
                # Filing Number
                elif any(word in case_search for word in ['2', 'two', 'do', 'दो', 'ਦੋ', 'filing', 'filing number']):
                    translated_text = self.translate_text(text="Please speak Filing Number.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    filing_number = self.listen(lang=lang).upper() # F/2025/00123
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(filing_number))

                    translated_text = self.translate_text(text="Please speak year.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    year = str(self.listen_case_year(lang=lang))
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(year))
                    
                    self.client.post("filing", {
                        "filing_number": filing_number,
                        "year": year
                    })

                # Registration Number
                elif any(word in case_search for word in ['3', 'three', 'teen', 'तीन', 'ਤਿੰਨ', 'registration', 'registration number']):
                    translated_text = self.translate_text(text="Please speak Case Type.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    case_type = self.listen_case_type(lang=lang)
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(case_type))
                    
                    translated_text = self.translate_text(text="Please speak Registration Number.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    registration_number = self.listen(lang=lang).upper() # REG/2025/78456
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(registration_number))
                    
                    translated_text = self.translate_text(text="Please speak Year.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    year = str(self.listen_case_year(lang=lang))
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(year))

                    self.client.post("registration", {
                        "case_type": case_type,
                        "registration_number": registration_number,
                        "year": year
                    })

                # FIR Search
                elif any(word in case_search for word in ['4', 'four', 'char', 'चार', 'ਚਾਰ', 'fir', 'fir number']):
                    translated_text = self.translate_text(text="Please speak State name.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    state = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(state))

                    translated_text = self.translate_text(text="Please speak District name.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    district = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(district))

                    translated_text = self.translate_text(text="Please speak Police Station name.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    police_station = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(police_station))

                    translated_text = self.translate_text(text="Please speak FIR Number.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    fir_number = self.listen(lang=lang).upper() # FIR123/2025
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(fir_number))

                    translated_text = self.translate_text(text="Please speak case year.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    year = str(self.listen_case_year(lang=lang))
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(year))

                    translated_text = self.translate_text(text="Please speak case status.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    status = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(status))

                    self.client.post("fir", {
                        "state": state,
                        "district": district,
                        "police_station": police_station,
                        "fir_number": fir_number,
                        "year": year,
                        "status": status
                    })

                # Party Search
                elif any(word in case_search for word in ['5', 'five', 'panch', 'पांच', 'ਪੰਜ', 'party', 'party name']):
                    translated_text = self.translate_text(text="Please speak Petitioner Name.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    petitioner_name = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(petitioner_name))
                    
                    translated_text = self.translate_text(text="Please speak Respondent Name.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    respondent_name = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(respondent_name))

                    party_name = f"{petitioner_name} vs {respondent_name}"

                    translated_text = self.translate_text(text="Please speak case status.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    status = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(status))

                    self.client.post("party", {
                        "petitioner_respondent": party_name,
                        "status": status
                    })

                # Subordinate Search
                elif any(word in case_search for word in ['6', 'six', 'cheh', 'छह', 'ਛੇ', 'subordinate', 'subordinate court']):
                    translated_text = self.translate_text(text="Please speak state name.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    state = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(state))

                    translated_text = self.translate_text(text="Please speak district name.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    district = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(district))

                    court_name = court_establishment.title()

                    translated_text = self.translate_text(text="Please speak case judge name.", source='en', target=lang)
                    self.speak_text(translated_text, lang=lang)
                    judge_name = self.listen(lang=lang).title()
                    self.text_input.delete(0, ctk.END)
                    self.text_input.insert(0, str(judge_name))

                    self.client.post("subordinate", {
                        "state": state,
                        "district": district,
                        "subordinate_court_name": court_name,
                        "judge_name": judge_name
                    })

                else:
                    print("Unrecognized case search type. Please try again.")

            # Advocate Search
            elif any(word in search_type for word in ['2', 'two', 'do', 'दो', 'ਦੋ', 'advocate', 'वकील', 'ਵਕੀਲ']):
                translated_text = self.translate_text(text="Please speak advocate name.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                advocate_name = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(advocate_name))

                translated_text = self.translate_text(text="Please speak case status.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                status = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(status))

                self.client.post("advocate", {
                    "advocate_name": advocate_name,
                    "status": status
                })
            
            # Cause List Search
            elif any(word in search_type for word in ['3', 'three', 'teen', 'तीन', 'ਤਿੰਨ', 'cause list', 'कारण सूची', 'ਕਾਰਨ ਸੂਚੀ']):
                court_name = court_establishment.title()

                translated_text = self.translate_text(text="Please speak case type.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                court_type = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(court_type))

                self.client.post("cause_list", {
                    "court_name": court_name,
                    "court_type": court_type
                })

            # Lok Adalat Report
            elif any(word in search_type for word in ['4', 'four', 'char', 'चार', 'ਚਾਰ', 'lok adalat', 'लोक अदालत', 'ਲੋਕ ਅਦਾਲਤ']):
                translated_text = self.translate_text(text="Please speak case status.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                status = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(status))
                
                translated_text = self.translate_text(text="Please speak lokadalt (yes or no).", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                lokadalat = self.listen(lang=lang).lower()
                lokadalat = 'Yes' if any(item in ['yes', 'yeah'] for item in list(lokadalat)) else 'No'
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(lokadalat))
                
                translated_text = self.translate_text(text="Please speak panle.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                panel = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(panel))
                
                self.client.post("lokadalat", {
                    "status": status,
                    "lokadalat": lokadalat,
                    "panel": panel
                })

            # Caveat Search
            elif any(word in search_type for word in ['5', 'five', 'panch', 'पांच', 'ਪੰਜ', 'caveat', 'कैविएट', 'ਕੇਵੀਅਟ']):
                translated_text = self.translate_text(text="Please speak caveat type.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                caveat_type = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(caveat_type))
                
                translated_text = self.translate_text(text="Please speak caveator name.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                caveator_name = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(caveator_name))
                
                translated_text = self.translate_text(text="Please speak caveatee name.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                caveatee_name = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(caveatee_name))
                
                self.client.post("caveat", {
                    "caveat_type": caveat_type,
                    "caveator_name": caveator_name,
                    "caveatee_name": caveatee_name
                })

            # Panel Search
            elif any(word in search_type for word in ['6', 'six', 'cheh', 'छह', 'ਛੇ', 'panel', 'पैनल', 'ਪੈਨਲ']):
                translated_text = self.translate_text(text="Please tell me police station name.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                police_station = self.listen(lang=lang).title()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(police_station))
                
                translated_text = self.translate_text(text="Please tell me FIR Type.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                fir_type = self.listen(lang=lang).title()   # IPC 420/506
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(fir_type))
                
                translated_text = self.translate_text(text="Please speak FIR number.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                fir_number = self.listen(lang=lang).upper()
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(fir_number))
                
                translated_text = self.translate_text(text="Please speak case year.", source='en', target=lang)
                self.speak_text(translated_text, lang=lang)
                year = self.listen_case_year(lang=lang)
                self.text_input.delete(0, ctk.END)
                self.text_input.insert(0, str(year))
                
                self.client.post("pre_panel", {
                    "police_station": police_station,
                    "fir_type": fir_type,
                    "fir_number": fir_number,
                    "year": year
                })

            else:
                print("No valid option detected. Please try again.")

            self.camera_pause = False
            self.listen_pause = False
        
        except Exception as e:
            print("Conversation error ", e)
    
    # ===================================================================================================

    # ======================================== destructor ===============================================
    def __del__(self):
        self.reset_timer.join()
    
    # ===================================================================================================

if __name__ == "__main__":
    root = ctk.CTk()
    tts = HighCourt(root)
    root.mainloop()



