import os
import json
import re
import random
import numpy as np
import traceback

# Color Configuration
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
        print(f"{Colors.FAIL}JSON read error {path}: {e}{Colors.ENDC}")
        return None

def get_energy_at_beat(beat_idx, analysis_data):
    """
    Calculates energy (Onset Strength) at a given beat (including fractional).
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
            print(f"{Colors.FAIL}No valid song found (SM + JSON required).{Colors.ENDC}")
            return None

        print(f"\n{Colors.HEADER}--- SELECT SONG TO MODIFY ---{Colors.ENDC}")
        for i, entry in enumerate(entries):
            folder_name = os.path.basename(entry['folder'])
            print(f"{i+1}. [{folder_name}] {entry['sm_file']}")
            
        print("-" * 40)
        print("0. Exit")

        try:
            choice = int(input(f"\n{Colors.BLUE}Choice: {Colors.ENDC}"))
            if choice == 0: return None
            if 1 <= choice <= len(entries):
                return entries[choice - 1]
        except ValueError:
            pass
        return None

    def parse_charts_metadata(self, sm_path):
        """
        Extracts metadata for all charts in the SM file.
        Returns a list of chart objects.
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
                _ = parts[-1]
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
            print("No difficulty found in SM file.")
            return None

        print(f"\n{Colors.HEADER}--- SELECT DIFFICULTY ---{Colors.ENDC}")
        valid_charts = []
        
        for i, c in enumerate(charts):
            # Filter dance-single only for safety?
            if "dance-single" in c['type']:
                print(f"{len(valid_charts)+1}. {c['difficulty']} (Meter: {c['meter']}) - {c['description']}")
                valid_charts.append(c)
        
        if not valid_charts:
            print("No 'dance-single' chart found.")
            return None

        print("-" * 40)
        print("0. Cancel")

        try:
            choice = int(input(f"\n{Colors.BLUE}Choice: {Colors.ENDC}"))
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
        print(f"\n{Colors.BLUE}🔨 Processing steps... (Mode: {'Increase' if is_increase else 'Decrease'} {int(percentage*100)}%){Colors.ENDC}")

        # Global Beat Mapping and Analysis
        flat_slots = [] 
        
        # Global Hold Simulation
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
                        active_holds[c] = True  # Roll as hold
                        row_has_hold_head = True

                # Count active inputs at THIS moment (including newly started ones)
                
                # How many taps in this row?
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
                    'active_holds_count': active_holds_count_before, # Holds active from PREVIOUS rows
                    'taps_count': taps_in_row
                }
                flat_slots.append(slot_info)

        target_count = int(current_taps * percentage)
        print(f"   Current notes (Tap): {current_taps}")
        print(f"   Target change: {target_count} notes")
        
        changes_made = 0
        
        if is_increase:
            # --- INCREASE LOGIC ---
            # Look for rows where we can add notes respecting:
            # 1. Max 2 total inputs (active holds + taps)
            # 2. Don't add on hold heads/tails (for simplicity)

            # --- SAFER RE-IMPLEMENTATION FOR INCREASE ---
            # We need to redo the active_holds pass tracking exact columns

            # Reset simulation
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
                    
                    # Snapshot of active holds BEFORE this row
                    holds_here = list(active_holds_cols)
                    
                    # Update holds logic
                    row_is_complex = False
                    for c in range(4):
                        char = cols[c]
                        if char == '2' or char == '4': active_holds_cols[c] = True
                        elif char == '3': active_holds_cols[c] = False
                        
                        if char in ['2','3','4']: row_is_complex = True

                    # Calculate total inputs if we don't change anything
                    # Input = Taps ('1') + Active Holds ('True' in holds_here)
                    # Note: if there's a '1' on a column with active hold? (Impossible in valid SM usually)
                    
                    taps = cols.count('1')
                    active_h_count = sum(1 for x in holds_here if x)
                    total_inputs = taps + active_h_count
                    
                    refined_slots.append({
                        'cols': cols,
                        'energy': energy,
                        'total_inputs': total_inputs,
                        'holds_mask': holds_here, # Which columns are occupied by passing holds
                        'row_is_complex': row_is_complex # If it has heads or tails
                    })
            
            # Filter candidates
            candidates = [s for s in refined_slots if not s['row_is_complex'] and s['total_inputs'] < 2]
            candidates.sort(key=lambda x: x['energy'], reverse=True)

            for s in candidates:
                if changes_made >= target_count: break

                # Look for free column
                # Free = is '0' AND not in holds_mask
                free_indices = [i for i, c in enumerate(s['cols']) if c == '0' and not s['holds_mask'][i]]

                if free_indices:
                    # Choose randomly
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
            # Remove weakest Tap '1' that are not on complex rows (hold heads/tails)

            potential_remove = [
                s for s in flat_slots
                if s['row_has_tap'] and not s['row_has_hold_head'] and not s['row_has_hold_tail']
            ]

            # Sort by ASCENDING energy (weakest first)
            potential_remove.sort(key=lambda x: x['energy'])
            
            to_remove = potential_remove[:target_count]
            
            for s in to_remove:
                # Remove all taps in this row
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
        print(f"Saving (OVERWRITE) to: {sm_path}")
        print(f"Modifying chart: {chart_metadata['difficulty']} ({chart_metadata['description']})")
        
        # 1. Reconstruct note data block
        new_data_str = ""
        for i, m in enumerate(new_measures):
            new_data_str += "\n".join(m)
            if i < len(new_measures) - 1:
                new_data_str += ",\n"
        
        # 2. Replace ONLY the note data part in the original content
        start = chart_metadata['note_data_start_abs']
        end = chart_metadata['note_data_end_abs']
        
        final_content = original_content[:start] + "\n" + new_data_str + original_content[end:]
        
        with open(sm_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        print(f"{Colors.GREEN}✅ File updated successfully!{Colors.ENDC}")

    def run(self):
        # 1. Select Song
        entry = self.select_song_menu()
        if not entry: return

        sm_path = entry['sm_path']
        json_path = entry['json_path']

        # 2. Load Analysis
        analysis_data = load_json(json_path)
        if not analysis_data: return

        # 3. Parse SM to find difficulty
        full_content, charts = self.parse_charts_metadata(sm_path)

        # 4. Select Difficulty
        selected_chart = self.select_difficulty_menu(charts)
        if not selected_chart: return

        # 5. Ask Action (+/-)
        print(f"\n{Colors.HEADER}--- MODIFY: {selected_chart['difficulty']} ---{Colors.ENDC}")
        print("1. Increase Difficulty (+20% arrows)")
        print("2. Decrease Difficulty (-20% arrows)")
        print("0. Cancel")

        try:
            choice = input(f"\n{Colors.BLUE}Choice: {Colors.ENDC}")
            if choice == '0': return
            if choice not in ['1', '2']:
                print("Invalid choice.")
                return

            is_increase = (choice == '1')

            # 6. Process
            measures = self.parse_measures_from_string(selected_chart['note_data'])
            new_measures = self.modify_steps(measures, analysis_data, is_increase, 0.20)

            # 7. Save
            self.save_chart_overwrite(sm_path, full_content, selected_chart, new_measures)

        except Exception as e:
            print(f"{Colors.FAIL}Error: {e}{Colors.ENDC}")
            traceback.print_exc()

if __name__ == "__main__":
    app = StepModifier()
    app.run()
