#!/usr/bin/env python3
"""
StepMania Generator v2.2
Genera un file .sm basato sui dati di timing_data.json.
Corregge il formato .sm per compatibilità StepMania.
- Offset positivo: StepMania usa offset positivo = start time.
- Rimuove punto e virgola extra alla fine di BPMS e NOTES se non necessario.
- Assicura formato corretto delle note.

Pattern: 4th notes (frecce rosse).
- Downbeat (1/4): Jump (Sinistra + Destra) -> 1001
- Altri beat (2/4, 3/4, 4/4): Destra -> 0001
"""

import json
import os
import sys
import glob
import math
import subprocess
from pathlib import Path
import shutil

# Configurazione
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
SONGS_FOLDER = os.path.join(ROOT_DIR, "songs")
TIMING_DATA_FILE = "timing_data.json"

def load_timing_data():
    """Carica i dati di timing dal file JSON."""
    if not os.path.exists(TIMING_DATA_FILE):
        print(f"❌ Errore: File '{TIMING_DATA_FILE}' non trovato. Esegui prima il Beat Tester.")
        return None
    
    try:
        with open(TIMING_DATA_FILE, 'r') as f:
            data = json.load(f)
            # Verifica che ci siano i dati essenziali
            if data.get('offset') is None or not data.get('bpm_changes'):
                 print("❌ Errore: Dati di timing incompleti (manca offset o bpm_changes).")
                 return None
            return data
    except Exception as e:
        print(f"❌ Errore nel caricamento di '{TIMING_DATA_FILE}': {e}")
        return None

def find_mp3_file():
    """Trova il file MP3 corrispondente nella cartella songs chiedendo all'utente."""
    mp3_files = sorted(glob.glob(os.path.join(SONGS_FOLDER, "*.mp3")))
    
    if not mp3_files:
        print(f"❌ Nessun file MP3 trovato nella cartella '{SONGS_FOLDER}'.")
        return None
    
    print("\n📀 File MP3 disponibili:")
    print("-" * 60)
    for idx, mp3_file in enumerate(mp3_files, 1):
        print(f"   {idx}. {os.path.basename(mp3_file)}")
    print("-" * 60)
    
    while True:
        try:
            choice = input("👉 Seleziona il numero del file da processare (0 per uscire): ")
            choice_num = int(choice)
            if choice_num == 0:
                return None
            if 1 <= choice_num <= len(mp3_files):
                selected = mp3_files[choice_num - 1]
                print(f"✅ Selezionato: {os.path.basename(selected)}")
                return selected
            else:
                print("❌ Numero non valido.")
        except ValueError:
            print("❌ Inserisci un numero valido.")

def get_audio_duration(file_path):
    """Ottiene la durata dell'audio in secondi."""
    try:
        import librosa
        return librosa.get_duration(path=file_path)
    except ImportError:
        print("⚠️  Libreria 'librosa' non trovata. Uso stima basata sulla dimensione file.")
        try:
            from mutagen.mp3 import MP3
            audio = MP3(file_path)
            return audio.info.length
        except ImportError:
             print("⚠️  Neanche 'mutagen' trovato. Genero 5 minuti di note.")
             return 300.0
    except Exception as e:
        print(f"⚠️  Errore nel calcolo durata: {e}. Genero 5 minuti.")
        return 300.0

def quantize_bpm_segments(timing_data):
    """
    Analizza i timestamp dei bpm_changes e calcola i BPM 'corretti'
    per far sì che ogni cambio avvenga su un beat intero (allineamento).
    
    Ritorna una lista di segmenti:
    [
      {
        'start_beat': float,
        'bpm': float,
        'duration_beats': int (o None per l'ultimo),
        'start_time': float
      }, ...
    ]
    """
    offset = timing_data['offset']
    # Ordina i cambi per tempo
    raw_changes = sorted(timing_data['bpm_changes'], key=lambda x: x[0])
    
    segments = []
    current_beat = 0.0
    
    # Se il primo cambio non è all'offset, c'è qualcosa di strano, ma gestiamo.
    # Assumiamo che raw_changes[0] sia il punto di partenza (offset).
    
    for i in range(len(raw_changes) - 1):
        t_start, bpm_est = raw_changes[i]
        t_end, _ = raw_changes[i+1]
        
        dt = t_end - t_start
        
        # Se i timestamp sono troppo vicini, salta (doppio tap involontario?)
        if dt < 0.1:
            continue
            
        # Calcola quanti beat "stimati" ci sono in questo intervallo
        est_beats = dt * (bpm_est / 60.0)
        
        # Arrotonda al beat intero più vicino (Quantizzazione)
        # Questo forza l'allineamento del prossimo segmento
        q_beats = round(est_beats)
        
        if q_beats < 1:
            q_beats = 1 # Evitiamo segmenti da 0 beat
            
        # Calcola il BPM esatto per coprire dt in esattamente q_beats
        corrected_bpm = (q_beats * 60.0) / dt
        
        segments.append({
            'start_beat': current_beat,
            'start_time': t_start,
            'duration_beats': int(q_beats),
            'bpm': corrected_bpm,
            'is_last': False
        })
        
        current_beat += q_beats
        
    # Ultimo segmento (fino alla fine del brano)
    last_t, last_bpm = raw_changes[-1]
    segments.append({
        'start_beat': current_beat,
        'start_time': last_t,
        'duration_beats': None, # Infinito (fino a fine song)
        'bpm': last_bpm, # Qui ci fidiamo dell'utente perché non abbiamo un punto finale
        'is_last': True
    })
    
    return segments

