import tkinter as tk
from tkinter import ttk
import json
import os
import datetime
import time
import threading
from pathlib import Path
import subprocess
import sys

# For notifications
try:
    from plyer import notification
except ImportError:
    # If plyer is not installed, we'll handle this in the setup_requirements function
    pass

class DailyTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Daily Health Tracker")
        self.root.geometry("400x400")
        self.root.resizable(False, False)
        
        # Set application icon and theme
        self.root.iconbitmap(default=None)  # You can add an icon file path here if you have one
        
        # Configure style
        self.style = ttk.Style()
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TButton", padding=6, relief="flat", background="#4CAF50", foreground="black")
        self.style.configure("TLabel", background="#f0f0f0", font=('Helvetica', 12))
        self.style.configure("Header.TLabel", font=('Helvetica', 14, 'bold'))
        self.style.configure("Counter.TLabel", font=('Helvetica', 24, 'bold'))
        
        # Data file paths - now in project directory
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.app_dir, "tracker_data")
        self.data_file = os.path.join(self.data_dir, "tracker_data.json")
        self.log_file = os.path.join(self.data_dir, "tracker_log.txt")
        
        # Create directory if it doesn't exist
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # Initialize data
        self.today = datetime.date.today().strftime("%Y-%m-%d")
        self.data = self.load_data()
        
        # Notification flags
        self.notification_threads = []
        self.stop_notifications = threading.Event()
        
        # Create UI elements
        self.create_widgets()
        
        # Start date checker thread
        self.date_checker_thread = threading.Thread(target=self.check_date_change, daemon=True)
        self.date_checker_thread.start()
        
        # Start notification schedulers
        self.schedule_notifications()
        
        # Update UI with current data
        self.update_ui()
    
    def load_data(self):
        """Load existing data or create default data structure"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    
                # Check if the loaded data is for today
                if data.get("date") != self.today:
                    # It's a new day, reset the data
                    self.log_message(f"New day detected. Resetting trackers from {data.get('date')} to {self.today}")
                    return self.get_default_data()
                return data
            except Exception as e:
                self.log_message(f"Error loading data: {str(e)}")
                return self.get_default_data()
        else:
            # No existing data file, create default data
            return self.get_default_data()
    
    def get_default_data(self):
        """Return the default data structure for a new day"""
        return {
            "date": self.today,
            "creatine_taken": False,
            "water_bottles": 0,
            "sunscreen_applications": 0
        }
    
    def save_data(self):
        """Save current data to file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f)
        except Exception as e:
            self.log_message(f"Error saving data: {str(e)}")
    
    def log_message(self, message):
        """Add a timestamped message to the log file"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Error writing to log: {str(e)}")
    
    def check_date_change(self):
        """Thread function to periodically check for date changes"""
        while True:
            current_date = datetime.date.today().strftime("%Y-%m-%d")
            if current_date != self.today:
                self.today = current_date
                self.data = self.get_default_data()
                self.save_data()
                self.log_message(f"Date changed to {self.today}. Trackers reset.")
                
                # Reset notification schedules
                self.stop_notifications.set()
                for thread in self.notification_threads:
                    if thread.is_alive():
                        thread.join(timeout=1.0)
                
                self.stop_notifications.clear()
                self.schedule_notifications()
                
                # Update UI from the main thread
                self.root.after(0, self.update_ui)
            
            # Check every minute
            time.sleep(60)
    
    def schedule_notifications(self):
        """Schedule notifications for water and sunscreen reminders"""
        self.log_message("Setting up notification schedules")
        
        # Clear existing threads
        self.notification_threads = []
        
        # Start new threads for water and sunscreen reminders
        water_thread = threading.Thread(
            target=self.water_notification_scheduler,
            daemon=True
        )
        water_thread.start()
        self.notification_threads.append(water_thread)
        
        sunscreen_thread = threading.Thread(
            target=self.sunscreen_notification_scheduler,
            daemon=True
        )
        sunscreen_thread.start()
        self.notification_threads.append(sunscreen_thread)
    
    def water_notification_scheduler(self):
        """Thread to handle water reminder notifications"""
        self.log_message("Water notification scheduler started")
        
        while not self.stop_notifications.is_set():
            now = datetime.datetime.now()
            target_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
            
            # If it's already past 9:15 AM, add 1.25 hours to current time for first notification
            if now > target_time:
                # Calculate how many 1.25 hour intervals have passed since 9:15 AM
                time_diff = (now - target_time).total_seconds()
                intervals = time_diff // (75 * 60)  # 1.25 hours = 75 minutes
                
                # Calculate the next notification time
                next_notification = target_time + datetime.timedelta(minutes=75 * (intervals + 1))
            else:
                # If before 9:15 AM, set first notification to 10:40 AM (9:15 + 1.25 hours)
                next_notification = target_time + datetime.timedelta(minutes=75)
            
            # Sleep until next notification time
            sleep_seconds = (next_notification - datetime.datetime.now()).total_seconds()
            if sleep_seconds > 0:
                self.log_message(f"Next water reminder scheduled for {next_notification.strftime('%H:%M:%S')}")
                
                # Wait until notification time or until stop event is set
                if self.stop_notifications.wait(timeout=sleep_seconds):
                    break
                
                # Send notification if we still have bottles to drink
                if self.data["water_bottles"] < 6:
                    self.show_notification(
                        title="Water Reminder",
                        message=f"Time to drink water! ({self.data['water_bottles']}/6 bottles)",
                        timeout=10
                    )
                    self.log_message("Water reminder notification sent")
            else:
                # If sleep_seconds is negative, wait a minute and recalculate
                time.sleep(60)
    
    def sunscreen_notification_scheduler(self):
        """Thread to handle sunscreen reminder notifications"""
        self.log_message("Sunscreen notification scheduler started")
        
        while not self.stop_notifications.is_set():
            now = datetime.datetime.now()
            target_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
            
            # If it's already past 9:15 AM, add 2.5 hours to current time for first notification
            if now > target_time:
                # Calculate how many 2.5 hour intervals have passed since 9:15 AM
                time_diff = (now - target_time).total_seconds()
                intervals = time_diff // (150 * 60)  # 2.5 hours = 150 minutes
                
                # Calculate the next notification time
                next_notification = target_time + datetime.timedelta(minutes=150 * (intervals + 1))
            else:
                # If before 9:15 AM, set first notification to 11:45 AM (9:15 + 2.5 hours)
                next_notification = target_time + datetime.timedelta(minutes=150)
            
            # Sleep until next notification time
            sleep_seconds = (next_notification - datetime.datetime.now()).total_seconds()
            if sleep_seconds > 0:
                self.log_message(f"Next sunscreen reminder scheduled for {next_notification.strftime('%H:%M:%S')}")
                
                # Wait until notification time or until stop event is set
                if self.stop_notifications.wait(timeout=sleep_seconds):
                    break
                
                # Send notification if we still have applications to do
                if self.data["sunscreen_applications"] < 3:
                    self.show_notification(
                        title="Sunscreen Reminder",
                        message=f"Time to apply sunscreen! ({self.data['sunscreen_applications']}/3 applications)",
                        timeout=10
                    )
                    self.log_message("Sunscreen reminder notification sent")
            else:
                # If sleep_seconds is negative, wait a minute and recalculate
                time.sleep(60)
    
    def show_notification(self, title, message, timeout=10):
        """Show a system notification"""
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Daily Health Tracker",
                timeout=timeout
            )
        except Exception as e:
            self.log_message(f"Error showing notification: {str(e)}")
            
            # Fallback notification using tkinter
            self.root.attributes('-topmost', True)
            notification_window = tk.Toplevel(self.root)
            notification_window.title(title)
            notification_window.geometry("300x100")
            notification_window.attributes('-topmost', True)
            
            label = ttk.Label(notification_window, text=message, wraplength=280)
            label.pack(pady=20)
            
            def close_notification():
                notification_window.destroy()
                self.root.attributes('-topmost', False)
            
            notification_window.after(timeout * 1000, close_notification)
            
            # Center the notification
            notification_window.update_idletasks()
            width = notification_window.winfo_width()
            height = notification_window.winfo_height()
            x = (notification_window.winfo_screenwidth() // 2) - (width // 2)
            y = (notification_window.winfo_screenheight() // 2) - (height // 2)
            notification_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    
    def create_widgets(self):
        """Create and arrange all UI widgets"""
        main_frame = ttk.Frame(self.root, padding="20 20 20 20", style="TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_label = ttk.Label(main_frame, text="Daily Health Tracker", style="Header.TLabel")
        header_label.pack(pady=(0, 20))
        
        # Date display
        self.date_label = ttk.Label(main_frame, text=f"Date: {self.today}")
        self.date_label.pack(pady=(0, 10))
        
        # Creatine Section
        creatine_frame = ttk.Frame(main_frame)
        creatine_frame.pack(fill=tk.X, pady=10)
        
        creatine_label = ttk.Label(creatine_frame, text="Creatine")
        creatine_label.pack(side=tk.LEFT)
        
        self.creatine_var = tk.BooleanVar(value=self.data["creatine_taken"])
        self.creatine_check = ttk.Checkbutton(
            creatine_frame, 
            text="Taken", 
            variable=self.creatine_var,
            command=self.toggle_creatine
        )
        self.creatine_check.pack(side=tk.RIGHT)
        
        # Water Section
        water_frame = ttk.Frame(main_frame)
        water_frame.pack(fill=tk.X, pady=10)
        
        water_label = ttk.Label(water_frame, text="Water Bottles")
        water_label.pack(side=tk.LEFT)
        
        self.water_count_label = ttk.Label(
            water_frame, 
            text=f"{self.data['water_bottles']}/6", 
            style="Counter.TLabel"
        )
        self.water_count_label.pack(side=tk.RIGHT)
        
        # Water Progress Bar
        self.water_progress = ttk.Progressbar(
            main_frame, 
            orient=tk.HORIZONTAL, 
            length=360, 
            mode='determinate',
            maximum=6
        )
        self.water_progress.pack(pady=(0, 10))
        
        # Water Button
        self.water_button = ttk.Button(
            main_frame,
            text="+ Add Water Bottle",
            command=self.add_water_bottle
        )
        self.water_button.pack(pady=(0, 10))
        
        # Sunscreen Section
        sunscreen_frame = ttk.Frame(main_frame)
        sunscreen_frame.pack(fill=tk.X, pady=10)
        
        sunscreen_label = ttk.Label(sunscreen_frame, text="Sunscreen Applications")
        sunscreen_label.pack(side=tk.LEFT)
        
        self.sunscreen_count_label = ttk.Label(
            sunscreen_frame, 
            text=f"{self.data['sunscreen_applications']}/3", 
            style="Counter.TLabel"
        )
        self.sunscreen_count_label.pack(side=tk.RIGHT)
        
        # Sunscreen Progress Bar
        self.sunscreen_progress = ttk.Progressbar(
            main_frame, 
            orient=tk.HORIZONTAL, 
            length=360, 
            mode='determinate',
            maximum=3
        )
        self.sunscreen_progress.pack(pady=(0, 10))
        
        # Sunscreen Button
        self.sunscreen_button = ttk.Button(
            main_frame,
            text="+ Add Sunscreen Application",
            command=self.add_sunscreen_application
        )
        self.sunscreen_button.pack(pady=(0, 10))
        
        # Status message
        self.status_label = ttk.Label(main_frame, text="")
        self.status_label.pack(pady=10)
    
    def toggle_creatine(self):
        """Handle creatine checkbox toggle"""
        new_state = self.creatine_var.get()
        self.data["creatine_taken"] = new_state
        self.save_data()
        
        if new_state:
            self.log_message("Creatine taken")
            self.status_label.config(text="✅ Creatine marked as taken!")
        else:
            self.log_message("Creatine marked as not taken")
            self.status_label.config(text="Creatine marked as not taken")
        
        # Clear status after 3 seconds
        self.root.after(3000, lambda: self.status_label.config(text=""))
    
    def add_water_bottle(self):
        """Increment water bottle count"""
        if self.data["water_bottles"] < 6:
            self.data["water_bottles"] += 1
            self.save_data()
            self.log_message(f"Water bottle added. Total: {self.data['water_bottles']}/6")
            self.update_ui()
            
            if self.data["water_bottles"] == 6:
                self.status_label.config(text="🎉 Daily water goal achieved!")
            else:
                self.status_label.config(text=f"Added water bottle #{self.data['water_bottles']}")
            
            # Clear status after 3 seconds
            self.root.after(3000, lambda: self.status_label.config(text=""))
    
    def add_sunscreen_application(self):
        """Increment sunscreen application count"""
        if self.data["sunscreen_applications"] < 3:
            self.data["sunscreen_applications"] += 1
            self.save_data()
            self.log_message(f"Sunscreen applied. Total: {self.data['sunscreen_applications']}/3")
            self.update_ui()
            
            if self.data["sunscreen_applications"] == 3:
                self.status_label.config(text="🎉 Daily sunscreen goal achieved!")
            else:
                self.status_label.config(text=f"Added sunscreen application #{self.data['sunscreen_applications']}")
            
            # Clear status after 3 seconds
            self.root.after(3000, lambda: self.status_label.config(text=""))
    
    def update_ui(self):
        """Update UI elements to reflect current data"""
        self.date_label.config(text=f"Date: {self.today}")
        self.creatine_var.set(self.data["creatine_taken"])
        
        self.water_count_label.config(text=f"{self.data['water_bottles']}/6")
        self.water_progress["value"] = self.data["water_bottles"]
        
        self.sunscreen_count_label.config(text=f"{self.data['sunscreen_applications']}/3")
        self.sunscreen_progress["value"] = self.data["sunscreen_applications"]
        
        # Update button states
        if self.data["water_bottles"] >= 6:
            self.water_button.config(state="disabled")
        else:
            self.water_button.config(state="normal")
            
        if self.data["sunscreen_applications"] >= 3:
            self.sunscreen_button.config(state="disabled")
        else:
            self.sunscreen_button.config(state="normal")


def setup_requirements():
    """Check and install required packages"""
    try:
        import plyer
    except ImportError:
        print("Installing required package: plyer")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "plyer"])
            print("Successfully installed plyer")
        except Exception as e:
            print(f"Error installing plyer: {str(e)}")
            print("Please install it manually by running: pip install plyer")


def setup_autostart():
    """Create a shortcut or script to run the application at startup"""
    try:
        app_path = os.path.abspath(__file__)
        
        if os.name == 'nt':  # Windows
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "DailyHealthTracker", 0, winreg.REG_SZ, f'pythonw "{app_path}"')
            winreg.CloseKey(key)
            print("Added to Windows startup")
            return True
        elif os.name == 'posix':  # macOS or Linux
            home = str(Path.home())
            # For macOS
            if os.path.exists(f"{home}/Library"):
                plist_dir = f"{home}/Library/LaunchAgents"
                if not os.path.exists(plist_dir):
                    os.makedirs(plist_dir)
                plist_path = f"{plist_dir}/com.user.dailyhealthtracker.plist"
                
                plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.dailyhealthtracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>{app_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
                
                with open(plist_path, 'w') as f:
                    f.write(plist_content)
                
                os.system(f"chmod 644 {plist_path}")
                print("Added to macOS startup")
                return True
            # For Linux
            else:
                autostart_dir = f"{home}/.config/autostart"
                if not os.path.exists(autostart_dir):
                    os.makedirs(autostart_dir)
                desktop_file = f"{autostart_dir}/dailyhealthtracker.desktop"
                
                desktop_content = f"""[Desktop Entry]
Type=Application
Name=Daily Health Tracker
Exec=python3 {app_path}
Terminal=false
X-GNOME-Autostart-enabled=true
"""
                
                with open(desktop_file, 'w') as f:
                    f.write(desktop_content)
                
                os.system(f"chmod +x {desktop_file}")
                print("Added to Linux startup")
                return True
        
        return False
    except Exception as e:
        print(f"Error setting up autostart: {str(e)}")
        return False


if __name__ == "__main__":
    # Check and install requirements
    setup_requirements()
    
    # Try to set up autostart if not already set
    setup_autostart()
    
    # Start the application
    root = tk.Tk()
    app = DailyTrackerApp(root)
    root.mainloop()
