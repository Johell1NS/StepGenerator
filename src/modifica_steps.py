import os
import sys
import json
import re
import random
import subprocess
import numpy as np
import glob
import traceback

# Configurazione Colori
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"{Colors.FAIL}Errore lettura JSON {path}: {e}{Colors.ENDC}")
        return None

def get_energy_at_beat(beat_idx, analysis_data):
    """
    Calcola l'energia (Onset Strength) in un determinato beat (anche frazionario).
    """
    if not analysis_data or 'raw_features' not in analysis_data:
        return 0.0

    raw = analysis_data['raw_features']
    onset_env = np.array(raw.get('onset_env', []))
    if len(onset_env) == 0: return 0.0

    sr = raw['metadata']['sr']
    hop_length = raw['metadata']['hop_length']
    
    # beats_times deve essere un array di float (tempi)
    beats_data = analysis_data.get('beats', [])
    if not beats_data: return 0.0

    if isinstance(beats_data[0], dict):
        beats_times = np.array([b['time'] for b in beats_data])
    else:
        beats_times = np.array(beats_data)
    
    # 1. Trova il tempo assoluto del beat_idx
    if beat_idx < 0: beat_idx = 0
    
    max_beat = len(beats_times) - 1
    
    if beat_idx <= max_beat:
        time_sec = np.interp(beat_idx, np.arange(len(beats_times)), beats_times)
    else:
        # Estrapola
        last_time = beats_times[-1]
        if len(beats_times) > 1:
            avg_dur = (beats_times[-1] - beats_times[0]) / max_beat
        else:
            avg_dur = 0.5 
        time_sec = last_time + (beat_idx - max_beat) * avg_dur

    # 2. Converti tempo in frame index
    frame_idx = int(time_sec * sr / hop_length)
    
    # 3. Leggi valore
    if frame_idx < 0: frame_idx = 0
    if frame_idx >= len(onset_env): frame_idx = len(onset_env) - 1
    
    return float(onset_env[frame_idx])

