#!/usr/bin/env python3
"""
🔴 Hard Refiner 8th - The Rhythm Layer (Hard)

Logic:
1. Expands resolution to 8th notes.
2. Adds Blue Arrows (8ths) based on energy.
3. Targets ~50% density ratio (Blue/Red).
4. Includes "Bridge", "Syncopation", and "Stream" patterns.
"""

import json
import random
import sys
import numpy as np
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HardRefiner8th:
    def __init__(self, sm_input, sm_output, analysis_file, target_difficulty="hard", target_ratio=0.50):
        self.sm_input = Path(sm_input)
        self.sm_output = Path(sm_output)
        self.analysis_file = Path(analysis_file)
        self.target_difficulty = target_difficulty.lower()
        self.target_ratio = float(target_ratio)
        
    def run(self):
        logger.info(f"🔴 Starting Hard 8th Refiner...")
        
        with open(self.analysis_file, 'r') as f:
            self.analysis = json.load(f)
            
        with open(self.sm_input, 'r', encoding='utf-8') as f:
            self.sm_content = f.read()
            
        existing_measures, chart_header_parts = self._parse_chart()
        if not existing_measures:
            logger.error(f"Could not find {self.target_difficulty.capitalize()} chart to refine!")
            return
            
        refined_measures = self._process_measures(existing_measures)
        self._inject_chart(refined_measures, chart_header_parts)
        logger.info(f"✅ Hard 8th Layer Applied: {self.sm_output}")

    def _parse_chart(self):
        content_buffer = self.sm_content
        notes_pattern = re.compile(r'#NOTES:(.*?);', re.DOTALL)
        matches = notes_pattern.findall(content_buffer)
        
        target_chart_data = None
        target_header_parts = None
        
        for match_str in matches:
            parts = [p.strip() for p in match_str.split(':')]
            if len(parts) >= 3:
                if parts[2].strip().lower() == self.target_difficulty:
                    target_chart_data = parts[-1].strip()
                    target_header_parts = parts[:-1]
                    break
        
        if not target_chart_data:
            return None, None
            
        chart_data = re.sub(r'//.*', '', target_chart_data)
        measures_raw = chart_data.split(',')
        measures = []
        for m in measures_raw:
            lines = [l.strip() for l in m.strip().split('\n') if l.strip()]
            measures.append(lines)
        return measures, target_header_parts

    def _calculate_density_ratio(self, measures):
        red_count = 0
        blue_count = 0
        for m in measures:
            for i, row in enumerate(m):
                note_count = self._count_notes(row)
                if note_count > 0:
                    if i % 2 == 0: red_count += 1
                    else: blue_count += 1
        if red_count == 0: return 0.0
        return blue_count / red_count

    def _process_measures(self, existing_measures):
        sensitivity = 1.0
        best_measures = None
        min_diff = 1.0
        TARGET_RATIO = self.target_ratio
        
        # Auto-Tuner Loop
        for iteration in range(5):
            measures = self._generate_measures(existing_measures, sensitivity)
            ratio = self._calculate_density_ratio(measures)
            diff = abs(ratio - TARGET_RATIO)
            
            if diff < min_diff:
                min_diff = diff
                best_measures = measures
            
            if diff <= 0.02: break
                
            error = TARGET_RATIO - ratio
            sensitivity += error * 3.0
            sensitivity = max(0.5, min(sensitivity, 3.0))
            
        return best_measures

    def _generate_measures(self, existing_measures, sensitivity=1.0):
        flat_rows_4th = [row for m in existing_measures for row in m]
        new_flat_rows = []
        
        beat_stats = self.analysis['beat_stats']
        onset_env = self.analysis['raw_features']['onset_env']
        low_freq_rms = self.analysis['raw_features'].get('low_freq_rms', None)
        sr = self.analysis['raw_features']['metadata']['sr']
        hop_length = self.analysis['raw_features']['metadata']['hop_length']
        
        total_4th_notes = len(flat_rows_4th)
        bass_threshold = 0.0
        if low_freq_rms:
            bass_threshold = np.mean(low_freq_rms) * 0.3 # Lower bass threshold for Hard
        
        def get_onset_energy(beat_idx):
            if beat_idx < len(beat_stats):
                t = beat_stats[beat_idx]['time']
                f = min(int(t * sr / hop_length), len(onset_env)-1)
                return onset_env[f]
            return 0.0

        beat_energies = [get_onset_energy(i) for i in range(total_4th_notes + 1)]
        local_thresholds = []
        for i in range(len(beat_energies)):
            start = max(0, i - 4)
            end = min(len(beat_energies), i + 4)
            local_win = beat_energies[start:end]
            local_thresholds.append(np.mean(local_win) if local_win else 0.0)
            
        global_avg_energy = np.mean(onset_env)
        beats_since_last_blue = 0
        current_streak = 0
        
        for i in range(total_4th_notes):
            current_red = flat_rows_4th[i]
            new_flat_rows.append(current_red)
            
            is_red_note = (self._count_notes(current_red) > 0)
            if is_red_note: current_streak += 1
            else: current_streak = 0
                
            if i == total_4th_notes - 1:
                new_flat_rows.append('0000')
                continue
                
            next_red = flat_rows_4th[i+1]
            
            # Rule A: Jump Adjacency (Relaxed for Hard - allows streams near jumps)
            # if self._is_jump(current_red) or self._is_jump(next_red):
            #    new_flat_rows.append('0000')
            #    continue
                
            # Rule B: Run Length (Allows longer streams for Hard)
            is_next_note = (self._count_notes(next_red) > 0)
            if is_next_note and current_streak >= 7: # Extended stream limit
                new_flat_rows.append('0000')
                current_streak = 0
                beats_since_last_blue += 1
                continue
                
            # Rule C: Audio Check
            if i < len(beat_stats):
                b_curr = beat_stats[i]
                t_mid = (b_curr['time'] + beat_stats[i+1]['time']) / 2 if i+1 < len(beat_stats) else b_curr['time'] + 0.3
                frame = min(int(t_mid * sr / hop_length), len(onset_env)-1)
                energy_at_half = onset_env[frame]
                
                if low_freq_rms:
                    bass_at_half = low_freq_rms[min(frame, len(low_freq_rms)-1)]
                    if bass_at_half < bass_threshold:
                        new_flat_rows.append('0000')
                        beats_since_last_blue += 1
                        continue

                local_avg = local_thresholds[i]
                floor = global_avg_energy * 0.3 # Lower floor for Hard
                adaptive_thresh = max(floor, local_avg * 0.8) / sensitivity if sensitivity > 0 else 0
                
                is_bridge = is_red_note and is_next_note
                is_synco = (not is_red_note) and is_next_note
                
                place_blue = False
                if is_bridge and energy_at_half > adaptive_thresh: place_blue = True
                elif is_synco and energy_at_half > (adaptive_thresh * 1.1): place_blue = True
                
                # Drought Breaker
                if not place_blue and beats_since_last_blue > 4: # More frequent drought breaking
                    if is_red_note or is_next_note: place_blue = True
                        
                if place_blue:
                    bad_cols = set(self._get_cols(current_red) + self._get_cols(next_red))
                    valid_cols = list({0,1,2,3} - bad_cols)
                    
                    if not valid_cols:
                        new_flat_rows.append('0000')
                        current_streak = 0
                        beats_since_last_blue += 1
                    else:
                        col = random.choice(valid_cols)
                        row_arr = ['0']*4
                        row_arr[col] = '1'
                        new_flat_rows.append("".join(row_arr))
                        current_streak += 1
                        beats_since_last_blue = 0
                else:
                    new_flat_rows.append('0000')
                    current_streak = 0
                    beats_since_last_blue += 1
            else:
                 new_flat_rows.append('0000')
                 beats_since_last_blue += 1

        final_measures = []
        for i in range(0, len(new_flat_rows), 8):
            chunk = new_flat_rows[i:i+8]
            while len(chunk) < 8: chunk.append('0000')
            final_measures.append(chunk)
        return final_measures

    def _count_notes(self, row):
        return row.count('1') + row.count('2') + row.count('4') 

    def _is_jump(self, row):
        return self._count_notes(row) >= 2

    def _get_cols(self, row):
        return [i for i, c in enumerate(row) if c in '124']

    def _inject_chart(self, measures, header_parts):
        measure_str = ',\n'.join(['\n'.join(m) for m in measures])
        
        with open(self.sm_input, 'r', encoding='utf-8') as f:
            content = f.read()
            
        parts = re.split(r'(?=#NOTES:)', content, flags=re.IGNORECASE)
        header = parts[0]
        existing_charts = parts[1:]
        
        new_charts = []
        replaced = False
        target_diff = self.target_difficulty
        
        for chart in existing_charts:
            clean_chart = re.sub(r'//.*', '', chart)
            clean_chart = clean_chart.strip()
            if clean_chart.upper().startswith('#NOTES:'):
                body = clean_chart[7:]
            else:
                body = clean_chart
            
            fields = body.split(':')
            if len(fields) >= 3:
                curr_diff = fields[2].strip().lower()
                if curr_diff == target_diff.lower():
                    # Reconstruct header
                    if header_parts:
                        h_str = "\n     " + ":\n     ".join([p.strip() for p in header_parts])
                    else:
                        h_str = "\n     " + ":\n     ".join([f.strip() for f in fields[:5]])
                    
                    new_chart = f"\n//--------------- dance-single - {target_diff.capitalize()} ----------------\n#NOTES:{h_str}:\n{measure_str}\n;"
                    new_charts.append(new_chart)
                    replaced = True
                    continue
            
            new_charts.append(chart)
            
        if not replaced:
             meter = "8"
             header_str = f"\n     dance-single:\n     Hard Refiner:\n     {self.target_difficulty.capitalize()}:\n     {meter}:\n     0.0,0.0,0.0,0.0,0.0"
             new_chart = f"\n//--------------- dance-single - {self.target_difficulty.capitalize()} ----------------\n#NOTES:{header_str}:\n{measure_str}\n;"
             new_charts.append(new_chart)
             
        full_content = header + "".join(new_charts)
             
        with open(self.sm_output, 'w', encoding='utf-8') as f:
            f.write(full_content)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python hard_8th.py <input_sm> <output_sm> <analysis_json>")
    else:
        refiner = HardRefiner8th(sys.argv[1], sys.argv[2], sys.argv[3])
        refiner.run()
