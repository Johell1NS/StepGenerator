#!/usr/bin/env python3
"""
StepMania Generator v3.0 (Simplified Orchestrator)
Orchestra la pipeline di generazione chart per StepMania partendo da un file .sm esistente.

Workflow:
1. Seleziona un file .sm esistente (creato/gestito con ArrowVortex).
2. Analizza l'audio corrispondente (audio_analyzer.py).
3. Esegue gli script di generazione livelli (Easy, Medium, Hard).
4. Esegue script di post-processing e grafica.

Questo script NON modifica timing, BPM o offset del file originale.
Si limita a iniettare le note generate dagli script di livello.
"""

import os
import sys
import glob
import subprocess
import re

# Configurazione Percorsi
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
SONGS_FOLDER = os.path.join(ROOT_DIR, "songs")

def find_sm_file():
    """Trova il file SM nella cartella songs chiedendo all'utente."""
    # Cerca file .sm in songs e sottocartelle immediate
    sm_files = []
    
    # Ricerca in songs/
    sm_files.extend(glob.glob(os.path.join(SONGS_FOLDER, "*.sm")))
    
    # Ricerca in sottocartelle di songs/ (es. songs/Group/Song.sm)
    for item in os.listdir(SONGS_FOLDER):
        item_path = os.path.join(SONGS_FOLDER, item)
        if os.path.isdir(item_path):
            sm_files.extend(glob.glob(os.path.join(item_path, "*.sm")))
            
    sm_files = sorted(sm_files)
    
    if not sm_files:
        print(f"❌ Nessun file .sm trovato in '{SONGS_FOLDER}'.")
        print("ℹ️  Crea prima il file con ArrowVortex o assicurati che sia nella cartella songs.")
        return None
    
    print("\n📄 File SM disponibili:")
    print("-" * 60)
    for idx, sm_file in enumerate(sm_files, 1):
        # Mostra percorso relativo a songs per brevità
        rel_path = os.path.relpath(sm_file, SONGS_FOLDER)
        print(f"   {idx}. {rel_path}")
    print("-" * 60)
    
    while True:
        try:
            choice = input("👉 Seleziona il numero del file da processare (0 per uscire): ")
            choice_num = int(choice)
            if choice_num == 0:
                return None
            if 1 <= choice_num <= len(sm_files):
                selected = sm_files[choice_num - 1]
                print(f"✅ Selezionato: {selected}")
                return selected
            else:
                print("❌ Numero non valido.")
        except ValueError:
            print("❌ Inserisci un numero valido.")

