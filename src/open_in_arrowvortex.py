import os
import subprocess
import sys
import time
import glob

# Try importing optional dependencies for automation
try:
    import pyautogui
    import ctypes
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False

# Console Color Configuration
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Dynamic Path for ArrowVortex
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
CONFIG_FILE = os.path.join(ROOT_DIR, "path.txt")
ARROW_VORTEX_PATH = None

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                raw_line = line.strip()
                clean_line = raw_line.replace('"', '').replace("'", "")
                
                # Look for the ArrowVortex executable
                if "arrowvortex" in clean_line.lower() and clean_line.lower().endswith(".exe"):
                    ARROW_VORTEX_PATH = clean_line
                    break
    except Exception:
        pass

def find_songs():
    """
    Finds all MP3 files in 'songs' directory (root and 1 level deep).
    Returns a list of dicts: {'name': display_name, 'mp3_path': full_path, 'sm_path': full_path_or_none}
    """
    songs_dir = os.path.join(ROOT_DIR, "songs")
    if not os.path.exists(songs_dir):
        # Fallback if structure is different
        songs_dir = os.path.join(os.getcwd(), "songs")
        
    if not os.path.exists(songs_dir):
        return []

    found_songs = []
    
    # 1. Check root of songs/
    for file in os.listdir(songs_dir):
        if file.lower().endswith(".mp3"):
            full_path = os.path.join(songs_dir, file)
            sm_path = os.path.splitext(full_path)[0] + ".sm"
            if not os.path.exists(sm_path): sm_path = None
            found_songs.append({
                'name': file,
                'mp3_path': full_path,
                'sm_path': sm_path
            })
            
    # 2. Check subdirectories
    for entry in os.scandir(songs_dir):
        if entry.is_dir():
            # Look for mp3 inside
            mp3s = glob.glob(os.path.join(entry.path, "*.mp3"))
            for mp3 in mp3s:
                sm_path = os.path.splitext(mp3)[0] + ".sm"
                if not os.path.exists(sm_path): sm_path = None
                
                # Display name: "Folder - File.mp3" or just "File.mp3" if matches folder
                display_name = os.path.basename(mp3)
                if entry.name != os.path.splitext(display_name)[0]:
                     display_name = f"{entry.name} / {display_name}"
                     
                found_songs.append({
                    'name': display_name,
                    'mp3_path': mp3,
                    'sm_path': sm_path
                })
    
    return found_songs