def generate_notes_and_bpms(segments, song_duration):
    """
    Genera la stringa delle note e la stringa BPMS basandosi sui segmenti quantizzati.
    """
    notes_measures = []
    bpms_str_list = []
    
    # Aggiungiamo i BPMS
    for seg in segments:
        bpms_str_list.append(f"{seg['start_beat']:.3f}={seg['bpm']:.3f}")
        
    # Generiamo le note segmento per segmento
    # Pattern:
    # Beat % 4 == 0 (Downbeat): 1001 (Jump)
    # Beat % 4 != 0: 0001 (Right)
    # In StepMania, le note sono raggruppate in misure (4 beat per misura standard 4/4).
    # Dobbiamo riempire le misure.
    
    current_measure_notes = []
    total_beats_generated = 0
    
    # Funzione helper per aggiungere una nota
    def add_note(beat_index):
        # beat_index è assoluto.
        # Determiniamo il tipo di nota basandoci sulla posizione nella misura (0,1,2,3)
        measure_pos = beat_index % 4
        if measure_pos == 0:
            return "1001" # Downbeat -> Jump
        else:
            return "0001" # Altri -> Right
            
    # Iteriamo sui segmenti
    for seg in segments:
        if not seg['is_last']:
            # Genera esattamente duration_beats
            for b in range(seg['duration_beats']):
                # beat assoluto = seg['start_beat'] + b
                # Ma per il pattern ci basta sapere se è downbeat globale o locale?
                # Generalmente globale.
                abs_beat = int(seg['start_beat']) + b
                note = add_note(abs_beat)
                current_measure_notes.append(note)
                
                if len(current_measure_notes) == 4:
                    notes_measures.append("\n".join(current_measure_notes))
                    current_measure_notes = []
        else:
            # Ultimo segmento: genera fino alla fine della canzone
            # Calcoliamo quanti beat mancano
            start_time = seg['start_time']
            
            print(f"DEBUG: Generating last segment. Song duration: {song_duration}, Start time: {start_time}")
            
            # MARGINE DI SICUREZZA: Sottraiamo 1.5 secondi dalla durata totale
            # per evitare di generare frecce proprio sul finale (sfumatura/silenzio)
            effective_duration = max(start_time, song_duration - 1.5)
            
            rem_time = effective_duration - start_time
            print(f"DEBUG: Effective duration: {effective_duration}, Rem time: {rem_time}")
            
            if rem_time > 0:
                rem_beats = rem_time * (seg['bpm'] / 60.0)
                # Usa floor invece di ceil per essere conservativi e restare dentro la durata
                num_beats = int(math.floor(rem_beats))
                
                print(f"DEBUG: Rem beats: {rem_beats}, Num beats: {num_beats}")
                
                # RIMOSSO MARGINE EXTRA: Aggiungiamo un po' di margine
                # num_beats += 8 
                
                start_beat = int(seg['start_beat'])
                for b in range(num_beats):
                    abs_beat = start_beat + b
                    note = add_note(abs_beat)
                    current_measure_notes.append(note)
                    
                    if len(current_measure_notes) == 4:
                        notes_measures.append("\n".join(current_measure_notes))
                        current_measure_notes = []
    
    # Se è rimasta una misura incompleta, riempiamola con 0000
    if current_measure_notes:
        while len(current_measure_notes) < 4:
            current_measure_notes.append("0000")
        notes_measures.append("\n".join(current_measure_notes))
        
    # Uniamo le misure con la virgola
    # NOTA: StepMania si aspetta ; alla fine della lista di note, ma la lista è dentro un tag #NOTES
    # che ha i suoi campi separati da :. L'ultimo campo sono le note.
    # Il terminatore ; va alla fine del tag #NOTES.
    full_notes_str = ",\n".join(notes_measures)
    
    # BPMS è un tag a sé stante
    bpms_str = ",\n".join(bpms_str_list)
    
    return full_notes_str, bpms_str

def create_sm_content(title, artist, music_file, offset, bpms_str, notes_str, stops_str=""):
    """
    Crea il contenuto del file .sm
    """
    # OFFSET: StepMania usa offset negativo per indicare che il Beat 0 avviene DOPO l'inizio del file.
    # Esempio: Se il primo beat è a 9.045s, OFFSET = -9.045.
    
    content = f"#TITLE:{title};\n"
    content += f"#SUBTITLE:;\n"
    content += f"#ARTIST:{artist};\n"
    content += f"#TITLETRANSLIT:;\n"
    content += f"#SUBTITLETRANSLIT:;\n"
    content += f"#ARTISTTRANSLIT:;\n"
    content += f"#GENRE:;\n"
    content += f"#CREDIT:StepGenerator;\n"
    content += f"#MUSIC:{music_file};\n"
    content += f"#BANNER:;\n"
    content += f"#BACKGROUND:;\n"
    content += f"#CDTITLE:;\n"
    # Imposta SAMPLESTART: offset (negativo) -> -offset è l'inizio effettivo dei beat.
    # Aggiungiamo 20 secondi per saltare l'intro e dare un'anteprima più significativa.
    sample_start = -offset + 20.0
    content += f"#SAMPLESTART:{max(0, sample_start):.3f};\n"
    content += f"#SAMPLELENGTH:15.000;\n"
    content += f"#SELECTABLE:YES;\n"
    
    # Usa l'offset passato direttamente (se positivo, scrive positivo).
    # Abbiamo verificato che per l'utente l'offset positivo funzionava nel .sm.
    content += f"#OFFSET:{offset:.3f};\n"
    
    content += f"#BPMS:{bpms_str};\n"
    content += f"#STOPS:{stops_str};\n"
    content += f"#DELAYS:;\n"
    content += f"#WARPS:;\n"
    content += f"#TIMESIGNATURES:0.000=4=4;\n"
    content += f"#TICKCOUNTS:0.000=4;\n"
    content += f"#COMBOS:0.000=1;\n"
    content += f"#SPEEDS:0.000=1.000=0.000=0;\n"
    content += f"#SCROLLS:0.000=1.000;\n"
    content += f"#FAKES:;\n"
    content += f"#LABELS:0.000=Song Start;\n"
    
    # NOTE DATA
    # Single - Medium
    content += f"\n//---------------dance-single - S_Medium----------------\n"
    content += f"#NOTES:\n"
    content += f"     dance-single:\n"
    content += f"     :\n"
    content += f"     S_Medium:\n"
    content += f"     Medium:\n"
    content += f"     5:\n"
    content += f"     0.500,0.500,0.500,0.500,0.500:\n"
    content += f"{notes_str}\n"
    content += f";\n"
    
    return content

