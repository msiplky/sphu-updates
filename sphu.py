import cv2
import io
import pexpect
import pyudev
import torch
import base64
import getpass
import json
import logging
import sched
import shutil
import signal
from pprint import pprint
import numpy as np
from playsound import playsound
import binascii
import calendar
import datetime
import os.path
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import *
from tkinter import font
from tkinter import ttk, messagebox
import requests
from Crypto.Cipher import AES
# from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad  # pip install pycryptodome
import pyexcel_ods3 as ods
import serial
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageEnhance
import glob
from tkinter import filedialog
import ultralytics

# import folium
# from io import BytesIO
# from firebase_admin import db
# from reportlab.lib.pagesizes import A4
# from reportlab.pdfgen import canvas
# from selenium import webdriver
# from selenium.webdriver.firefox.service import Service
# from common import write_on_image
# from simplelpr_linux.samples.python.simplelpr_demo import main
# from simplelpr_linux.samples.python.new_simplelpr import new_main
# from dtk_image import main, send_image
# from new_dtk_image import new_main
# from plate_recognizer import main
# from new_plate_recognizer import new_main

if getattr(sys, 'frozen', False):
    import pyi_splash

def validate_input(new_value):
    # Check if the new value is empty (allows backspace/delete)
    if new_value == "":
        return True
    # Check if the new value is a digit and its length is 4 or less
    elif new_value.isdigit() and len(new_value) <= 4:
        return True
    else:
        return False

def list_printers():
    try:
        command = 'lpstat -p -d'
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        printer_info = result.stdout.strip().split('\n')

        printers = []
        for line in printer_info:
            if 'printer' in line:
                printer_name = line.split(' ')[1]
                if printer_name.endswith('.local'):
                    printers.append(printer_name)

        return printers
    except Exception as p:
        print("Error listing printers:", p)
        return []


def run_command(command, use_sudo=False):
    try:
        if use_sudo:
            child = pexpect.spawn(f'sudo {command}')
            child.expect('password for .*:')
            child.sendline('nvidia')
            child.expect(pexpect.EOF)
            return child.before.decode().strip()
        else:
            result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
            return result.stdout.strip()
    except Exception as e:
        print(f"Error running command {command}: {e}")
        return None

def get_mounted_devices():
    mount_output = run_command('mount')
    if mount_output is None:
        return []

    devices = []
    for line in mount_output.splitlines():
        if '/media/nvidia/' in line:
            parts = line.split()
            if len(parts) >= 3:
                devices.append(parts[2])
    return devices

def unmount_device(device):
    run_command(f'umount {device}', use_sudo=True)

def remove_directory(directory):
    run_command(f'sudo rm -r {directory}', use_sudo=True)

def create_directory(directory):
    run_command(f'sudo mkdir -p {directory}', use_sudo=True)

def get_all_block_devices():
    ls_output = run_command('ls /dev/sd*')
    if ls_output is None:
        return []

    devices = ls_output.split()
    return devices

def mount_device(device_partition, mount_point):
    run_command(f'sudo mount {device_partition} {mount_point}', use_sudo=True)

def er13():
    external_devices = get_mounted_devices()

    ele_device = None
    for device in external_devices:
        if os.path.basename(device).startswith('Ele'):
            ele_device = device
            break

    if ele_device:
        logging.info(f"Unmounting device: {ele_device}")
        unmount_device(ele_device)

    other_devices = [d for d in external_devices if d != ele_device]

    for device in other_devices:
        logging.info(f"Unmounting other device: {device}")
        unmount_device(device)

    if ele_device:
        ele_directory = ele_device
        logging.info(f"Removing directory: {ele_directory}")
        remove_directory('/media/nvidia/')

    # Create the directory if it doesn't exist
    create_directory('/media/nvidia/Elements')

    # Remount all external devices
    all_block_devices = get_all_block_devices()
    for device in all_block_devices:
        if device.endswith('1'):  # Only consider partitions
            logging.info(f"Mounting device: {device}")
            mount_device(device, '/media/nvidia/Elements')

    logging.info("All devices have been remounted.")


def delete_old_folders(base_folder, days_threshold=5):
    try:
        current_date = datetime.datetime.now()

        for folder_name in os.listdir(base_folder):
            folder_path = os.path.join(base_folder, folder_name)

            # Check if it's a directory
            if os.path.isdir(folder_path):
                # Extract the date from the folder name (assuming the folder name is in YYYY-MM-DD format)
                folder_date_str = folder_name
                folder_date = datetime.datetime.strptime(folder_date_str, "%Y-%m-%d")

                # Calculate the difference in the past days
                days_difference = (current_date - folder_date).days

                # Delete the folder if it's older than the threshold
                if days_difference >= days_threshold:
                    # print(f"Deleting folder: {folder_path}")
                    try:
                        # Use shutil.rmtree to delete the entire folder and its contents
                        shutil.rmtree(folder_path)
                        print(f"Folder deleted successfully: {folder_path}")
                    except Exception as df:
                        print(f"Error deleting folder: {df}")
    except Exception as ex:
        print("exception in delete_old_folders:", ex)


def print_pdf(pdf_path, printer_name):
    try:
        # Use the chosen printer name to print the PDF
        command = f'lpr -P {printer_name} {pdf_path}'
        subprocess.run(command, shell=True)

        print(f"PDF sent to '{printer_name}'.")
    except Exception as pp:
        print("Error printing PDF:", pp)


def get_current_date_folder():
    date = datetime.date.today().strftime("%Y-%m-%d")
    return str(date)


caps_on = False


def open_onboard_keyboard():
    global caps_on
    try:
        try:
            subprocess.Popen(['pkill', 'onboard'])
        except Exception:
            pass
        subprocess.Popen(["onboard"])
        # subprocess.Popen(["sleep", "1"])
        if not caps_on:
            subprocess.Popen(["xdotool", "key", "Caps_Lock"])
            caps_on = True
    except Exception as key:
        print("onboard keyboard", key)


def helmet_write_on_image(image_id, cur_time, current_date, location, officer_name, officer_id, number_plate, laser_id,
                          lat, lon):
    username = getpass.getuser()
    try:
        folder_path = os.path.join(f"/media/{username}/Elements", "helmet_info")
        folder_path = os.path.join(folder_path, str(current_date))
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)

        firebase_folder_path = os.path.join(f"/media/{username}/Elements", "without_helmet")
        main_folder_path = os.path.join(firebase_folder_path, str(current_date))
        firebase_folder_path = os.path.join(main_folder_path, "upload")
        if not os.path.exists(firebase_folder_path):
            os.makedirs(firebase_folder_path, exist_ok=True)
        ff = os.path.join(main_folder_path, f"{image_id}.jpg")
        image = cv2.imread(ff)
        cv2.putText(image, '+', (935, 560), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 2)
        # Add KARNATAKA STATE POLICE DEPARTMENT text in the bottom-left of the image
        cv2.putText(image, "MAHARASHTRA MOTOR VEHICLE DEPARTMENT", (30, image.shape[0] - 220),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)  # (B,G,R)

        # Add LOCATION: followed by location details in the next line
        cv2.putText(image, f"LOCATION: {location}", (30, image.shape[0] - 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Add OFFICER NAME: followed by officer details in next line
        cv2.putText(image, f"OFFICER NAME: {officer_name}", (30, image.shape[0] - 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Add OFFICER ID: followed by officer id details in next line
        cv2.putText(image, f"OFFICER ID: {officer_id}", (30, image.shape[0] - 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Add NUMBER PLATE: followed by num plate in next line
        cv2.putText(image, f"NUMBER PLATE: {number_plate}", (30, image.shape[0] - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Add OFFENCE TIME: followed by offence time in next line
        cv2.putText(image, f"OFFENCE TIME: {cur_time}", (30, image.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        y_start = 100  # Starting y-coordinate for the text
        x_start = image.shape[1] - 400  # Starting x-coordinate for the text

        latitude = "GPS Unavailable" if lat == '' else lat
        longitude = "GPS Unavailable" if lon == '' else lon

        # Add latitude text
        cv2.putText(image, f"LATITUDE: {latitude}", (x_start, y_start),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        y_start += 40

        # Add longitude text
        cv2.putText(image, f"LONGITUDE: {longitude}", (x_start, y_start),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        y_start += 40

        # Add device ID text
        cv2.putText(image, f"DEVICE ID: {laser_id}", (x_start, y_start),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        output_file_path = os.path.join(folder_path, f"{image_id}.jpg")
        cv2.imwrite(output_file_path, image)
        try:
            img = Image.open(output_file_path)
            img.thumbnail((1000, 800))
            img.save(f"/media/{username}/Elements/without_helmet/{current_date}/upload/{image_id}.jpg", "JPEG",
                     quality=95)
            img.close()
        except Exception as resize:
            logging.error(f"Exception in resize write_on_image for helmet: {str(resize)}")

    except Exception as ex:
        logging.error(f"Exception in helmet_write_on_image(): {str(ex)}")


class Helmet_Offence(tk.Toplevel):
    instance = None

    def __init__(self, parent):
        super().__init__(parent)
        self.offence_id = None
        self.selected_offence = None
        self.extracted_dir = None
        self.geometry("1280x762+0+0")
        self.title("Generate Without Helmet Challan")
        self.result = None
        self.resizable(False, False)
        self.configure(bg="orange")
        self.transient(parent)  # To always set this window on top of the MainApplication window
        self.grab_set()
        conn = sqlite3.connect('msiplusersettingsmh.db')
        time.sleep(0.02)
        cursor = conn.cursor()
        columns = ["RTO_Code", "District_Name", "NIC_District_ID", "NIC_userId"]
        sql_query = f"SELECT {', '.join(columns)} FROM initialization_status"
        cursor.execute(sql_query)
        row = cursor.fetchone()
        if row:
            rto_code, district_name, nic_district_id, nic_user_id = row
            self.rto_code = int(rto_code[2:])
            self.district_name = district_name
            self.nic_district_id = int(nic_district_id)
            self.nic_user_id = int(nic_user_id)
        else:
            messagebox.showerror("Critical", "Missing table in database.Please check.")
        conn.commit()
        conn.close()

        self.selected_offences = []

        self.offences_dict = {
            "Riding Without Helmet Owner Responsibility": 10735,
            "Riding Without Helmet Driver Responsibility": 10736,
            "Pillion Without Helmet Owner Responsibility": 10737,
            "Pillion Without Helmet Driver Responsibility": 10738,
        }

        self.helmet_canvas_frame = tk.Frame(self, bg="orange")
        self.helmet_canvas_frame.grid(row=0, column=0)

        # Canvas
        self.helmet_canvas = tk.Canvas(self.helmet_canvas_frame, width=800, height=537, bg="white")
        self.helmet_canvas.pack()

        '''self.plate_label = tk.Label(self.helmet_canvas_frame, text="Number Plate", bg="orange")
        self.plate_label.pack()'''

        self.right_frame = tk.Frame(self, bg="orange")
        self.right_frame.grid(row=0, column=1, columnspan=2, padx=5)

        self.helmet_canvas1 = tk.Canvas(self.right_frame, width=400, height=135, bg="white")
        self.helmet_canvas1.grid(row=0, columnspan=2, column=0, padx=35)

        back_img = Image.open('resources/48PX/back.png')
        back_img = back_img.resize((60, 60), Image.LANCZOS)
        back_photo = ImageTk.PhotoImage(back_img)
        self.back_photo = back_photo
        back_img.close()
        # Create buttons
        self.back = ttk.Button(self.helmet_canvas, command=self.load_previous_image)
        self.back.configure(width=7, takefocus=False, image=self.back_photo)
        self.back.pack()
        self.helmet_canvas.create_window(60, 268, window=self.back)

        next_img = Image.open('resources/48PX/right.png')
        next_img = next_img.resize((58, 58), Image.LANCZOS)
        next_photo = ImageTk.PhotoImage(next_img)
        self.next_photo = next_photo
        next_img.close()
        # Create buttons
        self.next = ttk.Button(self.helmet_canvas, command=self.load_next_image)
        self.next.configure(width=7, takefocus=False, image=self.next_photo)
        self.next.pack()
        self.helmet_canvas.create_window(740, 268, window=self.next)

        zoom_img = Image.open('resources/48PX/zoomin.png')
        zoom_img = zoom_img.resize((48, 48), Image.LANCZOS)
        zoom_photo = ImageTk.PhotoImage(zoom_img)
        self.zoom_photo = zoom_photo
        # Create buttons
        self.zoom = ttk.Button(self.helmet_canvas, command=self.start_crop_zoom)
        self.zoom.configure(width=7, takefocus=False, image=self.zoom_photo)
        self.zoom.pack()
        self.zoom_id = self.helmet_canvas.create_window(750, 500, window=self.zoom)

        refresh_img = Image.open('resources/48PX/Refresh_Again.png')
        refresh_img = refresh_img.resize((48, 48), Image.LANCZOS)
        refresh_photo = ImageTk.PhotoImage(refresh_img)
        self.refresh_photo = refresh_photo
        # Create buttons
        self.refresh = ttk.Button(self.helmet_canvas, command=self.refresh_func)
        self.refresh.configure(width=7, takefocus=False, image=self.refresh_photo)
        self.refresh.pack()
        self.refresh_id = self.helmet_canvas.create_window(750, 500, window=self.refresh)
        self.helmet_canvas.itemconfigure(self.refresh_id, state='hidden')

        # Create a close window button
        self.close_button = tk.Button(self.right_frame, text="Close", height=3, width=10, bg="red",
                                      compound=tk.LEFT, command=self.destroy_window)
        self.close_button.grid(row=1, column=1, pady=5)

        # Button to open file dialog
        open_img = Image.open('resources/48PX/View.png')
        open_img = open_img.resize((30, 30), Image.LANCZOS)
        open_photo = ImageTk.PhotoImage(open_img)
        self.open_photo = open_photo
        open_img.close()
        # Create a open image button
        self.button = tk.Button(self.right_frame, text="Browse Images",
                                compound=tk.LEFT, command=self.open_file_dialog)
        self.button.configure(image=self.open_photo)
        self.button.grid(row=1, column=0, pady=5)

        # Location
        self.image_id_label = tk.Label(self.right_frame, text="Image ID:", bg="orange")
        self.image_id_label.grid(row=2, column=0, pady=5)
        self.image_id_entry = tk.Entry(self.right_frame)
        self.image_id_entry.grid(row=3, column=0, pady=5)

        '''# Officer ID
        self.officer_id_label = tk.Label(self.right_frame, text="Officer ID:", bg="orange")
        self.officer_id_label.grid(row=2, column=0, pady=5)
        self.officer_id_entry = tk.Entry(self.right_frame)
        self.officer_id_entry.grid(row=2, column=1, pady=5)

        # Officer Name
        self.officer_name_label = tk.Label(self.right_frame, text="Officer Name:", bg="orange")
        self.officer_name_label.grid(row=3, column=0, pady=5)
        self.officer_name_entry = tk.Entry(self.right_frame)
        self.officer_name_entry.grid(row=3, column=1, pady=5)

        # Laser ID
        self.laser_label = tk.Label(self.right_frame, text="Laser ID:", bg="orange")
        self.laser_label.grid(row=4, column=0, pady=5)
        self.laser_entry = tk.Entry(self.right_frame)
        self.laser_entry.grid(row=4, column=1, pady=5)'''

        # Time
        self.time_label = tk.Label(self.right_frame, text="Time:", bg="orange")
        self.time_label.grid(row=4, column=0, pady=5)
        self.time_entry = tk.Entry(self.right_frame)
        self.time_entry.grid(row=5, column=0, pady=5)

        '''# Date
        self.date_label = tk.Label(self.right_frame, text="Date:", bg="orange")
        self.date_label.grid(row=10, column=0, pady=5)
        self.date_entry = tk.Entry(self.right_frame)
        self.date_entry.grid(row=10, column=1, pady=5)'''

        # Create progress bar
        bigfont = font.Font(family="Arial", size=14)
        self.option_add("*Font", bigfont)
        style = ttk.Style()
        style.configure("green.Horizontal.TProgressbar", troughcolor="white", background="green")
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(self, style="green.Horizontal.TProgressbar", variable=self.progress_var,
                                            maximum=100, mode="determinate", length=750,
                                            orient=tk.HORIZONTAL)
        self.progress_bar.grid(row=1, column=0, pady=10)

        self.nic_uploaded_label = tk.Label(self, text="NO VIOLATIONS TODAY", bg="green", font=("Arial", 50))
        self.nic_uploaded_label.grid(row=2, column=0, pady=25)

        # Create a label to display the extracted number plate text
        self.number_plate_label = tk.Label(self.right_frame, text="Number Plate:", bg="orange")
        self.number_plate_label.grid(row=6, column=0, pady=5)

        entry_var = StringVar()
        validate_cmd = self.register(self.on_validate)
        self.number_plate_entry = tk.Entry(self.right_frame, textvariable=entry_var, width=12, validate="key",
                                           validatecommand=(validate_cmd, '%P', '%d'), font=("Arial", 25))
        self.number_plate_entry.grid(row=7, column=0, pady=5)
        self.number_plate_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        self.combobox = ttk.Combobox(self, values=list(self.offences_dict.keys()), state="readonly", width=40,
                                     font=("Arial", 15))
        self.combobox.set("Select Offence")
        self.combobox.grid(row=1, column=1, pady=5)

        # Bind event handler to ComboBox selection
        self.combobox.bind("<<ComboboxSelected>>", self.on_combobox_select)

        # Save Button
        save_img = Image.open('resources/48PX/save.png')
        save_img = save_img.resize((30, 30), Image.LANCZOS)
        save_photo = ImageTk.PhotoImage(save_img)
        self.save_photo = save_photo
        # Create a print button
        self.save_button = tk.Button(self.right_frame, text="Save",
                                     compound=tk.LEFT, command=self.save_details)
        self.save_button.configure(image=self.save_photo)
        self.save_button.grid(row=7, column=1)

        firebase_img = Image.open('resources/img/firebase.png')
        firebase_img = firebase_img.resize((30, 30), Image.LANCZOS)
        firebase_photo = ImageTk.PhotoImage(firebase_img)
        self.firebase_photo = firebase_photo
        # Create a firebase button
        self.nic_button = tk.Button(self.right_frame, text="Upload",
                                    compound=tk.LEFT, command=self.manual_helmet_upload, state=DISABLED)
        self.nic_button.configure(image=self.firebase_photo)
        self.nic_button.grid(row=3, column=1, pady=5)

        # Crop Button
        crop_img = Image.open('resources/48PX/Edit.png')
        crop_img = crop_img.resize((30, 30), Image.LANCZOS)
        crop_photo = ImageTk.PhotoImage(crop_img)
        self.crop_photo = crop_photo
        # Create a print button
        self.crop_button = tk.Button(self.right_frame, text="Crop",
                                     compound=tk.LEFT, command=self.start_crop)
        self.crop_button.configure(image=self.crop_photo)
        self.crop_button.grid(row=5, column=1, pady=5)

        '''print_img = Image.open('resources/48PX/Print.png')
        print_img = print_img.resize((30, 30), Image.LANCZOS)
        print_photo = ImageTk.PhotoImage(print_img)
        self.print_photo = print_photo
        # Create a print button
        self.print_button = tk.Button(self.right_frame, text="Print",
                                      compound=tk.LEFT, command=self.print_func)
        self.print_button.configure(image=self.print_photo)
        self.print_button.grid(row=11, column=2, pady=5)'''

        # Initialize cropping variables
        self.crop_start_x = 0
        self.crop_start_y = 0
        self.crop_rect = None
        self.file_path = None  # Variable to store the current image file path
        self.crop_window = None

        self.crop_start_x1 = 0
        self.crop_start_y1 = 0
        self.crop_rect1 = None
        self.file_path1 = None
        self.crop_window1 = None

        # Load the default image to the canvas
        self.load_default_image()

    def refresh_func(self):
        self.crop_button.configure(state=NORMAL)
        pil_image = Image.open(self.file_path)
        pil_image = pil_image.resize((800, 537), Image.LANCZOS)  # 600, 437
        # Convert image to Tkinter PhotoImage format
        tk_image = ImageTk.PhotoImage(pil_image)

        # self.canvas.delete("all")
        self.helmet_canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
        self.helmet_canvas.image = tk_image
        pil_image.close()
        self.helmet_canvas.itemconfigure(self.refresh_id, state='hidden')
        self.helmet_canvas.itemconfigure(self.zoom_id, state='normal')

    def on_combobox_select(self, event):
        self.nic_uploaded_label.config(text="Selected Offences: None", bg="orange", font=("Arial", 12))
        self.nic_uploaded_label.grid()

        '''self.selected_offence = self.combobox.get()
        self.offence_id = self.offences_dict.get(self.selected_offence, "N/A")'''
        self.nic_button.config(state=NORMAL)

        selected_offence = self.combobox.get()
        if selected_offence in self.selected_offences:
            self.selected_offences.remove(selected_offence)
        elif len(self.selected_offences) < 2:
            self.selected_offences.append(selected_offence)
        else:
            self.withdraw()
            messagebox.showerror("Selection Error", "You can select up to 2 offences only.")
            self.deiconify()

        self.update_selected_label()

    def update_selected_label(self):
        if self.selected_offences:
            display_text = ', '.join(self.selected_offences)
            self.combobox.set(display_text)
        else:
            display_text = "None"
        self.nic_uploaded_label.config(text=f"Selected Offences: {display_text}")

    @classmethod
    def create(cls, parent):
        # Create a new instance of Offence
        if cls.instance is not None:
            cls.instance.destroy()
        cls.instance = cls(parent)
        cls.instance.protocol("WM_DELETE_WINDOW", cls.destroy_instance)

    @classmethod
    def destroy_instance(cls):
        # Destroy current instance of Offence
        if cls.instance is not None:
            cls.instance.destroy()
            cls.instance = None

    def on_validate(self, value, action):
        # Check if the length of the input is less than or equal to 10
        return len(value) <= 10

    def destroy_window(self):
        self.destroy()
        Helmet_Offence.instance = None

    def send_helmet_image(self, laser_id, image_base64, lpimage_base64, location, lat, lon, number_plate, image_key,
                          date, cur_time):
        """self.rto_code = int(rto_code[2:])
            self.district_name = district_name
            self.nic_district_id = int(nic_district_id)
            self.nic_user_id = int(nic_user_id)"""
        try:
            if not check_internet_connection():
                return False
            selected_offences_ids = [str(self.offences_dict[offence]) for offence in self.selected_offences]
            formatted_ids = ", ".join(selected_offences_ids)
            dp = cur_time.split('_')
            fd = dp[1].replace('-', ':')
            cur_time = f"{dp[0]} {fd}"

            # Format the datetime object as a string
            current_datetime = datetime.datetime.now()
            # Format the datetime object as a string
            action_time = current_datetime - datetime.timedelta(minutes=2)
            formatted_datetime = action_time.strftime("%Y-%m-%d %H:%M:%S")
            url = "https://itmschallan.parivahan.gov.in/pushwssg/api/echallan/pushdata"
            # url = "https://staging.parivahan.gov.in/pushwssg/api/echallan/pushdata/"
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            }
            cctv_notice_data = [
                {
                    "offenceId": f"{str(formatted_ids)}",
                    "dpCd": "TR",
                    "latitude": 1.0 if lat == '' else float(lat),
                    "transactionNo": str(image_key),
                    "userId": self.nic_user_id,
                    "regnNo": str(number_plate),
                    "voilationSource": "RLVD",
                    "voilationSourceCatg": "ITMS System",
                    "stateCd": "MH",
                    "districtId": self.nic_district_id,
                    "location": str(location),
                    "offCd": self.rto_code,
                    "equipmentId": str(laser_id),
                    "vendorName": "MSI",
                    "vehicleSpeed": 0,
                    "speedLimit": 0,
                    "district": self.district_name,
                    "vehicleWeight": 0,
                    "voilationTime": f"{cur_time}",
                    "actionTime": f"{formatted_datetime}",
                    "longitude": 1.0 if lon == '' else float(lon),
                    "image1": image_base64,
                    "image2": lpimage_base64
                }
            ]
            self.progress_var.set(70)
            self.update_idletasks()
            data = {
                'cctvNoticeData': cctv_notice_data
            }

            try:
                with open(f'/media/{getpass.getuser()}/Elements/helmet_info/{dp[0]}/Log/{image_key}.json',
                          'w') as filez:
                    json.dump(data, filez, indent=2)
            except Exception as js:
                logging.error(f"Exception while writing data to json file: {str(js)}")
            self.progress_var.set(90)
            self.update_idletasks()

            # Set timeout in seconds
            timeout_seconds = 60
            try:
                response = requests.post(url, json=data, headers=headers, timeout=timeout_seconds)
                response_data = response.json()  # Parse JSON response
                pprint(response_data)
                self.progress_var.set(100)
                self.update_idletasks()
                # Check the response
                if response.status_code == 200:
                    self.selected_offences = []
                    status_message = response_data.get("responseMsg", {}).get("status", "")
                    success_message = response_data.get("responseMsg", {}).get("reason", "")
                    '''self.withdraw()
                    messagebox.showinfo(f"Code:{status_message}", success_message)
                    self.deiconify()'''
                    '''present_dialog = tk.Toplevel()
                    present_dialog.title(f"{status_message}")
                    present_dialog.resizable(False, False)
                    present_dialog.geometry("350x100+550+350")
                    tk.Label(present_dialog, text=f"{success_message}").pack(pady=10)'''
                    # pprint(success_message)
                    conn = sqlite3.connect('msiplusersettingsmh.db')
                    time.sleep(0.02)
                    cursor = conn.cursor()
                    query = """
                                UPDATE helmetoffencerecords
                                SET uploaded = ?, numberplate = ?, offence_type = ?
                                WHERE image_id = ?;
                            """
                    cursor.execute(query, ('y', number_plate, f"{self.combobox.get()}", image_key))
                    conn.commit()
                    conn.close()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    return True
                elif response.status_code == 400:
                    if response_data.get("responseMsg", {}) is None:
                        try:
                            with open(f'/media/{getpass.getuser()}/Elements/helmet_info/{dp[0]}/Log/{image_key}.json',
                                      'r+') as filez:
                                json_data = json.load(filez)
                                json.dump(response_data, filez, indent=2)
                        except Exception as js:
                            logging.error(f"Exception while writing response data to json file in helmet response code 400: {str(js)}")

                        self.withdraw()
                        messagebox.showinfo(f"NIC-Reply", "Response Status Code : 400")
                        self.deiconify()
                        self.progress_var.set(0)
                        self.update_idletasks()
                        '''present_dialog = tk.Toplevel()
                        present_dialog.title(f"{status_message}")
                        present_dialog.resizable(False, False)
                        present_dialog.geometry("350x100+550+350")
                        tk.Label(present_dialog, text=f"{error_message}").pack(pady=10)'''
                        # pprint(error_message)
                        logging.warning(f"Failed to push helmet data")
                        return False
                    status_message = response_data.get("responseMsg", {}).get("status", "")
                    error_message = response_data.get("responseMsg", {}).get("reason", "")
                    self.withdraw()
                    # Append response message to the JSON file
                    rejected_response_msg = response_data['rejectedData'][0]['responseMsg']
                    try:
                        with open(f'/media/{getpass.getuser()}/Elements/helmet_info/{dp[0]}/Log/{image_key}.json',
                                  'r+') as filez:
                            json_data = json.load(filez)
                            json.dump(rejected_response_msg, filez, indent=2)
                    except Exception as js:
                        logging.error(f"Exception while writing response data to json file: {str(js)}")
                    messagebox.showinfo(f"NIC-Reply:{status_message}", error_message)
                    self.deiconify()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    '''present_dialog = tk.Toplevel()
                    present_dialog.title(f"{status_message}")
                    present_dialog.resizable(False, False)
                    present_dialog.geometry("350x100+550+350")
                    tk.Label(present_dialog, text=f"{error_message}").pack(pady=10)'''
                    # pprint(error_message)
                    logging.warning(f"Failed to push helmet data")
                    return False
                elif response.status_code != 200 and response.status_code != 400:
                    status_message = response_data.get("responseMsg", {}).get("status", "")
                    error_message = response_data.get("responseMsg", {}).get("reason", "")
                    self.withdraw()
                    # Append response message to the JSON file
                    rejected_response_msg = response_data['rejectedData'][0]['responseMsg']
                    try:
                        with open(f'/media/{getpass.getuser()}/Elements/helmet_info/{dp[0]}/Log/{image_key}.json',
                                  'r+') as filez:
                            json_data = json.load(filez)
                            json.dump(rejected_response_msg, filez, indent=2)
                    except Exception as js:
                        logging.error(f"Exception while writing response data to json file: {str(js)}")
                    messagebox.showinfo(f"NIC-Reply:{status_message}", error_message)
                    self.deiconify()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    '''present_dialog = tk.Toplevel()
                    present_dialog.title(f"{status_message}")
                    present_dialog.resizable(False, False)
                    present_dialog.geometry("350x100+550+350")
                    tk.Label(present_dialog, text=f"{error_message}").pack(pady=10)'''
                    # pprint(error_message)
                    logging.warning(f"Failed to push helmet data")
                    return False
                elif any('Transaction number already' in entry['responseMsg']['reason'] for entry in
                         response_data['rejectedData']):
                    self.selected_offences = []
                    conn = sqlite3.connect('msiplusersettingsmh.db')
                    time.sleep(0.02)
                    cursor = conn.cursor()
                    query = """
                                UPDATE helmetoffencerecords
                                SET uploaded = ?, numberplate = ?, offence_type = ?
                                WHERE image_id = ?;
                            """
                    cursor.execute(query, ('y', number_plate, f"{self.combobox.get()}", image_key))
                    conn.commit()
                    conn.close()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    return True

                else:
                    status_message = response_data.get("responseMsg", {}).get("status", "")
                    error_message = response_data.get("responseMsg", {}).get("reason", "")
                    self.withdraw()
                    # Append response message to the JSON file
                    rejected_response_msg = response_data['rejectedData'][0]['responseMsg']
                    try:
                        with open(f'/media/{getpass.getuser()}/Elements/helmet_info/{dp[0]}/Log/{image_key}.json',
                                  'r+') as filez:
                            json_data = json.load(filez)
                            json.dump(rejected_response_msg, filez, indent=2)
                    except Exception as js:
                        logging.error(f"Exception while writing response data to json file: {str(js)}")
                    messagebox.showinfo(f"NIC-Reply:{status_message}", error_message)
                    self.deiconify()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    '''present_dialog = tk.Toplevel()
                    present_dialog.title(f"{status_message}")
                    present_dialog.resizable(False, False)
                    present_dialog.geometry("350x100+550+350")
                    tk.Label(present_dialog, text=f"{error_message}").pack(pady=10)'''
                    # pprint(error_message)
                    logging.warning(f"Failed to push helmet data")
                    return False
            except requests.exceptions.Timeout:
                self.withdraw()
                error_message1 = f"Error: Request timed out. Please try again."
                messagebox.showerror("Timeout Error", error_message1)
                self.deiconify()
                self.progress_var.set(0)
                self.update_idletasks()
                '''present_dialog = tk.Toplevel()
                present_dialog.title("Error")
                present_dialog.resizable(False, False)
                present_dialog.geometry("350x100+550+350")
                tk.Label(present_dialog, text=f"{error_message1}").pack(pady=10)'''

                logging.error(f"Exception in uploading data to itms: {str(error_message1)}")
                return False
            except requests.exceptions.RequestException as e:
                # Handle other request exceptions
                error_message2 = f"Request Error: {e}"
                self.withdraw()
                messagebox.showerror("Try again", error_message2)
                self.deiconify()
                self.progress_var.set(0)
                self.update_idletasks()
                '''present_dialog = tk.Toplevel()
                present_dialog.title("Error!")
                present_dialog.resizable(False, False)
                present_dialog.geometry("350x100+550+350")
                tk.Label(present_dialog, text=f"{error_message2}").pack(pady=10)'''
                logging.error(f"Exception in uploading data to itms: {str(error_message2)}")
                return False
            except Exception as e1:
                # Handle other request exceptions
                error_message2 = f"{e1}"
                self.withdraw()
                messagebox.showerror("Error", error_message2)
                self.deiconify()
                self.progress_var.set(0)
                self.update_idletasks()
                '''present_dialog = tk.Toplevel()
                present_dialog.title("Error!")
                present_dialog.resizable(False, False)
                present_dialog.geometry("350x100+550+350")
                tk.Label(present_dialog, text=f"{error_message2}").pack(pady=10)'''
                logging.error(f"Exception in uploading data to itms: {str(error_message2)}")
                return False
        except Exception as ex:
            logging.error(f"Exception in Class Helmet_Offence inside send_helmet_image(): {str(ex)}")
            return False

    def manual_helmet_upload(self):
        try:
            # Connect to the database and retrieve data
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query = "SELECT * FROM helmetoffencerecords WHERE image_id = ?"
            data = cursor.execute(query, (self.image_id_entry.get(),)).fetchone()
            conn.close()  # total 12 columns (0-11)
            laser_id = data[7]
            date = data[2]
            # Use 'Time' as the unique key
            image_key = data[0]
            actual_lp = data[6]

            if actual_lp != self.number_plate_entry.get():
                self.withdraw()
                messagebox.showwarning("Unsaved LP", "Please click on SAVE before uploading!")
                self.deiconify()
                return
            self.nic_button.config(state=DISABLED)
            self.close_button.config(state=DISABLED)
            if check_internet_connection():
                self.progress_var.set(10)
                self.update_idletasks()
                if len(self.number_plate_entry.get()) > 6:
                    self.progress_var.set(20)
                    self.update_idletasks()
                    if self.combobox.get() != 'Select Offence':
                        self.progress_var.set(30)
                        self.update_idletasks()
                        is_not_uploaded = check_and_upload_data(self.time_entry.get())
                        if is_not_uploaded:
                            self.progress_var.set(50)
                            self.update_idletasks()

                            helmet_write_on_image(data[0], data[1], date, data[3], data[4], data[5], data[6], laser_id,
                                                  data[9], data[10])

                            # Read the image file and convert it to Base64
                            time.sleep(0.02)
                            with open(
                                    f"/media/{getpass.getuser()}/Elements/without_helmet/{date}/upload/{self.image_id_entry.get()}.jpg",
                                    "rb") as image_file:
                                image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
                            if os.path.exists(
                                    f"/media/{getpass.getuser()}/Elements/helmet_cropped_plates/{date}/{self.image_id_entry.get()}.jpg"):
                                with open(
                                        f"/media/{getpass.getuser()}/Elements/helmet_cropped_plates/{date}/{self.image_id_entry.get()}.jpg",
                                        "rb") as image_file:
                                    lpimage_base64 = base64.b64encode(image_file.read()).decode("utf-8")
                            else:
                                with open("resources/img/notavailable.jpg", "rb") as image_file:
                                    lpimage_base64 = base64.b64encode(image_file.read()).decode("utf-8")
                            self.progress_var.set(60)
                            self.update_idletasks()

                            ret = self.send_helmet_image(laser_id, image_base64, lpimage_base64, data[3], data[9],
                                                         data[10], self.number_plate_entry.get(), image_key, date,
                                                         self.time_entry.get())
                            if ret:
                                self.progress_var.set(0)
                                self.update_idletasks()
                                self.fetch_and_update_data_from_database(self.image_id_entry.get())
                                self.nic_button.config(state=NORMAL)
                                self.close_button.config(state=NORMAL)
                            else:
                                self.progress_var.set(0)
                                self.update_idletasks()
                                self.nic_button.config(state=NORMAL)
                                self.close_button.config(state=NORMAL)
                        else:
                            present_dialog = tk.Toplevel(self)
                            present_dialog.title("Information")
                            present_dialog.resizable(False, False)
                            present_dialog.geometry("350x100+550+350")
                            tk.Label(present_dialog, text="Data is already uploaded.").pack()
                            logging.error(
                                f"Data with {str(self.image_id_entry.get())} is already uploaded.")
                            self.nic_button.config(state=NORMAL)
                            self.close_button.config(state=NORMAL)
                    else:
                        self.withdraw()
                        error_message0 = "Select a valid Offence type."
                        messagebox.showwarning("Warning", error_message0)
                        self.progress_var.set(0)
                        self.update_idletasks()
                        self.deiconify()
                        self.nic_button.config(state=NORMAL)
                        self.close_button.config(state=NORMAL)
                else:
                    self.withdraw()
                    error_message = "Number Plate should have atleast 7 characters."
                    messagebox.showwarning("Warning", error_message)
                    self.progress_var.set(0)
                    self.update_idletasks()
                    self.deiconify()
                    self.nic_button.config(state=NORMAL)
                    self.close_button.config(state=NORMAL)
            else:
                self.withdraw()
                error_message1 = "No Internet Connection."
                messagebox.showerror("Connection Error", error_message1)
                self.progress_var.set(0)
                self.update_idletasks()
                self.deiconify()
                self.nic_button.config(state=NORMAL)
                self.close_button.config(state=NORMAL)
                '''
                error_dialog = tk.Toplevel(self)
                error_dialog.title("Connection Error")
                error_dialog.resizable(False, False)
                error_dialog.geometry("350x100+550+350")
                tk.Label(error_dialog, text="No Internet Connection.").pack()'''

                logging.error("No Internet Connection to push data.")
            # self.fetch_and_update_data_from_database(self.image_id_entry.get())
        except Exception as eex:
            self.nic_button.config(state=NORMAL)
            self.close_button.config(state=NORMAL)
            self.progress_var.set(0)
            self.update_idletasks()
            logging.error(f"Exception in Class Helmet_Offence in manual_helmet_upload(): {str(eex)}")
            pass

    def print_func(self):
        try:
            if self.number_plate_entry.get() == '' or self.number_plate_entry.get() == ' ':
                error_dialog = tk.Toplevel(self)
                error_dialog.title("No Number Plate found.")
                error_dialog.geometry("350x100+550+350")
                tk.Label(error_dialog, text="Number plate cannot be empty.").pack()

            # Connect to the database and retrieve data
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query = "SELECT * FROM helmetoffencerecords WHERE image_id = ?"
            data = cursor.execute(query, (self.image_id_entry.get(),)).fetchone()
            # print("print data:", data)
            conn.close()

            selected_printer = self.printer_combo.get()
            if selected_printer:
                output_filename = f"{self.time_entry.get()}.pdf"
                self.generate_pdf(data, output_filename)
                print_pdf(output_filename, selected_printer)
            else:
                error_dialog = tk.Toplevel(self)
                error_dialog.title("Print Status")
                error_dialog.geometry("350x100+550+350")
                tk.Label(error_dialog, text="No printer is selected. Select a printer and try again.").pack()

        except Exception as e:
            print(e)

    def generate_pdf(self, data, output_filename):
        '''c = canvas.Canvas(output_filename, pagesize=A4)
        c.setFillColorRGB(1, 0, 0)
        c.setFont("Helvetica-Bold", 30)
        c.drawString(130, 800, "OVER-SPEED CHALLAN")

        # Draw images
        c.drawImage('resources/img/Maharashtra_State_Road_Transport_Corporation_logo.png', 495, 775, width=80,
                    height=60)
        c.drawImage(self.file_path, 20, 520, width=555, height=250)
        if os.path.exists(f'case_on_cropped_plates/{get_current_date_folder()}/{self.image_id_entry.get()}.jpg'):
            c.drawImage(f'case_on_cropped_plates/{get_current_date_folder()}/{self.image_id_entry.get()}.jpg', 20, 400,
                        width=255,
                        height=100)
        elif os.path.exists(f'cropped_numplate_images/{get_current_date_folder()}/{self.image_id_entry.get()}.jpg'):
            c.drawImage(f'cropped_numplate_images/{get_current_date_folder()}/{self.image_id_entry.get()}.jpg', 20, 400,
                        width=255, height=100)
        else:
            c.drawImage('resources/img/notavailable.jpg', 20, 400, width=255, height=100)
        if os.path.exists(f'number_plate_images/{get_current_date_folder()}/maps/map_screenshot.png'):
            c.drawImage(f'number_plate_images/{get_current_date_folder()}/maps/map_screenshot.png', 275, 300, width=300,
                        height=200)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 12)
        if data:
            c.drawString(50, 300, f"Offence Time: {data[1]}")
            c.drawString(50, 280, f"Date: {data[2]}")
            c.drawString(300, 280, f"Location: {data[3]}")
            c.drawString(50, 260, f"Officer Name: {data[4]}")
            c.drawString(50, 240, f"Officer ID: {data[5]}")
            c.drawString(50, 220, f"Speed Limit: {data[6]} kmph")
            c.drawString(50, 200, f"Vehicle Speed: {data[7]} kmph")
            c.drawString(50, 180, f"Distance: {data[8]} m")
            c.drawString(50, 160, f"Direction: {data[9]}")
            c.drawString(50, 380, f"Number Plate: {data[10]}")
            c.drawString(50, 140, f"Device ID: {data[11]}")

        # Draw signature and copyright text
        c.setFillColorRGB(1, 0, 0)  # Red color
        c.drawString(40, 50, "Signature of Officer")
        c.drawString(450, 50, "Signature of Offender")

        # Draw copyright symbol and text
        c.setFillColorRGB(0, 0, 0)  # Black color
        c.drawString(250, 20, "©")
        c.drawString(260, 20, " MSIPL, Bangalore.")

        c.save()'''

    # <----------------------------For Zoom Functions----------------------------------------------------------->
    def start_crop_zoom(self):
        self.crop_button.configure(state=DISABLED)
        # Bind the mouse events for cropping
        self.helmet_canvas.bind("<ButtonPress-1>", self.on_press_zoom)
        self.helmet_canvas.bind("<B1-Motion>", self.on_drag_zoom)
        self.helmet_canvas.bind("<ButtonRelease-1>", self.on_release_zoom)

        # Update cursor style for cropping
        self.helmet_canvas.config(cursor="cross")

    def on_press_zoom(self, event1):
        self.crop_start_x1 = event1.x
        self.crop_start_y1 = event1.y

        # Remove the previous cropping rectangle, if exists
        if self.crop_rect1:
            self.helmet_canvas.delete(self.crop_rect1)

        # Create a new cropping rectangle
        self.crop_rect1 = self.helmet_canvas.create_rectangle(self.crop_start_x1, self.crop_start_y1,
                                                              self.crop_start_x1, self.crop_start_y1, outline="red",
                                                              width=3)

    def on_drag_zoom(self, event1):
        self.helmet_canvas.coords(self.crop_rect1, self.crop_start_x1, self.crop_start_y1, event1.x, event1.y)

    def on_release_zoom(self, event1):
        # Get the final coordinates after dragging
        crop_end_x = event1.x
        crop_end_y = event1.y
        # Resize the coordinates to the original image size (1920x1080)
        original_width, original_height = 1920, 1080
        scale_x = original_width / 800  # 600
        scale_y = original_height / 537  # 437

        x1 = int(self.crop_start_x1 * scale_x)
        y1 = int(self.crop_start_y1 * scale_y)
        x2 = int(crop_end_x * scale_x)
        y2 = int(crop_end_y * scale_y)

        if y1 > y2:
            y1, y2 = y2, y1
        if x1 > x2:
            x1, x2 = x2, x1

        # Crop the zoom part from the original image
        image = Image.open(self.file_path)
        cropped_image = image.crop((x1, y1, x2, y2))
        cropped_image = cropped_image.resize((800, 537), Image.LANCZOS)
        self.cropped_image1 = ImageTk.PhotoImage(cropped_image)
        self.helmet_canvas.create_image(0, 0, anchor=tk.NW, image=self.cropped_image1)

        # Unbind the mouse events and reset the cursor
        self.helmet_canvas.unbind("<ButtonPress-1>")
        self.helmet_canvas.unbind("<B1-Motion>")
        self.helmet_canvas.unbind("<ButtonRelease-1>")
        self.helmet_canvas.config(cursor="")

        # Remove the cropping rectangle from the canvas
        self.helmet_canvas.delete(self.crop_rect1)
        image.close()
        self.helmet_canvas.itemconfigure(self.zoom_id, state='hidden')
        self.helmet_canvas.itemconfigure(self.refresh_id, state='normal')

    def start_crop(self):
        # Bind the mouse events for cropping
        self.helmet_canvas.bind("<ButtonPress-1>", self.on_press)
        self.helmet_canvas.bind("<B1-Motion>", self.on_drag)
        self.helmet_canvas.bind("<ButtonRelease-1>", self.on_release)

        # Update cursor style for cropping
        self.helmet_canvas.config(cursor="cross")

    def on_press(self, event):
        self.crop_start_x = event.x
        self.crop_start_y = event.y

        # Remove the previous cropping rectangle, if exists
        if self.crop_rect:
            self.helmet_canvas.delete(self.crop_rect)

        # Create a new cropping rectangle
        self.crop_rect = self.helmet_canvas.create_rectangle(self.crop_start_x, self.crop_start_y,
                                                             self.crop_start_x, self.crop_start_y, outline="green",
                                                             width=3)

    def on_drag(self, event):
        self.helmet_canvas.coords(self.crop_rect, self.crop_start_x, self.crop_start_y, event.x, event.y)

    def on_release(self, event):
        # Get the final coordinates after dragging
        crop_end_x = event.x
        crop_end_y = event.y

        # Resize the coordinates to the original image size (1920x1080)
        original_width, original_height = 1920, 1080
        scale_x = original_width / 800  # 600
        scale_y = original_height / 537  # 437

        x1 = int(self.crop_start_x * scale_x)
        y1 = int(self.crop_start_y * scale_y)
        x2 = int(crop_end_x * scale_x)
        y2 = int(crop_end_y * scale_y)

        if y1 > y2:
            y1, y2 = y2, y1
        if x1 > x2:
            x1, x2 = x2, x1

        # Crop the number plate from the original image
        image = Image.open(self.file_path)
        cropped_image = image.crop((x1, y1, x2, y2))

        # Resize the cropped image to fit canvas1 and display it
        cropped_image = cropped_image.resize((400, 135), Image.LANCZOS)
        self.cropped_image = ImageTk.PhotoImage(cropped_image)
        cur_date = self.time_entry.get()
        dp = cur_date.split('_')
        cur_date = dp[0]
        # print("date of violation of helmet detection in line 532:", cur_date)
        cropped_directory = os.path.join(f"/media/{getpass.getuser()}/Elements", "helmet_cropped_plates", cur_date)
        os.makedirs(cropped_directory, exist_ok=True)
        self.cropped_image_path = os.path.join(cropped_directory, f"{self.image_id_entry.get()}.jpg")
        # print(self.cropped_image_path)
        cropped_image.save(self.cropped_image_path)
        self.helmet_canvas1.create_image(0, 0, anchor=tk.NW, image=self.cropped_image)
        result = new_main(self.cropped_image_path)
        if result is not None:
            self.number_plate_entry.delete(0, tk.END)
            self.number_plate_entry.insert(0, result)
        else:
            self.number_plate_entry.delete(0, tk.END)
            self.number_plate_entry.insert(0, "-")

        # Unbind the mouse events and reset the cursor
        self.helmet_canvas.unbind("<ButtonPress-1>")
        self.helmet_canvas.unbind("<B1-Motion>")
        self.helmet_canvas.unbind("<ButtonRelease-1>")
        self.helmet_canvas.config(cursor="")

        # Remove the cropping rectangle from the canvas
        self.helmet_canvas.delete(self.crop_rect)

    def fetch_and_update_data_from_database(self, img_name):
        try:
            print(self.selected_offences)
            self.selected_offences = []
            self.img_name = img_name
            # Fetch the data from the database for the given image_name
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query = """
                        SELECT * FROM helmetoffencerecords
                        WHERE image_id = ?
                        LIMIT 1;
                    """
            cursor.execute(query, (img_name,))
            data = cursor.fetchone()
            # print("data=", data)
            conn.close()

            # Update the entry fields with the fetched data
            if data:
                self.image_id_entry.config(state="normal")
                self.image_id_entry.delete(0, tk.END)
                self.image_id_entry.insert(0, data[0])
                self.image_id_entry.config(state="readonly")
                '''self.officer_id_entry.config(state="normal")
                self.officer_id_entry.delete(0, tk.END)
                self.officer_id_entry.insert(0, data[5])
                self.officer_id_entry.config(state="readonly")
                self.officer_name_entry.config(state="normal")
                self.officer_name_entry.delete(0, tk.END)
                self.officer_name_entry.insert(0, data[4])
                self.officer_name_entry.config(state="readonly")
                self.laser_entry.config(state="normal")
                self.laser_entry.delete(0, tk.END)
                self.laser_entry.insert(0, data[7])
                self.laser_entry.config(state="readonly")'''
                self.time_entry.config(state="normal")
                self.time_entry.delete(0, tk.END)
                self.time_entry.insert(0, data[1])
                self.time_entry.config(state="readonly")
                if data[8] == 'y':
                    self.nic_button.config(state=DISABLED)
                    self.save_button.config(state=DISABLED)
                    self.crop_button.config(state=DISABLED)
                    self.combobox.config(state=NORMAL)
                    self.combobox.set(data[11])
                    self.combobox.config(state=DISABLED)
                    self.number_plate_entry.config(state="normal")
                    self.number_plate_entry.delete(0, tk.END)
                    self.number_plate_entry.insert(0, data[6])
                    self.number_plate_entry.config(state="readonly")
                    self.nic_uploaded_label.config(text="CHALLAN GENERATED", bg="red", font=("Arial", 50))
                    self.nic_uploaded_label.grid()
                else:
                    self.combobox.config(state="readonly")
                    self.combobox.set("Select Offence")
                    self.nic_button.config(state=DISABLED)
                    self.save_button.config(state=NORMAL)
                    self.crop_button.config(state=NORMAL)
                    self.nic_uploaded_label.grid_remove()
                    self.number_plate_entry.config(state="normal")
                    self.number_plate_entry.delete(0, tk.END)
                    self.number_plate_entry.insert(0, data[6])
                    self.nic_uploaded_label.config(text="WITHOUT HELMET", bg="orange", font=("Arial", 50))
                    self.nic_uploaded_label.grid()
            else:
                # If no data is found, clear the entry fields
                self.image_id_entry.config(state="normal")
                self.image_id_entry.delete(0, tk.END)
                self.image_id_entry.config(state="readonly")
                '''self.officer_id_entry.config(state="normal")
                self.officer_id_entry.delete(0, tk.END)
                self.officer_id_entry.config(state="readonly")
                self.officer_name_entry.config(state="normal")
                self.officer_name_entry.delete(0, tk.END)
                self.officer_name_entry.config(state="readonly")
                self.laser_entry.config(state="normal")
                self.laser_entry.delete(0, tk.END)
                self.laser_entry.config(state="readonly")'''
                self.time_entry.config(state="normal")
                self.time_entry.delete(0, tk.END)
                self.time_entry.config(state="readonly")
                self.number_plate_entry.delete(0, tk.END)
        except Exception:
            pass

    def get_image_files_in_folder(self, folder_path):
        if os.path.exists(folder_path):
            # Get a list of image files in the specified folder path
            files = os.listdir(folder_path)
            files.sort()
            image_files = glob.glob(os.path.join(folder_path, "*.*"))
            image_files.sort(key=lambda x: files.index(os.path.basename(x)))
            return [file for file in image_files if file.lower().endswith(('.jpg', '.bmp', '.png'))]
        else:
            return False

    def load_default_image(self):
        try:
            # Get the current date folder
            global image_name
            current_date_folder = get_current_date_folder()

            # Get a list of image files in the current date folder
            image_files = self.get_image_files_in_folder(
                os.path.join(f"/media/{getpass.getuser()}/Elements/without_helmet", current_date_folder))

            if not image_files:
                # If no image files are available for the current date, load the default image
                image_path = "resources/img/sphu.png"
                # Load the image to the canvas
                # self.load_image_to_canvas(image_path)
                pil_image = Image.open(image_path)
                pil_image = pil_image.resize((800, 537), Image.LANCZOS)  # 600, 437
                tk_image = ImageTk.PhotoImage(pil_image)
                self.helmet_canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
                self.helmet_canvas.image = tk_image
                pil_image.close()

                try:
                    image1 = Image.open(image_path)
                    # Resize the cropped image to fit canvas1 and display it
                    image1 = image1.resize((400, 135), Image.LANCZOS)
                    tk_image1 = ImageTk.PhotoImage(image1)
                    self.helmet_canvas1.create_image(0, 0, anchor=tk.NW, image=tk_image1)
                    self.helmet_canvas1.image = tk_image1
                    image1.close()
                except FileNotFoundError:
                    pass
            else:
                # Get the last image file in the list
                image_path1 = image_files[-1]
                file_name = os.path.basename(image_path1)
                image_name, _ = os.path.splitext(file_name)
                # Update the entry fields with data from the database for the current image
                self.fetch_and_update_data_from_database(image_name)
                # Load the image to the canvas
                self.load_image_to_canvas(image_path1)
                # Disable/enable the "Previous" and "Next" buttons accordingly
                self.update_button_state()
        except Exception:
            pass

    def load_image_to_canvas(self, image_path):
        try:
            global canvas_image_path
            canvas_image_path = image_path
            '''image = Image.open(image_path)
            # Create a drawing object
            draw = ImageDraw.Draw(image)
            # Define the position and size of the plus mark
            x, y = 980, 550
            size = 40
            # Draw the plus mark
            draw.line((x - size, y, x + size, y), fill=(255, 0, 0), width=4)
            draw.line((x, y - size, x, y + size), fill=(255, 0, 0), width=4)
            # Save the modified image with the plus mark
            modified_image_path = "plus_sign_image.bmp"
            image.save(modified_image_path)'''
            path = os.path.join(f"/media/{getpass.getuser()}/Elements", image_path)
            pil_image = Image.open(path)
            pil_image = pil_image.resize((800, 537), Image.LANCZOS)  # 600, 437
            # Convert image to Tkinter PhotoImage format
            tk_image = ImageTk.PhotoImage(pil_image)

            # self.canvas.delete("all")
            self.helmet_canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
            self.helmet_canvas.image = tk_image
            self.file_path = path
            '''os.remove(modified_image_path)
            image.close()'''

            folder, filename = os.path.split(path)
            new_folder = folder.replace('without_helmet', 'helmet_cropped_plates')
            self.new_image_path = os.path.join(new_folder, filename)
            self.cropped_image_path = self.new_image_path
            # print(new_image_path) ---> cropped_numplate_images/2023-09-22/230922110930875.jpg
            try:
                image1 = Image.open(self.new_image_path)
                # Resize the cropped image to fit canvas1 and display it
                image1 = image1.resize((400, 135), Image.LANCZOS)
                tk_image1 = ImageTk.PhotoImage(image1)
                self.helmet_canvas1.create_image(0, 0, anchor=tk.NW, image=tk_image1)
                self.helmet_canvas1.image = tk_image1
                image1.close()
            except FileNotFoundError:
                pass
            self.helmet_canvas.itemconfigure(self.refresh_id, state='hidden')
            self.helmet_canvas.itemconfigure(self.zoom_id, state='normal')
            self.crop_button.configure(state=NORMAL)
        except FileNotFoundError as fn:
            self.helmet_canvas.itemconfigure(self.refresh_id, state='hidden')
            self.helmet_canvas.itemconfigure(self.zoom_id, state='normal')
            self.crop_button.configure(state=NORMAL)
            logging.error(f"Exception in helmet_offence(): {str(fn)}")
            self.helmet_canvas1.delete("all")
        except TclError:
            self.helmet_canvas.itemconfigure(self.refresh_id, state='hidden')
            self.helmet_canvas.itemconfigure(self.zoom_id, state='normal')
            self.crop_button.configure(state=NORMAL)
        except Exception:
            self.helmet_canvas.itemconfigure(self.refresh_id, state='hidden')
            self.helmet_canvas.itemconfigure(self.zoom_id, state='normal')
            self.crop_button.configure(state=NORMAL)

    def load_previous_image(self):
        try:
            # Get the current date folder
            current_date_folder = get_current_date_folder()
            if self.extracted_dir is not None:
                image_files = self.get_image_files_in_folder(self.extracted_dir)
                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index > 0:
                    # Load the previous image to the canvas
                    previous_image_path = image_files[current_image_index - 1]
                    self.helmet_canvas1.delete("all")
                    self.load_image_to_canvas(previous_image_path)
                    file_name = os.path.basename(previous_image_path)
                    prev_img_name, _ = os.path.splitext(file_name)
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(prev_img_name)
            else:
                # Get a list of image files in the current date folder
                image_files = self.get_image_files_in_folder(
                    os.path.join(f"/media/{getpass.getuser()}/Elements/without_helmet", current_date_folder))

                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index > 0:
                    # Load the previous image to the canvas
                    previous_image_path = image_files[current_image_index - 1]
                    self.helmet_canvas1.delete("all")
                    self.load_image_to_canvas(previous_image_path)
                    file_name = os.path.basename(previous_image_path)
                    prev_img_name, _ = os.path.splitext(file_name)
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(prev_img_name)

            # Disable/enable the "Previous" and "Next" buttons accordingly
            self.update_button_state()
        except Exception:
            pass

    def load_next_image(self):
        try:
            # Get the current date folder
            current_date_folder = get_current_date_folder()
            if self.extracted_dir is not None:
                image_files = self.get_image_files_in_folder(self.extracted_dir)
                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index < len(image_files) - 1:
                    # Load the next image to the canvas
                    next_image_path = image_files[current_image_index + 1]
                    self.helmet_canvas1.delete("all")
                    self.load_image_to_canvas(next_image_path)
                    file_name = os.path.basename(next_image_path)
                    next_img_name, _ = os.path.splitext(file_name)
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(next_img_name)
            else:
                # Get a list of image files in the current date folder
                image_files = self.get_image_files_in_folder(
                    os.path.join(f"/media/{getpass.getuser()}/Elements/without_helmet", current_date_folder))
                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index < len(image_files) - 1:
                    # Load the next image to the canvas
                    next_image_path = image_files[current_image_index + 1]
                    self.helmet_canvas1.delete("all")
                    self.load_image_to_canvas(next_image_path)
                    file_name = os.path.basename(next_image_path)
                    next_img_name, _ = os.path.splitext(file_name)
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(next_img_name)

            # Disable/enable the "Previous" and "Next" buttons accordingly
            self.update_button_state()

        except Exception:
            pass

    def update_button_state(self):
        try:
            # Get the current date folder
            current_date_folder = get_current_date_folder()
            if self.extracted_dir is not None:
                image_files = self.get_image_files_in_folder(self.extracted_dir)
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path) if self.file_path in image_files else -1
                # Enable/disable "Previous" and "Next" buttons based on the current image index
                self.back.config(state=tk.NORMAL if current_image_index > 0 else tk.DISABLED)
                self.next.config(state=tk.NORMAL if current_image_index < len(image_files) - 1 else tk.DISABLED)
                # self.canvas1.delete("all")
            else:
                # Get a list of image files in the current date folder
                image_files = self.get_image_files_in_folder(
                    os.path.join(f"/media/{getpass.getuser()}/Elements/without_helmet", current_date_folder))

                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path) if self.file_path in image_files else -1

                # Enable/disable "Previous" and "Next" buttons based on the current image index
                self.back.config(state=tk.NORMAL if current_image_index > 0 else tk.DISABLED)
                self.next.config(state=tk.NORMAL if current_image_index < len(image_files) - 1 else tk.DISABLED)
                # self.canvas1.delete("all")
        except Exception:
            pass

    def open_file_dialog(self):
        self.withdraw()
        transient_window = tk.Toplevel()
        transient_window.attributes('-topmost', True)
        transient_window.withdraw()
        cur_date = datetime.date.today()
        file_path = filedialog.askopenfilename(parent=transient_window,
                                               initialdir=f"/media/{getpass.getuser()}/Elements/without_helmet/{cur_date}",
                                               title="Select Image File From 'without_helmet' Folder Only.",
                                               filetypes=(
                                                   ("JPEG files", ".jpg"), ("BMP files", ".bmp"),
                                                   ("PNG files", ".png")))
        transient_window.destroy()
        if file_path:
            self.deiconify()
            start_index = file_path.find('without_helmet/')
            if start_index != -1:
                image_path = file_path[start_index:]
                self.load_image_to_canvas(image_path)
                dir_name = os.path.dirname(file_path)
                self.extracted_dir = os.path.join(f'/media/{getpass.getuser()}/Elements/without_helmet',
                                                  os.path.basename(dir_name))
                # print("extracted dir=", self.extracted_dir)
                self.get_image_files_in_folder(self.extracted_dir)
                if self.extracted_dir is not None:
                    image_files = self.get_image_files_in_folder(self.extracted_dir)
                    # print("image files=", image_files)
                    if not image_files:
                        return
                    # Find the index of the current image file
                    # print("self. file path=", self.file_path)
                    current_image_index = image_files.index(self.file_path)
                    current_image_path = image_files[current_image_index]
                    # print("current img path=", current_image_path)
                    self.load_image_to_canvas(current_image_path)
                    file_name = os.path.basename(current_image_path)
                    cur_img_name, _ = os.path.splitext(file_name)
                    # print("cur img name=", cur_img_name)
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(cur_img_name)
        # Disable/enable the "Previous" and "Next" buttons accordingly
        else:
            self.deiconify()
        self.update_button_state()

    def save_details(self):
        try:
            try:
                subprocess.Popen(['pkill', 'onboard'])
            except Exception:
                pass
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query = """
                        UPDATE helmetoffencerecords
                        SET numberplate = ?
                        WHERE image_id = ?;
                    """
            cursor.execute(query, (self.number_plate_entry.get().upper(), self.img_name))
            conn.commit()
            self.fetch_and_update_data_from_database(self.img_name)
            # print(self.img_name)  # 230922110930875
            query1 = """
                        SELECT *
                        FROM helmetoffencerecords
                        WHERE image_id = ?;
                    """
            cursor.execute(query1, (self.img_name,))
            row = cursor.fetchone()
            conn.close()
            self.withdraw()
            messagebox.showinfo("Success", "Data is saved!")
            self.deiconify()
        except Exception as sd:
            logging.error(f"Exception in save_details(Class Helmet_Offence): {str(sd)}")
        try:
            image = Image.open(self.cropped_image_path)
            image.save(self.new_image_path)
            image.close()
        except Exception:
            pass


def check_and_upload_data(date_time):
    # Connect to the database
    conn = sqlite3.connect('msiplusersettingsmh.db')
    cursor = conn.cursor()

    # Check if a record with the same number plate exists for the current date
    cursor.execute("SELECT uploaded FROM numberplaterecords WHERE datetime = ?",
                   (date_time,))
    existing_record = cursor.fetchone()
    # print("existing record line 903:", existing_record) = ('n',)
    conn.close()

    if existing_record:
        uploaded_status = existing_record[0]
        if uploaded_status == 'n':
            # Data exists but not uploaded, so upload the data
            return True
        else:
            # Data already uploaded, no need to upload again
            return False
    else:
        # No existing record, insert the new data and mark as 'y' uploaded
        return True


# Function to check internet connectivity
def check_internet_connection():
    try:
        response = requests.get("https://www.google.com", timeout=2)
        return response.status_code == 200
    except requests.ConnectionError:
        return False


def is_valid(value):
    if 7 < len(value) <= 10:
        # EX: KA03MB0000
        pattern1 = r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{1,4}$"
        pattern2 = r"^[0-9]{2}[A-Z]{2}[0-9]{1,4}[A-Z]{1,2}$"
        if bool(re.match(pattern1, value)) or bool(re.match(pattern2, value)):
            return True
        else:
            pass
    elif len(value) == 8:
        pattern3 = r"^[A-Z]{2}[0-9]{6}$"
        return bool(re.match(pattern3, value))
    elif len(value) == 7:
        pattern4 = r"^[A-Z]{1,3}[0-9]{1,4}$"
        return bool(re.match(pattern4, value))
    else:
        return False


class Offence(tk.Toplevel):
    instance = None

    def __init__(self, parent):
        super().__init__(parent)
        self.updated_vehicle_category = None
        self.offence_id = None
        self.selected_offence = None
        logging.info("Entered Class Offence()")
        self.offences_dict = {
            "2 Wheeler / 3 Wheeler Speed Violation": 2451,
            "Tractor Speed Violation": 10913,
            "LMV Speed Violation": 10915,
            "Other than 2W,3W,Tractor & LMV Speed Violation": 10917,
        }
        self.vehicle_types = ["LMV-COMMERCIAL", "LMV-PERSONAL", "HMV", "BIKE"]
        self.extracted_dir = None
        self.geometry("1280x762+0+0")
        self.title("Generate Over Speed Challan")
        self.result = None
        # self.wm_overrideredirect(True)
        self.resizable(False, False)
        self.configure(bg="orange")
        self.transient(parent)  # To always set this window on top of the MainApplication window
        self.grab_set()

        conn = sqlite3.connect('msiplusersettingsmh.db')
        time.sleep(0.02)
        cursor = conn.cursor()
        columns = ["RTO_Code", "District_Name", "NIC_District_ID", "NIC_userId"]
        sql_query = f"SELECT {', '.join(columns)} FROM initialization_status"
        cursor.execute(sql_query)
        row = cursor.fetchone()
        if row:
            rto_code, district_name, nic_district_id, nic_user_id = row
            self.rto_code = int(rto_code[2:])
            self.district_name = district_name
            self.nic_district_id = int(nic_district_id)
            self.nic_user_id = int(nic_user_id)
        else:
            messagebox.showerror("Critical", "Missing table in database.Please check.")
        conn.commit()
        conn.close()

        self.canvas_frame = tk.Frame(self, bg="orange")
        self.canvas_frame.grid(row=0, column=0)

        # Canvas
        self.canvas = tk.Canvas(self.canvas_frame, width=800, height=537, bg="white")  # 600, 437
        self.canvas.pack()

        self.right_frame = tk.Frame(self, bg="orange")
        self.right_frame.grid(row=0, column=1, padx=5)

        self.right_bottom_frame = tk.Frame(self, bg="orange")
        self.right_bottom_frame.grid(row=2, column=1, padx=5)

        self.canvas1 = tk.Canvas(self.right_frame, width=400, height=135, bg="white")
        self.canvas1.grid(row=0, columnspan=2, column=0, padx=35)

        back_img = Image.open('resources/48PX/back.png')
        back_img = back_img.resize((60, 60), Image.LANCZOS)
        back_photo = ImageTk.PhotoImage(back_img)
        self.back_photo = back_photo
        # Create buttons
        self.back = ttk.Button(self.canvas, command=self.load_previous_image)
        self.back.configure(width=7, takefocus=False, image=self.back_photo)
        self.back.pack()
        self.canvas.create_window(60, 268, window=self.back)

        next_img = Image.open('resources/48PX/right.png')
        next_img = next_img.resize((58, 58), Image.LANCZOS)
        next_photo = ImageTk.PhotoImage(next_img)
        self.next_photo = next_photo
        # Create buttons
        self.next = ttk.Button(self.canvas, command=self.load_next_image)
        self.next.configure(width=7, takefocus=False, image=self.next_photo)
        self.next.pack()
        self.canvas.create_window(740, 268, window=self.next)

        zoom_img = Image.open('resources/48PX/zoomin.png')
        zoom_img = zoom_img.resize((48, 48), Image.LANCZOS)
        zoom_photo = ImageTk.PhotoImage(zoom_img)
        self.zoom_photo = zoom_photo
        # Create buttons
        self.zoom = ttk.Button(self.canvas, command=self.start_crop_zoom)
        self.zoom.configure(width=7, takefocus=False, image=self.zoom_photo)
        self.zoom.pack()
        self.zoom_id = self.canvas.create_window(750, 500, window=self.zoom)

        refresh_img = Image.open('resources/48PX/Refresh_Again.png')
        refresh_img = refresh_img.resize((48, 48), Image.LANCZOS)
        refresh_photo = ImageTk.PhotoImage(refresh_img)
        self.refresh_photo = refresh_photo
        # Create buttons
        self.refresh = ttk.Button(self.canvas, command=self.refresh_func)
        self.refresh.configure(width=7, takefocus=False, image=self.refresh_photo)
        self.refresh.pack()
        self.refresh_id = self.canvas.create_window(750, 500, window=self.refresh)
        self.canvas.itemconfigure(self.refresh_id, state='hidden')

        # Button to open file dialog
        open_img = Image.open('resources/48PX/View.png')
        open_img = open_img.resize((30, 30), Image.LANCZOS)
        open_photo = ImageTk.PhotoImage(open_img)
        self.open_photo = open_photo
        # Create an open image button
        self.button = tk.Button(self.right_frame, text="Browse Images",
                                compound=tk.LEFT, command=self.open_file_dialog)
        self.button.configure(image=self.open_photo)
        self.button.grid(row=1, column=0, pady=5)

        '''self.printer_label = tk.Label(self, text="Select a printer:", bg="orange")
        self.printer_label.grid(row=1, column=0, pady=5)
        printers = list_printers()'''
        bigfont = font.Font(family="Arial", size=14)
        self.option_add("*Font", bigfont)
        '''self.printer_combo = ttk.Combobox(self, values=printers, state="readonly", width=20, font=('Arial', 15))
        self.printer_combo.set('Select a printer')
        style = ttk.Style()  # "*Font"
        self.printer_combo.grid(row=2, column=0)'''
        # Create progress bar
        style = ttk.Style()
        style.configure("green.Horizontal.TProgressbar", troughcolor="white", background="green")
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(self, style="green.Horizontal.TProgressbar", variable=self.progress_var,
                                            maximum=100, mode="determinate", length=750,
                                            orient=tk.HORIZONTAL)
        self.progress_bar.grid(row=1, column=0, pady=10)

        self.nic_uploaded_label = tk.Label(self, text="NO VIOLATIONS TODAY", bg="green", font=("Arial", 50))
        self.nic_uploaded_label.grid(row=2, column=0, pady=5)
        # self.nic_uploaded_label.grid_remove()
        '''self.nic_uploaded_entry = tk.Entry(self)f'/media/{getpass.getuser()}/Elements/images_with_info'
        self.nic_uploaded_entry.grid(row=2, column=0, pady=5)'''

        # Create a close window button
        self.close_button = tk.Button(self.right_frame, text="Close", bg="red", height=3, width=10,
                                      compound=tk.LEFT, command=self.destroy_window)
        self.close_button.grid(row=1, column=1, pady=5)

        '''# Location
        self.location_label = tk.Label(self.right_frame, text="Location:", bg="orange")
        self.location_label.grid(row=1, column=0, pady=5)
        self.location_entry = tk.Entry(self.right_frame)
        self.location_entry.grid(row=1, column=1, pady=5)

        # Officer ID
        self.officer_id_label = tk.Label(self.right_frame, text="Officer ID:", bg="orange")
        self.officer_id_label.grid(row=2, column=0, pady=5)
        self.officer_id_entry = tk.Entry(self.right_frame)
        self.officer_id_entry.grid(row=2, column=1, pady=5)

        # Officer Name
        self.officer_name_label = tk.Label(self.right_frame, text="Officer Name:", bg="orange")
        self.officer_name_label.grid(row=3, column=0, pady=5)
        self.officer_name_entry = tk.Entry(self.right_frame)
        self.officer_name_entry.grid(row=3, column=1, pady=5)

        # Speed limit
        self.speed_label = tk.Label(self.right_frame, text="Speed Limit:", bg="orange")
        self.speed_label.grid(row=4, column=0, pady=5)
        self.speed_entry = tk.Entry(self.right_frame)
        self.speed_entry.grid(row=4, column=1, pady=5)'''

        '''# Vehicle speed
        self.vspeed_label = tk.Label(self.right_frame, text="Vehicle Speed: Distance:", bg="orange")
        self.vspeed_label.grid(row=2, column=0, pady=5)
        self.vspeed_entry = tk.Entry(self.right_frame, width=4)
        self.vspeed_entry.grid(row=3, column=0, pady=5)

        # Distance
        self.distance_label = tk.Label(self.right_frame, text="Distance:", bg="orange")
        self.distance_label.grid(row=4, column=0, pady=5)
        self.distance_entry = tk.Entry(self.right_frame, width=4)
        self.distance_entry.grid(row=3, column=1, pady=5)'''

        '''# Direction
        self.direction_label = tk.Label(self.right_frame, text="Direction:", bg="orange")
        self.direction_label.grid(row=7, column=0, pady=5)
        self.direction_entry = tk.Entry(self.right_frame)
        self.direction_entry.grid(row=7, column=1, pady=5)

        # Laser ID
        self.laser_label = tk.Label(self.right_frame, text="Laser ID:", bg="orange")
        self.laser_label.grid(row=8, column=0, pady=5)
        self.laser_entry = tk.Entry(self.right_frame)
        self.laser_entry.grid(row=8, column=1, pady=5)'''

        # Vehicle speed
        self.vspeed_label = tk.Label(self.right_frame, text="Vehicle Speed: ", bg="yellow")
        self.vspeed_label.grid(row=2, column=0, pady=5)

        # Speed limit
        self.speed_label = tk.Label(self.right_frame, text="Speed Limit: ", bg="yellow")
        self.speed_label.grid(row=2, column=1, pady=5)

        # Time
        self.time_label = tk.Label(self.right_frame, text="Time:", bg="orange")
        self.time_label.grid(row=3, column=0, pady=5)
        self.time_entry = tk.Entry(self.right_frame, state="readonly")
        self.time_entry.grid(row=4, column=0, pady=5)

        # Image ID
        self.image_id_label = tk.Label(self.right_frame, text="Image ID:", bg="orange")
        self.image_id_label.grid(row=5, column=0, pady=5)
        self.image_id_entry = tk.Entry(self.right_frame, state="readonly")
        self.image_id_entry.grid(row=6, column=0, pady=5)

        '''# Date
        self.date_label = tk.Label(self.right_frame, text="Date:", bg="orange")
        self.date_label.grid(row=10, column=0, pady=5)
        self.date_entry = tk.Entry(self.right_frame)
        self.date_entry.grid(row=10, column=1, pady=5)'''

        # Create a label to display the extracted number plate text
        self.number_plate_label = tk.Label(self.right_frame, text="Number Plate:", bg="orange")
        self.number_plate_label.grid(row=7, column=0, pady=5)

        # Create an entry field to show the extracted number plate text
        entry_var = StringVar()
        validate_cmd = self.register(self.on_validate)
        self.number_plate_entry = tk.Entry(self.right_frame, textvariable=entry_var, width=12, validate="key",
                                           validatecommand=(validate_cmd, '%P', '%d'), font=("Arial", 25))
        self.number_plate_entry.grid(row=8, column=0, pady=5)
        self.number_plate_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        # Save Button
        save_img = Image.open('resources/48PX/save.png')
        save_img = save_img.resize((30, 30), Image.LANCZOS)
        save_photo = ImageTk.PhotoImage(save_img)
        self.save_photo = save_photo

        # Update Button
        update_img = Image.open('resources/48PX/car.png')
        update_img = update_img.resize((30, 30), Image.LANCZOS)
        update_photo = ImageTk.PhotoImage(update_img)
        self.update_photo = update_photo

        # Create a print button
        self.save_button = tk.Button(self.right_frame, text="Save",
                                     compound=tk.LEFT, command=self.save_details)
        self.save_button.configure(image=self.save_photo)
        self.save_button.grid(row=8, column=1, pady=5)

        self.combobox = ttk.Combobox(self.right_bottom_frame, values=list(self.offences_dict.keys()), state="readonly", width=40,
                                     font=("Arial", 15))
        self.combobox.set("Select Offence")
        self.combobox.grid(row=2, columnspan=2, column=0, pady=10)

        # Bind event handler to ComboBox selection
        self.combobox.bind("<<ComboboxSelected>>", self.on_combobox_select)

        self.vehicle_combobox = ttk.Combobox(self.right_bottom_frame, values=self.vehicle_types, state="readonly", width=17,
                                     font=("Arial", 15))
        self.vehicle_combobox.set("")
        self.vehicle_combobox.grid(row=0, rowspan=2, column=0, pady=10)

        # Bind event handler to ComboBox selection
        self.vehicle_combobox.bind("<<ComboboxSelected>>", self.on_vehicle_combobox_select)

        self.update_button = tk.Button(self.right_bottom_frame, text="Update",
                                     compound=tk.LEFT, command=self.update_details, state=DISABLED)
        self.update_button.configure(image=self.update_photo)
        self.update_button.grid(row=0, column=1, pady=10)

        # Crop Button
        crop_img = Image.open('resources/48PX/Edit.png')
        crop_img = crop_img.resize((30, 30), Image.LANCZOS)
        crop_photo = ImageTk.PhotoImage(crop_img)
        self.crop_photo = crop_photo
        # Create a print button
        self.crop_button = tk.Button(self.right_frame, text="Crop",
                                     compound=tk.LEFT, command=self.start_crop)
        self.crop_button.configure(image=self.crop_photo)
        self.crop_button.grid(row=6, column=1, pady=5)

        '''print_img = Image.open('resources/48PX/Print.png')
        print_img = print_img.resize((30, 30), Image.LANCZOS)
        print_photo = ImageTk.PhotoImage(print_img)
        self.print_photo = print_photo
        # Create a print button
        self.print_button = tk.Button(self, text="Print",
                                      compound=tk.LEFT, command=self.print_func)
        self.print_button.configure(image=self.print_photo)
        self.print_button.grid(row=2, columnspan=2, pady=5)'''

        firebase_img = Image.open('resources/img/firebase.png')
        firebase_img = firebase_img.resize((30, 30), Image.LANCZOS)
        firebase_photo = ImageTk.PhotoImage(firebase_img)
        self.firebase_photo = firebase_photo
        # Create a firebase button
        self.nic_button = tk.Button(self.right_frame, text="Upload",
                                    compound=tk.LEFT, command=self.manual_upload, state=DISABLED)
        self.nic_button.configure(image=self.firebase_photo)
        self.nic_button.grid(row=4, column=1, pady=5)

        # Initialize cropping variables
        self.crop_start_x = 0
        self.crop_start_y = 0
        self.crop_rect = None
        self.file_path = None  # Variable to store the current image file path
        self.crop_window = None

        self.crop_start_x1 = 0
        self.crop_start_y1 = 0
        self.crop_rect1 = None
        self.file_path1 = None
        self.crop_window1 = None

        # Load the default image to the canvas
        self.load_default_image()

    def refresh_func(self):
        self.crop_button.configure(state=NORMAL)
        pil_image = Image.open(self.file_path)
        pil_image = pil_image.resize((800, 537), Image.LANCZOS)  # 600, 437
        # Convert image to Tkinter PhotoImage format
        tk_image = ImageTk.PhotoImage(pil_image)

        # self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
        self.canvas.image = tk_image
        pil_image.close()
        self.canvas.itemconfigure(self.refresh_id, state='hidden')
        self.canvas.itemconfigure(self.zoom_id, state='normal')

    def on_combobox_select(self, event):
        self.selected_offence = self.combobox.get()
        self.offence_id = self.offences_dict.get(self.selected_offence, "N/A")
        self.nic_button.config(state=NORMAL)

    def on_vehicle_combobox_select(self, event):
        self.updated_vehicle_category = self.vehicle_combobox.get()
        self.update_button.config(state=NORMAL)

    @classmethod
    def create(cls, parent):
        # Create a new instance of Offence
        if cls.instance is not None:
            cls.instance.destroy()
        cls.instance = cls(parent)
        cls.instance.protocol("WM_DELETE_WINDOW", cls.destroy_instance)

    @classmethod
    def destroy_instance(cls):
        # Destroy current instance of Offence
        if cls.instance is not None:
            cls.instance.destroy()
            cls.instance = None

    def on_validate(self, value, action):
        # Check if the length of the input is less than or equal to 10
        return len(value) <= 10

    def destroy_window(self):
        self.destroy()
        Offence.instance = None

    def send_image(self, laser_id, image_base64, lpimage_base64, location, lat, lon, vehicle_speed, speed_limit,
                   distance, number_plate, image_key, date, cur_time, vhclass):
        '''self.rto_code = int(rto_code[2:])
            self.district_name = district_name
            self.nic_district_id = int(nic_district_id)
            self.nic_user_id = int(nic_user_id)'''
        try:
            if not check_internet_connection():
                return False
            dp = cur_time.split('_')
            fd = dp[1].replace('-', ':')
            cur_time = f"{dp[0]} {fd}"

            # Format the datetime object as a string
            current_datetime = datetime.datetime.now()
            # Format the datetime object as a string
            action_time = current_datetime - datetime.timedelta(minutes=2)
            formatted_datetime = action_time.strftime("%Y-%m-%d %H:%M:%S")
            url = "https://itmschallan.parivahan.gov.in/pushwssg/api/echallan/pushdata"
            # url = "https://staging.parivahan.gov.in/pushwssg/api/echallan/pushdata/"
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            }
            combo = self.combobox.get()
            cctv_notice_data = [
                {
                    "offenceId": f"{self.offences_dict.get(combo, 'N/A')}",
                    "dpCd": "TR",
                    "latitude": 1.0 if lat == '' else float(lat),
                    "transactionNo": str(image_key),
                    "userId": self.nic_user_id,
                    "regnNo": str(number_plate),
                    "voilationSource": "RLVD",
                    "voilationSourceCatg": f"{combo}",
                    "stateCd": "MH",
                    "districtId": self.nic_district_id,
                    "location": str(location),
                    "offCd": self.rto_code,
                    "equipmentId": str(laser_id),
                    "vendorName": "MSI",
                    "vehicleSpeed": 0 if vehicle_speed is None else int(vehicle_speed),
                    "speedLimit": 0 if speed_limit is None else int(speed_limit),
                    "district": self.district_name,
                    "vehicleWeight": 0,
                    "voilationTime": f"{cur_time}",
                    "actionTime": f"{formatted_datetime}",
                    "longitude": 1.0 if lon == '' else float(lon),
                    "image1": image_base64,
                    "image2": lpimage_base64,
                    "vhClass": str(vhclass)
                }
            ]
            self.progress_var.set(70)
            self.update_idletasks()
            data = {
                'cctvNoticeData': cctv_notice_data
            }

            try:
                with open(f'/media/{getpass.getuser()}/Elements/original_images/{dp[0]}/Log/{image_key}.json',
                          'w') as filez:
                    json.dump(data, filez, indent=2)
            except Exception as js:
                logging.error(f"Exception while writing data to json file: {str(js)}")
                pass
            self.progress_var.set(90)
            self.update_idletasks()

            # Set timeout in seconds
            timeout_seconds = 60
            try:
                response = requests.post(url, json=data, headers=headers, timeout=timeout_seconds)
                response_data = response.json()  # Parse JSON response
                pprint(response_data)
                self.progress_var.set(100)
                self.update_idletasks()
                # Check the response
                if response.status_code == 200:
                    status_message = response_data.get("responseMsg", {}).get("status", "")
                    success_message = response_data.get("responseMsg", {}).get("reason", "")
                    '''self.withdraw()
                    messagebox.showinfo(f"Code:{status_message}", success_message)
                    self.deiconify()'''
                    '''present_dialog = tk.Toplevel()
                    present_dialog.title(f"{status_message}")
                    present_dialog.resizable(False, False)
                    present_dialog.geometry("350x100+550+350")
                    tk.Label(present_dialog, text=f"{success_message}").pack(pady=10)'''
                    # pprint(success_message)
                    conn = sqlite3.connect('msiplusersettingsmh.db')
                    time.sleep(0.01)
                    cursor = conn.cursor()
                    query = """
                                UPDATE numberplaterecords
                                SET uploaded = ?, numberplate = ?, offence_type = ?
                                WHERE image_id = ?;
                            """
                    cursor.execute(query, ('y', number_plate, f"{combo}", image_key))
                    conn.commit()
                    conn.close()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    return True
                elif response.status_code == 400:
                    if response_data.get("responseMsg", {}) is None:
                        try:
                            with open(
                                    f'/media/{getpass.getuser()}/Elements/original_images/{dp[0]}/Log/{image_key}.json',
                                    'r+') as filez:
                                json_data = json.load(filez)
                                json.dump(response_data, filez, indent=2)
                        except Exception as js:
                            logging.error(f"Exception while writing response data to json file in speed response code 400: {str(js)}")
                        self.withdraw()
                        messagebox.showinfo(f"NIC-Reply", "Response Status Code : 400")
                        self.deiconify()
                        self.progress_var.set(0)
                        self.update_idletasks()
                        '''present_dialog = tk.Toplevel()
                        present_dialog.title(f"{status_message}")
                        present_dialog.resizable(False, False)
                        present_dialog.geometry("350x100+550+350")
                        tk.Label(present_dialog, text=f"{error_message}").pack(pady=10)'''
                        # pprint(error_message)
                        logging.warning(f"Failed to push speed data")
                        return False
                    status_message = response_data.get("responseMsg", {}).get("status", "")
                    error_message = response_data.get("responseMsg", {}).get("reason", "")
                    self.withdraw()
                    # Append response message to the JSON file
                    rejected_response_msg = response_data['rejectedData'][0]['responseMsg']
                    try:
                        with open(f'/media/{getpass.getuser()}/Elements/original_images/{dp[0]}/Log/{image_key}.json',
                                  'r+') as filez:
                            json_data = json.load(filez)
                            json.dump(rejected_response_msg, filez, indent=2)
                    except Exception as js:
                        logging.error(f"Exception while writing response data to json file: {str(js)}")
                    messagebox.showinfo(f"NIC-Reply:{status_message}", error_message)
                    self.deiconify()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    '''present_dialog = tk.Toplevel()
                    present_dialog.title(f"{status_message}")
                    present_dialog.resizable(False, False)
                    present_dialog.geometry("350x100+550+350")
                    tk.Label(present_dialog, text=f"{error_message}").pack(pady=10)'''
                    pprint(error_message)
                    logging.warning(f"Failed to push speed data")
                    return False
                elif response.status_code != 200 and response.status_code != 400:
                    status_message = response_data.get("responseMsg", {}).get("status", "")
                    error_message = response_data.get("responseMsg", {}).get("reason", "")
                    self.withdraw()
                    # Append response message to the JSON file
                    rejected_response_msg = response_data['rejectedData'][0]['responseMsg']
                    try:
                        with open(f'/media/{getpass.getuser()}/Elements/original_images/{dp[0]}/Log/{image_key}.json',
                                  'r+') as filez:
                            json_data = json.load(filez)
                            json.dump(rejected_response_msg, filez, indent=2)
                    except Exception as js:
                        logging.error(f"Exception while writing response data to json file: {str(js)}")
                    messagebox.showinfo(f"NIC-Reply:{status_message}", error_message)
                    self.deiconify()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    '''present_dialog = tk.Toplevel()
                    present_dialog.title(f"{status_message}")
                    present_dialog.resizable(False, False)
                    present_dialog.geometry("350x100+550+350")
                    tk.Label(present_dialog, text=f"{error_message}").pack(pady=10)'''
                    pprint(error_message)
                    logging.warning(f"Failed to push speed data")
                    return False
                elif any('Transaction number already' in entry['responseMsg']['reason'] for entry in
                         response_data['rejectedData']):
                    # pprint(success_message)
                    conn = sqlite3.connect('msiplusersettingsmh.db')
                    time.sleep(0.01)
                    cursor = conn.cursor()
                    query = """
                                UPDATE numberplaterecords
                                SET uploaded = ?, numberplate = ?, offence_type = ?
                                WHERE image_id = ?;
                            """
                    cursor.execute(query, ('y', number_plate, f"{combo}", image_key))
                    conn.commit()
                    conn.close()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    return True
                else:
                    status_message = response_data.get("responseMsg", {}).get("status", "")
                    error_message = response_data.get("responseMsg", {}).get("reason", "")
                    self.withdraw()
                    # Append response message to the JSON file
                    rejected_response_msg = response_data['rejectedData'][0]['responseMsg']
                    try:
                        with open(f'/media/{getpass.getuser()}/Elements/original_images/{dp[0]}/Log/{image_key}.json',
                                  'r+') as filez:
                            json_data = json.load(filez)
                            json.dump(rejected_response_msg, filez, indent=2)
                    except Exception as js:
                        logging.error(f"Exception while writing response data to json file: {str(js)}")
                    messagebox.showinfo(f"NIC-Reply:{status_message}", error_message)
                    self.deiconify()
                    self.progress_var.set(0)
                    self.update_idletasks()
                    '''present_dialog = tk.Toplevel()
                    present_dialog.title(f"{status_message}")
                    present_dialog.resizable(False, False)
                    present_dialog.geometry("350x100+550+350")
                    tk.Label(present_dialog, text=f"{error_message}").pack(pady=10)'''
                    pprint(error_message)
                    logging.warning(f"Failed to push speed data")
                    return False
            except requests.exceptions.Timeout:
                self.withdraw()
                error_message1 = f"Error: Request timed out. Please try again."
                messagebox.showerror("Timeout Error", error_message1)
                self.deiconify()
                self.progress_var.set(0)
                self.update_idletasks()
                '''present_dialog = tk.Toplevel()
                present_dialog.title("Error")
                present_dialog.resizable(False, False)
                present_dialog.geometry("350x100+550+350")
                tk.Label(present_dialog, text=f"{error_message1}").pack(pady=10)'''

                logging.error(f"Exception in uploading data to itms: {str(error_message1)}")
            except requests.exceptions.RequestException as e:
                # Handle other request exceptions
                error_message2 = f"Try again: {e}"
                self.withdraw()
                messagebox.showerror("Request Error", error_message2)
                self.deiconify()
                self.progress_var.set(0)
                self.update_idletasks()
                '''present_dialog = tk.Toplevel()
                present_dialog.title("Error!")
                present_dialog.resizable(False, False)
                present_dialog.geometry("350x100+550+350")
                tk.Label(present_dialog, text=f"{error_message2}").pack(pady=10)'''
                logging.error(f"Exception in uploading data to itms: {str(error_message2)}")
            except Exception as a:
                print("E1 expected internet issue maybe")
                # Handle other request exceptions
                error_message3 = f"E1 - {a}"
                self.withdraw()
                messagebox.showerror("Error", error_message3)
                self.deiconify()
                self.progress_var.set(0)
                self.update_idletasks()
                logging.error(f"Exception in uploading data to itms, in sphu.py inside send_image(): {str(a)}")
                return False
        except Exception as ex:
            self.withdraw()
            messagebox.showerror("Error", f"{str(ex)}")
            self.deiconify()
            self.progress_var.set(0)
            self.update_idletasks()
            logging.error(f"Exception in sphu.py inside send_image(): {str(ex)}")
            return False

    def manual_upload(self):
        try:
            # Connect to the database and retrieve data
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query = "SELECT * FROM numberplaterecords WHERE image_id = ?"
            data = cursor.execute(query, (self.image_id_entry.get(),)).fetchone()
            conn.close()  # total 16 cloumns (0-15)
            laser_id = data[11]
            date = data[2]
            # Use 'Time' as the unique key
            image_key = data[0]
            actual_lp = data[10]
            if actual_lp != self.number_plate_entry.get():
                self.withdraw()
                messagebox.showwarning("LP Mismatch", "Please click on SAVE before uploading!")
                self.deiconify()
                return
            self.nic_button.config(state=DISABLED)
            self.update_button.config(state=DISABLED)
            self.close_button.config(state=DISABLED)
            if check_internet_connection():
                self.progress_var.set(10)
                self.update_idletasks()
                if len(self.number_plate_entry.get()) > 6:
                    self.progress_var.set(20)
                    self.update_idletasks()
                    if self.combobox.get() != 'Select Offence':
                        self.progress_var.set(30)
                        self.update_idletasks()
                        is_not_uploaded = check_and_upload_data(self.time_entry.get())
                        if is_not_uploaded:
                            self.progress_var.set(50)
                            self.update_idletasks()

                            # Read the image file and convert it to Base64
                            time.sleep(0.02)
                            with open(
                                    f"/media/{getpass.getuser()}/Elements/number_plate_images/{date}/upload/{self.image_id_entry.get()}.jpg",
                                    "rb") as image_file:
                                image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
                            if os.path.exists(
                                    f"/media/{getpass.getuser()}/Elements/cropped_numplate_images/{date}/{self.image_id_entry.get()}.jpg"):
                                with open(
                                        f"/media/{getpass.getuser()}/Elements/cropped_numplate_images/{date}/{self.image_id_entry.get()}.jpg",
                                        "rb") as image_file:
                                    lpimage_base64 = base64.b64encode(image_file.read()).decode("utf-8")
                            else:
                                with open("resources/img/notavailable.jpg", "rb") as image_file:
                                    lpimage_base64 = base64.b64encode(image_file.read()).decode("utf-8")
                            self.progress_var.set(60)
                            self.update_idletasks()

                            ret = self.send_image(laser_id, image_base64, lpimage_base64, data[3], data[13],
                                                  data[14],
                                                  data[7],
                                                  data[6], data[8], self.number_plate_entry.get(), image_key,
                                                  date,
                                                  self.time_entry.get(), data[17])
                            if ret:
                                self.progress_var.set(0)
                                self.update_idletasks()
                                self.fetch_and_update_data_from_database(self.image_id_entry.get())
                                self.nic_button.config(state=NORMAL)
                                self.update_button.config(state=NORMAL)
                                self.close_button.config(state=NORMAL)
                            else:
                                self.progress_var.set(0)
                                self.update_idletasks()
                                self.nic_button.config(state=NORMAL)
                                self.update_button.config(state=NORMAL)
                                self.close_button.config(state=NORMAL)
                        else:
                            present_dialog = tk.Toplevel(self)
                            present_dialog.title("Information")
                            present_dialog.resizable(False, False)
                            present_dialog.geometry("350x100+550+350")
                            tk.Label(present_dialog, text="Data is already uploaded.").pack()
                            logging.error(
                                f"Data with {str(self.image_id_entry.get())} is already uploaded.")
                            self.nic_button.config(state=NORMAL)
                            self.update_button.config(state=NORMAL)
                            self.close_button.config(state=NORMAL)
                    else:
                        self.withdraw()
                        error_message0 = "Select a valid Offence type."
                        messagebox.showwarning("Warning", error_message0)
                        self.progress_var.set(0)
                        self.update_idletasks()
                        self.deiconify()
                        self.nic_button.config(state=NORMAL)
                        self.update_button.config(state=NORMAL)
                        self.close_button.config(state=NORMAL)
                else:
                    self.withdraw()
                    error_message = "Number Plate should have atleast 7 characters."
                    messagebox.showwarning("Warning", error_message)
                    self.progress_var.set(0)
                    self.update_idletasks()
                    self.deiconify()
                    self.nic_button.config(state=NORMAL)
                    self.update_button.config(state=NORMAL)
                    self.close_button.config(state=NORMAL)
            else:
                self.withdraw()
                error_message1 = "No Internet Connection."
                messagebox.showerror("Connection Error", error_message1)
                self.progress_var.set(0)
                self.update_idletasks()
                self.deiconify()
                self.nic_button.config(state=NORMAL)
                self.update_button.config(state=NORMAL)
                self.close_button.config(state=NORMAL)
                '''
                error_dialog = tk.Toplevel(self)
                error_dialog.title("Connection Error")
                error_dialog.resizable(False, False)
                error_dialog.geometry("350x100+550+350")
                tk.Label(error_dialog, text="No Internet Connection.").pack()'''

                logging.error("No Internet Connection to push data.")
            # self.fetch_and_update_data_from_database(self.image_id_entry.get())

        except Exception as e:
            logging.error(f"{str(e)}, in manual_upload() speed cases")
            self.progress_var.set(0)
            self.update_idletasks()
            self.nic_button.config(state=NORMAL)
            self.update_button.config(state=NORMAL)
            self.close_button.config(state=NORMAL)

    def print_func(self):
        try:
            if self.number_plate_entry.get() == '' or self.number_plate_entry.get() == ' ':
                error_dialog = tk.Toplevel(self)
                error_dialog.title("No Number Plate found.")
                error_dialog.geometry("350x100+550+350")
                tk.Label(error_dialog, text="Number plate cannot be empty.").pack()
                return

            # Connect to the database and retrieve data
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query = "SELECT * FROM numberplaterecords WHERE image_id = ?"
            data = cursor.execute(query, (self.image_id_entry.get(),)).fetchone()
            # print("print data:", data)
            conn.close()

            selected_printer = self.printer_combo.get()
            if selected_printer:
                output_filename = f"{self.time_entry.get()}.pdf"
                self.generate_pdf(data, output_filename)
                print_pdf(output_filename, selected_printer)
            else:
                error_dialog = tk.Toplevel(self)
                error_dialog.title("Print Status")
                error_dialog.geometry("350x100+550+350")
                tk.Label(error_dialog, text="No printer is selected. Select a printer and try again.").pack()

        except Exception as e:
            print(e)

    def generate_pdf(self, data, output_filename):
        '''username = getpass.getuser()
        c = canvas.Canvas(output_filename, pagesize=A4)
        c.setFillColorRGB(1, 0, 0)
        c.setFont("Helvetica-Bold", 30)
        c.drawString(130, 800, "OVER-SPEED CHALLAN")

        # Draw images
        c.drawImage('resources/img/Maharashtra_State_Road_Transport_Corporation_logo.png', 495, 775, width=80,
                    height=60)
        c.drawImage(self.file_path, 20, 520, width=555, height=250)
        if os.path.exists(f'/media/{username}/Elements/cropped_numplate_images/{data[2]}/{self.image_id_entry.get()}.jpg'):
            c.drawImage(
                f'/media/{username}/Elements/cropped_numplate_images/{data[2]}/{self.image_id_entry.get()}.jpg',
                20, 400,
                width=255, height=100)
        else:
            c.drawImage('resources/img/notavailable.jpg', 20, 400, width=255, height=100)
        if os.path.exists(
                f'/media/{username}/Elements/number_plate_images/{data[2]}/maps/map_screenshot.png'):
            c.drawImage(
                f'/media/{username}/Elements/number_plate_images/{data[2]}/maps/map_screenshot.png',
                275, 300, width=300,
                height=200)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 12)
        if data:
            c.drawString(50, 300, f"Offence Time: {data[1]}")
            c.drawString(50, 280, f"Date: {data[2]}")
            c.drawString(300, 280, f"Location: {data[3]}")
            c.drawString(50, 260, f"Officer Name: {data[4]}")
            c.drawString(50, 240, f"Officer ID: {data[5]}")
            c.drawString(50, 220, f"Speed Limit: {data[6]} kmph")
            c.drawString(50, 200, f"Vehicle Speed: {data[7]} kmph")
            c.drawString(50, 180, f"Distance: {data[8]} m")
            c.drawString(50, 160, f"Direction: {data[9]}")
            c.drawString(50, 380, f"Number Plate: {data[10]}")
            c.drawString(50, 140, f"Device ID: {data[11]}")

        # Draw signature and copyright text
        c.setFillColorRGB(1, 0, 0)  # Red color
        c.drawString(40, 50, "Signature of Officer")
        c.drawString(450, 50, "Signature of Offender")

        # Draw copyright symbol and text
        c.setFillColorRGB(0, 0, 0)  # Black color
        c.drawString(250, 20, "©")
        c.drawString(260, 20, " MSIPL, Bangalore.")

        c.save()'''

    # <----------------------------For Zoom Functions----------------------------------------------------------->
    def start_crop_zoom(self):
        self.crop_button.configure(state=DISABLED)
        # Bind the mouse events for cropping
        self.canvas.bind("<ButtonPress-1>", self.on_press_zoom)
        self.canvas.bind("<B1-Motion>", self.on_drag_zoom)
        self.canvas.bind("<ButtonRelease-1>", self.on_release_zoom)

        # Update cursor style for cropping
        self.canvas.config(cursor="cross")

    def on_press_zoom(self, event1):
        self.crop_start_x1 = event1.x
        self.crop_start_y1 = event1.y

        # Remove the previous cropping rectangle, if exists
        if self.crop_rect1:
            self.canvas.delete(self.crop_rect1)

        # Create a new cropping rectangle
        self.crop_rect1 = self.canvas.create_rectangle(self.crop_start_x1, self.crop_start_y1,
                                                       self.crop_start_x1, self.crop_start_y1, outline="red", width=3)

    def on_drag_zoom(self, event1):
        self.canvas.coords(self.crop_rect1, self.crop_start_x1, self.crop_start_y1, event1.x, event1.y)

    def on_release_zoom(self, event1):
        # Get the final coordinates after dragging
        crop_end_x = event1.x
        crop_end_y = event1.y
        # Resize the coordinates to the original image size (1920x1080)
        original_width, original_height = 1920, 1080
        scale_x = original_width / 800  # 600
        scale_y = original_height / 537  # 437

        x1 = int(self.crop_start_x1 * scale_x)
        y1 = int(self.crop_start_y1 * scale_y)
        x2 = int(crop_end_x * scale_x)
        y2 = int(crop_end_y * scale_y)

        if y1 > y2:
            y1, y2 = y2, y1
        if x1 > x2:
            x1, x2 = x2, x1

        # Crop the zoom part from the original image
        image = Image.open(self.file_path)
        cropped_image = image.crop((x1, y1, x2, y2))
        cropped_image = cropped_image.resize((800, 537), Image.LANCZOS)
        self.cropped_image1 = ImageTk.PhotoImage(cropped_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.cropped_image1)

        # Unbind the mouse events and reset the cursor
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.config(cursor="")

        # Remove the cropping rectangle from the canvas
        self.canvas.delete(self.crop_rect1)
        image.close()
        self.canvas.itemconfigure(self.zoom_id, state='hidden')
        self.canvas.itemconfigure(self.refresh_id, state='normal')

    def start_crop(self):
        self.crop_button.configure(state=DISABLED)
        # Bind the mouse events for cropping
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # Update cursor style for cropping
        self.canvas.config(cursor="cross")

    def on_press(self, event):
        self.crop_start_x = event.x
        self.crop_start_y = event.y

        # Remove the previous cropping rectangle, if exists
        if self.crop_rect:
            self.canvas.delete(self.crop_rect)

        # Create a new cropping rectangle
        self.crop_rect = self.canvas.create_rectangle(self.crop_start_x, self.crop_start_y,
                                                      self.crop_start_x, self.crop_start_y, outline="green", width=3)

    def on_drag(self, event):
        self.canvas.coords(self.crop_rect, self.crop_start_x, self.crop_start_y, event.x, event.y)

    def on_release(self, event):
        self.crop_button.configure(state=NORMAL)
        # Get the final coordinates after dragging
        crop_end_x = event.x
        crop_end_y = event.y

        # Resize the coordinates to the original image size (1920x1080)
        original_width, original_height = 1920, 1080
        scale_x = original_width / 800  # 600
        scale_y = original_height / 537  # 437

        x1 = int(self.crop_start_x * scale_x)
        y1 = int(self.crop_start_y * scale_y)
        x2 = int(crop_end_x * scale_x)
        y2 = int(crop_end_y * scale_y)

        if y1 > y2:
            y1, y2 = y2, y1
        if x1 > x2:
            x1, x2 = x2, x1

        # Crop the number plate from the original image
        image = Image.open(self.file_path)
        cropped_image = image.crop((x1, y1, x2, y2))

        # Resize the cropped image to fit canvas1 and display it
        cropped_image = cropped_image.resize((400, 135), Image.LANCZOS)
        self.cropped_image = ImageTk.PhotoImage(cropped_image)
        cur_date = self.time_entry.get()
        dp = cur_date.split('_')
        cur_date = dp[0]
        username = getpass.getuser()
        cropped_directory = os.path.join(f"/media/{username}/Elements", "cropped_numplate_images", cur_date)
        os.makedirs(cropped_directory, exist_ok=True)
        self.cropped_image_path = os.path.join(cropped_directory, f"{self.image_id_entry.get()}.jpg")
        # print(self.cropped_image_path)
        cropped_image.save(self.cropped_image_path)
        self.canvas1.create_image(0, 0, anchor=tk.NW, image=self.cropped_image)
        result = new_main(self.cropped_image_path)
        if result is not None:
            self.number_plate_entry.delete(0, tk.END)
            self.number_plate_entry.insert(0, result)
        else:
            self.number_plate_entry.delete(0, tk.END)
            self.number_plate_entry.insert(0, "-")

        # Unbind the mouse events and reset the cursor
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.config(cursor="")

        # Remove the cropping rectangle from the canvas
        self.canvas.delete(self.crop_rect)

    def fetch_and_update_data_from_database(self, img_name):
        try:
            self.img_name = img_name
            # Fetch the data from the database for the given image_name
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query = """
                        SELECT * FROM numberplaterecords
                        WHERE image_id = ?
                        LIMIT 1;
                    """
            cursor.execute(query, (img_name,))
            data = cursor.fetchone()
            # print("data=", data)
            conn.close()

            # Update the entry fields with the fetched data
            if data:
                '''self.location_entry.config(state="normal")
                self.location_entry.delete(0, tk.END)
                self.location_entry.insert(0, data[2])
                self.location_entry.config(state="readonly")
                self.officer_id_entry.config(state="normal")
                self.officer_id_entry.delete(0, tk.END)
                self.officer_id_entry.insert(0, data[4])
                self.officer_id_entry.config(state="readonly")
                self.officer_name_entry.config(state="normal")
                self.officer_name_entry.delete(0, tk.END)
                self.officer_name_entry.insert(0, data[3])
                self.officer_name_entry.config(state="readonly")
                self.speed_entry.config(state="normal")
                self.speed_entry.delete(0, tk.END)
                self.speed_entry.insert(0, data[5] if data[5] is not None else '-')
                self.speed_entry.config(state="readonly")
                self.vspeed_entry.config(state="normal")
                self.vspeed_entry.delete(0, tk.END)
                self.vspeed_entry.insert(0, data[6] if data[6] is not None else '-')
                self.vspeed_entry.config(state="readonly")
                self.distance_entry.config(state="normal")
                self.distance_entry.delete(0, tk.END)
                self.distance_entry.insert(0, data[7] if data[7] is not None else '-')
                self.distance_entry.config(state="readonly")
                self.direction_entry.config(state="normal")
                self.direction_entry.delete(0, tk.END)
                self.direction_entry.insert(0, data[8] if data[8] is not None else '-')
                self.direction_entry.config(state="readonly")
                self.laser_entry.config(state="normal")
                self.laser_entry.delete(0, tk.END)
                self.laser_entry.insert(0, data[10])
                self.laser_entry.config(state="readonly")'''
                self.vspeed_label.config(text=f"Vehicle Speed: {data[7]} kmph")
                self.speed_label.config(text=f"Speed Limit: {data[6]} kmph")
                self.time_entry.config(state="normal")
                self.time_entry.delete(0, tk.END)
                self.time_entry.insert(0, data[1])
                self.time_entry.config(state="readonly")
                self.image_id_entry.config(state="normal")
                self.image_id_entry.delete(0, tk.END)
                self.image_id_entry.insert(0, data[0])
                self.image_id_entry.config(state="readonly")
                '''self.nic_uploaded_entry.config(state="normal")
                self.nic_uploaded_entry.delete(0, tk.END)
                self.nic_uploaded_entry.insert(0, "YES" if data[12] == 'y' else "NO")
                self.nic_uploaded_entry.config(state="readonly")'''
                if data[12] == 'y':
                    self.nic_button.config(state=DISABLED)
                    self.update_button.config(state=DISABLED)
                    self.save_button.config(state=DISABLED)
                    self.crop_button.config(state=DISABLED)
                    self.combobox.config(state=NORMAL)
                    self.combobox.set(data[15])
                    self.combobox.config(state=DISABLED)
                    self.vehicle_combobox.config(state=NORMAL)
                    self.vehicle_combobox.set(data[17])
                    self.vehicle_combobox.config(state=DISABLED)
                    self.number_plate_entry.config(state="normal")
                    self.number_plate_entry.delete(0, tk.END)
                    self.number_plate_entry.insert(0, data[10])
                    self.number_plate_entry.config(state="readonly")
                    self.nic_uploaded_label.config(text="CHALLAN GENERATED", bg="red", font=("Arial", 50))
                    self.nic_uploaded_label.grid()
                else:
                    self.nic_uploaded_label.grid_remove()
                    self.combobox.config(state="readonly")
                    self.combobox.set("Select Offence")
                    self.vehicle_combobox.config(state="readonly")
                    self.nic_button.config(state=DISABLED)
                    self.update_button.config(state=DISABLED)
                    self.save_button.config(state=NORMAL)
                    self.crop_button.config(state=NORMAL)
                    if data[16] == 'yellow' and data[17] == 'LMV':
                        '''self.nic_uploaded_label.config(text=f"{data[17].upper()}", bg="yellow",
                                                       font=("Arial", 50))
                        self.nic_uploaded_label.grid()'''
                        self.vehicle_combobox.set("LMV-COMMERCIAL")

                    elif data[16] != 'yellow' and data[17] == 'LMV':
                        '''self.nic_uploaded_label.config(text=f"{data[17].upper()}", bg="yellow",
                                                       font=("Arial", 50))
                        self.nic_uploaded_label.grid()'''
                        self.vehicle_combobox.set("LMV-PERSONAL")
                    elif data[16] == 'yellow' and data[17] is None:
                        # self.nic_uploaded_label.grid_remove()
                        self.vehicle_combobox.set("")
                        self.nic_uploaded_label.config(text="SNAPSHOT", bg="yellow",
                                                       font=("Arial", 50))
                        self.nic_uploaded_label.grid()
                    elif data[16] != 'yellow' and data[17] is None:
                        # self.nic_uploaded_label.grid_remove()
                        self.vehicle_combobox.set("")
                        self.nic_uploaded_label.config(text="SNAPSHOT", bg="orange",
                                                       font=("Arial", 50))
                        self.nic_uploaded_label.grid()
                    else:
                        # self.nic_uploaded_label.grid_remove()
                        '''self.nic_uploaded_label.config(text=f"{data[17].upper()}", bg="orange",
                                                       font=("Arial", 50))
                        self.nic_uploaded_label.grid()'''
                        self.vehicle_combobox.set(f"{data[17].upper()}")
                    '''# Extract the time part
                    time_str = data[1].split('_')[1].split('.')[0]  # Extracts '17-15-42'

                    # Convert time string to datetime object
                    time_obj = datetime.datetime.strptime(time_str, '%H-%M-%S')

                    # Define the threshold time
                    threshold_time = datetime.datetime.strptime('18:00:00', '%H:%M:%S')

                    # Compare with the threshold time
                    if time_obj.time() > threshold_time.time():
                        self.nic_uploaded_label.grid_remove()
                        # pass  # this is night mode
                    else:
                        '''
                    self.number_plate_entry.config(state="normal")
                    self.number_plate_entry.delete(0, tk.END)
                    self.number_plate_entry.insert(0, data[10])
            else:
                # If no data is found, clear the entry fields
                '''self.location_entry.config(state="normal")
                self.location_entry.delete(0, tk.END)
                self.location_entry.config(state="readonly")
                self.officer_id_entry.config(state="normal")
                self.officer_id_entry.delete(0, tk.END)
                self.officer_id_entry.config(state="readonly")
                self.officer_name_entry.config(state="normal")
                self.officer_name_entry.delete(0, tk.END)
                self.officer_name_entry.config(state="readonly")
                self.speed_entry.config(state="normal")
                self.speed_entry.delete(0, tk.END)
                self.speed_entry.config(state="readonly")
                self.vspeed_entry.config(state="normal")
                self.vspeed_entry.delete(0, tk.END)
                self.vspeed_entry.config(state="readonly")
                self.distance_entry.config(state="normal")
                self.distance_entry.delete(0, tk.END)
                self.distance_entry.config(state="readonly")
                self.direction_entry.config(state="normal")
                self.direction_entry.delete(0, tk.END)
                self.direction_entry.config(state="readonly")
                self.laser_entry.config(state="normal")
                self.laser_entry.delete(0, tk.END)
                self.laser_entry.config(state="readonly")'''
                self.combobox.set("Select Offence")
                self.time_entry.config(state="normal")
                self.time_entry.delete(0, tk.END)
                self.time_entry.config(state="readonly")
                self.image_id_entry.config(state="normal")
                self.image_id_entry.delete(0, tk.END)
                self.image_id_entry.config(state="readonly")
                '''self.nic_uploaded_entry.config(state="normal")
                self.nic_uploaded_entry.delete(0, tk.END)
                self.nic_uploaded_entry.config(state="readonly")'''
                self.number_plate_entry.delete(0, tk.END)
        except Exception:
            pass

    def get_image_files_in_folder(self, folder_path):
        if os.path.exists(folder_path):
            # Get a list of image files in the specified folder path
            files = os.listdir(folder_path)
            files.sort()
            image_files = glob.glob(os.path.join(folder_path, "*.*"))
            image_files.sort(key=lambda x: files.index(os.path.basename(x)))
            return [file for file in image_files if file.lower().endswith(('.jpg', '.bmp', '.png'))]
        else:
            return False

    def load_default_image(self):
        try:
            # Get the current date folder
            global image_name
            current_date_folder = get_current_date_folder()
            username = getpass.getuser()
            # Get a list of image files in the current date folder
            image_files = self.get_image_files_in_folder(
                os.path.join(f"/media/{username}/Elements/images_with_info", current_date_folder))

            if not image_files:
                # If no image files are available for the current date, load the default image
                image_path = "resources/img/sphu.png"
                pil_image = Image.open(image_path)
                pil_image = pil_image.resize((800, 537), Image.LANCZOS)  # 600, 437
                tk_image = ImageTk.PhotoImage(pil_image)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
                self.canvas.image = tk_image
                pil_image.close()

                try:
                    image1 = Image.open(image_path)
                    # Resize the cropped image to fit canvas1 and display it
                    image1 = image1.resize((400, 135), Image.LANCZOS)
                    tk_image1 = ImageTk.PhotoImage(image1)
                    self.canvas1.create_image(0, 0, anchor=tk.NW, image=tk_image1)
                    self.canvas1.image = tk_image1
                    image1.close()
                except FileNotFoundError:
                    pass
            else:
                # Get the last image file in the list
                image_path = image_files[-1]
                file_name = os.path.basename(image_path)
                image_name, _ = os.path.splitext(file_name)
                # Update the entry fields with data from the database for the current image
                self.fetch_and_update_data_from_database(image_name)
                # Load the image to the canvas
                self.load_image_to_canvas(image_path)
                # Disable/enable the "Previous" and "Next" buttons accordingly
                self.update_button_state()
        except Exception:
            pass

    def load_image_to_canvas(self, image_path):
        try:
            global canvas_image_path
            canvas_image_path = image_path
            '''image = Image.open(image_path)
            # Create a drawing object
            draw = ImageDraw.Draw(image)
            # Define the position and size of the plus mark
            x, y = 980, 550
            size = 40
            # Draw the plus mark
            draw.line((x - size, y, x + size, y), fill=(255, 0, 0), width=4)
            draw.line((x, y - size, x, y + size), fill=(255, 0, 0), width=4)
            # Save the modified image with the plus mark
            modified_image_path = "plus_sign_image.bmp"
            image.save(modified_image_path)'''
            path = os.path.join(f"/media/{getpass.getuser()}/Elements", image_path)
            pil_image = Image.open(path)
            pil_image = pil_image.resize((800, 537), Image.LANCZOS)  # 600, 437
            # Convert image to Tkinter PhotoImage format
            tk_image = ImageTk.PhotoImage(pil_image)

            # self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
            self.canvas.image = tk_image
            self.file_path = path
            '''os.remove(modified_image_path)
            image.close()'''
            pil_image.close()

            folder, filename = os.path.split(path)
            new_folder = folder.replace('images_with_info', 'cropped_numplate_images')
            self.new_image_path = os.path.join(new_folder, filename)
            self.cropped_image_path = self.new_image_path
            # print(self.new_image_path) #---> cropped_numplate_images/2023-09-22/230922110930875.jpg
            image1 = Image.open(self.new_image_path)
            # Resize the cropped image to fit canvas1 and display it
            image1 = image1.resize((400, 135), Image.LANCZOS)
            tk_image1 = ImageTk.PhotoImage(image1)
            self.canvas1.create_image(0, 0, anchor=tk.NW, image=tk_image1)
            self.canvas1.image = tk_image1
            image1.close()
            self.canvas.itemconfigure(self.refresh_id, state='hidden')
            self.canvas.itemconfigure(self.zoom_id, state='normal')
            self.crop_button.configure(state=NORMAL)
        except FileNotFoundError:
            self.canvas.itemconfigure(self.refresh_id, state='hidden')
            self.canvas.itemconfigure(self.zoom_id, state='normal')
            self.crop_button.configure(state=NORMAL)
            self.canvas1.delete("all")
        except TclError:
            self.canvas.itemconfigure(self.refresh_id, state='hidden')
            self.canvas.itemconfigure(self.zoom_id, state='normal')
            self.crop_button.configure(state=NORMAL)
        except Exception:
            self.canvas.itemconfigure(self.refresh_id, state='hidden')
            self.canvas.itemconfigure(self.zoom_id, state='normal')
            self.crop_button.configure(state=NORMAL)

    def load_previous_image(self):
        try:
            # Get the current date folder
            current_date_folder = get_current_date_folder()
            if self.extracted_dir is not None:
                image_files = self.get_image_files_in_folder(self.extracted_dir)
                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index > 0:
                    # Load the previous image to the canvas
                    previous_image_path = image_files[current_image_index - 1]
                    self.canvas1.delete("all")
                    self.load_image_to_canvas(previous_image_path)
                    file_name = os.path.basename(previous_image_path)
                    prev_img_name, _ = os.path.splitext(file_name)
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(prev_img_name)
            else:
                # Get a list of image files in the current date folder
                image_files = self.get_image_files_in_folder(
                    os.path.join(f"/media/{getpass.getuser()}/Elements/images_with_info", current_date_folder))

                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index > 0:
                    # Load the previous image to the canvas
                    previous_image_path = image_files[current_image_index - 1]
                    self.canvas1.delete("all")
                    self.load_image_to_canvas(previous_image_path)
                    file_name = os.path.basename(previous_image_path)
                    prev_img_name, _ = os.path.splitext(file_name)
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(prev_img_name)

            # Disable/enable the "Previous" and "Next" buttons accordingly
            self.update_button_state()
        except Exception:
            pass

    def load_next_image(self):
        try:
            # Get the current date folder
            current_date_folder = get_current_date_folder()
            if self.extracted_dir is not None:
                image_files = self.get_image_files_in_folder(self.extracted_dir)
                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index < len(image_files) - 1:
                    # Load the next image to the canvas
                    next_image_path = image_files[current_image_index + 1]
                    self.canvas1.delete("all")
                    self.load_image_to_canvas(next_image_path)
                    file_name = os.path.basename(next_image_path)
                    next_img_name, _ = os.path.splitext(file_name)
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(next_img_name)
            else:
                # Get a list of image files in the current date folder
                image_files = self.get_image_files_in_folder(
                    os.path.join(f"/media/{getpass.getuser()}/Elements/images_with_info", current_date_folder))
                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index < len(image_files) - 1:
                    # Load the next image to the canvas
                    next_image_path = image_files[current_image_index + 1]
                    self.canvas1.delete("all")
                    self.load_image_to_canvas(next_image_path)
                    file_name = os.path.basename(next_image_path)
                    next_img_name, _ = os.path.splitext(file_name)
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(next_img_name)

            # Disable/enable the "Previous" and "Next" buttons accordingly
            self.update_button_state()

        except Exception:
            pass

    def update_button_state(self):
        try:
            # Get the current date folder
            current_date_folder = get_current_date_folder()
            if self.extracted_dir is not None:
                image_files = self.get_image_files_in_folder(self.extracted_dir)
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path) if self.file_path in image_files else -1
                # Enable/disable "Previous" and "Next" buttons based on the current image index
                self.back.config(state=tk.NORMAL if current_image_index > 0 else tk.DISABLED)
                self.next.config(state=tk.NORMAL if current_image_index < len(image_files) - 1 else tk.DISABLED)
                # self.canvas1.delete("all")
            else:
                # Get a list of image files in the current date folder
                image_files = self.get_image_files_in_folder(
                    os.path.join(f"/media/{getpass.getuser()}/Elements/images_with_info", current_date_folder))

                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path) if self.file_path in image_files else -1

                # Enable/disable "Previous" and "Next" buttons based on the current image index
                self.back.config(state=tk.NORMAL if current_image_index > 0 else tk.DISABLED)
                self.next.config(state=tk.NORMAL if current_image_index < len(image_files) - 1 else tk.DISABLED)
                # self.canvas1.delete("all")
        except Exception:
            pass

    def open_file_dialog(self):
        self.withdraw()
        transient_window = tk.Toplevel()
        transient_window.attributes('-topmost', True)
        transient_window.withdraw()
        cur_date = datetime.date.today()
        username = getpass.getuser()
        file_path = filedialog.askopenfilename(parent=transient_window,
                                               initialdir=f"/media/{username}/Elements/images_with_info/{cur_date}",
                                               title="Select Image File From 'images_with_info' Folder Only.",
                                               filetypes=(
                                                   ("JPEG files", ".jpg"), ("BMP files", ".bmp"),
                                                   ("PNG files", ".png")))
        transient_window.destroy()
        if file_path:
            self.deiconify()
            start_index = file_path.find('images_with_info/')
            if start_index != -1:
                image_path = file_path[start_index:]
                self.load_image_to_canvas(image_path)
                dir_name = os.path.dirname(file_path)
                self.extracted_dir = os.path.join(f'/media/{getpass.getuser()}/Elements/images_with_info',
                                                  os.path.basename(dir_name))
                # print("extracted dir=", self.extracted_dir) -> extracted dir= images_with_info/2024-01-23
                self.get_image_files_in_folder(self.extracted_dir)
                if self.extracted_dir is not None:
                    image_files = self.get_image_files_in_folder(self.extracted_dir)
                    # print("image files=", image_files)
                    if not image_files:
                        return
                    # Find the index of the current image file
                    # print("self. file path=", self.file_path)
                    current_image_index = image_files.index(self.file_path)
                    current_image_path = image_files[current_image_index]
                    # print("current img path=", current_image_path) -->/media/nvidia/Elements/images_with_info/2024-01-23/1302001220240123143738792.jpg
                    self.load_image_to_canvas(current_image_path)
                    file_name = os.path.basename(current_image_path)
                    cur_img_name, _ = os.path.splitext(file_name)
                    # print("cur img name=", cur_img_name) -->1302001220240123143738792
                    # Update the entry fields with data from the database for the current image
                    self.fetch_and_update_data_from_database(cur_img_name)
        # Disable/enable the "Previous" and "Next" buttons accordingly
        else:
            self.deiconify()
        self.update_button_state()

    def save_details(self):
        try:
            try:
                subprocess.Popen(['pkill', 'onboard'])
            except Exception:
                pass
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query = """
                        UPDATE numberplaterecords 
                        SET numberplate = ?
                        WHERE image_id = ?;
                    """
            cursor.execute(query, (self.number_plate_entry.get().upper(), self.img_name))
            conn.commit()
            self.fetch_and_update_data_from_database(self.img_name)
            # print(self.img_name)  # 230922110930875
            conn.close()

            '''date_path = canvas_image_path.split(
                '/')  # canvas_image_path = images_with_info/2023-09-22/230922110930875.jpg
            date_path = date_path[1]  # date_path = 2023-09-22'''
        except Exception as sd:
            logging.error(f"Exception in save_details(Class Offence): {str(sd)}")
        try:
            image = Image.open(self.cropped_image_path)
            image.save(self.new_image_path)
            image.close()
        except Exception:
            pass
        finally:
            time.sleep(0.01)
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query1 = """
                        SELECT *
                        FROM numberplaterecords
                        WHERE image_id = ?;
                    """
            cursor.execute(query1, (self.img_name,))
            row = cursor.fetchone()
            conn.close()
            date_path = row[2]
            username = getpass.getuser()
            write_on_image(row[13], row[14], self.image_id_entry.get(), row[2], row[1],
                           f"/media/{username}/Elements/original_images/{date_path}/{self.img_name}.jpg", row[6],
                           row[7],
                           row[8], row[9], row[10], row[11], row[3], row[4], row[5])
            self.load_image_to_canvas(f'/media/{username}/Elements/images_with_info/{date_path}/{self.img_name}.jpg')
            self.withdraw()
            messagebox.showinfo("Success", "Data is saved!")
            self.deiconify()

    def update_details(self):
        try:
            try:
                subprocess.Popen(['pkill', 'onboard'])
            except Exception:
                pass
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()
            query1 = """
                        SELECT *
                        FROM numberplaterecords
                        WHERE image_id = ?;
                        """
            cursor.execute(query1, (self.img_name,))
            row1 = cursor.fetchone()
            # conn.close()
            veh_cat = None
            vehi = ""
            plate_color = ""
            if self.vehicle_combobox.get() == 'LMV-COMMERCIAL':
                veh_cat = row1[18]
                vehi = "LMV"
                plate_color = "yellow"
            elif self.vehicle_combobox.get() == 'LMV-PERSONAL':
                veh_cat = row1[19]
                vehi = "LMV"
                plate_color = "white"
            elif self.vehicle_combobox.get() == 'HMV':
                vehi = "HMV"
                plate_color = "yellow"
                veh_cat = row1[20]
            else:
                veh_cat = row1[21]
                vehi = "Bike"
                plate_color = "white"
            tole = int(row1[22]) / 100 * int(veh_cat)
            tole = round(tole)
            if row1[7] > int(veh_cat) + tole:
                query = """
                            UPDATE numberplaterecords 
                            SET speed_limit = ?, vehicle_type = ?, lp_color = ?
                            WHERE image_id = ?;
                        """
                cursor.execute(query, (veh_cat, vehi, plate_color, self.img_name))
                conn.commit()
                self.fetch_and_update_data_from_database(self.img_name)
                # print(self.img_name)  # 230922110930875
                query1 = """
                            SELECT *
                            FROM numberplaterecords
                            WHERE image_id = ?;
                        """
                cursor.execute(query1, (self.img_name,))
                row = cursor.fetchone()
                conn.close()
                date_path = row[2]
                username = getpass.getuser()
                write_on_image(row[13], row[14], self.image_id_entry.get(), row[2], row[1],
                               f"/media/{username}/Elements/original_images/{date_path}/{self.img_name}.jpg", row[6],
                               row[7],
                               row[8], row[9], row[10], row[11], row[3], row[4], row[5])
                self.load_image_to_canvas(
                    f'/media/{username}/Elements/images_with_info/{date_path}/{self.img_name}.jpg')
                self.withdraw()
                messagebox.showinfo("Success", "Vehicle class with speed limit was updated successfully!")
                self.deiconify()
            else:
                self.withdraw()
                messagebox.showinfo("INFO", "Vehicle speed is less than the selected vehicle type's speed limit.")
                self.deiconify()
            conn.close()
        except Exception as sd:
            logging.error(f"Exception in update_details(Class Offence): {str(sd)}")


class HelmetDatabaseWindow(tk.Toplevel):
    instance = None

    def __init__(self, parent):
        super().__init__(parent, bg="grey")
        bigfont = font.Font(family="Arial", size=17)
        self.option_add("*Font", bigfont)
        self.title("Helmet Offence Database Window")
        self.parent = parent
        self.geometry(f"{1280}x{762}+0+0")
        self.resizable(False, False)

        # Create a frame for the search options
        self.search_frame = tk.Frame(self, bg="grey")
        self.search_frame.pack(pady=15)

        self.date_frame = tk.Frame(self.search_frame, bg="grey")
        self.date_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5)

        save_img = Image.open('resources/48PX/Search.png')
        save_img = save_img.resize((30, 30), Image.LANCZOS)
        save_photo = ImageTk.PhotoImage(save_img)
        self.save_photo = save_photo
        save_img.close()

        refresh_img = Image.open('resources/48PX/Refresh.png')
        refresh_img = refresh_img.resize((30, 30), Image.LANCZOS)
        refresh_photo = ImageTk.PhotoImage(refresh_img)
        self.refresh_photo = refresh_photo
        refresh_img.close()

        excel_img = Image.open('resources/img/excel.png')
        excel_img = excel_img.resize((30, 30), Image.LANCZOS)
        excel_photo = ImageTk.PhotoImage(excel_img)
        self.excel_photo = excel_photo
        excel_img.close()

        # Year Combo Box
        self.year_label = tk.Label(self.date_frame, text="Start Year:", bg="grey")
        self.year_label.grid(row=0, column=0, padx=15, pady=5)
        self.year_combo = ttk.Combobox(self.date_frame, values=self.get_years(), state='readonly', width=7)
        self.year_combo.grid(row=0, column=1, padx=15, pady=5)
        self.year_combo.set(datetime.datetime.now().year)  # Set the current year as default

        # Month Combo Box
        self.month_label = tk.Label(self.date_frame, text="Start Month:", bg="grey")
        self.month_label.grid(row=0, column=2, padx=15, pady=5)
        self.month_combo = ttk.Combobox(self.date_frame, values=self.get_months(), state='readonly', width=15)
        self.month_combo.grid(row=0, column=3, padx=15, pady=5)
        self.month_combo.set(datetime.datetime.now().strftime("%B"))  # Set the current month as default

        # Date combobox
        self.date_label = tk.Label(self.date_frame, text="Start Date:", bg="grey")
        self.date_label.grid(row=0, column=4, padx=15, pady=5)
        self.date_combo = ttk.Combobox(self.date_frame,
                                       values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12",
                                               "13",
                                               "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25",
                                               "26", "27", "28", "29", "30", "31"], state='readonly', width=5)
        self.date_combo.grid(row=0, column=5, padx=15, pady=5)
        # self.date_combo.set(f"0{datetime.datetime.now().day}")  # Set the current date as default

        # Year Combo Box
        self.end_year_label = tk.Label(self.date_frame, text="End Year:", bg="grey")
        self.end_year_label.grid(row=1, column=0, padx=15, pady=5)
        self.end_year_combo = ttk.Combobox(self.date_frame, values=self.get_years(), state='readonly', width=7)
        self.end_year_combo.grid(row=1, column=1, padx=15, pady=5)
        self.end_year_combo.set(datetime.datetime.now().year)  # Set the current year as default

        # Month Combo Box
        self.end_month_label = tk.Label(self.date_frame, text="End Month:", bg="grey")
        self.end_month_label.grid(row=1, column=2, padx=15, pady=5)
        self.end_month_combo = ttk.Combobox(self.date_frame, values=self.get_months(), state='readonly', width=15)
        self.end_month_combo.grid(row=1, column=3, padx=15, pady=5)
        self.end_month_combo.set(datetime.datetime.now().strftime("%B"))  # Set the current month as default

        # Date combobox
        self.end_date_label = tk.Label(self.date_frame, text="End Date:", bg="grey")
        self.end_date_label.grid(row=1, column=4, padx=15, pady=5)
        self.end_date_combo = ttk.Combobox(self.date_frame,
                                           values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
                                                   "12",
                                                   "13",
                                                   "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24",
                                                   "25",
                                                   "26", "27", "28", "29", "30", "31"], state='readonly', width=5)
        self.end_date_combo.grid(row=1, column=5, padx=15, pady=5)

        # Create search labels and entry fields
        self.officer_label = tk.Label(self.search_frame, text="Search by Officer Name:", bg="grey")
        self.officer_label.grid(row=2, column=0, pady=10)
        self.officer_entry = ttk.Entry(self.search_frame)
        self.officer_entry.grid(row=2, column=1, pady=10)
        self.officer_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        self.number_plate_label = tk.Label(self.search_frame, text="Search by Number Plate:", bg="grey")
        self.number_plate_label.grid(row=3, column=0, pady=10)
        self.number_plate_entry = ttk.Entry(self.search_frame)
        self.number_plate_entry.grid(row=3, column=1, pady=10)
        self.number_plate_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        # Create a search button
        self.search_button = tk.Button(self.search_frame, text="Search",
                                       compound=tk.LEFT, command=self.search_database, bg="orange")
        self.search_button.configure(image=self.save_photo)
        self.search_button.grid(row=4, column=0, padx=5, pady=5, sticky='w')

        # Create a clear button
        self.clear_button = tk.Button(self.search_frame, text="Clear",
                                      compound=tk.LEFT, command=self.clear_entry, bg="orange")
        self.clear_button.configure(image=self.refresh_photo)
        self.clear_button.grid(row=4, column=1, padx=5, pady=5, sticky='w')

        # Excel button
        self.excel_button = tk.Button(self.search_frame, text="Export",
                                      compound=tk.LEFT, command=self.export_to_excel, bg="orange")
        self.excel_button.configure(image=self.excel_photo)
        self.excel_button.grid(row=4, column=2, padx=5, pady=5, sticky='e')

        self.exit_button = tk.Button(self.date_frame, text="Close", height=3, width=10,
                                     compound=tk.RIGHT, bg="red", command=self.destroy_window)
        self.exit_button.grid(row=0, column=6, rowspan=2, padx=15, pady=5, sticky='e')

        # Create a treeview widget to display the search results
        self.treeview = ttk.Treeview(self)
        self.treeview.pack(fill=tk.BOTH, expand=True)

        '''# Create vertical scrollbar
        vsb = Scrollbar(self, orient="vertical", command=self.treeview.yview)
        vsb.pack(side="right", fill="y")
        self.treeview.configure(yscrollcommand=vsb.set)'''

        # Create horizontal scrollbar
        hsb = Scrollbar(self, orient="horizontal", command=self.treeview.xview)
        hsb.pack(side="bottom", fill="x")
        self.treeview.configure(xscrollcommand=hsb.set)

        # Connect to the database and populate the treeview with all data initially
        self.connection = sqlite3.connect("msiplusersettingsmh.db")  # Replace with your actual database file name
        self.populate_treeview()

    @classmethod
    def create(cls, parent):
        # Create a new instance of DatabaseWindow
        if cls.instance is not None:
            cls.instance.destroy()
        cls.instance = cls(parent)
        cls.instance.protocol("WM_DELETE_WINDOW", cls.destroy_instance)

    @classmethod
    def destroy_instance(cls):
        # Destroy current instance of DatabaseWindow
        if cls.instance is not None:
            cls.instance.destroy()
            cls.instance = None

    def destroy_window(self):
        self.destroy()
        HelmetDatabaseWindow.instance = None

    def populate_treeview(self):
        # Clear existing data in the treeview
        self.treeview.delete(*self.treeview.get_children())

        column_names = ['Location', "Officer ID", "Officer Name", "Laser ID", "Time", "Date", "Number Plate", "Lat",
                        "Lon", "Y?N"]
        self.treeview["columns"] = column_names
        self.treeview.heading("#0", text="Count")
        for col_idx, column in enumerate(column_names):
            self.treeview.heading(column, text=column)

        self.treeview.column("#0", width=10)  # Count column
        self.treeview.column("Location", width=50)
        self.treeview.column("Officer ID", width=20)
        self.treeview.column("Officer Name", width=50)
        self.treeview.column("Laser ID", width=30)
        self.treeview.column("Time", width=115)
        self.treeview.column("Date", width=30)
        self.treeview.column("Number Plate", width=70)
        self.treeview.column("Lat", width=20)
        self.treeview.column("Lon", width=20)
        self.treeview.column("Y?N", width=10)

    def clear_entry(self):
        self.officer_entry.delete(0, tk.END)
        self.date_combo.set('')
        self.month_combo.set('')
        self.year_combo.set('')
        self.end_date_combo.set('')
        self.end_month_combo.set('')
        self.end_year_combo.set('')
        self.number_plate_entry.delete(0, tk.END)
        # Clear existing data in the treeview
        self.treeview.delete(*self.treeview.get_children())

    # AES encryption function
    def encrypt_aes(self, plaintext, key):
        cipher = AES.new(key, AES.MODE_CBC)
        ciphertext = cipher.encrypt(pad(plaintext.encode(), AES.block_size))
        return base64.b64encode(cipher.iv + ciphertext).decode()

    def export_to_excel(self):
        excel_thread = threading.Thread(target=self.export_to_excel_thread)
        excel_thread.start()

    def export_to_excel_thread(self):
        if not self.treeview.get_children():
            self.parent.after(0, lambda: messagebox.showerror("Export error", "No data available to export"))
            self.destroy_window()
            logging.error("No data available to export an excel file")
            return
        try:
            # Generate a random 128-bit AES encryption key (16 bytes)
            encryption_key = b')\xaf$n\x06\x9cW\xbc\xe2E\x05/\xea\xf4u\xdc'  # get_random_bytes(16)
            # print(encryption_key)

            self.excel_button.config(state=tk.DISABLED)
            # Generate a timestamp for the filename
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            folder_name = datetime.datetime.now().strftime("%Y-%m-%d")
            username = getpass.getuser()
            folder_path = os.path.join(f"/media/{username}/Elements/Excel files", folder_name)
            os.makedirs(folder_path, exist_ok=True)

            # Create the data array for ODS file
            data = [
                ["Location", "Officer ID", "Officer Name", "Laser ID", "Time",
                 "Date", "Number Plate", "Lat", "Lon", "Y?N"]]
            for item_id in self.treeview.get_children():
                item_values = self.treeview.item(item_id)["values"]
                # Encrypt the "V. Speed" column
                '''v_speed = item_values[4]
                encrypted_speed = self.encrypt_aes(str(v_speed), encryption_key)
                item_values[4] = encrypted_speed'''
                data.append(item_values)

            # Save the data to an ODS file
            file_name = f"helmet_offences_{timestamp}.ods"
            output_path = os.path.join(folder_path, file_name)
            ods.save_data(output_path, {"Sheet 1": data})

            self.parent.after(0, lambda: messagebox.showinfo("Export Success", "Export to ODS was successful."))
            self.excel_button.config(state=tk.NORMAL)
            logging.info("Export to excel success")
            self.destroy_window()

        except Exception as error:
            self.parent.after(0, lambda: messagebox.showerror("Export error",
                                                              f"An error occurred during export: {str(error)}"))
            logging.error(f"Exception occurred in excel export: {str(error)}")
            self.destroy_window()

    def get_years(self):
        current_year = datetime.datetime.now().year
        return [str(year) for year in range(current_year - 1, current_year + 3)]

    def get_months(self):
        return list(calendar.month_name)[1:]

    def search_database(self):
        try:
            # Clear existing data in the treeview
            self.treeview.delete(*self.treeview.get_children())
            dates = ''
            end_dates = ''
            count = 0
            datewise_count = 0
            m = {'January': '01', 'February': '02', 'March': '03', 'April': '04', 'May': '05', 'June': '06',
                 'July': '07',
                 'August': '08', 'September': '09', 'October': '10', 'November': '11', 'December': '12'}
            officer_name = self.officer_entry.get()
            year = self.year_combo.get()
            month = self.month_combo.get()
            month = m.get(month)
            date = self.date_combo.get()

            end_year = self.end_year_combo.get()
            end_month = self.end_month_combo.get()
            end_month = m.get(end_month)
            end_date = self.end_date_combo.get()

            number_plate = self.number_plate_entry.get()
            if date != '':
                if year != '':
                    if month is not None:
                        dates = f"{year}-{month}-{date}"
            else:
                dates = ''

            if end_date != '':
                if end_year != '':
                    if end_month is not None:
                        end_dates = f"{end_year}-{end_month}-{end_date}"
            else:
                end_dates = ''

            if not any([officer_name, year, month, date, number_plate]):
                self.destroy_window()
                messagebox.showerror("Error", "Please enter at least one search criteria.")
                return

            # SQL queries
            query = """
                SELECT n.location, n.officer_id, n.officername, n.laser_id, n.time, n.hel_date, n.numberplate, n.lat, n.lon, n.uploaded
                FROM locations AS l
                JOIN helmetoffencerecords AS n ON l.officer_name = n.officername
                WHERE l.date = n.hel_date AND n.uploaded = 'y'
            """

            datewise_query = """
                        SELECT n.location, n.officer_id, n.officername, n.laser_id, n.time, n.hel_date, n.numberplate, n.lat, n.lon, n.uploaded
                        FROM locations AS l
                        JOIN helmetoffencerecords AS n ON l.officer_name = n.officername
                        WHERE l.date = n.hel_date AND n.uploaded = 'y'
            """

            # AND n.uploaded = 'y'
            conditions = []
            datewise_conditions = []

            if dates and end_dates:
                self.officer_entry.delete(0, tk.END)
                self.number_plate_entry.delete(0, tk.END)
                datewise_conditions.append(f"n.hel_date BETWEEN '{dates}' AND '{end_dates}'")
                datewise_count += 1

            if officer_name:
                conditions.append(f"n.officername = '{officer_name}'")
                count += 1

            if year and month:
                conditions.append(f"n.hel_date LIKE '{year}-{month}-%'")
                count += 1

            if dates:
                conditions.append(f"n.hel_date = '{dates}'")
                count += 1

            if year:
                conditions.append(f"n.hel_date LIKE '{year}-%'")
                count += 1

            if number_plate:
                conditions.append(f"n.numberplate LIKE '{number_plate}%'")
                count += 1

            if conditions:
                query += " AND " + " AND ".join(conditions)
                count += 1

            if datewise_conditions:
                datewise_query += " AND " + " AND ".join(datewise_conditions)
                datewise_count += 1

            query += "GROUP BY n.location, n.officer_id, n.officername, n.laser_id, n.time, n.hel_date, " \
                     "n.numberplate, n.lat, n.lon, n.uploaded"

            datewise_query += "GROUP BY n.location, n.officer_id, n.officername, n.laser_id, n.time, n.hel_date, " \
                              "n.numberplate, n.lat, n.lon, n.uploaded"

            if count == 0:
                return
            if datewise_count > 0:
                # Execute the query and populate the treeview with the search results
                cursor = self.connection.cursor()
                cursor.execute(datewise_query)
                rows = cursor.fetchall()
                '''print(datewise_query)
                print(rows)'''

                if not rows:
                    self.treeview.insert("", tk.END, text="", values=("",))
                    self.treeview.insert("", tk.END, text='-No', values=["records found"])

                for item_id, row in enumerate(rows, start=1):
                    item_values = [col if col is not None else '-' for col in row]
                    self.treeview.insert("", tk.END, text=str(item_id), values=item_values)
                cursor.close()
            else:
                # Execute the query and populate the treeview with the search results
                cursor = self.connection.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()

                if not rows:
                    self.treeview.insert("", tk.END, text="", values=("",))
                    self.treeview.insert("", tk.END, text='-No', values=["records found"])

                for item_id, row in enumerate(rows, start=1):
                    item_values = [col if col is not None else '-' for col in row]
                    self.treeview.insert("", tk.END, text=str(item_id), values=item_values)
                cursor.close()
        except Exception as e:
            logging.error(f"Exception in helmet_search_database: {str(e)}")


class DatabaseWindow(tk.Toplevel):
    instance = None

    def __init__(self, parent):
        super().__init__(parent, bg="grey")
        self.title("Over Speed Offence Database Window")
        self.parent = parent
        bigfont = font.Font(family="Arial", size=17)
        self.option_add("*Font", bigfont)
        self.geometry(f"{1280}x{762}+0+0")
        self.resizable(False, False)

        # Create a frame for the search options
        self.search_frame = tk.Frame(self, bg="grey")
        self.search_frame.pack(pady=15)

        self.date_frame = tk.Frame(self.search_frame, bg="grey")
        self.date_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5)

        save_img = Image.open('resources/48PX/Search.png')
        save_img = save_img.resize((30, 30), Image.LANCZOS)
        save_photo = ImageTk.PhotoImage(save_img)
        self.save_photo = save_photo
        save_img.close()

        refresh_img = Image.open('resources/48PX/Refresh.png')
        refresh_img = refresh_img.resize((30, 30), Image.LANCZOS)
        refresh_photo = ImageTk.PhotoImage(refresh_img)
        self.refresh_photo = refresh_photo
        refresh_img.close()

        excel_img = Image.open('resources/img/excel.png')
        excel_img = excel_img.resize((30, 30), Image.LANCZOS)
        excel_photo = ImageTk.PhotoImage(excel_img)
        self.excel_photo = excel_photo
        excel_img.close()

        # Year Combo Box
        self.year_label = tk.Label(self.date_frame, text="Start Year:", bg="grey")
        self.year_label.grid(row=0, column=0, padx=15, pady=5)
        self.year_combo = ttk.Combobox(self.date_frame, values=self.get_years(), state='readonly', width=7)
        self.year_combo.grid(row=0, column=1, padx=15, pady=5)
        self.year_combo.set(datetime.datetime.now().year)  # Set the current year as default

        # Month Combo Box
        self.month_label = tk.Label(self.date_frame, text="Start Month:", bg="grey")
        self.month_label.grid(row=0, column=2, padx=15, pady=5)
        self.month_combo = ttk.Combobox(self.date_frame, values=self.get_months(), state='readonly', width=15)
        self.month_combo.grid(row=0, column=3, padx=15, pady=5)
        self.month_combo.set(datetime.datetime.now().strftime("%B"))  # Set the current month as default

        # Date combobox
        self.date_label = tk.Label(self.date_frame, text="Start Date:", bg="grey")
        self.date_label.grid(row=0, column=4, padx=15, pady=5)
        self.date_combo = ttk.Combobox(self.date_frame,
                                       values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12",
                                               "13",
                                               "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25",
                                               "26", "27", "28", "29", "30", "31"], state='readonly', width=5)
        self.date_combo.grid(row=0, column=5, padx=15, pady=5)
        # self.date_combo.set(f"0{datetime.datetime.now().day}")  # Set the current date as default

        # Year Combo Box
        self.end_year_label = tk.Label(self.date_frame, text="End Year:", bg="grey")
        self.end_year_label.grid(row=1, column=0, padx=15, pady=5)
        self.end_year_combo = ttk.Combobox(self.date_frame, values=self.get_years(), state='readonly', width=7)
        self.end_year_combo.grid(row=1, column=1, padx=15, pady=5)
        self.end_year_combo.set(datetime.datetime.now().year)  # Set the current year as default

        # Month Combo Box
        self.end_month_label = tk.Label(self.date_frame, text="End Month:", bg="grey")
        self.end_month_label.grid(row=1, column=2, padx=15, pady=5)
        self.end_month_combo = ttk.Combobox(self.date_frame, values=self.get_months(), state='readonly', width=15)
        self.end_month_combo.grid(row=1, column=3, padx=15, pady=5)
        self.end_month_combo.set(datetime.datetime.now().strftime("%B"))  # Set the current month as default

        # Date combobox
        self.end_date_label = tk.Label(self.date_frame, text="End Date:", bg="grey")
        self.end_date_label.grid(row=1, column=4, padx=15, pady=5)
        self.end_date_combo = ttk.Combobox(self.date_frame,
                                           values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
                                                   "12",
                                                   "13",
                                                   "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24",
                                                   "25",
                                                   "26", "27", "28", "29", "30", "31"], state='readonly', width=5)
        self.end_date_combo.grid(row=1, column=5, padx=15, pady=5)

        # Create search labels and entry fields
        self.officer_label = tk.Label(self.search_frame, text="Search by Officer Name:", bg="grey")
        self.officer_label.grid(row=2, column=0, pady=5)
        self.officer_entry = ttk.Entry(self.search_frame)
        self.officer_entry.grid(row=2, column=1, pady=5)
        self.officer_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        self.number_plate_label = tk.Label(self.search_frame, text="Search by Number Plate:", bg="grey")
        self.number_plate_label.grid(row=3, column=0, pady=5)
        self.number_plate_entry = ttk.Entry(self.search_frame)
        self.number_plate_entry.grid(row=3, column=1, pady=5)
        self.number_plate_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        # Create a search button
        self.search_button = tk.Button(self.search_frame, text="Search",
                                       compound=tk.LEFT, command=self.search_database, bg="orange")
        self.search_button.configure(image=self.save_photo)
        self.search_button.grid(row=4, column=0, padx=5, pady=5, sticky='w')

        # Create a clear button
        self.clear_button = tk.Button(self.search_frame, text="Clear",
                                      compound=tk.LEFT, command=self.clear_entry, bg="orange")
        self.clear_button.configure(image=self.refresh_photo)
        self.clear_button.grid(row=4, column=1, padx=5, pady=5, sticky='w')

        # Excel button
        self.excel_button = tk.Button(self.search_frame, text="Export",
                                      compound=tk.LEFT, command=self.export_to_excel, bg="orange")
        self.excel_button.configure(image=self.excel_photo)
        self.excel_button.grid(row=4, column=2, padx=5, pady=5, sticky='w')

        self.exit_button = tk.Button(self.date_frame, text="Close", height=3, width=10,
                                     compound=tk.RIGHT, bg="red", command=self.destroy_window)
        self.exit_button.grid(row=0, column=6, rowspan=2, padx=5, pady=5, sticky='e')

        # Create a treeview widget to display the search results
        self.treeview = ttk.Treeview(self)
        self.treeview.pack(fill=tk.BOTH, expand=True)

        '''# Create vertical scrollbar
        vsb = Scrollbar(self, orient="vertical", command=self.treeview.yview)
        vsb.pack(side="right", fill="y")
        self.treeview.configure(yscrollcommand=vsb.set)'''

        # Create horizontal scrollbar
        hsb = Scrollbar(self, orient="horizontal", command=self.treeview.xview)
        hsb.pack(side="bottom", fill="x")
        self.treeview.configure(xscrollcommand=hsb.set)

        # Connect to the database and populate the treeview with all data initially
        self.connection = sqlite3.connect("msiplusersettingsmh.db")  # Replace with your actual database file name
        self.populate_treeview()

    @classmethod
    def create(cls, parent):
        # Create a new instance of DatabaseWindow
        if cls.instance is not None:
            cls.instance.destroy()
        cls.instance = cls(parent)
        cls.instance.protocol("WM_DELETE_WINDOW", cls.destroy_instance)

    @classmethod
    def destroy_instance(cls):
        # Destroy current instance of DatabaseWindow
        if cls.instance is not None:
            cls.instance.destroy()
            cls.instance = None

    def destroy_window(self):
        self.destroy()
        DatabaseWindow.instance = None

    def populate_treeview(self):
        # Clear existing data in the treeview
        self.treeview.delete(*self.treeview.get_children())

        column_names = ['Location', "Officer ID", "Officer Name", "Speed Limit", "V. Speed", "Distance", "Laser ID",
                        "Time", "Date", "Number Plate", "Lat", "Lon", "Y?N"]
        self.treeview["columns"] = column_names
        self.treeview.heading("#0", text="Count")
        for col_idx, column in enumerate(column_names):
            self.treeview.heading(column, text=column)

        self.treeview.column("#0", width=10)  # Count column
        self.treeview.column("Location", width=50)
        self.treeview.column("Officer ID", width=20)
        self.treeview.column("Officer Name", width=50)
        self.treeview.column("Speed Limit", width=40)
        self.treeview.column("V. Speed", width=25)
        self.treeview.column("Distance", width=30)
        self.treeview.column("Laser ID", width=30)
        self.treeview.column("Time", width=115)
        self.treeview.column("Date", width=30)
        self.treeview.column("Number Plate", width=70)
        self.treeview.column("Lat", width=20)
        self.treeview.column("Lon", width=20)
        self.treeview.column("Y?N", width=10)

    def clear_entry(self):
        self.officer_entry.delete(0, tk.END)
        self.date_combo.set('')
        self.month_combo.set('')
        self.year_combo.set('')
        self.end_date_combo.set('')
        self.end_month_combo.set('')
        self.end_year_combo.set('')
        self.number_plate_entry.delete(0, tk.END)
        # Clear existing data in the treeview
        self.treeview.delete(*self.treeview.get_children())

    # AES encryption function
    def encrypt_aes(self, plaintext, key):
        cipher = AES.new(key, AES.MODE_CBC)
        ciphertext = cipher.encrypt(pad(plaintext.encode(), AES.block_size))
        return base64.b64encode(cipher.iv + ciphertext).decode()

    def export_to_excel(self):
        excel_thread = threading.Thread(target=self.export_to_excel_thread)
        excel_thread.start()

    def export_to_excel_thread(self):
        if not self.treeview.get_children():
            self.parent.after(0, lambda: messagebox.showerror("Export error", "No data available to export"))
            self.destroy_window()
            logging.error("No data available to export an excel file")
            return
        try:
            # Generate a random 128-bit AES encryption key (16 bytes)
            encryption_key = b')\xaf$n\x06\x9cW\xbc\xe2E\x05/\xea\xf4u\xdc'  # get_random_bytes(16)
            # print(encryption_key)

            self.excel_button.config(state=tk.DISABLED)
            # Generate a timestamp for the filename
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            folder_name = datetime.datetime.now().strftime("%Y-%m-%d")
            username = getpass.getuser()
            folder_path = os.path.join(f"/media/{username}/Elements/Excel files", folder_name)
            os.makedirs(folder_path, exist_ok=True)

            # Create the data array for ODS file
            data = [
                ["Location", "Officer ID", "Officer Name", "Speed Limit", "V. Speed", "Distance", "Laser ID", "Time",
                 "Date", "Number Plate", "Lat", "Lon", "Y?N"]]
            for item_id in self.treeview.get_children():
                item_values = self.treeview.item(item_id)["values"]
                # Encrypt the "V. Speed" column
                v_speed = item_values[4]
                encrypted_speed = self.encrypt_aes(str(v_speed), encryption_key)
                item_values[4] = encrypted_speed
                data.append(item_values)

            # Save the data to an ODS file
            file_name = f"database_{timestamp}.ods"
            output_path = os.path.join(folder_path, file_name)
            ods.save_data(output_path, {"Sheet 1": data})

            self.parent.after(0, lambda: messagebox.showinfo("Export Success", "Export to ODS was successful."))
            self.excel_button.config(state=tk.NORMAL)
            logging.info("Export to excel success")
            self.destroy_window()

        except Exception as error:
            self.parent.after(0, lambda: messagebox.showerror("Export error",
                                                              f"An error occurred during export: {str(error)}"))
            logging.error(f"Exception occurred in excel export: {str(error)}")
            self.destroy_window()

    def get_years(self):
        current_year = datetime.datetime.now().year
        return [str(year) for year in range(current_year - 1, current_year + 3)]

    def get_months(self):
        return list(calendar.month_name)[1:]

    def search_database(self):
        try:
            # Clear existing data in the treeview
            self.treeview.delete(*self.treeview.get_children())
            dates = ''
            end_dates = ''
            count = 0
            datewise_count = 0
            m = {'January': '01', 'February': '02', 'March': '03', 'April': '04', 'May': '05', 'June': '06',
                 'July': '07',
                 'August': '08', 'September': '09', 'October': '10', 'November': '11', 'December': '12'}
            officer_name = self.officer_entry.get()
            year = self.year_combo.get()
            month = self.month_combo.get()
            month = m.get(month)
            date = self.date_combo.get()

            end_year = self.end_year_combo.get()
            end_month = self.end_month_combo.get()
            end_month = m.get(end_month)
            end_date = self.end_date_combo.get()

            number_plate = self.number_plate_entry.get()
            if date != '':
                if year != '':
                    if month is not None:
                        dates = f"{year}-{month}-{date}"
            else:
                dates = ''

            if end_date != '':
                if end_year != '':
                    if end_month is not None:
                        end_dates = f"{end_year}-{end_month}-{end_date}"
            else:
                end_dates = ''

            if not any([officer_name, year, month, date, number_plate]):
                self.destroy_window()
                messagebox.showerror("Error", "Please enter at least one search criteria.")
                return

            # SQL queries
            query = """
                SELECT n.location, n.officer_id, n.officername, n.speed_limit, n.vehicle_speed, n.distance, n.laser_id, n.datetime, n.num_date, n.numberplate, n.lat, n.lon, n.uploaded
                FROM locations AS l
                JOIN numberplaterecords AS n ON l.officer_name = n.officername
                WHERE l.date = n.num_date AND n.uploaded = 'y'
            """

            datewise_query = """
                        SELECT n.location, n.officer_id, n.officername, n.speed_limit, n.vehicle_speed, n.distance, n.laser_id, n.datetime, n.num_date, n.numberplate, n.lat, n.lon, n.uploaded
                        FROM locations AS l
                        JOIN numberplaterecords AS n ON l.officer_name = n.officername
                        WHERE l.date = n.num_date AND n.uploaded = 'y'
            """

            # AND n.uploaded = 'y'
            conditions = []
            datewise_conditions = []

            if dates and end_dates:
                self.officer_entry.delete(0, tk.END)
                self.number_plate_entry.delete(0, tk.END)
                datewise_conditions.append(f"n.num_date BETWEEN '{dates}' AND '{end_dates}'")
                datewise_count += 1

            if officer_name:
                conditions.append(f"n.officername = '{officer_name}'")
                count += 1

            if year and month:
                conditions.append(f"n.num_date LIKE '{year}-{month}-%'")
                count += 1

            if dates:
                conditions.append(f"n.num_date = '{dates}'")
                count += 1

            if year:
                conditions.append(f"n.num_date LIKE '{year}-%'")
                count += 1

            if number_plate:
                conditions.append(f"n.numberplate LIKE '{number_plate}%'")
                count += 1

            if conditions:
                query += " AND " + " AND ".join(conditions)
                count += 1

            if datewise_conditions:
                datewise_query += " AND " + " AND ".join(datewise_conditions)
                datewise_count += 1

            query += "GROUP BY n.location, n.officer_id, n.officername, n.speed_limit, n.vehicle_speed, n.distance, n.laser_id, n.datetime, n.num_date, " \
                     "n.numberplate, n.lat, n.lon, n.uploaded"

            datewise_query += "GROUP BY n.location, n.officer_id, n.officername, n.speed_limit, n.vehicle_speed, n.distance, n.laser_id, n.datetime, n.num_date, " \
                              "n.numberplate, n.lat, n.lon, n.uploaded"

            if count == 0:
                return
            if datewise_count > 0:
                # Execute the query and populate the treeview with the search results
                cursor = self.connection.cursor()
                cursor.execute(datewise_query)
                rows = cursor.fetchall()
                '''print(datewise_query)
                print(rows)'''

                if not rows:
                    self.treeview.insert("", tk.END, text="", values=("",))
                    self.treeview.insert("", tk.END, text='-No', values=["records found"])

                for item_id, row in enumerate(rows, start=1):
                    item_values = [col if col is not None else '-' for col in row]
                    self.treeview.insert("", tk.END, text=str(item_id), values=item_values)
                cursor.close()
            else:
                # Execute the query and populate the treeview with the search results
                cursor = self.connection.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()

                if not rows:
                    self.treeview.insert("", tk.END, text="", values=("",))
                    self.treeview.insert("", tk.END, text='-No', values=["records found"])

                for item_id, row in enumerate(rows, start=1):
                    item_values = [col if col is not None else '-' for col in row]
                    self.treeview.insert("", tk.END, text=str(item_id), values=item_values)
                cursor.close()
        except Exception as e:
            logging.error(f"Exception in search_database: {str(e)}")


def new_main(ff):
    try:
        regions = ["in"]  # Change to your country
        with open(ff, 'rb') as fp:
            response = requests.post(
                'http://localhost:8080/v1/plate-reader/',
                data=dict(regions=regions),  # Optional
                files=dict(upload=fp),
                headers={'Authorization': 'Token 3d61f4570b13a5bd50dd7086c01a4dea0a735492'})
        response_data = response.json()
        if 'results' in response_data and len(response_data['results']) > 0:
            # Extract number plate text and coordinates
            results = response_data['results'][0]
            num = results['plate'].upper()
            num = num.strip()
            if num.startswith("XA") or num.startswith("WA"):
                num = "KA" + num[2:]
            elif num.startswith("NH") or num.startswith("WH"):
                num = "MH" + num[2:]
            elif num.startswith("MM") or num.startswith("MN"):
                num = "MH" + num[2:]
            elif num.startswith("WM") or num.startswith("MW"):
                num = "MH" + num[2:]
            elif num.startswith("NH") or num.startswith("WN"):
                num = "MH" + num[2:]
            return num
        else:
            return None
    except Exception as exception:
        logging.error(f"Exception in new_main(): {str(exception)}")


def write_on_image(lat, lon, image_id, current_date, cur_time, ff, speed_limit, speed, distance, direction,
                   number_plate, laser_id, location, officer_name, officer_id):
    username = getpass.getuser()
    try:
        folder_path = os.path.join(f"/media/{username}/Elements", "images_with_info")
        folder_path = os.path.join(folder_path, str(current_date))
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)

        firebase_folder_path = os.path.join(f"/media/{username}/Elements", "number_plate_images")
        firebase_folder_path = os.path.join(firebase_folder_path, str(current_date))
        firebase_folder_path = os.path.join(firebase_folder_path, "upload")
        if not os.path.exists(firebase_folder_path):
            os.makedirs(firebase_folder_path, exist_ok=True)
        image = cv2.imread(ff)
        cv2.putText(image, '+', (935, 560), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 2)
        # Add KARNATAKA STATE POLICE DEPARTMENT text in the bottom-left of the image
        cv2.putText(image, "MAHARASHTRA MOTOR VEHICLE DEPARTMENT", (30, image.shape[0] - 220),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)  # (B,G,R)

        # Add LOCATION: followed by location details in the next line
        cv2.putText(image, f"LOCATION: {location}", (30, image.shape[0] - 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Add OFFICER NAME: followed by officer details in next line
        cv2.putText(image, f"OFFICER NAME: {officer_name}", (30, image.shape[0] - 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Add OFFICER ID: followed by officer id details in next line
        cv2.putText(image, f"OFFICER ID: {officer_id}", (30, image.shape[0] - 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Add NUMBER PLATE: followed by num plate in next line
        cv2.putText(image, f"NUMBER PLATE: {number_plate}", (30, image.shape[0] - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Add OFFENCE TIME: followed by offence time in next line
        cv2.putText(image, f"OFFENCE TIME: {cur_time}", (30, image.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Add speed limit, vehicle speed, distance, latitude, longitude, and device ID on the right side of the image
        y_start = 100  # Starting y-coordinate for the text
        x_start = image.shape[1] - 400  # Starting x-coordinate for the text

        latitude = "GPS Unavailable" if lat == '' else lat
        longitude = "GPS Unavailable" if lon == '' else lon

        # Check if speed is not None
        if speed is None:
            pass
        else:
            # Add speed limit text
            cv2.putText(image, f"SPEED LIMIT: {speed_limit}kmph", (x_start, y_start),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            y_start += 40
            # Add vehicle speed text
            cv2.putText(image, f"VEHICLE SPEED: {speed}kmph", (x_start, y_start),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            y_start += 40

            cv2.putText(image, f"DIRECTION: {direction}", (x_start, y_start),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            y_start += 40

        # Check is distance is not None
        if distance is None:
            pass
        else:
            # Add distance text
            cv2.putText(image, f"DISTANCE: {distance}m", (x_start, y_start),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            y_start += 40

        # Add latitude text
        cv2.putText(image, f"LATITUDE: {latitude}", (x_start, y_start),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        y_start += 40

        # Add longitude text
        cv2.putText(image, f"LONGITUDE: {longitude}", (x_start, y_start),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        y_start += 40

        # Add device ID text
        cv2.putText(image, f"DEVICE ID: {laser_id}", (x_start, y_start),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        output_file_path = os.path.join(folder_path, f"{image_id}.jpg")
        cv2.imwrite(output_file_path, image)
        try:
            img = Image.open(output_file_path)
            img.thumbnail((1000, 800))
            img.save(f"/media/{username}/Elements/number_plate_images/{current_date}/upload/{image_id}.jpg", "JPEG",
                     quality=95)
            img.close()
        except Exception as resize:
            logging.error(f"Exception in resize write_on_image for overspeed: {str(resize)}")

    except Exception as ex:
        logging.error(f"Exception in write_n_image: {str(ex)}")


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_color_name(image):
    try:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Define color ranges for white, green, and yellow plates
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 25, 255])

        '''lower_green = np.array([35, 50, 50])
        upper_green = np.array([90, 255, 255])'''

        lower_yellow = np.array([20, 100, 100])
        upper_yellow = np.array([30, 255, 255])

        # Threshold the HSV image to get binary masks
        mask_white = cv2.inRange(hsv, lower_white, upper_white)
        # mask_green = cv2.inRange(hsv, lower_green, upper_green)
        mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)

        # Count non-zero pixels in each mask
        white_pixels = cv2.countNonZero(mask_white)
        # green_pixels = cv2.countNonZero(mask_green)  # "green": green_pixels,
        yellow_pixels = cv2.countNonZero(mask_yellow)

        # Determine the dominant color based on pixel counts
        color_counts = {"white": white_pixels, "yellow": yellow_pixels}
        # print(color_counts)
        pc = max(color_counts, key=color_counts.get)

        return pc
    except Exception as e:
        logging.error(f"Exception in get_color_name(): {str(e)}")
        return False


def adjust_contrast(image, factor):
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(factor)


def plate_recognizer(lat, lon, image_id, cur_date, cur_time, ff, original_file_path, speed, distance, vehicle,
                     night_on, y_car_speed, w_car_speed, hmv_speed, bike_speed, tolerance):
    try:
        num = ''
        regions = ["in"]  # Change to your country
        if night_on:
            with open(original_file_path, 'rb') as fp:
                response = requests.post(
                    'http://localhost:8080/v1/plate-reader/',
                    data=dict(regions=regions),  # Optional
                    files=dict(upload=fp),
                    headers={'Authorization': 'Token 3d61f4570b13a5bd50dd7086c01a4dea0a735492'})
        else:
            with open(ff, 'rb') as fp:
                response = requests.post(
                    'http://localhost:8080/v1/plate-reader/',
                    data=dict(regions=regions),  # Optional
                    files=dict(upload=fp),
                    headers={'Authorization': 'Token 3d61f4570b13a5bd50dd7086c01a4dea0a735492'})
        response_data = response.json()
        if 'results' in response_data and len(response_data['results']) > 0:
            # Extract number plate text and coordinates
            results = response_data['results'][0]
            num = results['plate'].upper()
            plate_coordinates = results['box']
            if night_on:
                img = Image.open(original_file_path)
            else:
                img = Image.open(ff)
            # Define a margin to add around the number plate
            margin = 20  # adjust this value as needed

            # Adjust coordinates by adding/subtracting margin
            xmin = plate_coordinates['xmin'] - margin
            ymin = plate_coordinates['ymin'] - margin
            xmax = plate_coordinates['xmax'] + margin
            ymax = plate_coordinates['ymax'] + margin

            # Crop the image using the adjusted coordinates
            plate_img = img.crop((max(0, xmin), max(0, ymin), min(img.width, xmax), min(img.height, ymax)))

            # Extract coordinates
            xmin1 = plate_coordinates['xmin']
            ymin1 = plate_coordinates['ymin']
            xmax1 = plate_coordinates['xmax']
            ymax1 = plate_coordinates['ymax']

            # Crop the image using the coordinates
            plate_img1 = img.crop((xmin1, ymin1, xmax1, ymax1))
            num = num.strip()
            if num.startswith("XA") or num.startswith("WA"):
                num = "KA" + num[2:]
            elif num.startswith("NH") or num.startswith("WH"):
                num = "MH" + num[2:]
            elif num.startswith("MM") or num.startswith("MN"):
                num = "MH" + num[2:]
            elif num.startswith("WM") or num.startswith("MW"):
                num = "MH" + num[2:]
            elif num.startswith("NH") or num.startswith("WN"):
                num = "MH" + num[2:]
            username = getpass.getuser()
            crop_dir1 = os.path.join(f"/media/{username}/Elements", 'cropped_numplate_images')
            out_path = os.path.join(crop_dir1, cur_date)
            cropped_numplate_path = os.path.join(out_path, f"{image_id}.jpg")
            logging.info(f"LPR: {num}")
            if len(num) > 6:
                if is_valid(num):
                    username = getpass.getuser()
                    crop_dir1 = os.path.join(f"/media/{username}/Elements", 'cropped_numplate_images')
                    out_path = os.path.join(crop_dir1, cur_date)
                    try:
                        # Save the cropped num_plate image for reference
                        # print(output_path)
                        cropped_numplate_path = os.path.join(out_path, f"{image_id}.jpg")
                        plate_img.save(cropped_numplate_path)
                    except Exception as ex:
                        print(ex)
                    plate_img.close()
                    time.sleep(0.01)
                    if night_on:
                        if distance is not None:
                            if distance > 50:
                                distance = distance * 1.3
                                distance = round(distance, 1)
                    else:
                        if distance is not None:
                            if 100 < distance < 300:
                                distance = distance * 1.2
                                distance = round(distance, 1)
                    conn = sqlite3.connect('msiplusersettingsmh.db')
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM locations ORDER BY rowid DESC LIMIT 1")
                    row = cursor.fetchone()
                    lat = '' if lat is None else str(lat)
                    lon = '' if lon is None else str(lon)
                    direction = None
                    '''image = Image.open(cropped_numplate_path)
                    enhanced_contrast = adjust_contrast(image, 2)

                    # Convert the PIL image to OpenCV format
                    enhanced_contrast_cv = np.array(enhanced_contrast)
                    enhanced_contrast_cv = cv2.cvtColor(enhanced_contrast_cv, cv2.COLOR_RGB2BGR)

                    # Detect plate color
                    color_name = get_color_name(enhanced_contrast_cv)
                    enhanced_contrast.close()'''
                    enhanced_plate_img = adjust_contrast(plate_img1, 2)  # Adjust the enhancement factor as needed

                    # Convert the PIL image to OpenCV format
                    plate_img_cv = cv2.cvtColor(np.array(enhanced_plate_img), cv2.COLOR_RGB2BGR)

                    # Detect plate color
                    color_name = get_color_name(plate_img_cv)

                    # Close the PIL image
                    plate_img1.close()
                    # print("last record from locations table =", row)
                    if speed is not None and distance is not None:
                        if not night_on:
                            if vehicle == 'LMV':
                                if color_name == 'yellow':  # if yellow plate then speed_limit is set to ycar_speed
                                    speed_limit = row[6]
                                else:
                                    speed_limit = row[3]
                            elif vehicle == 'HMV':
                                speed_limit = row[4]
                            else:
                                speed_limit = row[7]
                            if speed < -speed_limit:
                                direction = 'Departing'
                            elif speed > speed_limit:
                                direction = 'Approaching'
                            '''elif -10 < speed < 0:
                                direction = 'wrong direction'''
                            speed = abs(speed)
                        else:
                            if vehicle == 'LMV':
                                speed_limit = max(row[3], row[6])
                            elif vehicle == 'HMV':
                                speed_limit = row[4]
                            else:
                                speed_limit = row[7]
                            if speed < -speed_limit:
                                direction = 'Departing'
                            elif speed > speed_limit:
                                direction = 'Approaching'
                            '''elif -10 < speed < 0:
                                direction = 'wrong direction'''
                            speed = abs(speed)
                    else:
                        speed_limit = None
                        speed = None
                        distance = None
                        direction = None

                    if speed is not None:
                        tole = int(row[8]) / 100 * int(speed_limit)
                        tole = round(tole)
                        if int(speed) > int(speed_limit) + tole:
                            cursor.execute(
                                "INSERT INTO numberplaterecords (image_id, datetime, num_date, location, officername, officer_id, "
                                "speed_limit, vehicle_speed, distance, direction, numberplate, laser_id, uploaded, lat, lon, offence_type, lp_color, vehicle_type, com_lmv_speed, per_lmv_speed, hmv_speed, bike_speed, tolerance) VALUES (?, ?, ?, ?, "
                                "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (image_id, cur_time, cur_date, row[0], row[1], row[2], speed_limit, speed, distance,
                                 direction, num, row[11], 'n', lat, lon, '', color_name, vehicle, y_car_speed, w_car_speed, hmv_speed, bike_speed, tolerance))

                            # Commit the changes and close the connection
                            conn.commit()
                            conn.close()
                            try:
                                music_path = resource_path("sound.wav")
                                playsound(music_path)
                            except Exception as m:
                                logging.error(f"{str(m)}")
                                pass
                            write_on_image(lat, lon, image_id, cur_date, cur_time, original_file_path, speed_limit,
                                           speed, distance, direction, num, row[11], row[0], row[1], row[2])
                        else:
                            pass
                    else:
                        cursor.execute(
                            "INSERT INTO numberplaterecords (image_id, datetime, num_date, location, officername, officer_id, "
                            "speed_limit, vehicle_speed, distance, direction, numberplate, laser_id, uploaded, lat, lon, offence_type, lp_color, vehicle_type) VALUES (?, ?, ?, ?, "
                            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (image_id, cur_time, cur_date, row[0], row[1], row[2], speed_limit, speed, distance,
                             direction, num, row[11], 'n', lat, lon, '', color_name, vehicle))

                        # Commit the changes and close the connection
                        conn.commit()
                        conn.close()
                        try:
                            music_path = resource_path("sound.wav")
                            playsound(music_path)
                        except Exception as m:
                            logging.error(f"{str(m)}")
                            pass
                        write_on_image(lat, lon, image_id, cur_date, cur_time, original_file_path, speed_limit, speed,
                                       distance, direction, num, row[11], row[0], row[1], row[2])
                else:
                    if night_on:
                        if distance is not None:
                            if distance > 50:
                                distance = distance * 1.3
                                distance = round(distance, 1)
                    else:
                        if distance is not None:
                            if 100 < distance < 300:
                                distance = distance * 1.2
                                distance = round(distance, 1)
                    conn = sqlite3.connect('msiplusersettingsmh.db')
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM locations ORDER BY rowid DESC LIMIT 1")
                    row = cursor.fetchone()
                    lat = '' if lat is None else str(lat)
                    lon = '' if lon is None else str(lon)
                    direction = None
                    '''image = Image.open(cropped_numplate_path)
                    enhanced_contrast = adjust_contrast(image, 2)

                    # Convert the PIL image to OpenCV format
                    enhanced_contrast_cv = np.array(enhanced_contrast)
                    enhanced_contrast_cv = cv2.cvtColor(enhanced_contrast_cv, cv2.COLOR_RGB2BGR)

                    # Detect plate color
                    color_name = get_color_name(enhanced_contrast_cv)
                    enhanced_contrast.close()'''
                    enhanced_plate_img = adjust_contrast(plate_img1, 2)  # Adjust the enhancement factor as needed

                    # Convert the PIL image to OpenCV format
                    plate_img_cv = cv2.cvtColor(np.array(enhanced_plate_img), cv2.COLOR_RGB2BGR)

                    # Detect plate color
                    color_name = get_color_name(plate_img_cv)

                    # Close the PIL image
                    plate_img1.close()
                    # print("last record from locations table =", row)
                    if speed is not None and distance is not None:
                        if not night_on:
                            if vehicle == 'LMV':
                                if color_name == 'yellow':  # if yellow plate then speed_limit is set to ycar_speed
                                    speed_limit = row[6]
                                else:
                                    speed_limit = row[3]
                            elif vehicle == 'HMV':
                                speed_limit = row[4]
                            else:
                                speed_limit = row[7]
                            if speed < -speed_limit:
                                direction = 'Departing'
                            elif speed > speed_limit:
                                direction = 'Approaching'
                            '''elif -10 < speed < 0:
                                direction = 'wrong direction'''
                            speed = abs(speed)
                        else:
                            if vehicle == 'LMV':
                                speed_limit = max(row[3], row[6])
                            elif vehicle == 'HMV':
                                speed_limit = row[4]
                            else:
                                speed_limit = row[7]
                            if speed < -speed_limit:
                                direction = 'Departing'
                            elif speed > speed_limit:
                                direction = 'Approaching'
                            '''elif -10 < speed < 0:
                                direction = 'wrong direction'''
                            speed = abs(speed)
                    else:
                        speed_limit = None
                        speed = None
                        distance = None
                        direction = None

                    if speed is not None:
                        tole = int(row[8]) / 100 * int(speed_limit)
                        tole = round(tole)
                        if int(speed) > int(speed_limit) + tole:
                            cursor.execute(
                                "INSERT INTO numberplaterecords (image_id, datetime, num_date, location, officername, officer_id, "
                                "speed_limit, vehicle_speed, distance, direction, numberplate, laser_id, uploaded, lat, lon, offence_type, lp_color, vehicle_type, com_lmv_speed, per_lmv_speed, hmv_speed, bike_speed, tolerance) VALUES (?, ?, ?, ?, "
                                "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (image_id, cur_time, cur_date, row[0], row[1], row[2], speed_limit, speed, distance,
                                 direction, '', row[11], 'n', lat, lon, '', color_name, vehicle, y_car_speed,
                                 w_car_speed,
                                 hmv_speed, bike_speed, tolerance))

                            # Commit the changes and close the connection
                            conn.commit()
                            conn.close()
                        else:
                            pass
                    else:
                        cursor.execute(
                            "INSERT INTO numberplaterecords (image_id, datetime, num_date, location, officername, officer_id, "
                            "speed_limit, vehicle_speed, distance, direction, numberplate, laser_id, uploaded, lat, lon, offence_type, lp_color, vehicle_type) VALUES (?, ?, ?, ?, "
                            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (image_id, cur_time, cur_date, row[0], row[1], row[2], speed_limit, speed, distance,
                             direction, '', row[11], 'n', lat, lon, '', color_name, vehicle))

                        # Commit the changes and close the connection
                        conn.commit()
                        conn.close()
            else:
                if night_on:
                    if distance is not None:
                        if distance > 50:
                            distance = distance * 1.3
                            distance = round(distance, 1)
                else:
                    if distance is not None:
                        if 100 < distance < 300:
                            distance = distance * 1.2
                            distance = round(distance, 1)
                conn = sqlite3.connect('msiplusersettingsmh.db')
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM locations ORDER BY rowid DESC LIMIT 1")
                row = cursor.fetchone()
                lat = '' if lat is None else str(lat)
                lon = '' if lon is None else str(lon)
                direction = None
                '''image = Image.open(cropped_numplate_path)
                enhanced_contrast = adjust_contrast(image, 2)

                # Convert the PIL image to OpenCV format
                enhanced_contrast_cv = np.array(enhanced_contrast)
                enhanced_contrast_cv = cv2.cvtColor(enhanced_contrast_cv, cv2.COLOR_RGB2BGR)

                # Detect plate color
                color_name = get_color_name(enhanced_contrast_cv)
                enhanced_contrast.close()'''
                enhanced_plate_img = adjust_contrast(plate_img1, 2)  # Adjust the enhancement factor as needed

                # Convert the PIL image to OpenCV format
                plate_img_cv = cv2.cvtColor(np.array(enhanced_plate_img), cv2.COLOR_RGB2BGR)

                # Detect plate color
                color_name = get_color_name(plate_img_cv)

                # Close the PIL image
                plate_img1.close()
                # print("last record from locations table =", row)
                if speed is not None and distance is not None:
                    if not night_on:
                        if vehicle == 'LMV':
                            if color_name == 'yellow':  # if yellow plate then speed_limit is set to ycar_speed
                                speed_limit = row[6]
                            else:
                                speed_limit = row[3]
                        elif vehicle == 'HMV':
                            speed_limit = row[4]
                        else:
                            speed_limit = row[7]
                        if speed < -speed_limit:
                            direction = 'Departing'
                        elif speed > speed_limit:
                            direction = 'Approaching'
                        '''elif -10 < speed < 0:
                            direction = 'wrong direction'''
                        speed = abs(speed)
                    else:
                        if vehicle == 'LMV':
                            speed_limit = max(row[3], row[6])
                        elif vehicle == 'HMV':
                            speed_limit = row[4]
                        else:
                            speed_limit = row[7]
                        if speed < -speed_limit:
                            direction = 'Departing'
                        elif speed > speed_limit:
                            direction = 'Approaching'
                        '''elif -10 < speed < 0:
                            direction = 'wrong direction'''
                        speed = abs(speed)
                else:
                    speed_limit = None
                    speed = None
                    distance = None
                    direction = None

                if speed is not None:
                    tole = int(row[8]) / 100 * int(speed_limit)
                    tole = round(tole)
                    if int(speed) > int(speed_limit) + tole:
                        cursor.execute(
                            "INSERT INTO numberplaterecords (image_id, datetime, num_date, location, officername, officer_id, "
                            "speed_limit, vehicle_speed, distance, direction, numberplate, laser_id, uploaded, lat, lon, offence_type, lp_color, vehicle_type, com_lmv_speed, per_lmv_speed, hmv_speed, bike_speed, tolerance) VALUES (?, ?, ?, ?, "
                            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (image_id, cur_time, cur_date, row[0], row[1], row[2], speed_limit, speed, distance,
                             direction, '', row[11], 'n', lat, lon, '', color_name, vehicle, y_car_speed, w_car_speed,
                             hmv_speed, bike_speed, tolerance))

                        # Commit the changes and close the connection
                        conn.commit()
                        conn.close()
                    else:
                        pass
                else:
                    cursor.execute(
                        "INSERT INTO numberplaterecords (image_id, datetime, num_date, location, officername, officer_id, "
                        "speed_limit, vehicle_speed, distance, direction, numberplate, laser_id, uploaded, lat, lon, offence_type, lp_color, vehicle_type) VALUES (?, ?, ?, ?, "
                        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (image_id, cur_time, cur_date, row[0], row[1], row[2], speed_limit, speed, distance,
                         direction, '', row[11], 'n', lat, lon, '', color_name, vehicle))

                    # Commit the changes and close the connection
                    conn.commit()
                    conn.close()
            img.close()
        else:
            logging.error(f"Plate Rec Response: {response_data}")
            if night_on:
                if distance is not None:
                    if distance > 50:
                        distance = distance * 1.3
                        distance = round(distance, 1)
            else:
                if distance is not None:
                    if 100 < distance < 300:
                        distance = distance * 1.2
                        distance = round(distance, 1)
            conn = sqlite3.connect('msiplusersettingsmh.db')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM locations ORDER BY rowid DESC LIMIT 1")
            row = cursor.fetchone()
            lat = '' if lat is None else str(lat)
            lon = '' if lon is None else str(lon)
            direction = None
            color_name = 'yellow'
            if speed is not None and distance is not None:
                if not night_on:
                    if vehicle == 'LMV':
                        color_name = 'yellow'
                        speed_limit = row[6]  # only yellow lmv speed limit is saved
                    elif vehicle == 'HMV':
                        color_name = 'yellow'
                        speed_limit = row[4]
                    else:
                        color_name = 'white'
                        speed_limit = row[7]
                    if speed < -speed_limit:
                        direction = 'Departing'
                    elif speed > speed_limit:
                        direction = 'Approaching'
                    '''elif -10 < speed < 0:
                        direction = 'wrong direction'''
                    speed = abs(speed)
                else:
                    if vehicle == 'LMV':
                        color_name = 'white'
                        speed_limit = max(row[3], row[6])
                    elif vehicle == 'HMV':
                        color_name = 'yellow'
                        speed_limit = row[4]
                    else:
                        speed_limit = row[7]
                        color_name = 'white'
                    if speed < -speed_limit:
                        direction = 'Departing'
                    elif speed > speed_limit:
                        direction = 'Approaching'
                    '''elif -10 < speed < 0:
                        direction = 'wrong direction'''
                    speed = abs(speed)
            else:
                speed_limit = None
                speed = None
                distance = None
                direction = None
                color_name = 'yellow'

            if speed is not None:
                tole = int(row[8]) / 100 * int(speed_limit)
                tole = round(tole)
                if int(speed) > int(speed_limit) + tole:
                    cursor.execute(
                        "INSERT INTO numberplaterecords (image_id, datetime, num_date, location, officername, officer_id, "
                        "speed_limit, vehicle_speed, distance, direction, numberplate, laser_id, uploaded, lat, lon, offence_type, lp_color, vehicle_type, com_lmv_speed, per_lmv_speed, hmv_speed, bike_speed, tolerance) VALUES (?, ?, ?, ?, "
                        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (image_id, cur_time, cur_date, row[0], row[1], row[2], speed_limit, speed, distance,
                         direction, '', row[11], 'n', lat, lon, '', color_name, vehicle, y_car_speed, w_car_speed,
                         hmv_speed, bike_speed, tolerance))

                    # Commit the changes and close the connection
                    conn.commit()
                    conn.close()
                else:
                    pass
            else:
                cursor.execute(
                    "INSERT INTO numberplaterecords (image_id, datetime, num_date, location, officername, officer_id, "
                    "speed_limit, vehicle_speed, distance, direction, numberplate, laser_id, uploaded, lat, lon, offence_type, lp_color, vehicle_type) VALUES (?, ?, ?, ?, "
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (image_id, cur_time, cur_date, row[0], row[1], row[2], speed_limit, speed, distance,
                     direction, '', row[11], 'n', lat, lon, '', color_name, vehicle))

                # Commit the changes and close the connection
                conn.commit()
                conn.close()
    except Exception as exx:
        # messagebox.showwarning("Speed Hunter III Plus", "Exception while reading LPR.")
        logging.error(f"Exception in reading LPR outer loop: {str(exx)}")


class View_All(tk.Toplevel):
    instance = None

    def __init__(self, parent):
        super().__init__(parent)
        self.updated_vehicle_category = None
        self.offence_id = None
        self.selected_offence = None
        logging.info("Entered Class View_All()")

        self.geometry("1280x762+0+0")
        self.title("View Unsaved Images")
        self.result = None
        # self.wm_overrideredirect(True)
        self.resizable(False, False)
        self.configure(bg="orange")
        self.transient(parent)  # To always set this window on top of the MainApplication window
        self.grab_set()
        self.extracted_dir = None

        self.canvas_frame = tk.Frame(self, bg="orange")
        self.canvas_frame.grid(row=0, column=0)

        # Canvas
        self.canvas = tk.Canvas(self.canvas_frame, width=1000, height=752, bg="white")  # 600, 437
        self.canvas.pack()

        self.right_frame = tk.Frame(self, bg="orange")
        self.right_frame.grid(row=0, column=1, padx=5)

        self.right_bottom_frame = tk.Frame(self, bg="orange")
        self.right_bottom_frame.grid(row=2, column=1, padx=5)

        back_img = Image.open('resources/48PX/back.png')
        back_img = back_img.resize((60, 60), Image.LANCZOS)
        back_photo = ImageTk.PhotoImage(back_img)
        self.back_photo = back_photo
        # Create buttons
        self.back = ttk.Button(self.canvas, command=self.load_previous_image)
        self.back.configure(width=7, takefocus=False, image=self.back_photo)
        self.back.pack()
        self.canvas.create_window(60, 368, window=self.back)

        next_img = Image.open('resources/48PX/right.png')
        next_img = next_img.resize((58, 58), Image.LANCZOS)
        next_photo = ImageTk.PhotoImage(next_img)
        self.next_photo = next_photo
        # Create buttons
        self.next = ttk.Button(self.canvas, command=self.load_next_image)
        self.next.configure(width=7, takefocus=False, image=self.next_photo)
        self.next.pack()
        self.canvas.create_window(942, 368, window=self.next)

        # Save Button
        save_img = Image.open('resources/48PX/save.png')
        save_img = save_img.resize((30, 30), Image.LANCZOS)
        save_photo = ImageTk.PhotoImage(save_img)
        self.save_photo = save_photo

        # Create a print button
        self.save_button = tk.Button(self.right_frame, text="Save",
                                     compound=tk.LEFT, command=self.save_details)
        self.save_button.configure(image=self.save_photo)
        self.save_button.grid(row=2, column=0, pady=15)

        # Create a close window button
        self.close_button = tk.Button(self.right_frame, text="Close", bg="red", height=3, width=10,
                                      compound=tk.LEFT, command=self.destroy_window)
        self.close_button.grid(row=0, column=0, pady=15)

        # Button to open file dialog
        open_img = Image.open('resources/48PX/View.png')
        open_img = open_img.resize((30, 30), Image.LANCZOS)
        open_photo = ImageTk.PhotoImage(open_img)
        self.open_photo = open_photo
        # Create an open image button
        self.button = tk.Button(self.right_frame, text="Browse Images",
                                compound=tk.LEFT, command=self.open_file_dialog)
        self.button.configure(image=self.open_photo)
        self.button.grid(row=1, column=0, pady=15)
        self.load_default_image()


    @classmethod
    def create(cls, parent):
        # Create a new instance of Offence
        if cls.instance is not None:
            cls.instance.destroy()
        cls.instance = cls(parent)
        cls.instance.protocol("WM_DELETE_WINDOW", cls.destroy_instance)

    @classmethod
    def destroy_instance(cls):
        # Destroy current instance of Offence
        if cls.instance is not None:
            cls.instance.destroy()
            cls.instance = None

    def destroy_window(self):
        self.destroy()
        View_All.instance = None

    def save_details(self):
        try:
            # print(self.file_path) ----> /media/nvidia/Elements/original_images/2024-05-14/1249000120231229181642746.jpg
            filename = os.path.splitext(os.path.basename(self.file_path))[0]
            # Extracting the date from the path
            date = self.file_path.split('/')[-2]
            # print(filename)  ----> 1249000120231229181642746
            conn = sqlite3.connect('msiplusersettingsmh.db')
            cursor = conn.cursor()
            query = """
                                SELECT image_id
                                FROM numberplaterecords
                                WHERE image_id = ?;
                    """
            cursor.execute(query, (filename,))
            ret = cursor.fetchone()
            if ret:
                if not os.path.exists(f"/media/{getpass.getuser()}/Elements/images_with_info/{date}/{filename}.jpg"):
                    try:
                        destination_path = f"/media/{getpass.getuser()}/Elements/images_with_info/{date}/{filename}.jpg"
                        shutil.copyfile(self.file_path, destination_path)
                        self.withdraw()
                        messagebox.showinfo("Success", "Image saved successfully!")
                        self.deiconify()
                    except Exception as d:
                        self.withdraw()
                        messagebox.showerror("Error", f"{d}")
                        logging.error(f"{str(d)}")
                        self.deiconify()
                else:
                    self.withdraw()
                    messagebox.showerror("Success", "Image is already saved!")
                    self.deiconify()
            else:
                self.withdraw()
                messagebox.showerror("Error", "No record found for this image!")
                self.deiconify()
            conn.close()
        except Exception as a:
            logging.error(f"{str(a)}")

    def get_image_files_in_folder(self, folder_path):
        if os.path.exists(folder_path):
            # Get a list of image files in the specified folder path
            files = os.listdir(folder_path)
            files.sort()
            image_files = glob.glob(os.path.join(folder_path, "*.*"))
            image_files.sort(key=lambda x: files.index(os.path.basename(x)))
            return [file for file in image_files if file.lower().endswith(('.jpg', '.bmp', '.png'))]
        else:
            return False

    def load_default_image(self):
        try:
            # Get the current date folder
            global image_name
            current_date_folder = get_current_date_folder()
            username = getpass.getuser()
            # Get a list of image files in the current date folder
            image_files = self.get_image_files_in_folder(
                os.path.join(f"/media/{username}/Elements/original_images", current_date_folder))

            if not image_files:
                # If no image files are available for the current date, load the default image
                image_path = "resources/img/sphu.png"
                pil_image = Image.open(image_path)
                pil_image = pil_image.resize((1000, 752), Image.LANCZOS)  # 600, 437
                tk_image = ImageTk.PhotoImage(pil_image)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
                self.canvas.image = tk_image
                pil_image.close()

            else:
                # Get the last image file in the list
                image_path = image_files[-1]
                file_name = os.path.basename(image_path)
                image_name, _ = os.path.splitext(file_name)
                # Load the image to the canvas
                self.load_image_to_canvas(image_path)
                # Disable/enable the "Previous" and "Next" buttons accordingly
                self.update_button_state()
        except Exception:
            pass

    def load_image_to_canvas(self, image_path):
        try:
            global canvas_image_path
            canvas_image_path = image_path
            '''image = Image.open(image_path)
            # Create a drawing object
            draw = ImageDraw.Draw(image)
            # Define the position and size of the plus mark
            x, y = 980, 550
            size = 40
            # Draw the plus mark
            draw.line((x - size, y, x + size, y), fill=(255, 0, 0), width=4)
            draw.line((x, y - size, x, y + size), fill=(255, 0, 0), width=4)
            # Save the modified image with the plus mark
            modified_image_path = "plus_sign_image.bmp"
            image.save(modified_image_path)'''
            path = os.path.join(f"/media/{getpass.getuser()}/Elements", image_path)
            pil_image = Image.open(path)
            pil_image = pil_image.resize((1000, 752), Image.LANCZOS)  # 600, 437
            # Convert image to Tkinter PhotoImage format
            tk_image = ImageTk.PhotoImage(pil_image)

            # self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
            self.canvas.image = tk_image
            self.file_path = path
            pil_image.close()

        except FileNotFoundError as e:
            print(e)
        except TclError as t:
            print(t)
        except Exception as m:
            print(m)

    def load_previous_image(self):
        try:
            # Get the current date folder
            current_date_folder = get_current_date_folder()
            if self.extracted_dir is not None:
                image_files = self.get_image_files_in_folder(self.extracted_dir)
                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index > 0:
                    # Load the previous image to the canvas
                    previous_image_path = image_files[current_image_index - 1]
                    self.load_image_to_canvas(previous_image_path)
                    file_name = os.path.basename(previous_image_path)
                    prev_img_name, _ = os.path.splitext(file_name)
            else:
                # Get a list of image files in the current date folder
                image_files = self.get_image_files_in_folder(
                    os.path.join(f"/media/{getpass.getuser()}/Elements/original_images", current_date_folder))

                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index > 0:
                    # Load the previous image to the canvas
                    previous_image_path = image_files[current_image_index - 1]
                    self.load_image_to_canvas(previous_image_path)
                    file_name = os.path.basename(previous_image_path)
                    prev_img_name, _ = os.path.splitext(file_name)

            # Disable/enable the "Previous" and "Next" buttons accordingly
            self.update_button_state()
        except Exception as w:
            print(w)

    def load_next_image(self):
        try:
            # Get the current date folder
            current_date_folder = get_current_date_folder()
            if self.extracted_dir is not None:
                image_files = self.get_image_files_in_folder(self.extracted_dir)
                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index < len(image_files) - 1:
                    # Load the next image to the canvas
                    next_image_path = image_files[current_image_index + 1]
                    self.load_image_to_canvas(next_image_path)
                    file_name = os.path.basename(next_image_path)
                    next_img_name, _ = os.path.splitext(file_name)
            else:
                # Get a list of image files in the current date folder
                image_files = self.get_image_files_in_folder(
                    os.path.join(f"/media/{getpass.getuser()}/Elements/original_images", current_date_folder))
                if not image_files:
                    return
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path)

                if current_image_index < len(image_files) - 1:
                    # Load the next image to the canvas
                    next_image_path = image_files[current_image_index + 1]
                    self.load_image_to_canvas(next_image_path)
                    file_name = os.path.basename(next_image_path)
                    next_img_name, _ = os.path.splitext(file_name)

            # Disable/enable the "Previous" and "Next" buttons accordingly
            self.update_button_state()

        except Exception:
            pass

    def update_button_state(self):
        try:
            # Get the current date folder
            current_date_folder = get_current_date_folder()
            if self.extracted_dir is not None:
                image_files = self.get_image_files_in_folder(self.extracted_dir)
                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path) if self.file_path in image_files else -1
                # Enable/disable "Previous" and "Next" buttons based on the current image index
                self.back.config(state=tk.NORMAL if current_image_index > 0 else tk.DISABLED)
                self.next.config(state=tk.NORMAL if current_image_index < len(image_files) - 1 else tk.DISABLED)
                # self.canvas1.delete("all")
            else:
                # Get a list of image files in the current date folder
                image_files = self.get_image_files_in_folder(
                    os.path.join(f"/media/{getpass.getuser()}/Elements/original_images", current_date_folder))

                # Find the index of the current image file
                current_image_index = image_files.index(self.file_path) if self.file_path in image_files else -1

                # Enable/disable "Previous" and "Next" buttons based on the current image index
                self.back.config(state=tk.NORMAL if current_image_index > 0 else tk.DISABLED)
                self.next.config(state=tk.NORMAL if current_image_index < len(image_files) - 1 else tk.DISABLED)
                # self.canvas1.delete("all")
        except Exception:
            pass

    def open_file_dialog(self):
        self.withdraw()
        transient_window = tk.Toplevel()
        transient_window.attributes('-topmost', True)
        transient_window.withdraw()
        cur_date = datetime.date.today()
        username = getpass.getuser()
        file_path = filedialog.askopenfilename(parent=transient_window,
                                               initialdir=f"/media/{username}/Elements/original_images/{cur_date}",
                                               title="Select Image File From 'original_images' Folder Only.",
                                               filetypes=(
                                                   ("JPEG files", ".jpg"), ("BMP files", ".bmp"),
                                                   ("PNG files", ".png")))
        transient_window.destroy()
        if file_path:
            self.deiconify()
            start_index = file_path.find('original_images/')
            if start_index != -1:
                image_path = file_path[start_index:]
                self.load_image_to_canvas(image_path)
                dir_name = os.path.dirname(file_path)
                self.extracted_dir = os.path.join(f'/media/{getpass.getuser()}/Elements/original_images',
                                                  os.path.basename(dir_name))
                # print("extracted dir=", self.extracted_dir) -> extracted dir= images_with_info/2024-01-23
                self.get_image_files_in_folder(self.extracted_dir)
                if self.extracted_dir is not None:
                    image_files = self.get_image_files_in_folder(self.extracted_dir)
                    # print("image files=", image_files)
                    if not image_files:
                        return
                    # Find the index of the current image file
                    # print("self. file path=", self.file_path)
                    current_image_index = image_files.index(self.file_path)
                    current_image_path = image_files[current_image_index]
                    # print("current img path=", current_image_path) -->/media/nvidia/Elements/images_with_info/2024-01-23/1302001220240123143738792.jpg
                    self.load_image_to_canvas(current_image_path)
                    file_name = os.path.basename(current_image_path)
                    cur_img_name, _ = os.path.splitext(file_name)
                    # print("cur img name=", cur_img_name) -->1302001220240123143738792
        # Disable/enable the "Previous" and "Next" buttons accordingly
        else:
            self.deiconify()
        self.update_button_state()



class MainApplication:
    def __init__(self, window, cam_port, laser_port, gps_port, vd):
        logging.info('Start of MainApplication')
        self.window = window
        self.window.title("Speed Hunter III Plus")

        #  <------------------SPEED HUNTER III PLUS BY KIRAN----------------------------------------------->
        self.vehicle_detection_is_on = True if vd == '1' else False
        self.licence_snapshot_lock = threading.Lock()
        # self.three_second_lock = threading.Lock()
        # self.buffer_size = 90
        # self.frames = []
        self.t = threading.Timer(60, self.read_gps_data_func)
        self.last_img = threading.Timer(2, self.show_last_image_func)
        self.officer_name = ''
        self.officer_id = ''
        self.device_id = ''
        self.written_duplicate_frame = None
        self.night_mode_is_on = None
        self.shutter_priority_is_on = None
        global output_path, ser1, original_path, helmet_path
        username = getpass.getuser()
        output_path = os.path.join(f"/media/{username}/Elements", "number_plate_images")
        # output_path = os.path.join(os.getcwd(), "number_plate_images")  # self.get_current_directory()
        output_path = os.path.join(output_path, get_current_date_folder())
        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path)
            except Exception as hd:
                er13()

        output_path = os.path.join(f"/media/{username}/Elements", "number_plate_images")
        # output_path = os.path.join(os.getcwd(), "number_plate_images")  # self.get_current_directory()
        output_path = os.path.join(output_path, get_current_date_folder())
        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path)
            except Exception as hd:
                if getattr(sys, 'frozen', False):
                    pyi_splash.close()
                messagebox.showwarning("Warning", "Path cannot be created! Contact MSIPL team now.")
                logging.error(f"{str(hd)}")
                logging.info("################################################################################")
                sys.exit()

        original_path = os.path.join(f"/media/{username}/Elements", "original_images")  # self.get_current_directory()
        original_path = os.path.join(original_path, get_current_date_folder())
        if not os.path.exists(original_path):
            os.makedirs(original_path)
        log_path = os.path.join(original_path, "Log")
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        crop_dir1 = os.path.join(f"/media/{username}/Elements", 'cropped_numplate_images')
        output_path0 = os.path.join(crop_dir1, get_current_date_folder())
        if not os.path.exists(output_path0):
            os.makedirs(output_path0)
        helmet_path = os.path.join(f"/media/{getpass.getuser()}/Elements/without_helmet", get_current_date_folder())
        if not os.path.exists(helmet_path):
            os.makedirs(helmet_path)
        helmet_info_path = os.path.join(f"/media/{getpass.getuser()}/Elements/helmet_info", get_current_date_folder())
        if not os.path.exists(helmet_info_path):
            os.makedirs(helmet_info_path)
        log_path1 = os.path.join(helmet_info_path, "Log")
        if not os.path.exists(log_path1):
            os.makedirs(log_path1)
        img_with_info_path = os.path.join(f"/media/{getpass.getuser()}/Elements/images_with_info",
                                          get_current_date_folder())
        if not os.path.exists(img_with_info_path):
            os.makedirs(img_with_info_path)
        '''delete_old_folders("original_images")
        delete_old_folders("cropped_numplate_images")
        delete_old_folders("number_plate_images")
        delete_old_folders("images_with_info")'''

        '''try:
            self.three_second_folder = os.path.join("/media/nvidia/Elements/3sOffence_Videos",
                                                    str(datetime.date.today().strftime("%Y-%m-%d")))
            os.makedirs(self.three_second_folder, exist_ok=True)
        except Exception:
            pass'''
        ser1 = serial.Serial(laser_port, 115200, timeout=1)
        self.second_copy_frame = None
        self.display_location = ''
        self.lati = None
        self.longi = None
        self.selected = ''
        print("[INFO] Loading model please wait...")
        logging.info("[INFO] Loading helmet model")
        self.model = torch.hub.load('yolov5', 'custom', source='local', path=self.resource_path("nhb.pt"),
                                    force_reload=True)
        self.classes = self.model.names
        logging.info("[INFO] Loading vehicle model")
        self.vehicle_model = torch.hub.load('yolov5', 'custom',
                                            source='local', path=self.resource_path('nvb.pt'),
                                            force_reload=True)
        self.vehicle_classes = self.vehicle_model.names
        self.bike_speed_limit = 0
        self.car_speed_limit = 0
        self.truck_speed_limit = 0
        # self.lmvtruck_speed_limit = 0
        # self.bus_speed_limit = 0
        self.no_detection = False
        self.box_size = 220  # You can adjust the size as needed
        self.rect_x1 = 640 - self.box_size
        self.rect_y1 = 360 - self.box_size
        self.rect_x2 = 640 + self.box_size
        self.rect_y2 = 360 + self.box_size
        self.rect_y1 -= 60
        self.rect_y2 += 60

        self.y = None
        self.x = None
        self.z = None
        self.w = None
        self.camera_thread = None
        self.gps_thread = None
        self.cur_distance = None
        self.timeout = 0
        self.cur_speed = None
        self.termination_condition = False
        self.manual_capture_active = False
        self.manual_capture_thread = None  # Thread for manual capture
        self.auto_capture_active = False
        self.auto_capture_thread = None  # Thread for auto capture
        self.video_rec_active = False
        self.video_rec_thread = None  # Thread for auto capture
        # pipeline = 'v4l2src device=/dev/video0 ! video/x-raw,width=1920,height=1080,framerate=30/1 ! videoconvert !
        # video/x-raw,format=BGR ! appsink sync=0 drop=1'
        self.cap = cv2.VideoCapture('/dev/video0')
        try:
            logging.info(f"Video Backend Name: {str(self.cap.getBackendName())}")
        except Exception as v:
            if getattr(sys, 'frozen', False):
                pyi_splash.close()
            messagebox.showwarning("Warning", "Frames from camera are unavailable. Check camera app and then try again!")
            logging.error(f"{str(v)}")
            logging.info("################################################################################")
            sys.exit()

        self.stop_event = threading.Event()
        self.helmet_on = False
        self.process_thread = None
        self.frame_queue = queue.Queue(maxsize=1)

        self.canvas = tk.Canvas(self.window, width=1280, height=700)
        self.canvas.pack(side=tk.BOTTOM)

        # Create a Label widget for displaying the last image
        self.last_image_label = Label(self.window, width=200, height=130)
        self.last_image_label.place(x=1068, y=580)
        self.img1 = Image.open("resources/img/notavailable.jpg")
        self.img1 = self.img1.resize((200, 130))
        self.img1 = ImageTk.PhotoImage(self.img1)
        self.last_image_label.config(image=self.img1)
        self.last_image_label.image = self.img1

        # Create a frame for the buttons
        self.button_frame = tk.LabelFrame(self.window, bg='green')
        self.button_frame.pack(anchor=tk.NW, fill=tk.BOTH, expand=True, padx=5)

        style = ttk.Style()
        style.configure("TButton", padding=8)

        zoomin_img = Image.open('resources/48PX/zoomin.png')
        zoomin_img = zoomin_img.resize((50, 50), Image.LANCZOS)
        zoomin_photo = ImageTk.PhotoImage(zoomin_img)
        self.zoomin_photo = zoomin_photo
        zoomin_img.close()

        zoomout_img = Image.open('resources/48PX/zoomout.png')
        zoomout_img = zoomout_img.resize((50, 50), Image.LANCZOS)
        zoomout_photo = ImageTk.PhotoImage(zoomout_img)
        self.zoomout_photo = zoomout_photo
        zoomout_img.close()

        close_img = Image.open('resources/48PX/Close.png')
        close_img = close_img.resize((70, 50), Image.LANCZOS)
        close_photo = ImageTk.PhotoImage(close_img)
        self.close_photo = close_photo
        close_img.close()

        menu_img = Image.open('resources/img/menu.png')
        menu_img = menu_img.resize((55, 100), Image.LANCZOS)
        menu_photo = ImageTk.PhotoImage(menu_img)
        self.menu_photo = menu_photo
        menu_img.close()

        offence_img = Image.open('resources/img/spotfine.png')
        offence_img = offence_img.resize((55, 55), Image.LANCZOS)
        offence_photo = ImageTk.PhotoImage(offence_img)
        self.offence_photo = offence_photo
        offence_img.close()

        settings_img = Image.open('resources/img/settings.png')
        settings_img = settings_img.resize((55, 55), Image.LANCZOS)
        settings_photo = ImageTk.PhotoImage(settings_img)
        self.settings_photo = settings_photo
        settings_img.close()

        helmet_img = Image.open('resources/img/helmet.png')
        helmet_img = helmet_img.resize((55, 55), Image.LANCZOS)
        helmet_photo = ImageTk.PhotoImage(helmet_img)
        self.helmet_photo = helmet_photo
        helmet_img.close()

        view_img = Image.open('resources/NEWview.png')
        view_img = view_img.resize((55, 55), Image.LANCZOS)
        view_photo = ImageTk.PhotoImage(view_img)
        self.view_photo = view_photo
        view_img.close()

        capture_img = Image.open('resources/img/Capture.png')
        capture_img = capture_img.resize((60, 55), Image.LANCZOS)
        capture_photo = ImageTk.PhotoImage(capture_img)
        self.capture_photo = capture_photo
        capture_img.close()

        db_img = Image.open('resources/img/db.png')
        db_img = db_img.resize((60, 65), Image.LANCZOS)
        db_photo = ImageTk.PhotoImage(db_img)
        self.db_photo = db_photo
        db_img.close()

        hel_db_img = Image.open('resources/img/heldb.png')
        hel_db_img = hel_db_img.resize((60, 65), Image.LANCZOS)
        hel_db_photo = ImageTk.PhotoImage(hel_db_img)
        self.hel_db_photo = hel_db_photo
        hel_db_img.close()

        '''refresh_img = Image.open('resources/img/refresh.png')
        refresh_img = refresh_img.resize((60, 55), Image.LANCZOS)
        refresh_photo = ImageTk.PhotoImage(refresh_img)
        self.refresh_photo = refresh_photo
        refresh_img.close()'''

        video_record_img = Image.open('resources/rec.png')
        video_record_img = video_record_img.resize((60, 60), Image.LANCZOS)
        video_record_photo = ImageTk.PhotoImage(video_record_img)
        self.video_record_photo = video_record_photo
        video_record_img.close()

        video_record_stop_img = Image.open('resources/stop_rec.png')
        video_record_stop_img = video_record_stop_img.resize((60, 60), Image.LANCZOS)
        video_record_stop_photo = ImageTk.PhotoImage(video_record_stop_img)
        self.video_record_stop_photo = video_record_stop_photo
        video_record_stop_img.close()

        '''increase_img = Image.open('resources/img/increase.png')
        increase_img = increase_img.resize((60, 60), Image.LANCZOS)
        increase_photo = ImageTk.PhotoImage(increase_img)
        self.increase_photo = increase_photo
        increase_img.close()

        decrease_img = Image.open('resources/img/decrease.png')
        decrease_img = decrease_img.resize((60, 60), Image.LANCZOS)
        decrease_photo = ImageTk.PhotoImage(decrease_img)
        self.decrease_photo = decrease_photo
        decrease_img.close()'''

        # Create buttons
        self.menu = tk.Button(self.canvas, compound=tk.LEFT, command=self.menu_click, state=DISABLED)
        self.menu.configure(width=50, image=self.menu_photo)
        self.menu.pack()
        self.canvas.create_window(40, 335, window=self.menu)

        # Check if the initialization has already occurred
        if not self.is_initialized():
            self.create_initialization_table()
            self.open_initialization_window()
        else:
            self.menu.config(state=NORMAL)

        self.offence_button = tk.Button(self.canvas, image=self.offence_photo, takefocus=False, bg="black",
                                        borderwidth=0, state=DISABLED, command=self.offence)
        self.settings_button = tk.Button(self.canvas, image=self.settings_photo, takefocus=False, bg="black",
                                         borderwidth=0, command=self.location)
        self.helmet_button = tk.Button(self.canvas, image=self.helmet_photo, takefocus=False, bg="black",
                                       borderwidth=0, state=DISABLED, command=self.helmet_offence)
        self.view_button = tk.Button(self.canvas, image=self.view_photo, takefocus=False, bg="black",
                                       borderwidth=0, state=DISABLED, command=self.view_all)
        self.menu_buttons_shown = False

        self.zoomin = ttk.Button(self.canvas, compound=tk.LEFT)
        self.zoomin.configure(width=5, takefocus=False, image=zoomin_photo)
        self.zoomin.pack()
        self.canvas.create_window(63, 625, window=self.zoomin)

        self.zoomout = ttk.Button(self.canvas, compound=tk.LEFT)
        self.zoomout.configure(width=5, takefocus=False, image=zoomout_photo)
        self.zoomout.pack()
        self.canvas.create_window(180, 625, window=self.zoomout)

        self.snapshot_btn = ttk.Button(self.canvas, compound=tk.CENTER, command=self.snapshot, state=tk.DISABLED)
        self.snapshot_btn.configure(width=2, takefocus=False, image=self.capture_photo)
        self.snapshot_btn.pack()
        self.canvas.create_window(1230, 475, window=self.snapshot_btn)

        self.database_btn = ttk.Button(self.canvas, compound=tk.CENTER, command=self.open_database_window,
                                       state=tk.DISABLED)
        self.database_btn.configure(width=2, takefocus=False, image=self.db_photo)
        self.database_btn.pack()
        self.canvas.create_window(1230, 385, window=self.database_btn)

        self.helmet_database_btn = ttk.Button(self.canvas, compound=tk.CENTER, command=self.open_helmet_database_window,
                                              state=tk.DISABLED)
        self.helmet_database_btn.configure(width=2, takefocus=False, image=self.hel_db_photo)
        self.helmet_database_btn.pack()
        self.canvas.create_window(1230, 295, window=self.helmet_database_btn)

        '''self.refresh_btn = ttk.Button(self.canvas, compound=tk.CENTER, command=self.show_last_image)
        self.refresh_btn.configure(width=2, takefocus=False, image=self.refresh_photo)
        self.refresh_btn.pack()
        self.canvas.create_window(1230, 200, window=self.refresh_btn)'''

        self.video_record_btn = ttk.Button(self.canvas, compound=tk.CENTER, command=self.start_video_record,
                                           state=tk.DISABLED)
        self.video_record_btn.configure(width=2, takefocus=False, image=self.video_record_photo)
        self.video_record_btn.pack()
        self.canvas.create_window(1230, 200, window=self.video_record_btn)

        '''self.decrease_box_btn = ttk.Button(self.canvas, compound=tk.CENTER, command=self.decrease_box_size)
        self.decrease_box_btn.configure(width=2, takefocus=False, image=self.decrease_photo)
        self.decrease_box_btn.pack()
        self.canvas.create_window(1230, 345, window=self.decrease_box_btn)

        self.increase_box_btn = ttk.Button(self.canvas, compound=tk.CENTER, command=self.increase_box_size)
        self.increase_box_btn.configure(width=2, takefocus=False, image=self.increase_photo)
        self.increase_box_btn.pack()
        self.canvas.create_window(1230, 260, window=self.increase_box_btn)'''

        self.button1 = tk.Button(self.canvas, text="Tools", command=self.open_window1, state=tk.DISABLED)
        self.button1.configure(width=5, height=3, takefocus=False)
        self.button1.pack()
        self.canvas.create_window(288, 625, window=self.button1)

        '''self.button3 = ttk.Button(self.button_frame, text="Snapshot", command=self.snapshot_even, state=tk.DISABLED)
        self.button3.configure(width=10, takefocus=False)
        self.button3.pack(side=tk.LEFT)'''

        self.manual_button = tk.Button(self.button_frame, text="Manual Capture", command=self.manual_capture,
                                       state=tk.DISABLED, bg="lightblue")
        self.manual_button.configure(width=30, height=10, takefocus=False)
        self.manual_button.pack(side=tk.LEFT)

        self.button2 = tk.Button(self.button_frame, text="Start Auto Capture", command=self.auto_capture,
                                 state=tk.DISABLED, bg="lightblue")
        self.button2.configure(width=30, height=10, takefocus=False)
        self.button2.pack(side=tk.LEFT)

        self.car_button = tk.Button(self.button_frame, text="LMV:", state=tk.DISABLED, command=self.car)
        self.car_button.configure(width=20, height=10, takefocus=False, bg="lightblue")
        self.car_button.pack(side=tk.LEFT)

        self.hmvtruck_button = tk.Button(self.button_frame, text="HMV:", state=tk.DISABLED,
                                         command=self.truck)
        self.hmvtruck_button.configure(width=20, height=10, takefocus=False, bg="lightblue")
        self.hmvtruck_button.pack(side=tk.LEFT)

        '''self.lmvtruck_button = tk.Button(self.button_frame, text="LMV-Truck:", state=tk.DISABLED,
                                         command=self.lmvtruck)
        self.lmvtruck_button.configure(width=15, height=10, takefocus=False, bg="lightblue")
        self.lmvtruck_button.pack(side=tk.LEFT)

        self.bus_button = tk.Button(self.button_frame, text="Bus:", state=tk.DISABLED, command=self.bus)
        self.bus_button.configure(width=10, height=10, takefocus=False, bg="lightblue")
        self.bus_button.pack(side=tk.LEFT)'''

        self.bike_button = tk.Button(self.button_frame, text="Bike:", state=tk.DISABLED, command=self.bike)
        self.bike_button.configure(width=23, height=10, takefocus=False, bg="lightblue")
        self.bike_button.pack(side=tk.LEFT)

        '''self.buttondb = ttk.Button(self.button_frame, text="DB", command=self.open_database_window)
        self.buttondb.configure(width=3, takefocus=False)
        self.buttondb.pack(side=tk.LEFT)'''

        '''self.gps_btn = ttk.Button(self.button_frame, text="GPS", command=self.read_gps_data, state=tk.DISABLED)
        self.gps_btn.configure(width=4, takefocus=False)
        self.gps_btn.pack(side=tk.LEFT)'''

        self.helmetbtn = tk.Button(self.button_frame, text="Helmet", command=self.helmet_thread, bg="lightblue",
                                   state=DISABLED)
        self.helmetbtn.configure(width=13, height=10, takefocus=False)
        self.helmetbtn.pack(side=tk.LEFT)

        self.button8 = tk.Button(self.button_frame, command=self.exit_app)
        self.button8.configure(image=self.close_photo, borderwidth=3)
        self.button8.pack(side=tk.RIGHT)

        self.zoomin.bind("<ButtonPress-1>", lambda event: self.zoom_in())
        self.zoomin.bind("<ButtonRelease-1>", lambda event: self.zoom_in_stop())
        self.zoomout.bind("<ButtonPress-1>", lambda event: self.zoom_out())
        self.zoomout.bind("<ButtonRelease-1>", lambda event: self.zoom_out_stop())
        if getattr(sys, 'frozen', False):
            pyi_splash.close()
        logging.info(f"OPENCV VERSION: {str(cv2.__version__)}")
        self.start_camera_thread()
        if check_internet_connection():
            pass
        else:
            root.withdraw()
            logging.warning("Internet is OFF at software opening time!")
            messagebox.showwarning("Internet Is OFF", "Please Turn ON The Internet NOW!")
            root.deiconify()
        if self.check_software_expiration():
            logging.error("SOFTWARE EXPIRED!!!, terminating the application")
            logging.info("################################################################################")
            sys.exit()

        # Open the camera stream
        '''build_info = cv2.getBuildInformation()
        video_io_start = build_info.find("Video I/O:")
        video_io_end = build_info.find("\n\n", video_io_start)
        video_io_innfo = build_info[video_io_start:video_io_end].strip()
        logging.info(f"{str(video_io_innfo)}")'''
        # self.show_last_image()

    def check_software_expiration(self):
        # Hardcoded expiration date
        expiration_date = datetime.datetime(2024, 3, 30) + datetime.timedelta(days=365)
        current_date = datetime.datetime.now()

        # Check if the current date is after the expiration date
        if current_date > expiration_date:
            custom_error_message("Software Expired",
                                 "Your software has expired. Please contact Medical Sensors India Pvt Ltd, Bangalore.")
            return True
        elif expiration_date - current_date <= datetime.timedelta(days=15):
            # Show a warning message box if within the last 15 days before expiration
            warning_days_left = (expiration_date - current_date).days
            custom_error_message("Software Expiry Warning",
                                 f"Warning: Your software will expire in {warning_days_left} days. Contact Medical Sensors India Pvt Ltd, Bangalore soon.")
            return False
        else:
            # Software is still valid
            return False

    def is_initialized(self):
        # Connect to the database
        conn = sqlite3.connect('msiplusersettingsmh.db')
        cursor = conn.cursor()

        # Check if the initialization status table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='initialization_status'")
        table_exists = cursor.fetchone()

        if table_exists:
            # Check if the initialization status is set
            cursor.execute(
                "SELECT initialized,RTO_Code,RTO_Name,District_Name,NIC_District_ID,NIC_userId,initialization_date FROM initialization_status")
            initialization_status = cursor.fetchone()
            logging.info(f"{str(initialization_status)}")
            conn.close()

            return initialization_status and initialization_status[0] == 1

        conn.close()
        return False

    def create_initialization_table(self):
        # Connect to the database
        conn = sqlite3.connect('msiplusersettingsmh.db')
        cursor = conn.cursor()

        table_check = "SELECT name FROM sqlite_master WHERE type='table' AND name='production_user_credentials';"
        cursor.execute(table_check)
        result = cursor.fetchone()
        if result:
            pass
        else:
            # Create the production_user_credentials table if it doesn't exist
            create_table_query = """
                    CREATE TABLE IF NOT EXISTS production_user_credentials (
                        RTO_Code TEXT PRIMARY KEY,
                        RTO_Name TEXT,
                        District_Name TEXT,
                        NIC_District_ID INTEGER,
                        NIC_userId INTEGER
                    );
                    """
            cursor.execute(create_table_query)
            data_to_insert = [
                ("MH00", "RTO-TC Office", "MUMBAI", 519, 646),
                ("MH01", "RTO-MUMBAI CENTRAL", "MUMBAI", 519, 577),
                ("MH02", "RTO-MUMBAI WEST", "MUMBAI SUBURBAN", 518, 578),
                ("MH03", "RTO-MUMBAI EAST", "MUMBAI SUBURBAN", 518, 578),
                ("MH04", "RTO-THANE", "THANE", 517, 592),
                ("MH05", "RTO-KALYAN", "THANE", 517, 592),
                ("MH06", "RTO-PEN", "RAIGARH", 520, 586),
                ("MH07", "RTO-SINDHUDURG", "SINDHUDURG", 529, 590),
                ("MH08", "RTO-RATNAGIRI", "RATNAGIRI", 528, 587),
                ("MH09", "RTO-KOLHAPUR", "KOLHAPUR", 530, 575),
                ("MH10", "RTO-SANGLI", "SANGLI", 531, 588),
                ("MH11", "RTO-SATARA", "SATARA", 527, 589),
                ("MH12", "RTO-PUNE", "PUNE", 521, 585),
                ("MH13", "RTO-SOLAPUR", "SOLAPUR", 526, 591),
                ("MH14", "RTO-PIMPRI CHINCHWAD", "PUNE", 521, 709),
                ("MH15", "RTO-NASIK", "NASHIK", 516, 582),
                ("MH16", "RTO-AHMEDNAGAR", "AHMADNAGAR", 522, 562),
                ("MH17", "RTO-SRIRAMPUR", "AHMADNAGAR", 522, 562),
                ("MH18", "RTO-DHULE", "DHULE", 498, 569),
                ("MH19", "RTO-JALGAON", "JALGAON", 499, 573),
                ("MH20", "RTO-AURANGABAD", "AURANGABAD", 515, 565),
                ("MH21", "RTO-JALNA", "JALNA", 514, 574),
                ("MH22", "RTO-PARBHANI", "PARBHANI", 513, 584),
                ("MH23", "RTO-BID", "BID", 523, 566),
                ("MH24", "RTO-LATUR", "LATUR", 524, 576),
                ("MH25", "RTO-OSMANABAD", "OSMANABAD", 525, 583),
                ("MH26", "RTO-NANDED", "NANDED", 511, 580),
                ("MH27", "RTO-AMRAVATI", "AMRAVATI", 503, 564),
                ("MH28", "RTO-BULDHANA", "BULDANA", 500, 567),
                ("MH29", "RTO-YAVATMAL", "YAVATMAL", 510, 595),
                ("MH30", "RTO-AKOLA", "AKOLA", 501, 563),
                ("MH31", "RTO-NAGPUR CITY", "NAGPUR", 505, 579),
                ("MH32", "RTO-WARDHA", "WARDHA", 504, 593),
                ("MH33", "RTO-GADCHIROLI", "GADCHIROLI", 508, 570),
                ("MH34", "RTO-CHANDRAPUR", "CHANDRAPUR", 509, 568),
                ("MH35", "RTO-GONDIA", "GONDIYA", 507, 571),
                ("MH36", "RTO-BHANDARA", "BHANDARA", 506, 561),
                ("MH37", "RTO-WASHIM", "WASHIM", 502, 594),
                ("MH38", "RTO-HINGOLI", "HINGOLI", 512, 572),
                ("MH39", "RTO-NANDURBAR", "NANDURBAR", 497, 581),
                ("MH40", "RTO-NAGPUR GRAMIN", "NAGPUR", 505, 579),
                ("MH41", "RTO-MALEGAON", "NASHIK", 516, 582),
                ("MH42", "RTO-BARAMATI", "PUNE", 521, 708),
                ("MH43", "RTO-VASHI", "THANE", 517, 592),
                ("MH44", "RTO-AMBEJOGAI", "BID", 523, 566),
                ("MH45", "RTO-AKLUJ", "SATARA", 527, 589),
                ("MH46", "RTO-PANVEL", "RAIGARH", 520, 586),
                ("MH47", "RTO-BORIVALI", "MUMBAI SUBURBAN", 518, 764),
                ("MH48", "RTO-VASAI", "THANE", 517, 592),
                ("MH49", "RTO-NAGPUR EAST", "NAGPUR", 505, 579),
                ("MH50", "RTO-KARAD", "SATARA", 527, 589),
            ]

            # Execute the INSERT query
            query = "INSERT INTO production_user_credentials (RTO_Code, RTO_Name, District_Name, NIC_District_ID, NIC_userId) VALUES (?, ?, ?, ?, ?)"
            cursor.executemany(query, data_to_insert)

            # Commit the changes
            conn.commit()
            '''# Read CSV data and insert into the table
            with open(self.resource_path('prod.csv'), 'r') as csv_file:
                csv_reader = csv.reader(csv_file)
                next(csv_reader)  # Skip header row

                for row in csv_reader:
                    cursor.execute(
                                INSERT INTO production_user_credentials (RTO_Code, RTO_Name, District_Name, NIC_District_ID, NIC_userId)
                                VALUES (?, ?, ?, ?, ?)
                            , (row[0], row[1], row[2], int(row[3]), int(row[4])))'''

        # Create the initialization status table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS initialization_status (
                initialized INTEGER,
                RTO_Code TEXT,
                RTO_Name TEXT,
                District_Name TEXT,
                NIC_District_ID INTEGER,
                NIC_userId INTEGER,
                initialization_date TEXT
            )
        ''')
        # Create the 'helmetoffencerecords' table if it doesn't exist
        cursor.execute('''CREATE TABLE IF NOT EXISTS helmetoffencerecords (
                                                    image_id TEXT PRIMARY KEY,
                                                    time TEXT,
                                                    hel_date DATE,
                                                    location TEXT,
                                                    officername TEXT,
                                                    officer_id TEXT,
                                                    numberplate TEXT,
                                                    laser_id TEXT,
                                                    uploaded TEXT,
                                                    lat TEXT,
                                                    lon TEXT,
                                                    offence_type TEXT
                                                    )
                                                ''')
        # Create the 'numberplaterecords' table if it doesn't exist
        cursor.execute('''CREATE TABLE IF NOT EXISTS numberplaterecords (
                                                    image_id TEXT PRIMARY KEY,
                                                    datetime TEXT,
                                                    num_date DATE,
                                                    location TEXT,
                                                    officername TEXT,
                                                    officer_id TEXT,
                                                    speed_limit INTEGER,
                                                    vehicle_speed INTEGER,
                                                    distance REAL,
                                                    direction TEXT,
                                                    numberplate TEXT,
                                                    laser_id TEXT,
                                                    uploaded TEXT,
                                                    lat TEXT,
                                                    lon TEXT,
                                                    offence_type TEXT,
                                                    lp_color TEXT,
                                                    vehicle_type TEXT,
                                                    com_lmv_speed INTEGER,
                                                    per_lmv_speed INTEGER,
                                                    hmv_speed INTEGER,
                                                    bike_speed INTEGER,
                                                    tolerance INTEGER
                                                    )
                                                ''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS dummylocations
                                                    (location TEXT, officer_name TEXT, officer_id TEXT, car_speed INTEGER,
                                                    truck_speed INTEGER, lmvtruck_speed INTEGER,
                                                    ycar_speed INTEGER, bike_speed INTEGER,max_tolerance INTEGER,
                                                    min_distance INTEGER,max_distance INTEGER,laser_id TEXT, date DATE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS locations
                                                    (location TEXT, officer_name TEXT, officer_id TEXT, car_speed INTEGER,
                                                    truck_speed INTEGER, lmvtruck_speed INTEGER,
                                                    ycar_speed INTEGER, bike_speed INTEGER,max_tolerance INTEGER,
                                                    min_distance INTEGER,max_distance INTEGER,laser_id TEXT, date DATE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS officerdetails(officer_name TEXT, officer_id TEXT)''')

        # Commit and close the database connection
        conn.commit()
        conn.close()
        try:
            if os.path.exists('msiplusersettings.db'):
                os.remove('msiplusersettings.db')
            if os.path.exists('device_ports.txt'):
                os.remove('device_ports.txt')
        except Exception:
            pass

    def open_initialization_window(self):
        initialization_window = tk.Toplevel(self.window)
        initialization_window.attributes('-topmost', True)
        initialization_window.resizable(False, False)
        initialization_window.overrideredirect(True)
        initialization_window.geometry(f"{490}x{190}+420+120")
        initialization_window.title("Initialization Window")
        # initialization_window.overrideredirect(1)

        rto_label = tk.Label(initialization_window, text="This device belongs to which RTO?", font=("Arial", 15))
        rto_label.grid(row=0, column=1, padx=10, pady=5)

        state_code_label = tk.Label(initialization_window, text="State Code:", font=("Arial", 15))
        state_code_entry = tk.Entry(initialization_window, font=("Arial", 15), width=6)
        state_code_entry.delete(0, tk.END)
        state_code_entry.insert(tk.END, 'MH')
        # state_code_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        district_code_label = tk.Label(initialization_window, text="RTO Code:", font=("Arial", 15))
        district_code_entry = tk.Entry(initialization_window, font=("Arial", 15), width=6)
        district_code_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        submit_button = tk.Button(initialization_window, text="Submit", height=2, width=8,
                                  command=lambda: self.save_initialization_data(
                                      state_code_entry.get().upper(), district_code_entry.get(), initialization_window
                                  ), bg="green")

        # Layout
        state_code_label.grid(row=1, column=0, padx=10, pady=5)
        state_code_entry.grid(row=1, column=1, padx=10, pady=5)
        district_code_label.grid(row=2, column=0, padx=10, pady=5)
        district_code_entry.grid(row=2, column=1, padx=10, pady=5)
        submit_button.grid(row=3, column=0, columnspan=2, pady=10)

    def save_initialization_data(self, state_code, district_code, initialization_window):
        if len(state_code) < 2 and len(district_code) < 2:
            messagebox.showerror("Error", "Fill the required details.")
            return
        # Connect to the database
        try:
            subprocess.Popen(['pkill', 'onboard'])
        except Exception:
            pass
        Rto_Code = state_code + district_code
        conn = sqlite3.connect('msiplusersettingsmh.db')
        cursor = conn.cursor()
        try:
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT * FROM production_user_credentials WHERE RTO_Code = ?", (Rto_Code,))
            prod_credentials = cursor.fetchone()
            ret = messagebox.askyesno(f"Are you sure {Rto_Code}?",
                                      f"RTO_Name:{prod_credentials[1]}\nDistrict_Name:{prod_credentials[2]}\nNIC_District_ID:{prod_credentials[3]}\nNIC_userId:{prod_credentials[4]}")
            if ret:
                cursor.execute(
                    "INSERT OR REPLACE INTO initialization_status (initialized,RTO_Code,RTO_Name,District_Name,NIC_District_ID,NIC_userId,initialization_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (1, prod_credentials[0], prod_credentials[1], prod_credentials[2], prod_credentials[3],
                     prod_credentials[4], current_date))
                conn.commit()
                initialization_window.destroy()
                messagebox.showinfo(f"Device belongs to {Rto_Code}",
                                    f"RTO_Name:{prod_credentials[1]}\nDistrict_Name:{prod_credentials[2]}\nNIC_District_ID:{prod_credentials[3]}\nNIC_userId:{prod_credentials[4]}\nDetails saved successfully.")
            else:
                return
            conn.close()
            self.menu.config(state=NORMAL)
            # Close the initialization window
            initialization_window.destroy()
        except Exception as e:
            print(f"Error saving initialization data: {e}")

    def call_show_last_image_func_periodically(self, scheduler, interval):
        self.show_last_image_func()
        scheduler.enter(interval, 1, self.call_show_last_image_func_periodically, (scheduler, interval))

    def show_last_image(self):
        s = sched.scheduler(time.time, time.sleep)
        s.enter(0, 1, self.call_show_last_image_func_periodically, (s, 1))
        threading.Thread(target=s.run).start()

    def show_last_image_func(self):
        try:
            image_folder = f'original_images/{get_current_date_folder()}'
            last_image_path = None
            img1 = Image.open("resources/img/notavailable.jpg")
            img1 = img1.resize((200, 130))
            img1 = ImageTk.PhotoImage(img1)
            image_files = os.listdir(image_folder)
            if image_files:
                latest_image = sorted(image_files)[-1]
                image_path = os.path.join(image_folder, latest_image)

                if image_path != last_image_path:
                    img = Image.open(image_path)
                    img = img.resize((200, 130))
                    img = ImageTk.PhotoImage(img)
                    self.last_image_label.config(image=img)
                    self.last_image_label.image = img
                    last_image_path = image_path
            else:
                # If there are no images, clear the label
                self.last_image_label.config(image=img1)
                self.last_image_label.image = img1
        except Exception as show:
            print("exception in picture in picture:", show)
            logging.error(f"Exception in picture in picture: {str(show)}")

    def car(self):
        self.selected = 'LMV'
        self.car_button.configure(bg="white")
        self.hmvtruck_button.configure(bg="lightblue")
        # self.lmvtruck_button.configure(bg="lightblue")
        # self.bus_button.configure(bg="lightblue")
        self.bike_button.configure(bg="lightblue")

    def truck(self):
        self.selected = 'HMV'
        self.car_button.configure(bg="lightblue")
        self.hmvtruck_button.configure(bg="white")
        # self.lmvtruck_button.configure(bg="lightblue")
        # self.bus_button.configure(bg="lightblue")
        self.bike_button.configure(bg="lightblue")

    def lmvtruck(self):
        self.selected = 'lmv-truck'
        self.car_button.configure(bg="lightblue")
        self.hmvtruck_button.configure(bg="lightblue")
        # self.lmvtruck_button.configure(bg="white")
        # self.bus_button.configure(bg="lightblue")
        self.bike_button.configure(bg="lightblue")

    def bus(self):
        self.selected = 'bus'
        self.car_button.configure(bg="lightblue")
        self.hmvtruck_button.configure(bg="lightblue")
        # self.lmvtruck_button.configure(bg="lightblue")
        # self.bus_button.configure(bg="white")
        self.bike_button.configure(bg="lightblue")

    def bike(self):
        self.selected = 'bike'
        self.car_button.configure(bg="lightblue")
        self.hmvtruck_button.configure(bg="lightblue")
        # self.lmvtruck_button.configure(bg="lightblue")
        # self.bus_button.configure(bg="lightblue")
        self.bike_button.configure(bg="white")

    def vehicle_detection_on(self):
        self.vehicle_detection_is_on = True

    def vehicle_detection_off(self):
        self.vehicle_detection_is_on = False

    def offence(self):
        self.menu_click()
        Offence.create(self.window)

    def helmet_offence(self):
        self.menu_click()
        Helmet_Offence.create(self.window)

    def view_all(self):
        self.menu_click()
        View_All.create(self.window)

    def menu_click(self):
        try:
            self.close_tools()
        except Exception:
            pass
        if self.menu_buttons_shown:
            # If menu buttons are shown, hide them
            self.canvas.delete(self.x)
            self.canvas.delete(self.y)
            self.canvas.delete(self.z)
            self.canvas.delete(self.w)
            self.menu_buttons_shown = False
        else:
            self.x = self.canvas.create_window(95, 255, window=self.offence_button, anchor=tk.CENTER)
            self.y = self.canvas.create_window(95, 415, window=self.settings_button, anchor=tk.CENTER)
            self.z = self.canvas.create_window(95, 335, window=self.helmet_button, anchor=tk.CENTER)
            self.w = self.canvas.create_window(95, 175, window=self.view_button, anchor=tk.CENTER)
            self.menu_buttons_shown = True

    def auto_capture(self):
        if self.auto_capture_active:
            # Stop auto capture thread
            self.auto_capture_active = False
            if ser1.is_open:
                ser1.write(b'SF\r\n')
                ser1.close()
                self.cur_speed = None
                self.cur_distance = None
                self.manual_button.config(state=NORMAL)
                self.settings_button.config(state=tk.NORMAL)
                self.button2.config(text="Start Auto Capture")  # b'H\x80\xf7#<$F\xab\tk\xc1\xb6C\xd4R\xc7'
                self.car()
        else:
            # Start the auto capture thread
            self.auto_capture_active = True
            self.manual_button.config(state=DISABLED)
            self.settings_button.config(state=tk.DISABLED)
            self.button2.config(text="Stop Auto Capture")
            if self.auto_capture_thread is None or not self.auto_capture_thread.is_alive():
                self.auto_capture_thread = threading.Thread(target=self.auto_capture_thread_func)
                # self.auto_capture_thread.daemon = True
                self.auto_capture_thread.start()

    def auto_capture_thread_func(self):
        try:
            if self.auto_capture_active:
                if not ser1.is_open:
                    ser1.open()
                ser1.write('SO\r\n'.encode())
            tolerance = int(self.tolerance) / 100 * int(self.car_speed_limit)
            tolerance = round(tolerance)
            tolerance1 = int(self.tolerance) / 100 * int(self.truck_speed_limit)
            tolerance1 = round(tolerance1)
            '''tolerance2 = int(self.tolerance) / 100 * int(self.lmvtruck_speed_limit)
            tolerance2 = round(tolerance2)'''
            tolerance3 = int(self.tolerance) / 100 * int(self.bike_speed_limit)
            tolerance3 = round(tolerance3)

            while self.auto_capture_active:  # Check if auto capture is active
                try:
                    if self.selected == 'LMV':
                        self.maxspeed = self.car_speed_limit + tolerance  # car speed limit + tolerance is default in auto capture
                        # print("maximum speed allowed is", self.maxspeed, 'kmph for vehicle', self.selected)
                    elif self.selected == 'HMV':
                        self.maxspeed = self.truck_speed_limit + tolerance1
                        # print("maximum speed allowed is", self.maxspeed, 'kmph for vehicle', self.selected)

                    elif self.selected == 'bike':
                        self.maxspeed = self.bike_speed_limit + tolerance3
                        # print("maximum speed allowed is", self.maxspeed, 'kmph for vehicle', self.selected)
                    # Read a line of data from the serial port
                    if ser1.is_open:
                        line = ser1.readline()
                        line = line.decode().strip()
                        # print("line=", line)
                        # Check if the line contains the NUL character
                        if '\x00' in line:
                            line = line.replace('\x00', '')
                        # Split the line into speed and distance values
                        parts = line.split(':')
                        if len(parts) == 2:
                            speed = int(parts[0].strip())
                            distance = float(parts[1].strip())
                            if type(speed) is not str and type(distance) is not str:
                                if type(speed) is not str and speed > self.maxspeed:  # max-speed
                                    frame = self.second_copy_frame
                                    self.snapshot(frame, speed, distance, self.selected)
                                elif type(speed) is not str and speed < -self.maxspeed:
                                    frame = self.second_copy_frame
                                    self.snapshot(frame, speed, distance, self.selected)
                                self.cur_speed = speed
                                self.cur_distance = distance
                            else:
                                self.cur_speed = None
                                self.cur_distance = None
                        else:
                            continue
                except Exception as ex:
                    logging.info(f"Exception in updated auto capture: {str(ex)}")
                    continue
            return
        except TypeError:
            self.auto_capture_active = False
            if ser1.is_open:
                ser1.write(b'SF\r\n')
                ser1.close()
                self.cur_speed = None
                self.cur_distance = None
                self.manual_button.config(state=NORMAL)
                self.settings_button.config(state=tk.NORMAL)
                self.button2.config(text="Auto Capture")
        except Exception as ac:
            print("Exception in auto capture----------------", ac)
            self.auto_capture_active = False
            if ser1.is_open:
                ser1.write(b'SF\r\n')
                ser1.close()
                self.cur_speed = None
                self.cur_distance = None
                self.manual_button.config(state=NORMAL)
                self.settings_button.config(state=tk.NORMAL)
                self.button2.config(text="Auto Capture")

    def open_database_window(self):
        DatabaseWindow.create(self.window)

    def open_helmet_database_window(self):
        HelmetDatabaseWindow.create(self.window)

    def start_camera_thread(self):
        self.camera_thread = threading.Thread(target=self.open_camera_thread)
        self.camera_thread.daemon = True
        self.camera_thread.start()

    def manual_capture(self):
        if self.manual_capture_active:
            # Stop manual capture thread
            self.manual_capture_active = False
            self.cur_speed = None
            self.cur_distance = None
            if ser1.is_open:
                ser1.write(b'SF\r\n')
                ser1.close()
                self.car()
                self.button2.config(state=NORMAL)
                self.settings_button.config(state=tk.NORMAL)
                self.manual_button.config(text="Manual Capture")
        else:
            # Start the manual capture thread
            self.manual_capture_active = True
            self.button2.config(state=DISABLED)
            self.settings_button.config(state=tk.DISABLED)
            self.manual_button.config(text="Stop Manual Capture")
            if self.manual_capture_thread is None or not self.manual_capture_thread.is_alive():
                self.manual_capture_thread = threading.Thread(target=self.manual_capture_thread_func)
                # self.manual_capture_thread.daemon = True
                self.manual_capture_thread.start()

    def manual_capture_thread_func(self):
        try:
            if self.manual_capture_active:
                if not ser1.is_open:
                    ser1.open()
                ser1.write('SO\r\n'.encode())
            tolerance = int(self.tolerance) / 100 * int(self.car_speed_limit)
            tolerance = round(tolerance)
            tolerance1 = int(self.tolerance) / 100 * int(self.truck_speed_limit)
            tolerance1 = round(tolerance1)
            '''tolerance2 = int(self.tolerance) / 100 * int(self.lmvtruck_speed_limit)
            tolerance2 = round(tolerance2)'''
            tolerance3 = int(self.tolerance) / 100 * int(self.bike_speed_limit)
            tolerance3 = round(tolerance3)

            while self.manual_capture_active:  # Check if manual capture is active
                try:
                    if self.selected == 'LMV':
                        self.maxspeed = self.car_speed_limit + tolerance  # car speed limit + tolerance is default in auto capture
                        # print("maximum speed allowed is", self.maxspeed, 'kmph for vehicle', self.selected)
                    elif self.selected == 'HMV':
                        self.maxspeed = self.truck_speed_limit + tolerance1
                        # print("maximum speed allowed is", self.maxspeed, 'kmph for vehicle', self.selected)

                    elif self.selected == 'bike':
                        self.maxspeed = self.bike_speed_limit + tolerance3
                        # print("maximum speed allowed is", self.maxspeed, 'kmph for vehicle', self.selected)
                    # Read a line of data from the serial port
                    line = ser1.readline()
                    line = line.decode().strip()
                    # Check if the line contains the NUL character
                    if '\x00' in line:
                        line = line.replace('\x00', '')
                    # Split the line into speed and distance values
                    parts = line.split(':')
                    if len(parts) == 2:
                        speed = int(parts[0].strip())
                        distance = float(parts[1].strip())
                        # print("speed=", speed, "kmph", "dist=", distance, "m")
                        if type(speed) is not str and type(distance) is not str:
                            if type(speed) is not str and speed > self.maxspeed:  # max-speed
                                ser1.write(b'SF\r\n')
                                # ser1.write('OFF\r\n'.encode())
                                ser1.close()
                                self.cur_speed = None
                                self.cur_distance = None
                                frame = self.second_copy_frame
                                self.snapshot(frame, speed, distance, self.selected)
                                self.manual_capture_active = False
                                self.button2.config(state=NORMAL)
                                self.settings_button.config(state=tk.NORMAL)
                                self.manual_button.config(text="Manual Capture")
                                break
                            elif type(speed) is not str and speed < -self.maxspeed:
                                ser1.write(b'SF\r\n')
                                # ser1.write('OFF\r\n'.encode())
                                ser1.close()
                                self.cur_speed = None
                                self.cur_distance = None
                                frame = self.second_copy_frame
                                self.snapshot(frame, speed, distance, self.selected)
                                self.manual_capture_active = False
                                self.button2.config(state=NORMAL)
                                self.settings_button.config(state=tk.NORMAL)
                                self.manual_button.config(text="Manual Capture")
                                break
                            self.cur_speed = speed
                            self.cur_distance = distance
                        else:
                            self.cur_speed = None
                            self.cur_distance = None
                    else:
                        continue
                except Exception as ee:
                    logging.info(f"Exception in updated manual capture: {str(ee)}")
            if ser1.is_open:
                ser1.write(b'SF\r\n')
                ser1.close()
                self.car()
                self.cur_speed = None
                self.cur_distance = None
                self.button2.config(state=NORMAL)
                self.settings_button.config(state=tk.NORMAL)
                self.manual_button.config(text="Manual Capture")
                return
        except TypeError:
            self.manual_capture_active = False
            self.cur_speed = None
            self.cur_distance = None
            if ser1.is_open:
                ser1.write(b'SF\r\n')
                ser1.close()
                self.car()
                self.button2.config(state=NORMAL)
                self.settings_button.config(state=tk.NORMAL)
                self.manual_button.config(text="Manual Capture")
        except Exception as mc:
            print("Exception caught in manual capture---------------:", mc)
            self.manual_capture_active = False
            self.cur_speed = None
            self.cur_distance = None
            if ser1.is_open:
                ser1.write(b'SF\r\n')
                ser1.close()
                self.car()
                self.button2.config(state=NORMAL)
                self.settings_button.config(state=tk.NORMAL)
                self.manual_button.config(text="Manual Capture")

    def open_camera_thread(self):
        cur_time = datetime.datetime.now()
        milliseconds = cur_time.microsecond // 1000
        cur_time = cur_time.strftime('%y-%m-%d_%H-%M-%S') + f".{milliseconds}"
        logging.info(f"Starting time: {str(cur_time)}")
        # print(self.camera_thread.ident)
        # logging.info(f"open_camera_thread_ID: {str(self.camera_thread.ident)}")
        count = 0
        hel_count = 0
        try:
            while self.cap.isOpened():
                # print("active threads =", threading.active_count() if threading.active_count() > 2 else '')
                ret, frame = self.cap.read()
                if ret:
                    self.second_copy_frame = frame
                    frame = cv2.resize(frame, (1280, 700))  # (640,480)
                    if self.helmet_on:
                        hel_count += 1
                        if hel_count % 8 == 0:
                            self.frame_queue.put(self.second_copy_frame)
                        else:
                            pass
                    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    cv2.rectangle(image, (self.rect_x1, self.rect_y1), (self.rect_x2, self.rect_y2), (0, 255, 0), 2)
                    if self.vehicle_detection_is_on and not self.night_mode_is_on and self.auto_capture_active:
                        crpd_frame = frame[self.rect_y1:self.rect_y2, self.rect_x1:self.rect_x2]
                        # cv2.imwrite("crpd.jpg", crpd_frame)
                        self.process_vehicle_detection_frame(crpd_frame)
                    # cv2.putText(image, self.selected.upper(), (580, 170), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    if self.lati is not None and self.longi is not None:
                        cv2.putText(image, f"LAT:{self.lati}", (950, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                    (0, 255, 255), 2)
                        cv2.putText(image, f"LON:{self.longi}", (1080, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                    (0, 255, 255), 2)
                    if self.cur_speed is not None and self.cur_distance is not None and type(
                            self.cur_speed) is int and type(self.cur_distance) is float:
                        if int(self.cur_speed) > self.maxspeed or int(self.cur_speed) < -self.maxspeed:
                            cv2.putText(image, f"{abs(self.cur_speed)}KPH", (700, 370), cv2.FONT_HERSHEY_SIMPLEX, 1,
                                        (255, 0, 0), 2)
                        else:
                            cv2.putText(image, f"{abs(self.cur_speed)}KPH", (700, 370), cv2.FONT_HERSHEY_SIMPLEX, 1,
                                        (0, 255, 0), 2)
                        cv2.putText(image, f"DISTANCE: {self.cur_distance}M", (725, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                    (0, 255, 255), 2)
                    # center = (512, 275)
                    # radius = min(1024, 550) // 64
                    # cv2.circle(image, center, radius, (255, 0, 0), 1)
                    cv2.putText(image, '+', (620, 370), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 2)
                    # cv2.rectangle(image, (499, 262), (525, 288), (255, 0, 0), 2)
                    cv2.putText(image, f"PLACE: {self.display_location}", (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0, 255, 255), 2)
                    cv2.putText(image, f"OFFICER NAME: {self.officer_name}", (300, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0, 255, 255), 2)
                    cv2.putText(image, f"OFFICER ID: {self.officer_id}", (725, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0, 255, 255), 2)
                    cv2.putText(image, f"DEVICE ID: {self.device_id}", (1025, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0, 255, 255), 2)
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(image, current_time, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                    cv2.putText(image, "MHv1.5", (1225, 665), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
                    '''percentage = self.get_battery_status()
                    cv2.putText(image, f"{percentage}", (1215, 680), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 9)'''
                    img = ImageTk.PhotoImage(Image.fromarray(image))
                    self.canvas.create_image(0, 0, anchor=tk.NW, image=img)
                    self.canvas.image = img
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                    self.written_duplicate_frame = image
                    # self.frames.append(image)

                    # Maintain the buffer size
                    # if len(self.frames) > self.buffer_size:
                    # self.frames.pop(0)
                else:
                    count += 1
                    hel_count = 0
                    cur_time = datetime.datetime.now()
                    milliseconds = cur_time.microsecond // 1000
                    cur_time = cur_time.strftime('%y-%m-%d_%H-%M-%S') + f".{milliseconds}"
                    logging.info(f"Suspended: {str(cur_time)} for {str(count)} time(s)")
                    self.cap.release()
                    # pipeline = 'v4l2src device=/dev/video0 ! video/x-raw,width=1920,height=1080,framerate=30/1 ! videoconvert ! video/x-raw,format=BGR ! appsink sync=0 drop=1'
                    self.cap = cv2.VideoCapture('/dev/video0')
        except Exception as cam_exception:
            logging.info(f"Exception in open_camera_thread: {str(cam_exception)}")

    # Function to increase the size of the green box
    def increase_box_size(self):
        self.box_size += 10
        self.rect_x1 = 640 - self.box_size
        self.rect_y1 = 360 - self.box_size
        self.rect_x2 = 640 + self.box_size
        self.rect_y2 = 360 + self.box_size

    # Function to decrease the size of the green box
    def decrease_box_size(self):
        if self.box_size > 100:
            self.box_size -= 10
            self.rect_x1 = 640 - self.box_size
            self.rect_y1 = 360 - self.box_size
            self.rect_x2 = 640 + self.box_size
            self.rect_y2 = 360 + self.box_size

    def vehicle_detection_detectx(self, frame, model):
        frame = [frame]
        results = model(frame)
        labels, coordinates = results.xyxyn[0][:, -1], results.xyxyn[0][:, :-1]
        return labels, coordinates

    def vehicle_detection_plot_boxes(self, results, frame, classes):
        try:
            labels, cord = results
            n = len(labels)
            # x_shape, y_shape = frame.shape[1], frame.shape[0]

            for i in range(n):
                row = cord[i]
                if row[4] >= 0.7:
                    # _, _, _, _ = int(row[0] * x_shape), int(row[1] * y_shape), int(row[2] * x_shape), int(row[3] *
                    # y_shape)
                    text_d = classes[int(labels[i])]

                    if text_d == 'car':
                        self.car()
                        return

                    elif text_d == 'bike':
                        self.bike()
                        return

                    elif text_d == 'hmt':
                        self.truck()
                        return

                    elif text_d == 'three-wheeler':
                        # self.lmvtruck()
                        self.car()
                        return

        except Exception as ex:
            print("vehicle plot box func", ex)

    def process_vehicle_detection_frame(self, frame):
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.vehicle_detection_detectx(frame, model=self.vehicle_model)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        labels, coordinates = results
        if len(labels) > 0:
            self.vehicle_detection_plot_boxes(results, frame, classes=self.vehicle_classes)

    def capture_snapshot(self, image_id):
        three_second_thread = threading.Thread(target=self.capture_snapshot_func, args=(image_id,))
        three_second_thread.start()

    def capture_snapshot_func(self, image_id):
        '''if not self.video_rec_active:
            try:
                with self.three_second_lock:
                    if self.frames:
                        snapshot_frames = self.frames[-self.buffer_size:]  # Get the last 3 seconds of frames
                        three_second_video_filename = os.path.join(self.three_second_folder, f"{image_id}.avi")
                        snapshot_writer = cv2.VideoWriter(three_second_video_filename, cv2.VideoWriter_fourcc(*'XVID'),
                                                          30,
                                                          (1280, 700))
                        for frame in snapshot_frames:
                            snapshot_writer.write(frame)
                        snapshot_writer.release()
            except Exception as three_sec:
                print("3sec error:", three_sec)
        else:
            pass'''

    def helmet_thread(self):
        if self.helmet_on:
            self.helmet_on = False
            self.helmetbtn.configure(bg="lightblue")
            # self.process_thread.join()
        else:
            self.helmet_on = True
            self.helmetbtn.configure(bg="red")
            if self.process_thread is None or not self.process_thread.is_alive():
                self.process_thread = threading.Thread(target=self.process_frame)
                self.process_thread.daemon = True
                self.process_thread.start()

    def detectx(self, frame, model):
        frame = [frame]
        results = model(frame)
        labels, coordinates = results.xyxyn[0][:, -1], results.xyxyn[0][:, :-1]
        return labels, coordinates

    def plot_boxes(self, results, frame, classes):
        try:
            global helmet_path
            num = ''
            cur_date = datetime.date.today()
            cur_time = datetime.datetime.now()
            milliseconds = cur_time.microsecond // 1000
            image_id = str(self.device_id) + cur_time.strftime('%Y%m%d%H%M%S') + f"{milliseconds}" + 'h'
            cur_time = cur_time.strftime('%Y-%m-%d_%H-%M-%S') + f".{milliseconds}"
            # Connect to the database
            conn = sqlite3.connect("msiplusersettingsmh.db")
            cursor = conn.cursor()

            # Find officer_name in locations table
            cursor.execute("SELECT * FROM locations ORDER BY rowid DESC LIMIT 1")
            location_row = cursor.fetchone()
            lat = '' if self.lati is None else str(self.lati)
            lon = '' if self.longi is None else str(self.longi)

            labels, cord = results
            n = len(labels)
            x_shape, y_shape = frame.shape[1], frame.shape[0]

            for i in range(n):
                row = cord[i]
                if row[4] >= 0.8:
                    # x1, y1, x2, y2 = int(row[0] * x_shape), int(row[1] * y_shape), int(row[2] * x_shape), int(
                    #    row[3] * y_shape)
                    text_d = classes[int(labels[i])]

                    '''if text_d == 'with helmet':
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.rectangle(frame, (x1, y1 - 20), (x2, y1), (0, 255, 0), -1)
                        cv2.putText(frame, text_d, (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                    (255, 255, 255), 1)'''

                    if text_d == 'without helmet':
                        # Encode the frame in JPEG format
                        _, buffer = cv2.imencode('.jpg', frame)
                        # Convert the buffer to bytes
                        io_buf = io.BytesIO(buffer)
                        files = {'upload': ('frame.jpg', io_buf, 'image/jpeg')}
                        response = requests.post('http://localhost:8080/v1/plate-reader/', files=files, headers={'Authorization': 'Token 3d61f4570b13a5bd50dd7086c01a4dea0a735492'})
                        response_data = response.json()
                        if 'results' in response_data and len(response_data['results']) > 0:
                            # Extract number plate text and coordinates
                            results = response_data['results'][0]
                            num = results['plate']
                            if len(num) > 6:
                                '''cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                                        cv2.rectangle(frame, (x1, y1 - 20), (x2, y1), (0, 0, 255), -1)
                                                        cv2.putText(frame, text_d, (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                                                    (255, 255, 255), 1)'''

                                # Insert the record into the table
                                cursor.execute(
                                    "INSERT INTO helmetoffencerecords (image_id, time, hel_date, location, officername, officer_id, "
                                    "numberplate, laser_id, uploaded, lat, lon, offence_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                    (
                                        image_id, cur_time, cur_date, location_row[0], location_row[1], location_row[2],
                                        '',
                                        location_row[11], 'n', lat, lon, ''))
                                conn.commit()
                                cv2.imwrite(os.path.join(helmet_path, f"{str(image_id)}.jpg"), frame)
                                try:
                                    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                    img = Image.fromarray(img)
                                    img = img.resize((200, 130))
                                    # Create a drawing context
                                    draw = ImageDraw.Draw(img)

                                    # Define the font and text position
                                    font = ImageFont.load_default()
                                    text = "NO HELMET"
                                    text_position = (75, 60)  # Adjust the position as needed

                                    # Draw the text on the image
                                    draw.text(text_position, text, font=font, fill="white")
                                    img = ImageTk.PhotoImage(img)
                                    self.last_image_label.config(image=img)
                                    self.last_image_label.image = img
                                except Exception:
                                    pass
                            else:
                                pass
                        else:
                            pass
            conn.close()
        except Exception as ex:
            logging.error(f"{str(ex)}")

    def process_frame(self):
        while True:
            frame = self.frame_queue.get()
            if frame is None:
                continue
            if self.stop_event.is_set():
                break
            # st = time.time()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.detectx(frame, model=self.model)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            labels, coordinates = results
            # et = time.time()
            # print(et - st)
            if len(labels) > 0:
                self.plot_boxes(results, frame, classes=self.classes)
        # self.process_thread.join()
        return

    # <----------------video recording function------------------------------------------->

    def start_video_record(self):
        if self.video_rec_active:
            # Stop the record thread
            # self.out.release()
            self.video_rec_active = False
            self.video_record_btn.config(image=self.video_record_photo)
        else:
            # Start the record thread
            self.video_rec_active = True
            self.video_record_btn.config(image=self.video_record_stop_photo)
            if self.video_rec_thread is None or not self.video_rec_thread.is_alive():
                self.video_rec_thread = threading.Thread(target=self.start_video_record_func)
                self.video_rec_thread.start()

    def start_video_record_func(self):
        try:
            cur_time = datetime.datetime.now().strftime("%H-%M-%S")
            username = getpass.getuser()
            output_video_path = os.path.join(f"/media/{username}/Elements/Offence_Videos", get_current_date_folder())
            if not os.path.exists(output_video_path):
                os.makedirs(output_video_path, exist_ok=True)
            output_video_file_name = f"{cur_time}.avi"
            vid_path = os.path.join(output_video_path, output_video_file_name)
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.out = cv2.VideoWriter(vid_path, fourcc, 30, (1280, 700))

            while self.video_rec_active:
                self.out.write(self.written_duplicate_frame)
                time.sleep(0.01)
        except Exception as vid:
            print(vid)
            logging.error(f"Exception in start_video_record_func: {str(vid)}")

    # <---------------GPS data checking function------------------------------------------->

    def read_gps_data(self):
        self.gps_thread = threading.Thread(target=self.read_gps_data_func)
        self.gps_thread.daemon = True
        self.gps_thread.start()

    def read_gps_data_func(self):
        if self.lati is None:
            try:
                with serial.Serial(gps_port, 9600, timeout=1) as ser2:
                    try:
                        while ser2.is_open:
                            data = ser2.read_all().decode('utf-8')
                            # print("data=", data)
                            str_arr = data.split("$")
                            if len(str_arr) > 1:
                                try:
                                    for str_temp in str_arr:
                                        line_arr = str_temp.split(",")
                                        # print(line_arr)

                                        if line_arr[0] == "GPGGA":
                                            try:
                                                # Latitude
                                                d_lat = float(line_arr[2])
                                                d_lat /= 100
                                                lat = str(d_lat).split(".")

                                                # Longitude
                                                d_lon = float(line_arr[4])
                                                d_lon /= 100
                                                lon = str(d_lon).split(".")
                                                ser2.close()
                                                latitude = lat[0] + "." + "{:.0f}".format(float(lat[1]) / 60)
                                                self.lati = "{:.5f}".format(float(latitude))
                                                longitude = lon[0] + "." + "{:.0f}".format(float(lon[1]) / 60)
                                                self.longi = "{:.5f}".format(float(longitude))
                                                logging.info(f"GPS Data: Lat-{str(self.lati)}, Lon-{str(self.longi)}")
                                                '''# print("lat", self.lati)
                                                longitude = lon[0] + "." + "{:.0f}".format(float(lon[1]) / 60)
                                                self.longi = "{:.5f}".format(float(longitude))
                                                logging.info(f"GPS Data: Lat-{str(self.lati)}, Lon-{str(self.longi)}")
                                                # print("lon", self.longi)
                                                messagebox.showinfo("Speed Hunter III Plus",
                                                                    f"{line_arr[3] + self.lati}, {line_arr[5] + self.longi}")
                                                # Create a map centered at a specific location
                                                map_center = (self.lati, self.longi)  # Replace with the desired coordinates
                                                m = folium.Map(location=map_center, zoom_start=17)

                                                # Add a marker at a specific location
                                                marker_location = (self.lati, self.longi)  # Replace with marker coordinates
                                                folium.Marker(location=marker_location, popup="Marker Popup Text").add_to(m)

                                                # Save the map as an HTML file
                                                file_path = os.path.join(f"/media/{getpass.getuser()}/Elements/number_plate_images", str(datetime.date.today()))
                                                file_path = os.path.join(file_path, "maps")
                                                if not os.path.exists(file_path):
                                                    os.makedirs(file_path)
                                                m.save(f"{file_path}/my_map.html")
                                                # Set up the WebDriver
                                                chrome_options = webdriver.FirefoxOptions()
                                                chrome_options.add_argument(
                                                    '--headless')  # Run Chrome in headless mode (no UI)
                                                usn = getpass.getuser()
                                                driver = webdriver.Firefox(service=Service(
                                                    executable_path=f'/home/{usn}/.wdm/drivers/geckodriver/linux64/v0.32.0/geckodriver'),
                                                    options=chrome_options)
                                                driver.get(f"file://{os.path.abspath(f'{file_path}/my_map.html')}")
                                                time.sleep(0.5)
                                                driver.save_screenshot(f"{file_path}/map_screenshot.png")
                                                driver.quit()'''
                                                break

                                            except Exception:
                                                ser2.close()
                                                self.t.start()
                                except Exception:
                                    pass
                    except Exception:
                        ser2.close()
                        messagebox.showerror("Error", "Data unavailable from GPS or can't read data from GPS")
                        logging.error(f"GPS Data: unavailable")
            except serial.SerialException:
                messagebox.showerror("Error", f"Port {gps_port} for GPS is not open")
                logging.error(f"GPS Data: Port {gps_port} for GPS is not open")
        else:
            return

    def location(self):
        self.menu_click()
        self.settings_button.config(state=tk.DISABLED)
        self.helmet_button.config(state=tk.DISABLED)
        self.offence_button.config(state=tk.DISABLED)
        self.manual_button.config(state=tk.DISABLED)
        self.button2.config(state=tk.DISABLED)
        # Register the validation function
        vcmd = (root.register(validate_input), '%P')
        bigfont = font.Font(family="Arial", size=14)
        root.option_add("*Font", bigfont)
        self.new_window = tk.Toplevel(self.window)
        self.new_window.attributes('-topmost', True)
        self.new_window.resizable(False, False)
        self.new_window.overrideredirect(True)
        self.new_window.title("Settings")
        self.new_window.geometry(f"{700}x{450}+300+50")
        self.location_frame = tk.LabelFrame(self.new_window, bg="orange")

        #  check db exists
        if os.path.exists('msiplusersettingsmh.db'):
            conn = sqlite3.connect('msiplusersettingsmh.db')
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT location FROM dummylocations;")
            rowz1 = cursor.fetchall()
            rowz1 = [list(item)[0] for item in rowz1]
            conn.close()
        else:
            rowz1 = []
        self.location_listbox = ttk.Combobox(self.location_frame, values=rowz1, state='readonly', width=35,
                                             font=("Arial", 15))
        self.location_listbox.bind("<<ComboboxSelected>>", self.handle_combobox_selection)
        self.location_listbox.set("Select Location")
        self.location_listbox.grid(row=0, pady=10, padx=10)

        #  check db exists
        if os.path.exists('msiplusersettingsmh.db'):
            conn = sqlite3.connect('msiplusersettingsmh.db')
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT officer_name FROM officerdetails;")
            rowz = cursor.fetchall()
            rowz = [list(item)[0] for item in rowz]
            conn.close()
        else:
            rowz = []
        self.previous_officers_listbox = ttk.Combobox(self.location_frame, values=rowz, state='readonly',
                                                      font=("Arial", 15))
        self.previous_officers_listbox.bind("<<ComboboxSelected>>", self.handle_officers_combobox_selection)
        self.previous_officers_listbox.set('Previous Officers')
        self.previous_officers_listbox.grid(row=0, column=1, padx=10)

        # Create "Officer Name" label and Entry box
        officer_label = tk.Label(self.location_frame, text="Officer Name:", font=("Arial", 12), bg="orange")
        officer_label.grid(row=1, column=0, padx=10, pady=10)

        self.setting_officer_entry = tk.Entry(self.location_frame, font=("Arial", 12))
        self.setting_officer_entry.grid(row=1, column=1, padx=10, pady=10)
        self.setting_officer_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        # Create "Officer ID" label and Entry box
        officer_id_label = tk.Label(self.location_frame, text="Officer ID:", font=("Arial", 12), bg="orange")
        officer_id_label.grid(row=2, column=0, padx=10, pady=10)

        self.setting_officer_id_entry = tk.Entry(self.location_frame, font=("Arial", 12))
        self.setting_officer_id_entry.grid(row=2, column=1, padx=10, pady=10)
        self.setting_officer_id_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        #  create "vehicle speed frame"
        vehicle_frame = tk.LabelFrame(self.location_frame, bg="orange")
        vehicle_frame.grid(row=3, columnspan=2, padx=10, pady=10)

        speed_label = tk.Label(vehicle_frame, text="Speed Range", font=("Arial", 12), bg="orange")
        speed_label.grid(row=0, column=1, sticky="w")

        cap_label = tk.Label(vehicle_frame, text="Capture Range", font=("Arial", 12), bg="orange")
        cap_label.grid(row=0, column=4, sticky="w")

        car_label = tk.Label(vehicle_frame, text="White Board LMV:", font=("Arial", 12), bg="orange")
        car_label.grid(row=1, column=0, sticky="w", padx=10)

        self.setting_car_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.setting_car_entry.grid(row=1, column=1, padx=10, pady=10)
        self.setting_car_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        carkmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        carkmph_label.grid(row=1, column=2, sticky="w", padx=10)

        ycar_label = tk.Label(vehicle_frame, text="Yellow Board LMV:", font=("Arial", 12), bg="orange")
        ycar_label.grid(row=2, column=0, sticky="w", padx=10)

        self.setting_ycar_entry = tk.Entry(vehicle_frame,validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.setting_ycar_entry.grid(row=2, column=1, padx=10, pady=10)
        self.setting_ycar_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        ycarkmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        ycarkmph_label.grid(row=2, column=2, sticky="w", padx=10)

        truck_label = tk.Label(vehicle_frame, text="HMV:", font=("Arial", 12), bg="orange")
        truck_label.grid(row=3, column=0, sticky="w", padx=10)

        self.setting_truck_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.setting_truck_entry.grid(row=3, column=1, padx=10, pady=10)
        self.setting_truck_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        truckkmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        truckkmph_label.grid(row=3, column=2, sticky="w", padx=10)

        '''lmvtruck_label = tk.Label(vehicle_frame, text="LMV-Truck:", font=("Arial", 12), bg="orange")
        lmvtruck_label.grid(row=4, column=0, sticky="w", padx=10)

        self.setting_lmvtruck_entry = tk.Entry(vehicle_frame, font=("Arial", 12), width=5)
        self.setting_lmvtruck_entry.grid(row=4, column=1, padx=10, pady=10)
        self.setting_lmvtruck_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        lmvtruckkmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        lmvtruckkmph_label.grid(row=4, column=2, sticky="w", padx=10)'''

        bike_label = tk.Label(vehicle_frame, text="Bike:", font=("Arial", 12), bg="orange")
        bike_label.grid(row=4, column=0, sticky="w", padx=10)

        self.setting_bike_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.setting_bike_entry.grid(row=4, column=1, padx=10, pady=10)
        self.setting_bike_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        bikekmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        bikekmph_label.grid(row=4, column=2, sticky="w", padx=10)

        min_label = tk.Label(vehicle_frame, text="Min:", font=("Arial", 12), bg="orange")
        min_label.grid(row=1, column=3, sticky="w", padx=10)

        self.setting_min_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.setting_min_entry.grid(row=1, column=4, padx=10, pady=10, sticky="w")
        self.setting_min_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        mindist_label = tk.Label(vehicle_frame, text="Mtrs", font=("Arial", 12), bg="orange")
        mindist_label.grid(row=1, column=5, sticky="w", padx=10)

        max_label = tk.Label(vehicle_frame, text="Max:", font=("Arial", 12), bg="orange")
        max_label.grid(row=2, column=3, sticky="w", padx=10)

        self.setting_max_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.setting_max_entry.grid(row=2, column=4, padx=10, pady=10, sticky="w")
        self.setting_max_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        maxdist_label = tk.Label(vehicle_frame, text="Mtrs", font=("Arial", 12), bg="orange")
        maxdist_label.grid(row=2, column=5, sticky="w", padx=10)

        tolerance_label = tk.Label(vehicle_frame, text="Tolerance:", font=("Arial", 12), bg="orange")
        tolerance_label.grid(row=3, column=3, sticky="w", padx=10)

        self.setting_tolerance_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.setting_tolerance_entry.grid(row=3, column=4, padx=10, pady=10, sticky="w")
        self.setting_tolerance_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        maxtolerance_label = tk.Label(vehicle_frame, text="%", font=("Arial", 12), bg="orange")
        maxtolerance_label.grid(row=3, column=5, sticky="w", padx=10)

        #  create new location btn
        newloc_img = Image.open('resources/img/location.png')
        newloc_img = newloc_img.resize((140, 40), Image.LANCZOS)
        newloc_photo = ImageTk.PhotoImage(newloc_img)
        self.newloc_photo = newloc_photo
        newloc_img.close()

        new_location_button = tk.Button(self.location_frame, command=self.open_new_location, bg="orange")
        new_location_button.configure(image=newloc_photo, borderwidth=0)
        new_location_button.grid(row=4, columnspan=2)

        startt_img = Image.open('resources/start.png')
        startt_img = startt_img.resize((140, 40), Image.LANCZOS)
        startt_photo = ImageTk.PhotoImage(startt_img)
        self.startt_photo = startt_photo
        startt_img.close()

        cancel_img = Image.open('resources/img/cancel.png')
        cancel_img = cancel_img.resize((140, 40), Image.LANCZOS)
        cancel_photo = ImageTk.PhotoImage(cancel_img)
        self.cancel_photo = cancel_photo
        cancel_img.close()

        cancel_button = tk.Button(self.location_frame, bg="orange", command=self.new_window_cancel)
        cancel_button.configure(image=cancel_photo, borderwidth=0)
        cancel_button.grid(row=4, column=0, sticky='w', padx=55)

        # create start button
        self.start_button = tk.Button(self.location_frame, command=self.save_data_db,
                                      state=DISABLED, bg="orange")
        self.start_button.configure(image=self.startt_photo, borderwidth=0)
        self.start_button.grid(row=4, column=1)

        self.location_frame.pack(pady=10)

    def new_window_cancel(self):
        self.new_window.destroy()
        self.settings_button.config(state=tk.NORMAL)
        self.helmet_button.config(state=tk.NORMAL)
        self.offence_button.config(state=tk.NORMAL)
        self.view_button.config(state=tk.NORMAL)
        self.manual_button.config(state=tk.NORMAL)
        self.button2.config(state=tk.NORMAL)

    # <-----------When a location is selected from the list, if we make any changes this function works-------->
    def save_data_db(self):
        try:
            if not ser1.is_open:
                ser1.open()
                ser1.write('SF\r\n'.encode())
                time.sleep(0.1)
            ser1.write('SF\r\n'.encode())
            time.sleep(0.1)
            ser1.write('SN\r\n'.encode())
            time.sleep(0.1)
            laser_id = ser1.readline().decode().strip()
            if '\x00' in laser_id:
                laser_id = laser_id.replace('\x00', '').strip()
            laser_id = laser_id.split('SN: ')
            if len(laser_id[1]) < 3:
                ser1.write('SN\r\n'.encode())
                time.sleep(0.1)
                laser_id = ser1.readline().decode().strip()
                if '\x00' in laser_id:
                    laser_id = laser_id.replace('\x00', '').strip()
                laser_id = laser_id.split('SN: ')
            # print("Laser ID=", laser_id[1])
            date = datetime.date.today()
            if os.path.exists('msiplusersettingsmh.db'):
                if self.location_listbox.get():
                    conn = sqlite3.connect('msiplusersettingsmh.db')
                    cursor = conn.cursor()
                    cursor.execute("""
                                    DELETE FROM dummylocations
                                    WHERE location = ?;
                    """, (self.location_listbox.get(), ))
                    cursor.execute("INSERT INTO dummylocations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (self.location_listbox.get(), self.setting_officer_entry.get(),
                                    self.setting_officer_id_entry.get(), int(self.setting_car_entry.get()),
                                    int(self.setting_truck_entry.get()), 0,
                                    int(self.setting_ycar_entry.get()), int(self.setting_bike_entry.get()),
                                    int(self.setting_tolerance_entry.get()), int(self.setting_min_entry.get()),
                                    int(self.setting_max_entry.get()), str(laser_id[1]), date))
                    conn.commit()
                    # cursor.execute("DELETE FROM locations WHERE location=?", (self.location_listbox.get(),))
                    cursor.execute("INSERT INTO locations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (self.location_listbox.get(), self.setting_officer_entry.get(),
                                    self.setting_officer_id_entry.get(), int(self.setting_car_entry.get()),
                                    int(self.setting_truck_entry.get()), 0,
                                    int(self.setting_ycar_entry.get()), int(self.setting_bike_entry.get()),
                                    int(self.setting_tolerance_entry.get()), int(self.setting_min_entry.get()),
                                    int(self.setting_max_entry.get()), str(laser_id[1]), date))
                    conn.commit()
                    cursor.execute("SELECT * FROM locations ORDER BY rowid DESC LIMIT 1")
                    rowiz = cursor.fetchone()
                    conn.close()
                    low = int(self.setting_min_entry.get())
                    if low < 3:
                        low = 3
                    if ser1.is_open:
                        ser1.write(f'DL{low}\r\n'.encode())
                        time.sleep(0.1)
                        ser1.readline().decode()
                    high = int(self.setting_max_entry.get())
                    if ser1.is_open:
                        ser1.write(f'DH{high}\r\n'.encode())
                        time.sleep(0.1)
                        ser1.readline().decode()
                    lv = int(self.setting_car_entry.get())
                    if ser1.is_open:
                        ser1.write(f'LV{lv}\r\n'.encode())
                        time.sleep(0.1)
                        ser1.readline().decode()
                    if ser1.is_open:
                        ser1.close()
                    self.cancel()
                    try:
                        subprocess.Popen(['pkill', 'onboard'])
                    except Exception:
                        pass

                    self.settings_button.config(state=NORMAL)  # Settings button is disabled
                    self.display_location = rowiz[0]
                    self.officer_name = rowiz[1]
                    self.officer_id = rowiz[2]
                    self.device_id = rowiz[11]
                    self.bike_speed_limit = rowiz[7]
                    self.truck_speed_limit = rowiz[4]
                    # self.lmvtruck_speed_limit = rowiz[5]
                    self.ycar_speed_limit = rowiz[6]
                    if self.night_mode_is_on:
                        self.car_speed_limit = max(rowiz[3], rowiz[6])
                    else:
                        self.car_speed_limit = min(rowiz[3], rowiz[6])
                    self.w_car_speed = rowiz[3]
                    self.y_car_speed = rowiz[6]
                    self.tolerance = rowiz[8]
                    self.car()
                    self.add_buttons()
                    self.button2.config(state=NORMAL)
                    self.manual_button.config(state=NORMAL)
                    self.snapshot_btn.config(state=NORMAL)
                    self.helmet_database_btn.config(state=NORMAL)
                    self.video_record_btn.config(state=NORMAL)
                    self.database_btn.config(state=NORMAL)
                    self.button1.config(state=NORMAL)
                    self.button1.config(state=NORMAL)
                    self.helmetbtn.config(state=NORMAL)
                    self.settings_button.config(state=tk.NORMAL)
                    self.offence_button.config(state=NORMAL)
                    self.view_button.config(state=tk.NORMAL)
                    self.helmet_button.config(state=NORMAL)
                    self.manual_button.config(state=tk.NORMAL)
                    self.button2.config(state=tk.NORMAL)
                    self.read_gps_data()
                    cam = serial.Serial(cam_port, 9600)
                    hex_command = '81010447030D0608FF'  # '81010447020D0008FF'->12x  # ZOOM COMMAND now 16x
                    command = binascii.unhexlify(hex_command)
                    cam.write(command)
                    cam.close()
                    messagebox.showinfo("Ready to capture offenders!",
                                        f"Location: {rowiz[0]}\nLower limit: {low}mtrs\nUpper limit: {high}mtrs\nSpeed Zone: {min(rowiz[3], rowiz[6])}kmph")

                else:
                    messagebox.showerror("Speed Hunter III Plus", "No locations found in database!")
                    self.cancel()
            else:
                self.handle_combobox_selection(None)
                self.handle_officers_combobox_selection(None)
        except Exception as e:
            self.new_window.destroy()
            logging.error(f"Exception in save_data_db: {str(e)}")
            logging.info("################################################################################")
            self.settings_button.config(state=NORMAL)
            self.exit_app()

    # <-----------------To show available previous officer names------------------------------------------------------->
    def handle_officers_combobox_selection(self, event):
        if self.previous_officers_listbox.get():
            conn = sqlite3.connect('msiplusersettingsmh.db')
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT officer_id FROM officerdetails WHERE officer_name=?;",
                           (self.previous_officers_listbox.get(),))
            row1 = cursor.fetchone()
            conn.close()
            # Update entry fields
            self.setting_officer_entry.delete(0, tk.END)
            self.setting_officer_entry.insert(tk.END, self.previous_officers_listbox.get())
            self.setting_officer_id_entry.delete(0, tk.END)
            self.setting_officer_id_entry.insert(tk.END, row1)
            self.previous_officers_listbox.set('Select Officers')
        else:
            print("Previous officers not found")

    # <------------------To show list of available locations in combobox------------------------->
    def handle_combobox_selection(self, event):
        selected_location = self.location_listbox.get()
        if selected_location:
            conn = sqlite3.connect('msiplusersettingsmh.db')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dummylocations WHERE location=?", (selected_location,))
            row1 = cursor.fetchone()
            conn.close()

            # Update entry fields
            self.setting_officer_entry.delete(0, tk.END)
            self.setting_officer_entry.insert(tk.END, row1[1])

            self.setting_officer_id_entry.delete(0, tk.END)
            self.setting_officer_id_entry.insert(tk.END, row1[2])

            self.setting_car_entry.delete(0, tk.END)
            self.setting_car_entry.insert(tk.END, row1[3])

            self.setting_truck_entry.delete(0, tk.END)
            self.setting_truck_entry.insert(tk.END, row1[4])

            '''self.setting_lmvtruck_entry.delete(0, tk.END)
            self.setting_lmvtruck_entry.insert(tk.END, row1[5])'''

            self.setting_ycar_entry.delete(0, tk.END)
            self.setting_ycar_entry.insert(tk.END, row1[6])

            self.setting_bike_entry.delete(0, tk.END)
            self.setting_bike_entry.insert(tk.END, row1[7])

            self.setting_tolerance_entry.delete(0, tk.END)
            self.setting_tolerance_entry.insert(tk.END, row1[8])

            self.setting_min_entry.delete(0, tk.END)
            self.setting_min_entry.insert(tk.END, row1[9])

            self.setting_max_entry.delete(0, tk.END)
            self.setting_max_entry.insert(tk.END, row1[10])

            self.previous_officers_listbox.set('Previous Officers')

            self.start_button.config(state=NORMAL, bg="orange", borderwidth=0)
        else:
            print("location not found in database.")

    # <---------------Add new location button is pressed---------------------------------------->
    def open_new_location(self):
        # Register the validation function
        vcmd = (root.register(validate_input), '%P')
        self.location_frame.pack_forget()  # Hide the previous frame

        save_img = Image.open('resources/img/submit.png')
        save_img = save_img.resize((140, 40), Image.LANCZOS)
        save_photo = ImageTk.PhotoImage(save_img)
        self.save_photo = save_photo

        cancel_img = Image.open('resources/img/cancel.png')
        cancel_img = cancel_img.resize((140, 40), Image.LANCZOS)
        cancel_photo = ImageTk.PhotoImage(cancel_img)
        self.cancel_photo = cancel_photo

        # Create frame for new location input
        self.new_location_frame = tk.LabelFrame(self.new_window, bg="orange")

        # Create "Location" label and Entry box
        location_label = tk.Label(self.new_location_frame, text="New Location:", font=("Arial", 12), bg="orange",
                                  anchor="w", justify="right")
        location_label.grid(row=0, column=0, sticky=W, padx=10, pady=5)

        self.location_entry = tk.Entry(self.new_location_frame, width=45, font=("Arial", 12), justify="left")
        self.location_entry.grid(row=0, column=1, sticky=W, pady=2)
        self.location_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())
        #  check db exists
        if os.path.exists('msiplusersettingsmh.db'):
            conn = sqlite3.connect('msiplusersettingsmh.db')
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT officer_name FROM officerdetails;")
            self.rowz = cursor.fetchall()
            self.rowz = [list(item)[0] for item in self.rowz]
            conn.close()
        else:
            self.rowz = []

        # Create "Officer Name" label and Combobox
        officer_label = tk.Label(self.new_location_frame, text="Officer Name:", font=("Arial", 12), bg="orange",
                                 anchor="w", justify="right")
        officer_label.grid(row=1, column=0, sticky=W, padx=10, pady=5)

        self.officer_combobox = ttk.Combobox(self.new_location_frame, width=19, values=self.rowz, state='readonly',
                                             font=("Arial", 12), justify="left")
        self.officer_combobox.grid(row=1, column=1, sticky=W, pady=5, padx=5)
        self.officer_combobox.bind("<<ComboboxSelected>>", self.new_location_handle_officers_combobox_selection)

        add_officer_button = tk.Button(self.new_location_frame, bg="grey", text="Add New Officer", font=("Arial", 12),
                                       command=self.add_officer_details)
        add_officer_button.grid(row=1, columnspan=3, sticky=E, padx=5, pady=5)

        # Create "Officer ID" label and Entry box
        officer_id_label = tk.Label(self.new_location_frame, text="Officer ID:", font=("Arial", 12), bg="orange",
                                    anchor="w", justify="right")
        officer_id_label.grid(row=2, column=0, sticky=W, padx=10, pady=2)

        self.officer_id_entry = tk.Entry(self.new_location_frame, width=20, font=("Arial", 12), justify="left")
        self.officer_id_entry.grid(row=2, column=1, sticky=W, pady=5, padx=5)
        self.officer_id_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        #  create "vehicle speed frame"
        vehicle_frame = tk.LabelFrame(self.new_location_frame, bg="orange")
        vehicle_frame.grid(row=3, columnspan=2, padx=10, pady=20)

        speed_label = tk.Label(vehicle_frame, text="Speed Range", font=("Arial", 12), bg="orange")
        speed_label.grid(row=0, column=1)

        cap_label = tk.Label(vehicle_frame, text="Capture Range", font=("Arial", 12), bg="orange")
        cap_label.grid(row=0, column=4)

        car_label = tk.Label(vehicle_frame, text="White Board LMV:", font=("Arial", 12), bg="orange")
        car_label.grid(row=1, column=0, padx=10, pady=2, sticky="w")

        self.car_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.car_entry.grid(row=1, column=1, pady=2)
        self.car_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        carkmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        carkmph_label.grid(row=1, column=2, sticky="w", pady=2)

        ycar_label = tk.Label(vehicle_frame, text="Yellow Board LMV:", font=("Arial", 12), bg="orange")
        ycar_label.grid(row=2, column=0, sticky="w", padx=10, pady=2)

        self.ycar_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.ycar_entry.grid(row=2, column=1, pady=2)
        self.ycar_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        ycarkmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        ycarkmph_label.grid(row=2, column=2, sticky="w", pady=10)

        truck_label = tk.Label(vehicle_frame, text="HMV:", font=("Arial", 12), bg="orange")
        truck_label.grid(row=3, column=0, sticky="w", padx=10, pady=2)

        self.truck_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.truck_entry.grid(row=3, column=1, pady=2)
        self.truck_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        truckkmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        truckkmph_label.grid(row=3, column=2, sticky="w", pady=2)

        '''lmvtruck_label = tk.Label(vehicle_frame, text="LMV-Truck:", font=("Arial", 12), bg="orange")
        lmvtruck_label.grid(row=4, column=0, sticky="w", padx=10, pady=10)

        self.lmvtruck_entry = tk.Entry(vehicle_frame, font=("Arial", 12), width=5)
        self.lmvtruck_entry.grid(row=4, column=1, pady=2)
        self.lmvtruck_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        lmvtruckkmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        lmvtruckkmph_label.grid(row=4, column=2, sticky="w", pady=2)'''

        bike_label = tk.Label(vehicle_frame, text="Bike:", font=("Arial", 12), bg="orange")
        bike_label.grid(row=4, column=0, sticky="w", padx=10, pady=2)

        self.bike_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.bike_entry.grid(row=4, column=1, pady=10)
        self.bike_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        bikekmph_label = tk.Label(vehicle_frame, text="Kmph", font=("Arial", 12), bg="orange")
        bikekmph_label.grid(row=4, column=2, sticky="w", pady=10)

        min_label = tk.Label(vehicle_frame, text="Min:", font=("Arial", 12), bg="orange", anchor="w", justify="right")
        min_label.grid(row=1, column=3, sticky="w", padx=30)

        self.min_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.min_entry.grid(row=1, column=4, padx=10, pady=10, sticky="w")
        self.min_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        mindist_label = tk.Label(vehicle_frame, text="Mtrs", font=("Arial", 12), bg="orange")
        mindist_label.grid(row=1, column=5, sticky="w", padx=10)

        max_label = tk.Label(vehicle_frame, text="Max:", font=("Arial", 12), bg="orange", anchor=E, justify="right")
        max_label.grid(row=2, column=3, sticky="w", padx=30)

        self.max_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.max_entry.grid(row=2, column=4, padx=10, pady=10, sticky="w")
        self.max_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        maxdist_label = tk.Label(vehicle_frame, text="Mtrs", font=("Arial", 12), bg="orange")
        maxdist_label.grid(row=2, column=5, sticky="w", padx=10)

        tolerance_label = tk.Label(vehicle_frame, text="Tolerance:", font=("Arial", 12), bg="orange", anchor="w",
                                   justify="right")
        tolerance_label.grid(row=3, column=3, sticky="w", padx=30)

        self.tolerance_entry = tk.Entry(vehicle_frame, validate="key", validatecommand=vcmd, font=("Arial", 12), width=5)
        self.tolerance_entry.grid(row=3, column=4, padx=10, pady=10, sticky="w")
        self.tolerance_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        maxtolerance_label = tk.Label(vehicle_frame, text="%", font=("Arial", 12), bg="orange")
        maxtolerance_label.grid(row=3, column=5, sticky="w", padx=10)

        # create save and cancel button
        save_button = tk.Button(self.new_location_frame, bg="orange", command=self.submit_location)
        save_button.configure(image=save_photo, borderwidth=0)
        save_button.grid(row=4, column=1, padx=15, pady=10, sticky='e')

        cancel_button = tk.Button(self.new_location_frame, bg="orange", command=self.cancel)
        cancel_button.configure(image=cancel_photo, borderwidth=0)
        cancel_button.grid(row=4, column=0, padx=15, pady=10, sticky='w')

        self.new_location_frame.pack(pady=10, padx=10)

    def new_location_handle_officers_combobox_selection(self, event):
        if self.officer_combobox.get():
            conn = sqlite3.connect('msiplusersettingsmh.db')
            cursor = conn.cursor()
            cursor.execute("SELECT officer_id FROM officerdetails WHERE officer_name=?",
                           (self.officer_combobox.get(),))
            row1 = cursor.fetchone()
            conn.close()
            self.officer_id_entry.delete(0, tk.END)
            self.officer_id_entry.insert(tk.END, row1)
        else:
            print("Previous officers not found")

    def add_officer_details(self):
        self.new_window.withdraw()
        self.add_officer_window = tk.Toplevel(self.window)
        self.add_officer_window.attributes('-topmost', True)
        self.add_officer_window.resizable(False, False)
        self.add_officer_window.overrideredirect(True)
        self.add_officer_window.title("Add new officer")
        self.add_officer_window.geometry(f"{360}x{210}+450+150")
        self.add_officer_frame = tk.LabelFrame(self.add_officer_window, bg="orange")

        new_label = tk.Label(self.add_officer_frame, text="Add New Officer Details", font=("Arial", 12), bg="orange")
        new_label.grid(row=0, columnspan=2, padx=10, pady=10)

        # Create "Officer Name" label and Entry box
        officer_label = tk.Label(self.add_officer_frame, text="Officer Name:", font=("Arial", 12), bg="orange")
        officer_label.grid(row=1, column=0, padx=10, pady=10)

        self.new_officer_entry = tk.Entry(self.add_officer_frame, font=("Arial", 12))
        self.new_officer_entry.grid(row=1, column=1, padx=10, pady=10)
        self.new_officer_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        # Create "Officer ID" label and Entry box
        officer_id_label = tk.Label(self.add_officer_frame, text="Officer ID:", font=("Arial", 12), bg="orange")
        officer_id_label.grid(row=2, column=0, padx=10, pady=10)

        self.new_officer_id_entry = tk.Entry(self.add_officer_frame, font=("Arial", 12))
        self.new_officer_id_entry.grid(row=2, column=1, padx=10, pady=10)
        self.new_officer_id_entry.bind("<Button-1>", lambda event=None: open_onboard_keyboard())

        save_button = tk.Button(self.add_officer_frame, bg="green", text="Save",
                                command=self.submit_new_officer_details)
        save_button.grid(row=3, column=1, padx=10, pady=10, sticky='e')

        cancel_button = tk.Button(self.add_officer_frame, bg="red", text="Cancel",
                                  command=self.cancel_new_officer_details)
        cancel_button.grid(row=3, column=0, padx=10, pady=10, sticky='w')

        self.add_officer_frame.pack(pady=10)

    def submit_new_officer_details(self):
        if len(self.new_officer_entry.get()) >= 2 and len(self.new_officer_id_entry.get()) >= 2:
            if not self.new_officer_id_entry.get().isalnum():
                messagebox.showerror("Error", "Please enter a valid Officer ID.")
            else:
                try:
                    subprocess.Popen(['pkill', 'onboard'])
                except Exception:
                    pass
                conn = sqlite3.connect('msiplusersettingsmh.db')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO officerdetails VALUES (?, ?)",
                               (self.new_officer_entry.get().upper(), self.new_officer_id_entry.get().upper()))
                conn.commit()
                conn.close()
                self.add_officer_window.destroy()
                messagebox.showinfo("Success", "Officer details have been saved in database.")
                self.new_window.destroy()
                self.settings_button.config(state=tk.NORMAL)
                self.helmet_button.config(state=tk.NORMAL)
                self.offence_button.config(state=tk.NORMAL)
                self.view_button.config(state=tk.NORMAL)
                self.manual_button.config(state=tk.NORMAL)
                self.button2.config(state=tk.NORMAL)
        else:
            messagebox.showerror("Error", "Enter valid details.")

    def cancel(self):
        self.new_window.destroy()
        self.settings_button.config(state=tk.NORMAL)
        self.helmet_button.config(state=tk.NORMAL)
        self.offence_button.config(state=tk.NORMAL)
        self.view_button.config(state=tk.NORMAL)
        self.manual_button.config(state=tk.NORMAL)
        self.button2.config(state=tk.NORMAL)

    def cancel_new_officer_details(self):
        self.add_officer_window.destroy()
        try:
            subprocess.Popen(['pkill', 'onboard'])
        except Exception:
            pass
        self.new_window.deiconify()

    # <-------------------Location details saved to database when submit button is clicked---------------->
    def submit_location(self):
        try:
            # ser1 = serial.Serial(laser_port, 115200)
            if not ser1.is_open:
                ser1.open()
                ser1.write('SF\r\n'.encode())
                time.sleep(0.1)
            ser1.write('SF\r\n'.encode())
            time.sleep(0.1)
            ser1.write('SN\r\n'.encode())
            time.sleep(0.1)
            laser_id = ser1.readline().decode().strip()
            # print("with sn:", laser_id)
            laser_id = laser_id.replace('\x00', '')
            laser_id = laser_id.replace('SN: ', '').strip()
            # print("without sn:",laser_id)
            if ser1.is_open:
                ser1.close()
            location = self.location_entry.get().upper()
            officer_name = self.officer_combobox.get().upper()
            officer_id = self.officer_id_entry.get().upper()
            car_speed = self.car_entry.get()
            truck_speed = self.truck_entry.get()
            lmvtruck_speed = 0  # self.lmvtruck_entry.get()
            ycar_speed = self.ycar_entry.get()
            bike_speed = self.bike_entry.get()
            max_tolerance = self.tolerance_entry.get()
            min_dist = self.min_entry.get()
            max_dist = self.max_entry.get()
            date = datetime.date.today()
            if location and officer_name and officer_id and car_speed and truck_speed and ycar_speed and bike_speed and max_tolerance and max_dist and min_dist:
                # Perform field validation
                if not location:
                    messagebox.showerror("Error", "Please enter a valid location.")
                    return
                if not officer_name:
                    messagebox.showerror("Error", "Please select an officer name.")
                    return
                if not officer_id.isalnum():
                    messagebox.showerror("Error", "Please enter a valid officer ID.")
                    logging.error(f"Invalid officer ID: {str(officer_id)}")
                    return
                if not car_speed.isdigit():
                    messagebox.showerror("Error", "Please enter a valid car speed (integer).")
                    logging.error(f"Invalid car speed: {str(car_speed)}")
                    return
                if not truck_speed.isdigit():
                    messagebox.showerror("Error", "Please enter a valid hmv-truck speed (integer).")
                    logging.error(f"Invalid truck speed: {str(truck_speed)}")
                    return
                '''if not lmvtruck_speed.isdigit():
                    messagebox.showerror("Error", "Please enter a valid lmv-truck speed (integer).")
                    logging.error(f"Invalid lmv truck speed: {str(lmvtruck_speed)}")
                    return'''
                if not ycar_speed.isdigit():
                    messagebox.showerror("Error", "Please enter a valid car speed (integer).")
                    logging.error(f"Invalid bus speed: {str(ycar_speed)}")
                    return
                if not bike_speed.isdigit():
                    messagebox.showerror("Error", "Please enter a valid bike speed (integer).")
                    logging.error(f"Invalid bike speed: {str(bike_speed)}")
                    return
                if not max_tolerance.isdigit():
                    messagebox.showerror("Error", "Please enter a valid tolerance speed (integer).")
                    logging.error(f"Invalid max tolerance: {str(max_tolerance)}")
                    return
                if not min_dist.isdigit():
                    messagebox.showerror("Error", "Please enter a valid minimum distance in mtrs (integer).")
                    logging.error(f"Invalid min distance: {str(min_dist)}")
                    return
                if not max_dist.isdigit():
                    messagebox.showerror("Error", "Please enter a valid maximum distance in mtrs (integer).")
                    logging.error(f"Invalid max distance: {str(max_dist)}")
                    return
                if int(min_dist) > int(max_dist):
                    max_dist = int(max_dist) + int(min_dist)
                    min_dist = max_dist - int(min_dist)
                    max_dist = max_dist - min_dist
                if int(min_dist) < 3:
                    min_dist = 3
                if int(max_dist) < 10:
                    max_dist = 10
                conn = sqlite3.connect('msiplusersettingsmh.db')
                cursor = conn.cursor()
                # Insert the values into the table
                cursor.execute("INSERT INTO dummylocations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (location, officer_name, officer_id, int(car_speed), int(truck_speed),
                                int(lmvtruck_speed), int(ycar_speed), int(bike_speed),
                                int(max_tolerance), int(min_dist), int(max_dist), laser_id, date))

                # Commit the transaction and close the connection
                conn.commit()
                cursor.execute("INSERT INTO officerdetails VALUES (?, ?)",
                               (officer_name, officer_id))
                conn.commit()
                conn.close()
                self.cancel()
                try:
                    subprocess.Popen(['pkill', 'onboard'])
                except Exception:
                    pass
                # Show success message
                messagebox.showinfo("Speed Hunter III Plus", "Location details have been stored in the database.")
                logging.info("Location details have been stored in database")
                self.settings_button.config(state=tk.NORMAL)
                self.helmet_button.config(state=tk.NORMAL)
                self.offence_button.config(state=tk.NORMAL)
                self.view_button.config(state=tk.NORMAL)
                self.manual_button.config(state=tk.NORMAL)
                self.button2.config(state=tk.NORMAL)
                return
            else:
                self.cancel()
                try:
                    subprocess.Popen(['pkill', 'onboard'])
                except Exception:
                    pass
                messagebox.showinfo("Speed Hunter X", "Please fill all values and try again.")
                return
        except Exception as se:
            logging.error(f"Exception in submit_location_details: {str(se)}")
            messagebox.showinfo("Error",
                                f"{se}")
            logging.info("################################################################################")
            self.exit_app()

    def nightoff(self):
        try:
            self.night_mode_is_on = False
            self.car_speed_limit = min(self.w_car_speed, self.y_car_speed)
            self.car_button.config(text="LMV:{}".format(min(self.w_car_speed, self.y_car_speed)), state=tk.NORMAL)
            self.night_on.config(state=NORMAL)
            self.onepush_btn.config(state=DISABLED)
            self.manual_focus_far.config(state=DISABLED)
            self.manual_focus_near.config(state=DISABLED)
            ser = serial.Serial(cam_port, 9600)
            hex_command = '8101040103FF'  # ICR OFF COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101043802FF'  # AUTO FOCUS ON COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101043900FF'  # AE MODE AUTO COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101045B00FF'  # STANDARD S GAMMA ON COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140000FF'  # HLC OFF COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            '''hex_command = '81010414000EFF'  # HLM ON MAX-LEVEL = 14 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000DFF'  # HLM ON MAX-LEVEL = 13 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000CFF'  # HLM ON MAX-LEVEL = 12 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000BFF'  # HLM ON MAX-LEVEL = 11 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000AFF'  # HLM ON MAX-LEVEL = 10 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140009FF'  # HLM ON MAX-LEVEL = 9 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140008FF'  # HLM ON MAX-LEVEL = 8 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140007FF'  # HLM ON MAX-LEVEL = 7 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140006FF'  # HLM ON MAX-LEVEL = 6 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140005FF'  # HLM ON MAX-LEVEL = 5 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)'''
            '''hex_command = '810104140004FF'  # HLM ON MAX-LEVEL = 4 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140003FF'  # HLM ON MAX-LEVEL = 3 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140002FF'  # HLM ON MAX-LEVEL = 2 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140001FF'  # HLM ON MAX-LEVEL = 1 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140000FF'  # HLM O COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)'''
            time.sleep(0.1)
            ser.close()
        except Exception as catch:
            print(catch)

    def nighton(self):
        try:
            self.night_mode_is_on = True
            self.car_speed_limit = max(self.w_car_speed, self.y_car_speed)
            self.car_button.config(text="LMV:{}".format(max(self.w_car_speed, self.y_car_speed)), state=tk.NORMAL)
            self.car()
            self.onepush_btn.config(state=NORMAL)
            self.manual_focus_far.config(state=NORMAL)
            self.manual_focus_near.config(state=NORMAL)
            self.night_on.config(state=DISABLED)
            ser = serial.Serial(cam_port, 9600)
            hex_command = '8101040102FF'  # ICR ON COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101043803FF'  # MANUAL FOCUS ON COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101043903FF'  # AE MODE MANUAL COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101045B01FF'  # S GAMMA ON COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            '''hex_command = '810104390AFF'  # AE MODE SHUTTER PRIORITY COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)'''
            hex_command = '8101040A02FF'  # SHUTTER FAST 1 TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER FAST 2 TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER FAST 3 TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER FAST 4 TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER FAST 5-TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER FAST 6-TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER FAST 7-TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER FAST 8-TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER FAST 9-TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER FAST 10-TIME COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            '''hex_command = '810104140001FF'  # HLM ON MAX-LEVEL = 1 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140002FF'  # HLM ON MAX-LEVEL = 2 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140003FF'  # HLM ON MAX-LEVEL = 3 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140004FF'  # HLM ON MAX-LEVEL = 4 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)'''
            '''time.sleep(0.1)
            hex_command = '810104140005FF'  # HLM ON MAX-LEVEL = 5 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140006FF'  # HLM ON MAX-LEVEL = 6 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140007FF'  # HLM ON MAX-LEVEL = 7 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140008FF'  # HLM ON MAX-LEVEL = 8 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140009FF'  # HLM ON MAX-LEVEL = 9 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000AFF'  # HLM ON MAX-LEVEL = 10 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000BFF'  # HLM ON MAX-LEVEL = 11 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000CFF'  # HLM ON MAX-LEVEL = 12 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000DFF'  # HLM ON MAX-LEVEL = 13 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000EFF'  # HLM ON MAX-LEVEL = 14 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '81010414000FFF'  # HLM ON MAX-LEVEL = 15 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)'''
            ser.close()
        except Exception as catch:
            print(catch)

    def hlc_low(self):
        try:
            ser = serial.Serial(cam_port, 9600)
            hex_command = '810104140100FF'  # HLC LOW COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140307FF'  # HLM ON LEVEL = 7 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def hlc_mid(self):
        try:
            ser = serial.Serial(cam_port, 9600)
            hex_command = '810104140200FF'  # HLC MID COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140307FF'  # HLM ON LEVEL = 7 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def hlc_high(self):
        try:
            ser = serial.Serial(cam_port, 9600)
            hex_command = '810104140300FF'  # HLC HIGH COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '810104140307FF'  # HLM ON LEVEL = 7 COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def s_gamma_on(self):
        try:
            ser = serial.Serial(cam_port, 9600)
            hex_command = '8101045B01FF'  # S GAMMA ON COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def s_gamma_off(self):
        try:
            ser = serial.Serial(cam_port, 9600)
            hex_command = '8101045B00FF'  # STANDARD S GAMMA ON COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def bright_up(self):
        try:
            self.shutter_priority()
            ser = serial.Serial(cam_port, 9600)
            hex_command = '810104390DFF'  # BRIGHTNESS COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040D02FF'  # BRIGHT UP COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def shutter_priority(self):
        self.shutter_priority_is_on = False
        if not self.shutter_priority_is_on:
            ser = serial.Serial(cam_port, 9600)
            hex_command = '810104390AFF'  # AE MODE SHUTTER PRIORITY COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
            self.shutter_priority_is_on = True
        else:
            pass

    def bright_reset(self):
        try:
            self.shutter_priority()
            ser = serial.Serial(cam_port, 9600)
            hex_command = '810104390DFF'  # BRIGHTNESS COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040D00FF'  # BRIGHT RESET COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def bright_down(self):
        try:
            self.shutter_priority()
            ser = serial.Serial(cam_port, 9600)
            hex_command = '810104390DFF'  # BRIGHTNESS COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040D03FF'  # BRIGHT DOWN COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def shutter_slow(self):
        try:
            self.shutter_priority_is_on = False
            ser = serial.Serial(cam_port, 9600)
            hex_command = '8101043903FF'  # AE MODE MANUAL COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A03FF'  # SHUTTER  SLOW COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def shutter_reset(self):
        try:
            self.shutter_priority_is_on = False
            ser = serial.Serial(cam_port, 9600)
            hex_command = '8101043903FF'  # AE MODE MANUAL COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A00FF'  # SHUTTER  RESET COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def shutter_fast(self):
        try:
            self.shutter_priority_is_on = False
            ser = serial.Serial(cam_port, 9600)
            hex_command = '8101043903FF'  # AE MODE MANUAL COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            time.sleep(0.1)
            hex_command = '8101040A02FF'  # SHUTTER  FAST COMMAND
            command = binascii.unhexlify(hex_command)
            ser.write(command)
            ser.close()
        except Exception:
            pass

    def onepush(self):
        ser = serial.Serial(cam_port, 9600)
        hex_command = '8101041801FF'  # MANUAL ONE PUSH COMMAND
        command = binascii.unhexlify(hex_command)
        ser.write(command)
        ser.close()

    def mfocus_far(self):
        ser = serial.Serial(cam_port, 9600)
        hex_command = '8101040824FF8101040800FF81097E7E00FF'  # MANUAL FOCUS FAR COMMAND
        command = binascii.unhexlify(hex_command)
        ser.write(command)
        time.sleep(1)
        ser.close()

    def mfocus_near(self):
        ser = serial.Serial(cam_port, 9600)
        hex_command = '8101040834FF8101040800FF81097E7E00FF'  # MANUAL FOCUS NEAR COMMAND
        command = binascii.unhexlify(hex_command)
        ser.write(command)
        time.sleep(1)
        ser.close()

    def zoom_out(self):
        # if self.cap.isOpened():
        ser = serial.Serial(cam_port, 9600)
        hex_command = '8101040736FF'  # ZOOM OUT CONTINUOUSLY COMMAND
        command = binascii.unhexlify(hex_command)
        ser.write(command)
        ser.close()

    def zoom_out_stop(self):
        # if self.cap.isOpened():
        ser = serial.Serial(cam_port, 9600)
        hex_command = '8101040736FF8101040700FF81097E7E00FF'  # ZOOM OUT ONCE COMMAND
        command = binascii.unhexlify(hex_command)
        ser.write(command)
        ser.close()

    # <------------------------------zoom in functions------------------------------------>
    def zoom_in(self):
        # if self.cap.isOpened():
        ser = serial.Serial(cam_port, 9600)
        hex_command = '8101040726FF'  # ZOOM IN CONTINUOUSLY COMMAND
        command = binascii.unhexlify(hex_command)
        ser.write(command)
        ser.close()

    def zoom_in_stop(self):
        # if self.cap.isOpened():
        ser = serial.Serial(cam_port, 9600)
        hex_command = '8101040726FF8101040700FF81097E7E00FF'  # ZOOM IN ONCE COMMAND
        command = binascii.unhexlify(hex_command)
        ser.write(command)
        ser.close()

    def close_tools(self):
        self.button1.config(state=NORMAL)
        self.new_window1.destroy()
        return

    # <-----------------------Tools window function---------------------------------------------->
    def open_window1(self):
        self.button1.config(state=DISABLED)
        self.new_window1 = tk.Toplevel(self.window, bg="orange")
        self.new_window1.title("Tools")
        bigfont = font.Font(family="Arial", size=12)
        root.option_add("*Font", bigfont)
        self.new_window1.geometry(f"{440}x{330}+830+100")  # 1280-400 = 880
        self.new_window1.attributes('-topmost', True)
        self.new_window1.resizable(False, False)
        self.new_window1.overrideredirect(True)

        # create tools frame
        tools_frame = tk.LabelFrame(self.new_window1, bg="orange")
        tools_frame.pack(anchor=tk.NW, pady=10, padx=10)

        camera_label = tk.Label(tools_frame, text="Camera Tool's Settings", bg="orange")
        camera_label.grid(row=0, columnspan=4)
        close_btn = tk.Button(tools_frame, text="Close", bg="red", command=self.close_tools, width=10)
        close_btn.grid(row=1, column=3, pady=5)

        night_label = tk.Label(tools_frame, text="Night Mode:", bg="orange")
        night_label.grid(row=1, column=0, pady=5)

        self.night_on = tk.Button(tools_frame, text="On", command=self.nighton, width=10)
        self.night_on.grid(row=1, column=1, sticky="nsew", pady=5)

        nightoff = tk.Button(tools_frame, text="Off", command=self.nightoff, width=10)
        nightoff.grid(row=1, column=2, sticky="nsew", pady=5)

        focus_label = tk.Label(tools_frame, text="Focus Mode:", bg="orange")
        focus_label.grid(row=2, column=0, pady=5)

        auto = tk.Button(tools_frame, text="Auto", command=self.auto_focus, width=10)
        auto.grid(row=2, column=1, pady=5)

        manual = tk.Button(tools_frame, text="Manual", command=self.manual_focus, width=10)
        manual.grid(row=2, column=2, pady=5)

        self.onepush_btn = tk.Button(tools_frame, text="One Push", command=self.onepush, width=10, state=DISABLED)
        self.onepush_btn.grid(row=2, column=3, pady=5)

        hlc_label = tk.Label(tools_frame, text="HLC Mode:", bg="orange")
        hlc_label.grid(row=3, column=0, pady=5)

        hlc_low = tk.Button(tools_frame, text="Low", command=self.hlc_low, width=10)
        hlc_low.grid(row=3, column=1, pady=5)

        hlc_mid = tk.Button(tools_frame, text="Mid", command=self.hlc_mid, width=10)
        hlc_mid.grid(row=3, column=2, pady=5)

        hlc_high = tk.Button(tools_frame, text="High", command=self.hlc_high, width=10)
        hlc_high.grid(row=3, column=3, pady=5)

        sgamma_label = tk.Label(tools_frame, text="S Gamma:", bg="orange")
        sgamma_label.grid(row=4, column=0, pady=5)

        sgamma_on = tk.Button(tools_frame, text="On", command=self.s_gamma_on, width=10)
        sgamma_on.grid(row=4, column=1, pady=5)

        label = tk.Label(tools_frame, text="<----------->", bg="orange")
        label.grid(row=4, column=2, pady=5)

        sgamma_off = tk.Button(tools_frame, text="Off", command=self.s_gamma_off, width=10)
        sgamma_off.grid(row=4, column=3, pady=5)

        shutter_label = tk.Label(tools_frame, text="Shutter:", bg="orange")
        shutter_label.grid(row=5, column=0, pady=5)

        self.shutter_slow_btn = tk.Button(tools_frame, text="Slow", command=self.shutter_slow, width=10)
        self.shutter_slow_btn.grid(row=5, column=1, pady=5)

        self.shutter_reset_btn = tk.Button(tools_frame, text="Reset", command=self.shutter_reset, width=10)
        self.shutter_reset_btn.grid(row=5, column=2, pady=5)

        self.shutter_fast_btn = tk.Button(tools_frame, text="Fast", command=self.shutter_fast, width=10)
        self.shutter_fast_btn.grid(row=5, column=3, pady=5)

        mfocus_label = tk.Label(tools_frame, text="M.Focus:", bg="orange")
        mfocus_label.grid(row=6, column=0, pady=5)

        self.manual_focus_near = tk.Button(tools_frame, text="Near", command=self.mfocus_near, width=10, state=DISABLED)
        self.manual_focus_near.grid(row=6, column=1, pady=5)

        label1 = tk.Label(tools_frame, text="<----------->", bg="orange")
        label1.grid(row=6, column=2, pady=5)

        self.manual_focus_far = tk.Button(tools_frame, text="Far", command=self.mfocus_far, width=10, state=DISABLED)
        self.manual_focus_far.grid(row=6, column=3, pady=5)

        v_detect = tk.Label(tools_frame, text="V.Detection:", bg="orange")
        v_detect.grid(row=7, column=0, pady=5)

        self.vd_on = tk.Button(tools_frame, text="On", command=self.vehicle_detection_on, width=10)
        self.vd_on.grid(row=7, column=1, pady=5)

        label2 = tk.Label(tools_frame, text="<----------->", bg="orange")
        label2.grid(row=7, column=2, pady=5)

        self.vd_off = tk.Button(tools_frame, text="Off", command=self.vehicle_detection_off, width=10)
        self.vd_off.grid(row=7, column=3, pady=5)

        if self.night_mode_is_on:
            self.night_on.config(state=DISABLED)
            self.onepush_btn.config(state=NORMAL)
            self.manual_focus_near.config(state=NORMAL)
            self.manual_focus_far.config(state=NORMAL)
        else:
            self.night_on.config(state=NORMAL)
            self.onepush_btn.config(state=DISABLED)
            self.manual_focus_near.config(state=DISABLED)
            self.manual_focus_far.config(state=DISABLED)

    def auto_focus(self):
        ser = serial.Serial(cam_port, 9600)
        hex_command = '8101043802FF'  # AUTO-FOCUS ON COMMAND
        command = binascii.unhexlify(hex_command)
        ser.write(command)
        ser.close()
        self.onepush_btn.config(state=DISABLED)
        self.manual_focus_far.config(state=DISABLED)
        self.manual_focus_near.config(state=DISABLED)

    def manual_focus(self):
        ser = serial.Serial(cam_port, 9600)
        hex_command = '8101043803FF'  # MANUAL-FOCUS ON COMMAND
        command = binascii.unhexlify(hex_command)
        ser.write(command)
        ser.close()
        self.onepush_btn.config(state=NORMAL)
        self.manual_focus_far.config(state=NORMAL)
        self.manual_focus_near.config(state=NORMAL)

    def number_plate_images(self, image_id, cur_date, cur_time, speed, distance, vehicle, frame):
        global output_path, original_path
        try:
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            img = img.resize((200, 130))
            # Create a drawing context
            draw = ImageDraw.Draw(img)

            # Define the font and text position
            font = ImageFont.load_default()
            text = "OVER SPEED"
            if speed is None:
                text = "SNAPSHOT"
            text_position = (75, 60)  # Adjust the position as needed

            # Draw the text on the image
            draw.text(text_position, text, font=font, fill="red")
            img = ImageTk.PhotoImage(img)
            self.last_image_label.config(image=img)
            self.last_image_label.image = img
        except Exception as e:
            print(e)
        file_name = f"{image_id}.jpg"
        original_file_path = os.path.join(original_path, file_name)
        ff = os.path.join(output_path, file_name)
        cv2.imwrite(original_file_path, frame)
        #  <------for cropping some part to send for number plate reading-------->
        img = Image.open(original_file_path).convert('RGB')
        img_width, img_height = img.size
        crop_width = int(img_width * 0.3)  # Adjust the crop width as needed
        # crop_height = int(img_height * 0.5)  # Adjust the crop height as needed
        left = int((img_width - crop_width) / 2)
        top = 0  # int((img_height - crop_height) / 2)
        right = left + crop_width
        bottom = img_height  # top + crop_height
        cropped_img = img.crop((left, top, right, bottom))
        cropped_img.save(ff)
        # print(self.device_id)
        cropped_img.close()
        img.close()
        time.sleep(0.01)
        plate_recognizer(self.lati, self.longi, str(image_id), str(cur_date), str(cur_time), ff, original_file_path,
                         speed, distance, vehicle, self.night_mode_is_on, self.y_car_speed, self.w_car_speed, self.truck_speed_limit, self.bike_speed_limit, self.tolerance)

    # <------------------Snapshot button function---------------------------->

    def snapshot(self, frame=None, speed=None, distance=None, vehicle=None):
        with self.licence_snapshot_lock:
            if speed is None:
                frame = self.second_copy_frame
            cur_date = datetime.date.today()
            cur_time = datetime.datetime.now()
            milliseconds = cur_time.microsecond // 1000
            image_id = str(self.device_id) + cur_time.strftime('%Y%m%d%H%M%S') + f"{milliseconds}"
            cur_time = cur_time.strftime('%Y-%m-%d_%H-%M-%S') + f".{milliseconds}"
            snapshot_even_thread = threading.Thread(target=self.snapshot_thread,
                                                    args=(
                                                        image_id, cur_date, cur_time, speed, distance, vehicle, frame))
            snapshot_even_thread.daemon = True
            snapshot_even_thread.start()
            logging.info("Snapshot_Thread_Created.")

    def snapshot_thread(self, image_id, cur_date, cur_time, speed, distance, vehicle, frame):
        self.number_plate_images(image_id, cur_date, cur_time, speed, distance, vehicle, frame)

    # <----------------Function to add music files or image files to exe file---------------->
    def resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # <----------------Function to get data for current location and to display inside buttons------------->
    def fetch_data(self):
        conn = sqlite3.connect('msiplusersettingsmh.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations ORDER BY rowid DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row

    # <--------------------Update car, truck, bike speeds in buttons and enable them------------------>
    def add_buttons(self):
        data = self.fetch_data()
        # self.bus_button.destroy()
        if self.night_mode_is_on:
            self.car_button.config(text="LMV:{}".format(max(data[3], data[6])), state=tk.NORMAL, width=20)
        else:
            self.car_button.config(text="LMV:{}".format(min(data[3], data[6])), state=tk.NORMAL, width=20)
        self.hmvtruck_button.config(text="HMV:{}".format(data[4]), state=tk.NORMAL, width=20)
        # self.lmvtruck_button.config(text="LMV-Truck:{}".format(data[5]), state=tk.NORMAL)
        # self.bus_button.config(text="Bus:{}".format(data[6]), state=tk.NORMAL)
        self.bike_button.config(text="Bike:{}".format(data[7]), state=tk.NORMAL, width=23)

    # <--------------------Application exit function with process killed-------------------------->
    def exit_app(self):
        ret = messagebox.askyesno("Speed Hunter III Plus", "Do you really want to exit?")
        if ret:
            try:
                if self.night_mode_is_on:
                    self.nightoff()
                exit_ser = serial.Serial(cam_port, 9600, timeout=1)
                hex_command = '8101040736FF'  # ZOOM OUT CONTINUOUSLY COMMAND
                command = binascii.unhexlify(hex_command)
                exit_ser.write(command)
                time.sleep(0.2)
                hex_command = '8101041903FF'  # RESET CAMERA COMMAND
                command = binascii.unhexlify(hex_command)
                exit_ser.write(command)
                time.sleep(0.1)
                hex_command = '8101040002FF'  # CAMERA ON COMMAND
                command = binascii.unhexlify(hex_command)
                exit_ser.write(command)
                exit_ser.close()
                time.sleep(0.1)
                self.auto_capture_active = False
                self.manual_capture_active = False
                if ser1.is_open:
                    ser1.write(b'SF\r\n')
                    ser1.close()
                self.stop_event.set()
                self.cap.release()
                self.window.destroy()
                self.t.cancel()
                # sys.exit(0)
                logging.info("Ending of MainApplication")
                logging.info("################################################################################")
                pid = os.getpid()
                os.kill(pid, signal.SIGTERM)

            except serial.SerialException as ase:
                tk.messagebox.showerror("Serial Error", f"{ase}.")
                logging.error(f"The port {str(cam_port)} for camera is not open")
                self.t.cancel()
                pid = os.getpid()
                logging.info("Ending of MainApplication")
                logging.info("################################################################################")
                os.kill(pid, signal.SIGKILL)
            except Exception as ex:
                print(ex)
                self.t.cancel()
                pid = os.getpid()
                logging.info("Ending of MainApplication")
                logging.info("################################################################################")
                os.kill(pid, signal.SIGKILL)
        else:
            pass


def show_splash_screen():
    w = Tk()
    width_of_window = 600
    height_of_window = 250
    screen_width = w.winfo_screenwidth()
    screen_height = w.winfo_screenheight()
    x_coordinate = (screen_width / 2) - (width_of_window / 2)
    y_coordinate = (screen_height / 2) - (height_of_window / 2)
    w.geometry("%dx%d+%d+%d" % (width_of_window, height_of_window, x_coordinate, y_coordinate))
    w.overrideredirect(True)

    Frame(w, width=600, height=250, bg='#272727').place(x=0, y=0)
    label1 = Label(w, text='SPEED HUNTER III PLUS', fg='white', bg='#272727')  # 272727
    label1.configure(font=("Game Of Squids", 24, "bold"))
    label1.place(x=80, y=90)

    label2 = Label(w, text='MHv1.0 Loading...', fg='white', bg='#272727')
    label2.configure(font=("Calibri", 11))
    label2.place(x=10, y=215)

    # making animation
    image_a = ImageTk.PhotoImage(Image.open('resources/img/c2.png'))
    image_b = ImageTk.PhotoImage(Image.open('resources/img/c1.png'))

    for i in range(10):  # loops
        '''Label(w, image=image_a, border=0, relief=SUNKEN).place(x=260, y=145)
        Label(w, image=image_b, border=0, relief=SUNKEN).place(x=280, y=145)
        Label(w, image=image_b, border=0, relief=SUNKEN).place(x=300, y=145)
        Label(w, image=image_b, border=0, relief=SUNKEN).place(x=320, y=145)'''
        w.update_idletasks()
        time.sleep(0.5)

        '''Label(w, image=image_b, border=0, relief=SUNKEN).place(x=260, y=145)
        Label(w, image=image_a, border=0, relief=SUNKEN).place(x=280, y=145)
        Label(w, image=image_b, border=0, relief=SUNKEN).place(x=300, y=145)
        Label(w, image=image_b, border=0, relief=SUNKEN).place(x=320, y=145)'''
        w.update_idletasks()
        time.sleep(0.5)

        '''Label(w, image=image_b, border=0, relief=SUNKEN).place(x=260, y=145)
        Label(w, image=image_b, border=0, relief=SUNKEN).place(x=280, y=145)
        Label(w, image=image_a, border=0, relief=SUNKEN).place(x=300, y=145)
        Label(w, image=image_b, border=0, relief=SUNKEN).place(x=320, y=145)'''
        w.update_idletasks()
        time.sleep(0.5)

        '''Label(w, image=image_b, border=0, relief=SUNKEN).place(x=260, y=145)
        Label(w, image=image_b, border=0, relief=SUNKEN).place(x=280, y=145)
        Label(w, image=image_b, border=0, relief=SUNKEN).place(x=300, y=145)
        Label(w, image=image_a, border=0, relief=SUNKEN).place(x=320, y=145)'''
        w.update_idletasks()
        time.sleep(0.5)

    w.destroy()


def delete_old_numplate_folders():
    try:

        # Define the path to the folder containing the images
        folder_path = f"/media/{getpass.getuser()}/Elements/number_plate_images/"

        # Get the current date
        current_date = datetime.datetime.now().date()

        # Calculate the date 7 days ago
        date_7_days_ago = current_date - datetime.timedelta(days=7)

        # Loop through the folders and delete files older than 7 days
        for i in range(7):
            # Calculate the date of the folder
            folder_date = date_7_days_ago + datetime.timedelta(days=i)
            folder_date_str = folder_date.strftime("%Y-%m-%d")

            # Construct the path to the folder
            folder = os.path.join(folder_path, folder_date_str)

            # Check if the folder exists
            if os.path.exists(folder):
                # List all files in the folder
                files = os.listdir(folder)

                # Delete each file in the folder
                for file in files:
                    file_path = os.path.join(folder, file)
                    # Check if the file is not in the "upload" subfolder
                    if not file_path.startswith(os.path.join(folder, "upload")):
                        os.remove(file_path)

                # Optionally, you can also delete the empty folder (excluding "upload")
                for dirpath, dirnames, filenames in os.walk(folder):
                    for dirname in dirnames:
                        if dirname != "upload":
                            dir_to_delete = os.path.join(dirpath, dirname)
                            os.rmdir(dir_to_delete)
    except Exception:
        pass


def custom_error_message(title, message):
    root0 = tk.Tk()
    root0.withdraw()
    root0.attributes('-topmost', True)
    messagebox.showinfo(title, message)
    root0.destroy()


def check_rtc():
    hd_date = datetime.date(2024, 3, 30)
    cur_date = datetime.date.today()
    if cur_date < hd_date:
        if getattr(sys, 'frozen', False):
            pyi_splash.close()
        custom_error_message(f"CLOCK ERROR {str(cur_date)}",
                             "Your device date is inaccurate! Turn on internet and try again.")
        logging.error(f"RTC ERROR, TODAY'S DATE IS {str(cur_date)}?")
        logging.info("################################################################################")
        sys.exit()
    else:
        pass


delete_old_numplate_folders()
# show_splash_screen()
logging.basicConfig(filename='sphulog.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("################################################################################")

check_rtc()

# Read the contents of the file
laser_port = '/dev/ttyTHS0'
password = "nvidia"
vd = 1
context = pyudev.Context()

# Define the device paths
device_paths = ['/dev/ttyACM1', '/dev/ttyACM0']

# Define dictionaries to store manufacturer names
manufacturer_names = {}

# Iterate over the device paths
for device_path in device_paths:
    # Get the device object
    for device in context.list_devices(subsystem='tty', DEVNAME=device_path):
        # Get the manufacturer name
        manufacturer_name = device.get('ID_VENDOR')

        # Store the manufacturer name in the dictionary
        manufacturer_names[device_path] = manufacturer_name

# Assign variables based on manufacturer names
cam_port = None
gps_port = None
for device_path, manufacturer_name in manufacturer_names.items():
    if manufacturer_name == 'Aivion' or manufacturer_name == 'Twiga':
        cam_port = device_path
    else:
        gps_port = device_path

logging.info(f"CAM_PORT= {str(cam_port)}, GPS_PORT= {str(gps_port)}")
try:
    if not os.path.exists('config.txt'):
        content = "nvidia\n1"
        with open("config.txt", "w") as file:
            file.write(content)
    with open('config.txt', 'r') as file:
        lines = file.read().splitlines()

    # Assign values to variables
    if len(lines) >= 1:
        password = str(lines[0])
    if len(lines) >= 2:
        vd = str(lines[1])
except FileNotFoundError:
    custom_error_message("Error", "File 'config.txt' not found.")
    logging.error("File 'config.txt' not found.")

try:
    # Use sync to flush file system buffers
    subprocess.run(f'echo "{password}" | sudo -S sync', shell=True, check=True)

    # Drop file system cache
    subprocess.run(f'echo "{password}" | sudo -S sh -c "echo 3 > /proc/sys/vm/drop_caches"', shell=True,
                   check=True)
except subprocess.CalledProcessError as e:
    if getattr(sys, 'frozen', False):
        pyi_splash.close()
    custom_error_message("Error clearing cache", f"{e}")
    custom_error_message("Password is changed", "Contact Medical Sensors Team, ph-no: 9844908899")
    sys.exit()


# show_splash_screen()

def read_serial_data():
    while True:
        try:
            data = laz_ser.readline().decode().strip()  # Read and decode data
            # print(data)
            if len(data) > 5:
                logging.info("LASER OK Received Serial Number.")
                laz_ser.close()
                return True
            else:
                logging.error(f"Exception in read_serial_data: {str(data)}")
                logging.info("################################################################################")
                return False
        except Exception as rs:
            logging.error(f"Exception in read_serial_data: {str(rs)}")
            logging.info("################################################################################")
            return False


def send_hex_command_and_wait(timeout_seconds):
    laz_ser.write('SN\r\n'.encode())
    time.sleep(0.1)
    start_time = time.time()
    ret = False
    while time.time() - start_time < timeout_seconds:
        try:
            if laz_ser.in_waiting > 0:
                ret = read_serial_data()
                if ret:
                    return
            time.sleep(0.1)
        except Exception:
            return

    # If no response is received within the timeout
    if not ret:
        if getattr(sys, 'frozen', False):
            pyi_splash.close()
        custom_error_message("Laser OFF Error",
                             "Switch ON the laser and try again.")
        logging.error("LASER is switched OFF, terminating the application")
        logging.info("################################################################################")
        laz_ser.close()
        sys.exit()


# Function to start the serial communication thread
def start_serial_thread():
    global laz_ser, serial_thread
    try:
        laz_ser = serial.Serial(laser_port, baudrate=115200)
        serial_thread = threading.Thread(target=read_serial_data)
        serial_thread.daemon = True
        serial_thread.start()
    except serial.SerialException as e:
        if getattr(sys, 'frozen', False):
            pyi_splash.close()
        custom_error_message("Serial Error", f"{e}")
        logging.error(f"Exception in start_serial_thread: {str(e)}")
        logging.info("################################################################################")
        sys.exit()


# Start the serial communication thread
start_serial_thread()
send_hex_command_and_wait(1)


def on_close():
    pid = os.getpid()
    logging.info("Ending of MainApplication")
    logging.info("################################################################################")
    os.kill(pid, signal.SIGKILL)


# Create the main window
try:
    cam_ser = serial.Serial(cam_port, 9600)
    logging.info("CAMERA IS CONNECTED")
    if cam_ser.is_open:
        cam_ser.close()
    root = tk.Tk()
    root.geometry(f"{1280}x{762}+0+0")  # 1024,550
    # root.overrideredirect(True)
    icon = tk.PhotoImage(file="resources/img/icon.png")
    root.iconphoto(True, icon)
    root.resizable(False, False)
    app = MainApplication(root, cam_port, laser_port, gps_port, vd)  # Create an instance of the main application
    root.mainloop()  # Start the Tkinter event loop
    root.protocol("WM_DELETE_WINDOW", on_close())
except Exception as e:
    if getattr(sys, 'frozen', False):
        pyi_splash.close()
    custom_error_message("Error", f"{e}")
    logging.error(f"Exception while booting application: {str(e)}")
    logging.info("################################################################################")
    sys.exit()