def main():
    if AUTOMATION_AVAILABLE:
        try:
            ctypes.windll.kernel32.SetConsoleTitleW("StepGenerator Helper Console")
        except: pass

    if not ARROW_VORTEX_PATH:
        print(f"\n{Colors.WARNING}⚠️  ARROWVORTEX PATH MISSING{Colors.ENDC}")
        print("To use this feature, you need to specify where ArrowVortex is located.")
        print(f"1. Open the {Colors.BOLD}path.txt{Colors.ENDC} file in the main folder.")
        print("2. Paste the full path to the ArrowVortex executable.")
        print("   (You can also add the FFmpeg path on a new line)")
        print(f"\nExample of valid content:\n{Colors.BLUE}C:\\Program Files\\ArrowVortex\\ArrowVortex.exe\nC:\\ffmpeg\\bin{Colors.ENDC}")
        input("\nPress ENTER to go back to the menu...")
        return

    if not os.path.exists(ARROW_VORTEX_PATH):
        print(f"{Colors.FAIL}Error: ArrowVortex not found.{Colors.ENDC}")
        print(f"Path read: {ARROW_VORTEX_PATH}")
        print("Check that the path in 'path.txt' is correct and exists.")
        input("\nPress ENTER to go back to the menu...")
        return

    # --- AUTO MODE (Argument provided) ---
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        if not os.path.exists(input_path):
            print(f"{Colors.FAIL}Errore: File non trovato: {input_path}{Colors.ENDC}")
            return
            
        if input_path.lower().endswith(".mp3"):
            mp3_path = input_path
            sm_path = os.path.splitext(mp3_path)[0] + ".sm"
            target_file = sm_path if os.path.exists(sm_path) else mp3_path
            sm_path_for_generation = sm_path
        elif input_path.lower().endswith(".sm"):
            sm_path = input_path
            mp3_path = os.path.splitext(sm_path)[0] + ".mp3"
            target_file = sm_path
            sm_path_for_generation = sm_path
        else:
            print(f"{Colors.FAIL}Error: Unsupported file type.{Colors.ENDC}")
            return
            
    # --- INTERACTIVE MODE ---
    else:
        songs = find_songs()
        
        if not songs:
            print(f"{Colors.FAIL}No MP3 files found in the 'songs' folder (or subfolders).{Colors.ENDC}")
            input("\nPress ENTER to go back to the menu...")
            return

        print(f"\n{Colors.HEADER}--- OPEN WITH ARROWVORTEX ---{Colors.ENDC}")
        print(f"{Colors.BLUE}Select a song to open or create:{Colors.ENDC}")
        
        for i, song in enumerate(songs):
            status = " [Existing SM]" if song['sm_path'] else " [New]"
            print(f"{i+1}. {song['name']}{Colors.GREEN}{status}{Colors.ENDC}")
            
        print("-" * 50)
        print("0. Cancel / Exit")

        try:
            choice_input = input(f"\n{Colors.BLUE}Enter number: {Colors.ENDC}")
            choice = int(choice_input)
            
            if choice == 0:
                return
                
            if choice < 1 or choice > len(songs):
                raise ValueError
                
            selected = songs[choice - 1]
            
            # Decide what file to open
            target_file = selected['sm_path'] if selected['sm_path'] else selected['mp3_path']
            mp3_path = selected['mp3_path']
            sm_path_for_generation = selected['sm_path'] if selected['sm_path'] else os.path.splitext(mp3_path)[0] + ".sm"
            
        except ValueError:
            print(f"{Colors.FAIL}Invalid choice.{Colors.ENDC}")
            return

    # --- COMMON PROCESS ---
    # --- PRE-ANALYSIS AND GRAPHICS IN BACKGROUND ---
    # Starts audio analysis and graphics generation in background while the user works
    print(f"\n{Colors.BLUE}🔄 Starting pre-analysis and graphics search in background...{Colors.ENDC}")
    try:
        # Launch analyzer on the audio file (Generates analysis_data.json)
        audio_analyzer_path = os.path.join(SRC_DIR, "audio_analyzer.py")
        subprocess.Popen([sys.executable, audio_analyzer_path, mp3_path, "--pre-analyze"])
             
        # Launch add_grafic.py if images don't already exist (simple check)
        song_dir = os.path.dirname(mp3_path)
        if not (os.path.exists(os.path.join(song_dir, "BG.png")) and os.path.exists(os.path.join(song_dir, "BN.png"))):
            # Pass the SM path (whether it exists or not, the script will try to search)
            add_grafic_path = os.path.join(SRC_DIR, "add_grafic.py")
            subprocess.Popen([sys.executable, add_grafic_path, sm_path_for_generation])
    except Exception as e:
        print(f"{Colors.WARNING}Unable to start background processes: {e}{Colors.ENDC}")
    # ---------------------------------

    print(f"Launching ArrowVortex: {os.path.basename(target_file)}")
        
    # Launch ArrowVortex
    subprocess.Popen([ARROW_VORTEX_PATH, target_file])
        
    # Automation (Optional)
    if AUTOMATION_AVAILABLE:
        print(f"{Colors.BLUE}Waiting for interface to load for automation (if possible)...{Colors.ENDC}")
        window = None
        for _ in range(20): # 10 seconds timeout
            try:
                all_windows = pyautogui.getAllWindows()
                for w in all_windows:
                    if "ArrowVortex" in w.title and "StepGenerator" not in w.title:
                        window = w
                        break
                if window: break
            except: pass
            time.sleep(0.5)
                
        if window:
            try:
                if not window.isActive: window.activate()
                time.sleep(0.5)
                if not window.isMaximized: window.maximize()
                time.sleep(1.0) # Increased wait time after maximize

                # 1. Enable Beat Tick (F3)
                print("Enabling Beat Tick (F3)...")
                pyautogui.press('f3')
                time.sleep(0.2)

                # 2. Send shortcut for Adjust Sync (Shift+S)
                print("Opening Adjust Sync (Shift+S)...")
                pyautogui.hotkey('shift', 's')
                time.sleep(0.2)

                # 3. Send shortcut for Adjust Tempo (Shift+T)
                print("Opening Adjust Tempo (Shift+T)...")
                pyautogui.hotkey('shift', 't')
                    
            except Exception as e:
                    print(f"{Colors.WARNING}Window automation error: {e}{Colors.ENDC}")
        
        print("\n" + "="*60)
        print(f"{Colors.BOLD}INSTRUCTIONS:{Colors.ENDC}")
        print("1. Work on ArrowVortex (BPM, Offset, Notes).")
        print("2. Save the file (Ctrl+S).")
        print("3. Close ArrowVortex.")
        print("="*60 + "\n")
        
        input(f"{Colors.BLUE}Press ENTER when done to START GENERATION (or Ctrl+C to exit)...{Colors.ENDC}")
        
        # Check if SM exists now
        if os.path.exists(sm_path_for_generation):
            print(f"\n{Colors.GREEN}.sm file detected. Starting Pipeline...{Colors.ENDC}")
            try:
                # Since analysis was started in background, we might want to skip it if already done.
                # However, for safety, stepmania_generator should check if analysis_data.json exists and is valid.
                # If background analysis is still running, stepmania_generator might need to wait or redo it.
                # For now, we could add --skip-analysis if analysis_data.json already exists.

                stepmania_generator_path = os.path.join(SRC_DIR, "stepmania_generator.py")
                cmd_pipeline = [sys.executable, stepmania_generator_path, "--from-sm", "--pipeline", sm_path_for_generation]

                song_dir = os.path.dirname(mp3_path)
                # Note: Removed --skip-analysis to force sync update (but using cached raw features)
                subprocess.run(cmd_pipeline, check=True)
            except subprocess.CalledProcessError as e:
                 print(f"{Colors.FAIL}Pipeline error: {e}{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}.sm file not found. Generation cancelled.{Colors.ENDC}")
            input("Press Enter...")

if __name__ == "__main__":
    main()