def get_music_filename(sm_path):
    """Legge il tag #MUSIC dal file .sm."""
    try:
        with open(sm_path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r"#MUSIC:([^;]*);", content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    except Exception as e:
        print(f"⚠️  Errore lettura #MUSIC da .sm: {e}")
        return None

def find_audio_file(sm_path, music_filename):
    """Cerca il file audio basandosi sul path del .sm e il tag #MUSIC."""
    if not music_filename:
        return None
        
    sm_dir = os.path.dirname(sm_path)
    
    # 1. Cerca nella stessa cartella del .sm
    local_path = os.path.join(sm_dir, music_filename)
    if os.path.exists(local_path):
        return local_path
        
    # 2. Cerca nella root di songs (fallback legacy)
    root_song_path = os.path.join(SONGS_FOLDER, music_filename)
    if os.path.exists(root_song_path):
        return root_song_path
        
    # 3. Cerca ricorsivamente in songs (disperato)
    for root, dirs, files in os.walk(SONGS_FOLDER):
        if music_filename in files:
            return os.path.join(root, music_filename)
            
    return None

def main():
    print("🚀 StepMania Generator v3.0 - Orchestrator Mode")
    print(f"📂 Working Directory: {ROOT_DIR}")
    
    # 1. Identifica File SM Target
    sm_path = None
    
    # Controllo argomenti da riga di comando
    for arg in sys.argv:
        if arg.lower().endswith(".sm") and os.path.exists(arg):
            sm_path = arg
            break
            
    if not sm_path:
        sm_path = find_sm_file()
        
    if not sm_path:
        print("👋 Nessun file selezionato. Uscita.")
        sys.exit(0)
        
    # 2. Identifica File Audio
    music_filename = get_music_filename(sm_path)
    if not music_filename:
        print("❌ Tag #MUSIC non trovato o vuoto nel file .sm.")
        sys.exit(1)
        
    audio_path = find_audio_file(sm_path, music_filename)
    if not audio_path:
        print(f"❌ File audio '{music_filename}' non trovato.")
        print("ℹ️  Verifica che il file audio sia nella stessa cartella del file .sm.")
        sys.exit(1)
        
    print(f"🎵 Audio: {os.path.basename(audio_path)}")
    print(f"📄 Chart: {os.path.basename(sm_path)}")
    
    # 3. Esegui Pipeline
    skip_analysis = "--skip-analysis" in sys.argv
    
    # PULIZIA PRELIMINARE DEL FILE SM
    # Rimuoviamo vecchie chart e normalizziamo l'header per evitare corruzioni
    print("\n🧹 [0/4] Normalizzazione File SM...")
    try:
        with open(sm_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Trova l'inizio delle note
        # Cerchiamo il primo #NOTES: per separare l'header
        match = re.search(r'(?=#NOTES:)', content, re.IGNORECASE)
        if match:
            header = content[:match.start()].strip()
            # Se ci sono note dopo, vengono rimosse.
            print("   ⚠️  Rimosse chart pre-esistenti (saranno rigenerate).")
        else:
            # Nessuna nota trovata, assumiamo sia tutto header
            header = content.strip()

        # Pulizia Header da commenti spuri (es. //-------)
        # Rimuoviamo righe che iniziano con // per evitare che i tag finiscano dopo i separatori
        lines = header.split('\n')
        header = '\n'.join([L for L in lines if not L.strip().startswith('//')]).strip()
            
        # --- AUTO-FIX METADATA (Restored Logic) ---
        # Helper per trovare tag nell'header corrente
        def get_tag_val(tag, text):
            m = re.search(fr"#{tag}:([^;]*);", text, re.IGNORECASE)
            return m.group(1).strip() if m else None

        def set_tag_val(tag, val, text):
            # Se esiste il tag (anche vuoto), sostituisci il valore
            if re.search(fr"#{tag}:", text, re.IGNORECASE):
                return re.sub(fr"#{tag}:[^;]*;", f"#{tag}:{val};", text, flags=re.IGNORECASE)
            else:
                # Se non esiste, aggiungi alla fine
                return text.strip() + f"\n#{tag}:{val};"

        # 1. Recupero/Analisi TITLE e ARTIST
        curr_title = get_tag_val("TITLE", header)
        curr_artist = get_tag_val("ARTIST", header)
        curr_music = get_tag_val("MUSIC", header)
        
        new_title = curr_title
        new_artist = curr_artist

        # Se mancano o sono invalidi, calcolali dal filename
        if not curr_title or curr_title.lower() == "unknown" or not curr_artist:
            print("   ⚠️  Metadata mancanti o incompleti. Tentativo di ripristino automatico...")
            
            base_name = ""
            if curr_music:
                base_name = os.path.splitext(curr_music)[0]
            else:
                base_name = os.path.splitext(os.path.basename(sm_path))[0]
            
            parts = base_name.split(' - ')
            calc_title = base_name
            calc_artist = "Unknown"
            
            if len(parts) >= 2:
                calc_title = parts[0].strip()
                calc_artist = parts[1].strip()
            
            if not curr_title or curr_title.lower() == "unknown":
                new_title = calc_title
                header = set_tag_val("TITLE", new_title, header)
                print(f"      🔹 Title set to: {new_title}")
                
            if not curr_artist:
                new_artist = calc_artist
                header = set_tag_val("ARTIST", new_artist, header)
                print(f"      🔹 Artist set to: {new_artist}")

        # 2. Lista Completa Tag Standard con Default

        # Questi tag DEVONO esserci nel file .sm per compatibilità totale
        default_tags = {
            "TITLE": new_title if new_title else "",
            "SUBTITLE": "",
            "ARTIST": new_artist if new_artist else "Unknown",
            "TITLETRANSLIT": "",
            "SUBTITLETRANSLIT": "",
            "ARTISTTRANSLIT": "",
            "GENRE": "",
            "CREDIT": "StepGenerator",
            "MUSIC": os.path.basename(audio_path) if audio_path else "",
            "BANNER": "",
            "BACKGROUND": "",
            "LYRICSPATH": "",
            "CDTITLE": "",
            "SAMPLESTART": "20.000", # Default sicuro
            "SAMPLELENGTH": "15.000",
            "SELECTABLE": "YES",
            "OFFSET": "0.000",
            "BPMS": "0.000=120.000", # Fallback se manca
            "STOPS": "",
            "DELAYS": "",
            "WARPS": "",
            "TIMESIGNATURES": "0.000=4=4",
            "TICKCOUNTS": "0.000=4",
            "COMBOS": "0.000=1",
            "SPEEDS": "0.000=1.000=0.000=0",
            "SCROLLS": "0.000=1.000",
            "FAKES": "",
            "LABELS": "0.000=Song Start",
            "BGCHANGES": "",
            "FGCHANGES": ""
        }

        # 3. Applica Tag Mancanti
        for tag, default_val in default_tags.items():
            curr_val = get_tag_val(tag, header)
            
            if curr_val is None:
                # Se manca del tutto, aggiungilo
                header = set_tag_val(tag, default_val, header)
            elif curr_val == "" and tag in ["CREDIT", "SELECTABLE", "TIMESIGNATURES", "TICKCOUNTS", "COMBOS", "SPEEDS", "SCROLLS", "LABELS", "SAMPLESTART", "SAMPLELENGTH"]:
                # Se c'è ma è vuoto, e abbiamo un default utile, mettilo
                header = set_tag_val(tag, default_val, header)

        # Fix specifico SampleStart (se era presente ma 0)
        curr_sample = get_tag_val("SAMPLESTART", header)
        try:
            if float(curr_sample) <= 0.001:
                 header = set_tag_val("SAMPLESTART", "20.000", header)
                 print(f"      🔹 SampleStart fixed to: 20.000")
        except:
             pass

        # Fix specifico SampleLength (se era presente ma 0)
        curr_len = get_tag_val("SAMPLELENGTH", header)
        try:
            if not curr_len or float(curr_len) <= 0.001:
                 header = set_tag_val("SAMPLELENGTH", "15.000", header)
                 print(f"      🔹 SampleLength fixed to: 15.000")
        except:
             pass

        # ------------------------------------------

        # Assicuriamoci che l'header termini correttamente
        if not header.endswith(';') and not header.strip() == "":
             header += ";"
             
        # Riscriviamo il file con solo l'header pulito e fixato
        with open(sm_path, 'w', encoding='utf-8') as f:
            f.write(header + "\n")
            
        print("   ✅ Header normalizzato e corretto.")
        
    except Exception as e:
        print(f"   ❌ Errore durante la normalizzazione: {e}")
        # Non blocchiamo, proviamo a continuare
    
    # A. Audio Analysis
    if not skip_analysis:
        print("\n🎧 [1/4] Esecuzione Analisi Audio...")
        analyzer_script = os.path.join(SRC_DIR, "audio_analyzer.py")
        if os.path.exists(analyzer_script):
            try:
                subprocess.run([sys.executable, analyzer_script, audio_path, sm_path], check=True)
            except subprocess.CalledProcessError as e:
                print(f"❌ Errore analisi audio: {e}")
                sys.exit(1)
        else:
            print(f"❌ Script mancante: {analyzer_script}")
            sys.exit(1)
    else:
        print("\n⏭️  [1/4] Skipping Audio Analysis (Using existing analysis_data.json)")
        if not os.path.exists("analysis_data.json"):
            print("⚠️  Warning: analysis_data.json non trovato! Gli script successivi potrebbero fallire.")

    # B. Level Generation
    print("\n🎹 [2/4] Generazione Livelli...")
    levels = [
        {
            "name": "Easy",
            "folder": os.path.join(ROOT_DIR, "1 easy"),
            "scripts": ["easy_4th.py", "easy_8th.py", "easy_jump.py", "easy_hold.py"]
        },
        {
            "name": "Medium",
            "folder": os.path.join(ROOT_DIR, "2 medium"),
            "scripts": ["medium_4th.py", "medium_8th.py", "medium_jump.py", "medium_hold.py"]
        },
        {
            "name": "Hard",
            "folder": os.path.join(ROOT_DIR, "3 hard"),
            "scripts": ["hard_4th.py", "hard_8th.py", "hard_jump.py", "hard_hold.py"]
        }
    ]
    
    analysis_file = "analysis_data.json"
    
    for level in levels:
        print(f"   🔹 Difficulty: {level['name']}")
        for script_name in level['scripts']:
            script_path = os.path.join(level['folder'], script_name)
            if os.path.exists(script_path):
                # print(f"      Running {script_name}...")
                try:
                    # Gli script di livello si aspettano: input_sm, output_sm, analysis_json
                    # Qui input e output sono lo stesso file (modifica in-place)
                    subprocess.run(
                        [sys.executable, script_path, sm_path, sm_path, analysis_file], 
                        check=True,
                        stdout=subprocess.DEVNULL, # Riduciamo il rumore in console
                        stderr=subprocess.PIPE     # Catturiamo errori se ci sono
                    )
                    print(f"      ✅ {script_name}")
                except subprocess.CalledProcessError as e:
                    print(f"      ❌ Errore {script_name}: {e.stderr.decode().strip()}")
            else:
                # Silenzioso se lo script non esiste (magari non tutti i livelli hanno tutti gli script)
                pass

    # C. Post Processing
    print("\n✨ [3/4] Post-Processing...")
    tail_refiners = ["PP_mute.py", "PP_IntroEnd.py"]
    for script_name in tail_refiners:
        script_path = os.path.join(SRC_DIR, script_name)
        if os.path.exists(script_path):
            try:
                subprocess.run([sys.executable, script_path, sm_path, sm_path, analysis_file], check=True)
                print(f"   ✅ {script_name}")
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Errore {script_name}: {e}")

    # D. Graphics & Cleanup
    print("\n🖼️  [4/4] Grafica e Organizzazione...")
    
    # Grafica
    gfx_script = os.path.join(SRC_DIR, "add_grafic.py")
    if os.path.exists(gfx_script):
        try:
            print("   Running add_grafic.py...")
            subprocess.run([sys.executable, gfx_script, sm_path], check=True)
        except subprocess.CalledProcessError:
            print("   ⚠️  Warning: Errore generazione grafica (non critico).")
            
    # Azioni Finali
    final_script = os.path.join(SRC_DIR, "PP_azioniFinali.py")
    if os.path.exists(final_script):
        try:
            cmd = [sys.executable, final_script, sm_path]
            if skip_analysis:
                cmd.append("--preserve-json")
            subprocess.run(cmd, check=True)
            print("   ✅ Organizzazione finale completata.")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Errore azioni finali: {e}")
            
    print("\n✅✅✅ PIPELINE COMPLETATA CON SUCCESSO! ✅✅✅")
    print(f"File processato: {sm_path}")
    print("Ricordati di ricaricare le canzoni in StepMania!")

if __name__ == "__main__":
    main()