class StepModifier:
    def __init__(self):
        # Determine root dir relative to this script (src/modifica_steps.py -> root)
        src_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(src_dir)
        self.songs_root = os.path.join(root_dir, "songs")

    def find_valid_songs(self):
        """
        Cerca ricorsivamente in songs/ tutte le cartelle che contengono:
        1. Almeno un file .sm
        2. Un file analysis_data.json
        """
        valid_entries = []
        
        # Walk through directory
        for root, dirs, files in os.walk(self.songs_root):
            json_path = os.path.join(root, "analysis_data.json")
            if os.path.exists(json_path):
                # Cerca SM files
                sm_files = [f for f in files if f.lower().endswith('.sm')]
                for sm in sm_files:
                    valid_entries.append({
                        'folder': root,
                        'sm_file': sm,
                        'sm_path': os.path.join(root, sm),
                        'json_path': json_path
                    })
        return valid_entries

    def select_song_menu(self):
        entries = self.find_valid_songs()
        
        if not entries:
            print(f"{Colors.FAIL}Nessuna canzone valida trovata (SM + JSON richiesti).{Colors.ENDC}")
            return None

        print(f"\n{Colors.HEADER}--- SELEZIONA CANZONE DA MODIFICARE ---{Colors.ENDC}")
        for i, entry in enumerate(entries):
            folder_name = os.path.basename(entry['folder'])
            print(f"{i+1}. [{folder_name}] {entry['sm_file']}")
            
        print("-" * 40)
        print("0. Esci")

        try:
            choice = int(input(f"\n{Colors.BLUE}Scelta: {Colors.ENDC}"))
            if choice == 0: return None
            if 1 <= choice <= len(entries):
                return entries[choice - 1]
        except ValueError:
            pass
        return None

    def parse_charts_metadata(self, sm_path):
        """
        Estrae i metadati di tutte le chart nel file SM.
        Restituisce una lista di oggetti chart.
        """
        with open(sm_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Regex robusta per trovare blocchi #NOTES
        pattern = re.compile(r'#NOTES:(.*?);', re.DOTALL)
        matches = list(pattern.finditer(content))
        
        charts = []
        for i, m in enumerate(matches):
            block_content = m.group(1) # Contenuto dentro #NOTES:...;
            full_match_str = m.group(0)
            start_idx = m.start()
            end_idx = m.end()
            
            # Calcola posizione assoluta di note_data per sostituzione sicura
            # Cerca l'ultimo ':'
            last_colon_idx = block_content.rfind(':')
            if last_colon_idx == -1: continue # Non valido
            
            # Note data inizia dopo l'ultimo ':'
            note_data = block_content[last_colon_idx+1:]
            
            # Calcoliamo gli offset assoluti nel file
            # m.start() è l'inizio di #NOTES:...
            # len("#NOTES:") è 7
            # block_content inizia a m.start() + 7
            # note_data inizia a (m.start() + 7 + last_colon_idx + 1)
            # note_data finisce a m.end() - 1 (escluso il ;)
            
            note_data_start_abs = start_idx + 7 + last_colon_idx + 1
            note_data_end_abs = end_idx - 1
            
            # Parsing Metadata
            # Prendiamo tutto prima del note_data
            meta_str = block_content[:last_colon_idx]
            parts = [p.strip() for p in meta_str.split(':')]
            
            # Ci aspettiamo: type, desc, diff, meter, radar
            # Se ci sono più parti, desc potrebbe contenere ':'
            if len(parts) >= 5:
                chart_type = parts[0]
                radar = parts[-1]
                meter = parts[-2]
                difficulty = parts[-3]
                # Descrizione è tutto ciò che sta in mezzo
                desc = ":".join(parts[1:-3])
                
                charts.append({
                    'index': i,
                    'type': chart_type,
                    'description': desc,
                    'difficulty': difficulty,
                    'meter': meter,
                    'raw_content': full_match_str,
                    'note_data': note_data,
                    'note_data_start_abs': note_data_start_abs,
                    'note_data_end_abs': note_data_end_abs
                })
                
        return content, charts

    def select_difficulty_menu(self, charts):
        if not charts:
            print("Nessuna difficoltà trovata nel file SM.")
            return None

        print(f"\n{Colors.HEADER}--- SELEZIONA DIFFICOLTÀ ---{Colors.ENDC}")
        valid_charts = []
        
        for i, c in enumerate(charts):
            # Filtra solo dance-single per sicurezza?
            if "dance-single" in c['type']:
                print(f"{len(valid_charts)+1}. {c['difficulty']} (Meter: {c['meter']}) - {c['description']}")
                valid_charts.append(c)
        
        if not valid_charts:
            print("Nessuna chart 'dance-single' trovata.")
            return None
            
        print("-" * 40)
        print("0. Annulla")
        
        try:
            choice = int(input(f"\n{Colors.BLUE}Scelta: {Colors.ENDC}"))
            if choice == 0: return None
            if 1 <= choice <= len(valid_charts):
                return valid_charts[choice - 1]
        except ValueError:
            pass
        return None

    def parse_measures_from_string(self, note_data_str):
        measures_raw = note_data_str.split(',')
        measures = []
        for m in measures_raw:
            lines = [l.strip() for l in m.strip().split('\n') if l.strip()]
            # Rimuovi commenti //
            lines = [re.sub(r'//.*', '', l).strip() for l in lines]
            lines = [l for l in lines if l] # Rimuovi vuoti
            measures.append(lines)
        return measures

    def modify_steps(self, measures, analysis_data, is_increase, percentage):
        print(f"\n{Colors.BLUE}🔨 Elaborazione steps... (Mode: {'Increase' if is_increase else 'Decrease'} {int(percentage*100)}%){Colors.ENDC}")
        
        # Mappatura Beat Globale e Analisi
        flat_slots = [] 
        
        # Simulazione Holds Globale
        active_holds = [False] * 4 
        current_taps = 0
        
        for m_idx, measure in enumerate(measures):
            rows = len(measure)
            if rows == 0: continue
            
            for r_idx, row_str in enumerate(measure):
                beat_idx = m_idx * 4 + (r_idx / rows) * 4
                energy = get_energy_at_beat(beat_idx, analysis_data)
                
                row_clean = re.sub(r'[^01234M]', '0', row_str)
                if len(row_clean) < 4: row_clean = row_clean.ljust(4, '0')
                cols = list(row_clean)
                
                # Check Holds
                active_holds_count_before = sum(1 for x in active_holds if x)
                
                row_has_tap = False
                row_has_hold_head = False
                row_has_hold_tail = False
                
                for c in range(4):
                    char = cols[c]
                    if char == '1': row_has_tap = True
                    elif char == '2': 
                        active_holds[c] = True
                        row_has_hold_head = True
                    elif char == '3': 
                        active_holds[c] = False
                        row_has_hold_tail = True
                    elif char == '4': 
                        active_holds[c] = True # Roll as hold
                        row_has_hold_head = True

                # Conteggio input attivi in QUESTO momento (inclusi quelli appena iniziati)
                active_holds_count_now = sum(1 for x in active_holds if x)
                
                # Quanti tap ci sono in questa riga?
                taps_in_row = cols.count('1')
                current_taps += taps_in_row
                
                slot_info = {
                    'm_idx': m_idx,
                    'r_idx': r_idx,
                    'beat': beat_idx,
                    'energy': energy,
                    'cols': cols,
                    'row_has_tap': row_has_tap,
                    'row_has_hold_head': row_has_hold_head,
                    'row_has_hold_tail': row_has_hold_tail,
                    'active_holds_count': active_holds_count_before, # Holds attivi PROVENIENTI da righe prima
                    'taps_count': taps_in_row
                }
                flat_slots.append(slot_info)

        target_count = int(current_taps * percentage)
        print(f"   Note attuali (Tap): {current_taps}")
        print(f"   Target variazione: {target_count} note")
        
        changes_made = 0
        
        if is_increase:
            # --- INCREASE LOGIC ---
            # Cerca righe dove possiamo aggiungere note rispettando:
            # 1. Max 2 input totali (hold attivi + tap)
            # 2. Non aggiungere su teste/code di hold (per semplicità)
            
            # --- RE-IMPLEMENTAZIONE PIÙ SICURA PER INCREASE ---
            # Dobbiamo rifare il pass active_holds tracciando le colonne esatte
            
            # Reset simulazione
            active_holds_cols = [False] * 4
            refined_slots = []
            
            for m_idx, measure in enumerate(measures):
                rows = len(measure)
                if rows == 0: continue
                for r_idx, row_str in enumerate(measure):
                    beat_idx = m_idx * 4 + (r_idx / rows) * 4
                    energy = get_energy_at_beat(beat_idx, analysis_data)
                    row_clean = re.sub(r'[^01234M]', '0', row_str)
                    if len(row_clean) < 4: row_clean = row_clean.ljust(4, '0')
                    cols = list(row_clean)
                    
                    # Snapshot hold attivi PRIMA di questa riga
                    holds_here = list(active_holds_cols)
                    
                    # Update holds logic
                    row_is_complex = False
                    for c in range(4):
                        char = cols[c]
                        if char == '2' or char == '4': active_holds_cols[c] = True
                        elif char == '3': active_holds_cols[c] = False
                        
                        if char in ['2','3','4']: row_is_complex = True

                    # Calcola quanti input totali avremmo se non tocchiamo nulla
                    # Input = Taps ('1') + Holds Attivi ('True' in holds_here)
                    # Nota: se c'è un '1' su una colonna con hold attivo? (Impossible in valid SM usually)
                    
                    taps = cols.count('1')
                    active_h_count = sum(1 for x in holds_here if x)
                    total_inputs = taps + active_h_count
                    
                    refined_slots.append({
                        'cols': cols,
                        'energy': energy,
                        'total_inputs': total_inputs,
                        'holds_mask': holds_here, # Quali colonne sono occupate da hold passanti
                        'row_is_complex': row_is_complex # Se ha teste o code
                    })
            
            # Filtra candidati
            candidates = [s for s in refined_slots if not s['row_is_complex'] and s['total_inputs'] < 2]
            candidates.sort(key=lambda x: x['energy'], reverse=True)
            
            for s in candidates:
                if changes_made >= target_count: break
                
                # Cerca colonna libera
                # Libera = è '0' AND non è in holds_mask
                free_indices = [i for i, c in enumerate(s['cols']) if c == '0' and not s['holds_mask'][i]]
                
                if free_indices:
                    # Scegli a caso
                    idx = random.choice(free_indices)
                    s['cols'][idx] = '1'
                    changes_made += 1
                    
            # Ricostruisci direttamente
            final_measures = []
            slot_iter = iter(refined_slots)
            for m in measures:
                if not m: 
                    final_measures.append(m)
                    continue
                new_m = []
                for _ in range(len(m)):
                    s = next(slot_iter)
                    new_m.append("".join(s['cols']))
                final_measures.append(new_m)
                
            return final_measures

        else:
            # --- DECREASE LOGIC ---
            # Rimuovi Tap '1' più deboli che non sono su righe complesse (hold heads/tails)
            
            potential_remove = [
                s for s in flat_slots
                if s['row_has_tap'] and not s['row_has_hold_head'] and not s['row_has_hold_tail']
            ]
            
            # Ordina Energia CRESCENTE (Deboli prima)
            potential_remove.sort(key=lambda x: x['energy'])
            
            to_remove = potential_remove[:target_count]
            
            for s in to_remove:
                # Rimuovi tutti i tap in questa riga
                for c in range(4):
                    if s['cols'][c] == '1':
                        s['cols'][c] = '0'
                changes_made += 1
                
            # Ricostruzione
            final_measures = []
            slot_iter = iter(flat_slots)
            for m_idx, original_m in enumerate(measures):
                if len(original_m) == 0:
                    final_measures.append(original_m)
                    continue
                new_m = []
                for r_idx in range(len(original_m)):
                    s = next(slot_iter)
                    new_m.append("".join(s['cols']))
                final_measures.append(new_m)
                
            return final_measures

    def save_chart_overwrite(self, sm_path, original_content, chart_metadata, new_measures):
        print(f"Salvataggio (SOVRASCRITTURA) su: {sm_path}")
        print(f"Modifico chart: {chart_metadata['difficulty']} ({chart_metadata['description']})")
        
        # 1. Ricostruisci il blocco note data
        new_data_str = ""
        for i, m in enumerate(new_measures):
            new_data_str += "\n".join(m)
            if i < len(new_measures) - 1:
                new_data_str += ",\n"
        
        # 2. Sostituisci SOLO la parte di note data nel contenuto originale
        start = chart_metadata['note_data_start_abs']
        end = chart_metadata['note_data_end_abs']
        
        final_content = original_content[:start] + "\n" + new_data_str + original_content[end:]
        
        with open(sm_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        print(f"{Colors.GREEN}✅ File aggiornato con successo!{Colors.ENDC}")

    def run(self):
        # 1. Seleziona Canzone
        entry = self.select_song_menu()
        if not entry: return
        
        sm_path = entry['sm_path']
        json_path = entry['json_path']
        
        # 2. Carica Analisi
        analysis_data = load_json(json_path)
        if not analysis_data: return
        
        # 3. Parse SM per trovare difficoltà
        full_content, charts = self.parse_charts_metadata(sm_path)
        
        # 4. Seleziona Difficoltà
        selected_chart = self.select_difficulty_menu(charts)
        if not selected_chart: return
        
        # 5. Chiedi Azione (+/-)
        print(f"\n{Colors.HEADER}--- MODIFICA: {selected_chart['difficulty']} ---{Colors.ENDC}")
        print("1. Aumenta Difficoltà (+20% frecce)")
        print("2. Diminuisci Difficoltà (-20% frecce)")
        print("0. Annulla")
        
        try:
            choice = input(f"\n{Colors.BLUE}Scelta: {Colors.ENDC}")
            if choice == '0': return
            if choice not in ['1', '2']:
                print("Scelta non valida.")
                return
            
            is_increase = (choice == '1')
            
            # 6. Elabora
            measures = self.parse_measures_from_string(selected_chart['note_data'])
            new_measures = self.modify_steps(measures, analysis_data, is_increase, 0.20)
            
            # 7. Salva
            self.save_chart_overwrite(sm_path, full_content, selected_chart, new_measures)
            
        except Exception as e:
            print(f"{Colors.FAIL}Errore: {e}{Colors.ENDC}")
            traceback.print_exc()

if __name__ == "__main__":
    app = StepModifier()
    app.run()
