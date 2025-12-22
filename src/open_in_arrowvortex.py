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

# Configurazione Colori Console
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
CONFIG_FILE = os.path.join(ROOT_DIR, "path_arrowvortex.txt")
ARROW_VORTEX_PATH = None

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            line = f.readline().strip()
            if line:
                # Rimuovi eventuali virgolette se l'utente le ha messe
                ARROW_VORTEX_PATH = line.replace('"', '').replace("'", "")
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
        print(f"\n{Colors.WARNING}⚠️  PERCORSO ARROWVORTEX MANCANTE{Colors.ENDC}")
        print("Per utilizzare questa funzione, devi indicare dove si trova ArrowVortex.")
        print(f"1. Apri il file {Colors.BOLD}path_arrowvortex.txt{Colors.ENDC} nella cartella principale.")
        print("2. Incolla il percorso completo dell'eseguibile.")
        print(f"\nEsempio di contenuto valido:\n{Colors.BLUE}C:\\Program Files\\ArrowVortex\\ArrowVortex.exe{Colors.ENDC}")
        input("\nPremi INVIO per tornare al menu...")
        return

    if not os.path.exists(ARROW_VORTEX_PATH):
        print(f"{Colors.FAIL}Errore: ArrowVortex non trovato.{Colors.ENDC}")
        print(f"Percorso letto: {ARROW_VORTEX_PATH}")
        print("Controlla che il percorso nel file 'path_arrowvortex.txt' sia corretto ed esista.")
        input("\nPremi INVIO per tornare al menu...")
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
            print(f"{Colors.FAIL}Errore: Tipo file non supportato.{Colors.ENDC}")
            return
            
    # --- INTERACTIVE MODE ---
    else:
        songs = find_songs()
        
        if not songs:
            print(f"{Colors.FAIL}Nessun file MP3 trovato nella cartella 'songs' (o sottocartelle).{Colors.ENDC}")
            input("\nPremi INVIO per tornare al menu...")
            return

        print(f"\n{Colors.HEADER}--- APRI CON ARROWVORTEX ---{Colors.ENDC}")
        print(f"{Colors.BLUE}Seleziona un brano da aprire o creare:{Colors.ENDC}")
        
        for i, song in enumerate(songs):
            status = " [SM Esistente]" if song['sm_path'] else " [Nuovo]"
            print(f"{i+1}. {song['name']}{Colors.GREEN}{status}{Colors.ENDC}")
            
        print("-" * 50)
        print("0. Annulla / Esci")

        try:
            choice_input = input(f"\n{Colors.BLUE}Inserisci il numero: {Colors.ENDC}")
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
            print(f"{Colors.FAIL}Scelta non valida.{Colors.ENDC}")
            return

    # --- COMMON PROCESS ---
    # --- PRE-ANALISI E GRAFICA IN BACKGROUND ---
    # Avvia l'analisi audio e la generazione grafica in background mentre l'utente lavora
    print(f"\n{Colors.BLUE}🔄 Avvio pre-analisi audio e ricerca grafica in background...{Colors.ENDC}")
    try:
        # Lancia l'analizzatore sul file audio (Genera analysis_data.json)
        audio_analyzer_path = os.path.join(SRC_DIR, "audio_analyzer.py")
        subprocess.Popen([sys.executable, audio_analyzer_path, mp3_path, "--pre-analyze"])
             
        # Lancia add_grafic.py se non ci sono già immagini (semplice check)
        song_dir = os.path.dirname(mp3_path)
        if not (os.path.exists(os.path.join(song_dir, "BG.png")) and os.path.exists(os.path.join(song_dir, "BN.png"))):
            # Passiamo il path dell'SM (che esista o no, lo script proverà a cercare)
            add_grafic_path = os.path.join(SRC_DIR, "add_grafic.py")
            subprocess.Popen([sys.executable, add_grafic_path, sm_path_for_generation])
    except Exception as e:
        print(f"{Colors.WARNING}Impossibile avviare processi background: {e}{Colors.ENDC}")
    # ---------------------------------

    print(f"Avvio ArrowVortex: {os.path.basename(target_file)}")
        
    # Launch ArrowVortex
    subprocess.Popen([ARROW_VORTEX_PATH, target_file])
        
    # Automation (Optional)
    if AUTOMATION_AVAILABLE:
        print(f"{Colors.BLUE}Attendo caricamento interfaccia per automazione (se possibile)...{Colors.ENDC}")
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
                time.sleep(1.0) # Aumentato tempo attesa dopo maximize

                # 1. Attiva Beat Tick (F3)
                print("Attivazione Beat Tick (F3)...")
                pyautogui.press('f3')
                time.sleep(0.2)
                    
                # 2. Invia Shortcut per Adjust Sync (Shift+S)
                print("Apertura Adjust Sync (Shift+S)...")
                pyautogui.hotkey('shift', 's')
                time.sleep(0.2)

                # 3. Invia Shortcut per Adjust Tempo (Shift+T)
                print("Apertura Adjust Tempo (Shift+T)...")
                pyautogui.hotkey('shift', 't')
                    
            except Exception as e:
                    print(f"{Colors.WARNING}Errore automazione finestre: {e}{Colors.ENDC}")
        
        print("\n" + "="*60)
        print(f"{Colors.BOLD}ISTRUZIONI:{Colors.ENDC}")
        print("1. Lavora su ArrowVortex (BPM, Offset, Note).")
        print("2. Salva il file (Ctrl+S).")
        print("3. Chiudi ArrowVortex.")
        print("="*60 + "\n")
        
        input(f"{Colors.BLUE}Premi INVIO quando hai finito per AVVIARE LA GENERAZIONE (o Ctrl+C per uscire)...{Colors.ENDC}")
        
        # Check if SM exists now
        if os.path.exists(sm_path_for_generation):
            print(f"\n{Colors.GREEN}File .sm rilevato. Avvio Pipeline...{Colors.ENDC}")
            try:
                # Dato che l'analisi è stata avviata in background, potremmo volerla saltare qui se è già finita.
                # Tuttavia, per sicurezza, stepmania_generator dovrebbe controllare se analysis_data.json esiste ed è valido.
                # Se l'analisi in background è ancora in corso, stepmania_generator potrebbe dover attendere o rifarla.
                # Per ora, aggiungiamo --skip-analysis se analysis_data.json esiste già.
                
                stepmania_generator_path = os.path.join(SRC_DIR, "stepmania_generator.py")
                cmd_pipeline = [sys.executable, stepmania_generator_path, "--from-sm", "--pipeline", sm_path_for_generation]
                
                song_dir = os.path.dirname(mp3_path)
                # Nota: Rimosso --skip-analysis per forzare l'aggiornamento della sync (ma usando la cache raw features)
                subprocess.run(cmd_pipeline, check=True)
            except subprocess.CalledProcessError as e:
                 print(f"{Colors.FAIL}Errore pipeline: {e}{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}File .sm non trovato. Generazione annullata.{Colors.ENDC}")
            input("Premi Invio...")

if __name__ == "__main__":
    main()