def parse_sm_file(file_path):
    """
    Analizza un file .sm esistente per estrarre timing e metadati.
    Restituisce un dizionario con i dati.
    """
    import re
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Errore nella lettura del file .sm: {e}")
        return None
        
    data = {}
    
    # Helper per estrarre valori tag
    def get_tag(tag_name, default=""):
        match = re.search(fr"#{tag_name}:([^;]*);", content, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else default

    data['title'] = get_tag('TITLE', 'Unknown')
    data['artist'] = get_tag('ARTIST', 'Unknown')
    data['music'] = get_tag('MUSIC', '')
    
    # --- AUTO-FIX METADATA ---
    # Se Title o Artist sono mancanti/unknown, prova a parsare il file audio
    if (not data['title'] or data['title'].lower() == 'unknown') and data['music']:
        music_file = data['music']
        # Rimuovi estensione
        base_name = os.path.splitext(music_file)[0]
        
        # Pattern atteso: "Titolo - Artista"
        parts = base_name.split(' - ')
        if len(parts) >= 2:
            data['title'] = parts[0].strip()
            data['artist'] = parts[1].strip()
            print(f"⚠️  Metadata aggiornati da filename: '{data['title']}' - '{data['artist']}'")
        else:
            # Fallback: usa tutto il nome file come titolo
            data['title'] = base_name
            print(f"⚠️  Usato nome file come titolo: '{data['title']}'")

    # Offset
    offset_str = get_tag('OFFSET', '0.0')
    try:
        data['offset'] = float(offset_str)
    except:
        data['offset'] = 0.0
        
    # BPMS
    bpms_str = get_tag('BPMS', '')
    data['bpms_raw'] = bpms_str
    
    # Parse BPMS into list of (beat, bpm)
    bpms_list = []
    if bpms_str:
        pairs = bpms_str.replace('\n', '').split(',')
        for p in pairs:
            if '=' in p:
                b, v = p.split('=')
                try:
                    bpms_list.append((float(b), float(v)))
                except:
                    pass
    data['bpms'] = sorted(bpms_list, key=lambda x: x[0])
    
    # STOPS
    stops_str = get_tag('STOPS', '')
    data['stops_raw'] = stops_str
    
    return data

def segments_from_sm_bpms(bpms_list, song_duration, offset):
    """
    Converte la lista di BPMS (beat, bpm) in segmenti per la generazione note.
    Stima la durata in beat di ogni segmento.
    """
    segments = []
    
    # Offset in secondi (di solito negativo = inizio prima del file, positivo = inizio dopo)
    # Se offset è negativo (es -0.5), il beat 0 è a 0.5s.
    # Tempo del beat B = -offset + (B * 60/BPM) (se BPM costante)
    
    # Calcoliamo il tempo di inizio di ogni segmento
    current_time = -offset
    
    for i in range(len(bpms_list) - 1):
        start_beat, bpm = bpms_list[i]
        next_beat, _ = bpms_list[i+1]
        
        duration_beats = next_beat - start_beat
        
        segments.append({
            'start_beat': start_beat,
            'bpm': bpm,
            'duration_beats': int(duration_beats), 
            'is_last': False,
            'start_time': current_time
        })
        
        # Advance time
        dt = duration_beats * (60.0 / bpm)
        current_time += dt
        
    # Ultimo segmento
    if bpms_list:
        last_beat, last_bpm = bpms_list[-1]
        segments.append({
            'start_beat': last_beat,
            'bpm': last_bpm,
            'duration_beats': None, # Infinito
            'is_last': True,
            'start_time': current_time
        })
        
    return segments

def generate_ssc_timing(timing_data, song_duration):
    """
    Genera i dati di timing per il formato .ssc usando WARPS e STOPS
    per mantenere il BPM originale e riallineare la griglia.
    """
    offset = timing_data['offset']
    raw_changes = sorted(timing_data['bpm_changes'], key=lambda x: x[0])
    
    bpms = []
    stops = []
    warps = []
    
    current_beat = 0.0
    current_time = offset
    
    # Aggiungi il primo BPM
    first_bpm = raw_changes[0][1]
    bpms.append(f"0.000={first_bpm:.3f}")
    
    for i in range(len(raw_changes) - 1):
        t_start, bpm = raw_changes[i]
        t_next, next_bpm = raw_changes[i+1]
        
        dt = t_next - t_start
        beats_in_segment = dt * (bpm / 60.0)
        
        # Beat teorico alla fine del segmento
        end_beat_theoretical = current_beat + beats_in_segment
        
        # Arrotondiamo al beat intero più vicino (Downbeat desiderato)
        target_beat = round(end_beat_theoretical)
        if target_beat <= current_beat:
             target_beat = math.ceil(current_beat + 0.1) # Avanza almeno un po'
             
        diff = target_beat - end_beat_theoretical
        
        # Aggiungi il cambio BPM per il PROSSIMO segmento al target beat
        # Nota: StepMania applica il nuovo BPM dal beat specificato
        bpms.append(f"{target_beat:.3f}={next_bpm:.3f}")
        
        if diff > 0.001:
            # Siamo in ritardo (Shortfall). Abbiamo fatto meno beat del previsto.
            # Dobbiamo SALTARE (WARP) la differenza per arrivare al target.
            # Warp inizia dove siamo arrivati (end_beat_theoretical) e dura 'diff'.
            warps.append(f"{end_beat_theoretical:.3f}={diff:.3f}")
            current_beat = target_beat
            
        elif diff < -0.001:
            # Siamo in anticipo (Overshoot). Abbiamo fatto più beat del previsto.
            # Dobbiamo ASPETTARE (STOP).
            # Lo stop deve avvenire al target beat.
            # Quanto tempo dobbiamo aspettare?
            # Tempo reale passato: dt
            # Tempo per arrivare al target: (target_beat - current_beat) * 60 / bpm
            time_to_target = (target_beat - current_beat) * (60.0 / bpm)
            stop_time = dt - time_to_target
            
            if stop_time > 0:
                stops.append(f"{target_beat:.3f}={stop_time:.3f}")
            
            current_beat = target_beat
            
        else:
            # Allineamento perfetto (raro)
            current_beat = end_beat_theoretical

        current_time = t_next

    return bpms, stops, warps

def create_ssc_content(title, artist, music_file, offset, bpms, stops, warps, notes_str):
    bpms_str = ",\n".join(bpms)
    stops_str = ",\n".join(stops)
    warps_str = ",\n".join(warps)
    
    # Note: Notes string is same format as .sm but header is different
    # Notes data in .ssc usually includes more metadata per chart
    
    # Simple SSC template
    ssc = f"""
#VERSION:0.83;
#TITLE:{title};
#ARTIST:{artist};
#MUSIC:{music_file};
#OFFSET:{offset:.3f};
#SAMPLESTART:{max(0, -offset + 20.0):.3f};
#SAMPLELENGTH:15.000;
#SELECTABLE:YES;
#BPMS:{bpms_str};
#STOPS:{stops_str};
#DELAYS:;
#WARPS:{warps_str};
#NOTEDATA:;
#CHARTNAME:StepGenerator;
#STEPSTYPE:dance-single;
#DESCRIPTION:S_Medium_SSC;
#DIFFICULTY:Medium;
#METER:5;
#RADARVALUES:0.500,0.500,0.500,0.500,0.500;
#CREDIT:StepGenerator;
#NOTES:
{notes_str}
;
"""
    return ssc

def extract_notes_from_sm(sm_path):
    with open(sm_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple regex to find the notes block
    # Looks for #NOTES: ... then 5 header fields ... then the notes data
    # The notes data ends with ;
    
    # Pattern: #NOTES:\s*([^:]+:){5}\s*([^;]+);
    # But SM header fields might contain colons? Usually newlines.
    
    # Easier: Find the last occurrence of #NOTES: (assuming only one chart for now, or the one we want is last/only)
    # Our generator creates only one chart.
    
    parts = content.split("#NOTES:")
    if len(parts) < 2:
        return None
    
    chart_block = parts[-1] # The last chart
    
    # Split by colon to skip headers
    # Header format:
    # Type:
    # Description:
    # Difficulty:
    # Meter:
    # Radar:
    # Notes Data;
    
    chart_parts = chart_block.split(":")
    if len(chart_parts) < 6:
        return None
        
    notes_data = chart_parts[-1].strip()
    if notes_data.endswith(';'):
        notes_data = notes_data[:-1]
        
    return notes_data.strip()

def find_sm_file():
    """Trova il file SM nella cartella songs chiedendo all'utente."""
    sm_files = sorted(glob.glob(os.path.join(SONGS_FOLDER, "*.sm")))
    
    if not sm_files:
        print(f"❌ Nessun file .sm trovato nella cartella '{SONGS_FOLDER}'.")
        return None
    
    print("\n📄 File SM disponibili:")
    print("-" * 60)
    for idx, sm_file in enumerate(sm_files, 1):
        print(f"   {idx}. {os.path.basename(sm_file)}")
    print("-" * 60)
    
    while True:
        try:
            choice = input("👉 Seleziona il numero del file da processare (0 per uscire): ")
            choice_num = int(choice)
            if choice_num == 0:
                return None
            if 1 <= choice_num <= len(sm_files):
                selected = sm_files[choice_num - 1]
                print(f"✅ Selezionato: {os.path.basename(selected)}")
                return selected
            else:
                print("❌ Numero non valido.")
        except ValueError:
            print("❌ Inserisci un numero valido.")

def main():
    mode_from_sm = "--from-sm" in sys.argv
    run_pipeline = "--pipeline" in sys.argv
    skip_analysis = "--skip-analysis" in sys.argv

    if mode_from_sm:
        print("🚀 Modalità: Generazione da file .sm esistente (ArrowVortex)")
        
        # Cerca se è stato passato un percorso file .sm tra gli argomenti
        sm_path = None
        for arg in sys.argv:
            if arg.lower().endswith(".sm") and os.path.exists(arg):
                sm_path = arg
                break
        
        if not sm_path:
            sm_path = find_sm_file()
            
        if not sm_path:
            sys.exit(0)
            
        # Parse SM
        sm_data = parse_sm_file(sm_path)
        if not sm_data:
            sys.exit(1)
            
        print(f"🎵 Canzone: {sm_data['title']} - {sm_data['artist']}")
        
        # Trova MP3
        mp3_filename = sm_data['music']
        
        # STRATEGIA DI RICERCA MP3 (Ispirata al Backup 11 + Supporto Sottocartelle)
        
        # 1. Cerca nella cartella songs root (Come Backup 11)
        path_backup_11 = os.path.join(SONGS_FOLDER, mp3_filename)
        
        # 2. Cerca nella stessa cartella del file .sm (Per le nuove sottocartelle)
        sm_dir = os.path.dirname(sm_path)
        path_local = os.path.join(sm_dir, mp3_filename)
        
        mp3_path = None
        
        if os.path.exists(path_backup_11):
            mp3_path = path_backup_11
            print(f"✅ File audio trovato (Legacy): {mp3_path}")
        elif os.path.exists(path_local):
            mp3_path = path_local
            print(f"✅ File audio trovato (Locale): {mp3_path}")
        else:
            print(f"⚠️  File audio '{mp3_filename}' non trovato nelle posizioni standard. Cerco ricorsivamente...")
            # 3. Ricerca ricorsiva in songs
            found = False
            for root, dirs, files in os.walk(SONGS_FOLDER):
                if mp3_filename in files:
                    mp3_path = os.path.join(root, mp3_filename)
                    print(f"✅ Trovato ricorsivamente: {mp3_path}")
                    found = True
                    break
            
            if not found:
                 print(f"❌ Impossibile trovare il file audio: {mp3_filename}")
                 mp3_path = None

        # Durata
        if mp3_path and os.path.exists(mp3_path):
            duration = get_audio_duration(mp3_path)
        else:
            print("⚠️  Audio non trovato, uso durata di default (300s)")
            duration = 300.0
        print(f"⏱️  Durata audio: {duration:.2f}s")
        
        # Segmenti
        print("🔄 Calcolo segmenti da BPMS...")
        segments = segments_from_sm_bpms(sm_data['bpms'], duration, sm_data['offset'])
        
        # Genera Note
        print("🎹 Generazione note (Scheletro)...")
        notes_str, _ = generate_notes_and_bpms(segments, duration)
        
        # Ricrea SM content preservando tutto tranne le note
        new_sm_content = create_sm_content(
            sm_data['title'],
            sm_data['artist'],
            sm_data['music'],
            sm_data['offset'],
            sm_data['bpms_raw'],
            notes_str,
            sm_data['stops_raw']
        )
        
        # Sovrascrivi file
        try:
            with open(sm_path, 'w', encoding='utf-8') as f:
                f.write(new_sm_content)
            print(f"✅ File SM aggiornato: {sm_path}")
        except Exception as e:
            print(f"❌ Errore salvataggio SM: {e}")
            sys.exit(1)
            
        # Pipeline Refiners
        if run_pipeline:
            print("\n🚀 Avvio pipeline di raffinamento...")
            
            # 1. Audio Analysis
            analysis_ok = True
            if not skip_analysis:
                print("🎧 Analisi audio in corso (audio_analyzer.py)...")
                if mp3_path and os.path.exists(mp3_path):
                    audio_analyzer_path = os.path.join(SRC_DIR, "audio_analyzer.py")
                    if os.path.exists(audio_analyzer_path):
                        try:
                            subprocess.run([sys.executable, audio_analyzer_path, mp3_path, sm_path], check=True)
                        except subprocess.CalledProcessError as e:
                            print(f"   ⚠️  Errore nell'esecuzione di audio_analyzer.py: {e}")
                            analysis_ok = False
                    else:
                        print(f"   ⚠️  audio_analyzer.py non trovato in {SRC_DIR}!")
                        analysis_ok = False
                else:
                    print("❌ ERRORE: File audio mancante. Impossibile avviare analisi.")
                    analysis_ok = False
            else:
                print("🎧 Skipping Audio Analysis (Using existing analysis_data.json)...")
                if not os.path.exists("analysis_data.json"):
                     analysis_ok = False

            # 2. Refiners (New Modular Structure)
            if analysis_ok:
                print("   Running Refiners for all difficulties...")
                
                # Define the pipeline levels
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
            else:
                print("⛔ Skipping Refiners (Analisi fallita o dati mancanti).")
                levels = []
            
            current_sm = sm_path
            
            for level in levels:
                print(f"\n   🟢 Generating {level['name']} Level...")
                folder = level['folder']
                for script_name in level['scripts']:
                    script_path = os.path.join(folder, script_name)
                    if os.path.exists(script_path):
                        print(f"      Running {script_path}...")
                        try:
                            subprocess.run([sys.executable, script_path, current_sm, current_sm, "analysis_data.json"], check=True)
                        except subprocess.CalledProcessError as e:
                            print(f"      ⚠️  Errore nell'esecuzione di {script_name}: {e}")
                    else:
                        print(f"      ⚠️  Script {script_path} non trovato!")

            # 3. Post-Processing Refiners (Common)
            tail_refiners = ["PP_mute.py", "PP_IntroEnd.py"]
            for script_name in tail_refiners:
                script_path = os.path.join(SRC_DIR, script_name)
                if os.path.exists(script_path):
                    print(f"   Running {script_name}...")
                    try:
                        subprocess.run([sys.executable, script_path, current_sm, current_sm, "analysis_data.json"], check=True)
                    except subprocess.CalledProcessError as e:
                        print(f"   ⚠️  Errore nell'esecuzione di {script_name}: {e}")
                else:
                    print(f"   ⚠️  Script {script_path} non trovato, salto.")
            
            print(f"✅ Pipeline completata sul file: {sm_path}")
            
            # 2.5 Auto-Increase Difficulty (Optional now, as we generate all levels explicitly)
            # print("\n📈 Aumento automatico difficoltà (Medium -> Medium 2)...")
            # modifier_script = "modifica_steps.py"
            # if os.path.exists(modifier_script):
            #     try:
            #         subprocess.run([sys.executable, modifier_script, "--auto-increase", current_sm, "--analysis-file", "analysis_data.json"], check=True)
            #     except subprocess.CalledProcessError as e:
            #         print(f"   ⚠️  Errore durante l'aumento difficoltà: {e}")
            
            # Grafica (BG.png / BN.png)
            # Nota: Potrebbe essere già stato avviato in background da open_in_arrowvortex.py
            print("\n�️  Generazione grafica (BG.png / BN.png)...")
            gfx_script_name = "add_grafic.py"
            gfx_script_path = os.path.join(SRC_DIR, gfx_script_name)
            if os.path.exists(gfx_script_path):
                try:
                    subprocess.run([sys.executable, gfx_script_path, sm_path], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"   ⚠️  Errore durante la generazione grafica: {e}")
            else:
                print(f"   ⚠️  Script {gfx_script_path} non trovato, salto.")

            # AZIONI FINALI (Organizzazione cartelle)
            print("\n Esecuzione azioni finali (Organizzazione cartelle)...")
            final_script_name = "PP_azioniFinali.py"
            final_script_path = os.path.join(SRC_DIR, final_script_name)
            if os.path.exists(final_script_path):
                try:
                    cmd_final = [sys.executable, final_script_path, sm_path]
                    if skip_analysis:
                        cmd_final.append("--preserve-json")
                    subprocess.run(cmd_final, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"❌ Errore durante le azioni finali: {e}")
            else:
                 print(f"⚠️  Script {final_script_path} non trovato.")
            
        return

    # 1. Carica dati (Modalità Legacy / JSON)
    timing_data = load_timing_data()
    if not timing_data:
        sys.exit(1)
        
    # 2. Trova MP3
    mp3_path = None
    
    # Se abbiamo il nome file nei dati di timing, proviamo a usarlo
    if timing_data and timing_data.get('audio_file'):
        candidate_path = os.path.join(SONGS_FOLDER, timing_data['audio_file'])
        if os.path.exists(candidate_path):
            print(f"✅ Trovato file audio dai dati di calibrazione: {timing_data['audio_file']}")
            mp3_path = candidate_path
        else:
            print(f"⚠️  Il file '{timing_data['audio_file']}' indicato in timing_data.json non esiste.")

    if not mp3_path:
        mp3_path = find_mp3_file()
    
    if not mp3_path:
        sys.exit(1)
        
    mp3_filename = os.path.basename(mp3_path)
    base_name = os.path.splitext(mp3_filename)[0]
    # Estrai Artista e Titolo dal nome file (formato "Titolo - Artista.mp3" o viceversa?)
    # Assumiamo "Titolo - Artista" come da esempio utente "Incoscienti Giovani - Achille Lauro"
    name_parts = base_name.split(" - ")
    if len(name_parts) >= 2:
        title = name_parts[0]
        artist = name_parts[1]
    else:
        title = name_parts[0]
        artist = "Unknown"
        
    print(f"🎵 Processando: {title} - {artist}")
    
    # 3. Calcola durata
    duration = get_audio_duration(mp3_path)
    print(f"⏱️  Durata audio: {duration:.2f}s")
    
    # 4. Quantizza Segmenti BPM (Correzione Drift)
    print("🔄 Analisi e correzione timing (Quantizzazione BPM)...")
    segments = quantize_bpm_segments(timing_data)
    for idx, seg in enumerate(segments):
        end_info = f"{seg['duration_beats']} beats" if seg['duration_beats'] else "Inf"
        print(f"   Seg {idx}: Beat {seg['start_beat']:.1f} -> {seg['bpm']:.3f} BPM ({end_info})")

    # 5. Genera Note e Stringa BPM
    notes_str, bpms_str = generate_notes_and_bpms(segments, duration)
    
    # 7. Genera contenuto SM
    print("📝 Generazione file .sm (con correzione BPM)...")
    # Passiamo l'offset NEGATIVO. StepMania richiede offset negativo se il beat 0 è dopo l'inizio del file.
    # Esempio: Primo beat a 9.045s -> Offset -9.045.
    sm_content = create_sm_content(title, artist, mp3_filename, -timing_data['offset'], bpms_str, notes_str)
    
    # 7b. Genera contenuto SSC (con Warps/Stops)
    print("📝 Generazione file .ssc (con Warps/Stops per sync perfetto)...")
    ssc_bpms, ssc_stops, ssc_warps = generate_ssc_timing(timing_data, duration)
    # Rigeneriamo le note per SSC basandoci sulla griglia "perfetta" (integer beats)
    # In realtà, le note generate precedentemente sono basate su segmenti quantizzati (interi).
    # Per SSC, i segmenti sono "Stretti" o "Allungati" da Warp/Stop ma il conteggio beat è intero.
    # Quindi possiamo riusare notes_str?
    # notes_str è generato da 'generate_notes_and_bpms' che usa 'segments'.
    # 'segments' usa 'q_beats' (rounded).
    # Nella logica SSC, usiamo 'target_beat' (rounded).
    # Quindi il numero di beat è lo stesso!
    # Possiamo riusare notes_str.
    
    # Passiamo offset NEGATIVO anche qui.
    ssc_content = create_ssc_content(title, artist, mp3_filename, -timing_data['offset'], ssc_bpms, ssc_stops, ssc_warps, notes_str)
    
    # 8. Salva file SM
    sm_filename = os.path.join(SONGS_FOLDER, f"{base_name}.sm")
    try:
        with open(sm_filename, 'w', encoding='utf-8') as f:
            f.write(sm_content)
        print(f"✅ File SM salvato: {sm_filename}")
    except Exception as e:
        print(f"❌ Errore nel salvataggio SM: {e}")

    # 8b. Salva file SSC
    ssc_filename = os.path.join(SONGS_FOLDER, f"{base_name}.ssc")
    try:
        with open(ssc_filename, 'w', encoding='utf-8') as f:
            f.write(ssc_content)
        print(f"✅ File SSC salvato: {ssc_filename}")
        print("ℹ️  Il file .ssc usa WARPS/STOPS per rispettare esattamente i tuoi BPM.")
        print("    StepMania userà preferibilmente il file .ssc se presente.")
    except Exception as e:
        print(f"❌ Errore nel salvataggio SSC: {e}")

    print("⚠️  IMPORTANTE: Ricarica le canzoni in StepMania (Options -> Reload Songs).")
    
    # 9. Esegui Pipeline (se richiesto)
    if "--pipeline" in sys.argv:
        print("\n🚀 Avvio pipeline di raffinamento...")
        
        # Variabile per il processo di background (grafica)
        gfx_process = None
        
        # 9a. Esegui Audio Analyzer (CRITICO: Aggiorna analysis_data.json per la canzone corrente)
        if not skip_analysis:
            print("🎧 Analisi audio in corso (audio_analyzer.py)...")
            audio_analyzer_path = os.path.join(SRC_DIR, "audio_analyzer.py")
            if os.path.exists(audio_analyzer_path):
                try:
                    # mp3_path è il path assoluto o relativo corretto trovato all'inizio
                    # sm_filename è il path relativo (es. songs/Title.sm)
                    subprocess.run([sys.executable, audio_analyzer_path, mp3_path, sm_filename], check=True)
                    
                    # --- START BACKGROUND GRAPHICS SEARCH HERE ---
                    # Avviamo add_grafic.py in background subito dopo l'analisi audio.
                    # L'utente deve ancora fare ArrowVortex, ma intanto cerchiamo le immagini.
                    # Passiamo sm_filename (path relativo o assoluto del file SM creato preliminarmente).
                    print("\n🖼️  Avvio ricerca grafica in background (mentre prosegui con ArrowVortex)...")
                    gfx_script_path = os.path.join(SRC_DIR, "add_grafic.py")
                    if os.path.exists(gfx_script_path):
                        try:
                            # Usiamo Popen per non bloccare
                            gfx_process = subprocess.Popen([sys.executable, gfx_script_path, sm_filename])
                        except Exception as ex_gfx:
                            print(f"⚠️  Impossibile avviare add_grafic in background: {ex_gfx}")
                    else:
                        print(f"⚠️  Script {gfx_script_path} non trovato, salto grafica background.")
                    # ---------------------------------------------
                    
                except subprocess.CalledProcessError as e:
                    print(f"   ⚠️  Errore nell'esecuzione di audio_analyzer.py: {e}")
            else:
                print(f"   ⚠️  {audio_analyzer_path} non trovato! Impossibile aggiornare i dati di analisi.")
        else:
            print("🎧 Skipping Audio Analysis (Using existing analysis_data.json)...")

        # --- ARROWVORTEX WAIT ---
        # Aggiungiamo qui l'attesa per ArrowVortex se siamo in pipeline mode.
        # Questo permette all'utente di lavorare su ArrowVortex mentre la grafica scarica in background.
        print("============================================================")
        print("ISTRUZIONI ARROWVORTEX:")
        print("1. Apri il file .sm generato con ArrowVortex.")
        print("2. Trova BPM e Offset corretti.")
        print("3. Salva il file .sm (File -> Save o Ctrl+S).")
        print("4. Chiudi ArrowVortex.")
        print("============================================================")
        input("\nPremi INVIO quando hai salvato e chiuso ArrowVortex per CONTINUARE con la generazione...")
        # ------------------------

        # 2. Refiners (New Modular Structure - Pipeline Mode)
        print("   Running Refiners for all difficulties...")
        
        # Define the pipeline levels
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
        
        current_sm = sm_filename
        
        for level in levels:
            print(f"\n   🟢 Generating {level['name']} Level...")
            folder = level['folder']
            for script_name in level['scripts']:
                script_path = os.path.join(folder, script_name)
                if os.path.exists(script_path):
                    print(f"      Running {script_path}...")
                    try:
                        subprocess.run([sys.executable, script_path, current_sm, current_sm, "analysis_data.json"], check=True)
                    except subprocess.CalledProcessError as e:
                        print(f"      ⚠️  Errore nell'esecuzione di {script_name}: {e}")
                else:
                    print(f"      ⚠️  Script {script_path} non trovato!")

        # 3. Post-Processing Refiners (Common)
        tail_refiners = ["PP_mute.py", "PP_IntroEnd.py"]
        for script_name in tail_refiners:
            script_path = os.path.join(SRC_DIR, script_name)
            if os.path.exists(script_path):
                print(f"   Running {script_name}...")
                try:
                    subprocess.run([sys.executable, script_path, current_sm, current_sm, "analysis_data.json"], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"   ⚠️  Errore nell'esecuzione di {script_name}: {e}")
            else:
                print(f"   ⚠️  Script {script_path} non trovato, salto.")
        
        print(f"✅ Pipeline completata sul file: {sm_path}")
            
        return

    # 1. Carica dati (Modalità Legacy / JSON)
    timing_data = load_timing_data()
    if not timing_data:
        sys.exit(1)
        
    # 2. Trova MP3
    mp3_path = None
    
    # Se abbiamo il nome file nei dati di timing, proviamo a usarlo
    if timing_data and timing_data.get('audio_file'):
        candidate_path = os.path.join(SONGS_FOLDER, timing_data['audio_file'])
        if os.path.exists(candidate_path):
            print(f"✅ Trovato file audio dai dati di calibrazione: {timing_data['audio_file']}")
            mp3_path = candidate_path
        else:
            print(f"⚠️  Il file '{timing_data['audio_file']}' indicato in timing_data.json non esiste.")

    if not mp3_path:
        mp3_path = find_mp3_file()
    
    if not mp3_path:
        sys.exit(1)
        
    mp3_filename = os.path.basename(mp3_path)
    base_name = os.path.splitext(mp3_filename)[0]
    # Estrai Artista e Titolo dal nome file (formato "Titolo - Artista.mp3" o viceversa?)
    # Assumiamo "Titolo - Artista" come da esempio utente "Incoscienti Giovani - Achille Lauro"
    name_parts = base_name.split(" - ")
    if len(name_parts) >= 2:
        title = name_parts[0]
        artist = name_parts[1]
    else:
        title = name_parts[0]
        artist = "Unknown"
        
    print(f"🎵 Processando: {title} - {artist}")
    
    # 3. Calcola durata
    duration = get_audio_duration(mp3_path)
    print(f"⏱️  Durata audio: {duration:.2f}s")
    
    # 4. Quantizza Segmenti BPM (Correzione Drift)
    print("🔄 Analisi e correzione timing (Quantizzazione BPM)...")
    segments = quantize_bpm_segments(timing_data)
    for idx, seg in enumerate(segments):
        end_info = f"{seg['duration_beats']} beats" if seg['duration_beats'] else "Inf"
        print(f"   Seg {idx}: Beat {seg['start_beat']:.1f} -> {seg['bpm']:.3f} BPM ({end_info})")

    # 5. Genera Note e Stringa BPM
    notes_str, bpms_str = generate_notes_and_bpms(segments, duration)
    
    # 7. Genera contenuto SM
    print("📝 Generazione file .sm (con correzione BPM)...")
    # Passiamo l'offset NEGATIVO. StepMania richiede offset negativo se il beat 0 è dopo l'inizio del file.
    # Esempio: Primo beat a 9.045s -> Offset -9.045.
    sm_content = create_sm_content(title, artist, mp3_filename, -timing_data['offset'], bpms_str, notes_str)
    
    # 7b. Genera contenuto SSC (con Warps/Stops)
    print("📝 Generazione file .ssc (con Warps/Stops per sync perfetto)...")
    ssc_bpms, ssc_stops, ssc_warps = generate_ssc_timing(timing_data, duration)
    # Rigeneriamo le note per SSC basandoci sulla griglia "perfetta" (integer beats)
    # In realtà, le note generate precedentemente sono basate su segmenti quantizzati (interi).
    # Per SSC, i segmenti sono "Stretti" o "Allungati" da Warp/Stop ma il conteggio beat è intero.
    # Quindi possiamo riusare notes_str?
    # notes_str è generato da 'generate_notes_and_bpms' che usa 'segments'.
    # 'segments' usa 'q_beats' (rounded).
    # Nella logica SSC, usiamo 'target_beat' (rounded).
    # Quindi il numero di beat è lo stesso!
    # Possiamo riusare notes_str.
    
    # Passiamo offset NEGATIVO anche qui.
    ssc_content = create_ssc_content(title, artist, mp3_filename, -timing_data['offset'], ssc_bpms, ssc_stops, ssc_warps, notes_str)
    
    # 8. Salva file SM
    sm_filename = os.path.join(SONGS_FOLDER, f"{base_name}.sm")
    try:
        with open(sm_filename, 'w', encoding='utf-8') as f:
            f.write(sm_content)
        print(f"✅ File SM salvato: {sm_filename}")
    except Exception as e:
        print(f"❌ Errore nel salvataggio SM: {e}")

    # 8b. Salva file SSC
    ssc_filename = os.path.join(SONGS_FOLDER, f"{base_name}.ssc")
    try:
        with open(ssc_filename, 'w', encoding='utf-8') as f:
            f.write(ssc_content)
        print(f"✅ File SSC salvato: {ssc_filename}")
        print("ℹ️  Il file .ssc usa WARPS/STOPS per rispettare esattamente i tuoi BPM.")
        print("    StepMania userà preferibilmente il file .ssc se presente.")
    except Exception as e:
        print(f"❌ Errore nel salvataggio SSC: {e}")

    print("⚠️  IMPORTANTE: Ricarica le canzoni in StepMania (Options -> Reload Songs).")
    
    # 9. Esegui Pipeline (se richiesto)
    if "--pipeline" in sys.argv:
        print("\n🚀 Avvio pipeline di raffinamento...")
        
        # 9a. Esegui Audio Analyzer (CRITICO: Aggiorna analysis_data.json per la canzone corrente)
        if not skip_analysis:
            print("🎧 Analisi audio in corso (audio_analyzer.py)...")
            if os.path.exists("audio_analyzer.py"):
                try:
                    # mp3_path è il path assoluto o relativo corretto trovato all'inizio
                    # sm_filename è il path relativo (es. songs/Title.sm)
                    subprocess.run([sys.executable, "audio_analyzer.py", mp3_path, sm_filename], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"   ⚠️  Errore nell'esecuzione di audio_analyzer.py: {e}")
            else:
                print("   ⚠️  audio_analyzer.py non trovato! Impossibile aggiornare i dati di analisi.")
        else:
            print("🎧 Skipping Audio Analysis (Using existing analysis_data.json)...")

        # 2. Refiners (New Modular Structure)
        print("   Running Refiners for all difficulties...")
        
        # Define the pipeline levels
        levels = [
            {
                "name": "Easy",
                "folder": "1 easy",
                "scripts": ["easy_4th.py", "easy_8th.py", "easy_jump.py", "easy_hold.py"]
            },
            {
                "name": "Medium",
                "folder": "2 medium",
                "scripts": ["medium_4th.py", "medium_8th.py", "medium_jump.py", "medium_hold.py"]
            },
            {
                "name": "Hard",
                "folder": "3 hard",
                "scripts": ["hard_4th.py", "hard_8th.py", "hard_jump.py", "hard_hold.py"]
            }
        ]
        
        current_sm = sm_filename
        
        for level in levels:
            print(f"\n   🟢 Generating {level['name']} Level...")
            folder = level['folder']
            for script_name in level['scripts']:
                script_path = os.path.join(folder, script_name)
                if os.path.exists(script_path):
                    print(f"      Running {script_path}...")
                    try:
                        subprocess.run([sys.executable, script_path, current_sm, current_sm, "analysis_data.json"], check=True)
                    except subprocess.CalledProcessError as e:
                        print(f"      ⚠️  Errore nell'esecuzione di {script_name}: {e}")
                else:
                    print(f"      ⚠️  Script {script_path} non trovato!")

        # 3. Post-Processing Refiners (Common)
        tail_refiners = ["PP_mute.py", "PP_IntroEnd.py"]
        for script in tail_refiners:
            if os.path.exists(script):
                print(f"   Running {script}...")
                try:
                    subprocess.run([sys.executable, script, current_sm, current_sm, "analysis_data.json"], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"   ⚠️  Errore nell'esecuzione di {script}: {e}")
            else:
                print(f"   ⚠️  Script {script} non trovato, salto.")
        
        print(f"✅ Pipeline completata sul file: {sm_filename}")
        
        # 10. SINCRONIZZAZIONE SSC (Importante!)
        # I refiner hanno modificato il file .sm. Il file .ssc ha ancora le note vecchie.
        # Dobbiamo leggere le note dal .sm raffinato e aggiornare il .ssc.
        print("\n🔄 Sincronizzazione note raffinato nel file .ssc...")
        try:
            with open(sm_filename, 'r', encoding='utf-8') as f:
                sm_full_content = f.read()
            
            # Estrazione Note (Logica semplificata basata sulla struttura standard SM)
            # Cerchiamo l'ultimo blocco #NOTES:
            parts = sm_full_content.split("#NOTES:")
            if len(parts) >= 2:
                last_chart = parts[-1]
                # Splittiamo per ':' (ci sono 5 header prima dei dati)
                chart_sections = last_chart.split(":")
                if len(chart_sections) >= 6:
                    refined_notes_raw = chart_sections[-1].strip()
                    # Rimuoviamo il punto e virgola finale
                    if refined_notes_raw.endswith(';'):
                        refined_notes = refined_notes_raw[:-1].strip()
                    else:
                        refined_notes = refined_notes_raw
                    
                    # Rigeneriamo il contenuto SSC con le nuove note
                    ssc_content_updated = create_ssc_content(title, artist, mp3_filename, -timing_data['offset'], ssc_bpms, ssc_stops, ssc_warps, refined_notes)
                    
                    with open(ssc_filename, 'w', encoding='utf-8') as f:
                        f.write(ssc_content_updated)
                    print(f"✅ File SSC aggiornato con le note raffinate!")
                else:
                    print("⚠️  Impossibile parsare le note dal file .sm (struttura inattesa).")
            else:
                print("⚠️  Impossibile trovare blocchi #NOTES nel file .sm.")
                
        except Exception as e:
            print(f"❌ Errore durante la sincronizzazione SSC: {e}")

        # 11. Auto-Increase Difficulty
        print("\n📈 Aumento automatico difficoltà (Medium -> Medium 2)...")
        modifier_script = "modifica_steps.py"
        if os.path.exists(modifier_script):
            try:
                subprocess.run([sys.executable, modifier_script, "--auto-increase", current_sm], check=True)
            except subprocess.CalledProcessError as e:
                print(f"   ⚠️  Errore durante l'aumento difficoltà: {e}")
        else:
             print(f"⚠️  Script {modifier_script} non trovato.")

        # --- WAIT FOR BACKGROUND GRAPHICS ---
        # Prima di muovere i file, assicuriamoci che la grafica sia pronta.
        if gfx_process:
            if gfx_process.poll() is None:
                print("\n⏳ Attendo completamento download grafica in background...")
                gfx_process.wait()
            print("✅ Grafica pronta (o processo terminato).")
        # ------------------------------------

        # 12. AZIONI FINALI (Organizzazione cartelle)
        print("\n📂 Esecuzione azioni finali (Organizzazione cartelle)...")
        final_script = "PP_azioniFinali.py"
        if os.path.exists(final_script):
            try:
                subprocess.run([sys.executable, final_script, sm_filename], check=True)
            except subprocess.CalledProcessError as e:
                print(f"❌ Errore durante le azioni finali: {e}")
        else:
             print(f"⚠️  Script {final_script} non trovato.")

if __name__ == "__main__":
    main()













