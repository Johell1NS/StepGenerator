#!/usr/bin/env python3
"""
🦘 Medium Refiner Jump - The Energy Layer (Medium)

Logic:
1. Identifies existing notes (4th/8th).
2. Converts Single Notes -> Jumps (Double) IF:
   - Downbeat: Top 40% Energy.
   - Off-beat: Energy > 1.5x Global Average (Accents).
3. Bass Check: Requires bass energy > 40% of avg bass.
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

class MediumRefinerJump:
    def __init__(self, sm_input, sm_output, analysis_file):
        self.sm_input = Path(sm_input)
        self.sm_output = Path(sm_output)
        self.analysis_file = Path(analysis_file)
        
    def run(self):
        logger.info(f"🦘 Starting Medium Jump Refiner...")
        
        with open(self.analysis_file, 'r') as f:
            self.analysis = json.load(f)
            
        with open(self.sm_input, 'r', encoding='utf-8') as f:
            self.sm_content = f.read()
            
        existing_measures, chart_header = self._parse_chart()
        if not existing_measures:
            logger.error("Could not find Medium chart to refine!")
            return
            
        refined_measures = self._apply_jump_logic(existing_measures)
        self._inject_chart(refined_measures, chart_header)
        logger.info(f"✅ Medium Jump Layer Applied: {self.sm_output}")

    def _parse_chart(self):
        content_buffer = self.sm_content
        notes_pattern = re.compile(r'#NOTES:(.*?);', re.DOTALL)
        matches = notes_pattern.findall(content_buffer)
        
        target_chart_data = None
        target_header_parts = None
        
        for match_str in matches:
            parts = [p.strip() for p in match_str.split(':')]
            if len(parts) >= 3:
                if parts[2].strip().lower() == "medium":
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

    def _apply_jump_logic(self, measures):
        beat_stats = self.analysis['beat_stats']
        low_freq_rms = self.analysis['raw_features'].get('low_freq_rms', None)
        sr = self.analysis['raw_features']['metadata']['sr']
        hop_length = self.analysis['raw_features']['metadata']['hop_length']
        
        bass_threshold = 0.0
        if low_freq_rms:
            bass_threshold = np.mean(low_freq_rms) * 0.4
        
        candidates = []
        
        for m_idx, measure in enumerate(measures):
            rows_per_measure = len(measure) 
            if rows_per_measure == 0: continue
            
            for r_idx, row in enumerate(measure):
                if '1' in row:
                    beat_pos = (m_idx * 4) + (r_idx / rows_per_measure * 4)
                    closest_beat_idx = int(round(beat_pos))
                    
                    if closest_beat_idx < len(beat_stats):
                        stat = beat_stats[closest_beat_idx]
                        is_valid_bass = True
                        if low_freq_rms:
                            time_sec = stat['time']
                            frame = min(int(time_sec * sr / hop_length), len(low_freq_rms)-1)
                            if low_freq_rms[frame] < bass_threshold:
                                is_valid_bass = False
                        
                        if is_valid_bass:
                            candidates.append({
                                'm_idx': m_idx, 'r_idx': r_idx,
                                'row_str': row,
                                'rms': stat['rms_mean'],
                                'is_downbeat': stat['is_downbeat']
                            })

        if not candidates: return measures
            
        downbeat_candidates = [c for c in candidates if c['is_downbeat']]
        downbeat_candidates.sort(key=lambda x: x['rms'], reverse=True)
        
        qty_to_jump = int(len(downbeat_candidates) * 0.40)
        top_downbeats = downbeat_candidates[:qty_to_jump]
        
        jump_locations = set()
        for c in top_downbeats:
            if self._check_jump_safety(measures, c['m_idx'], c['r_idx']):
                jump_locations.add((c['m_idx'], c['r_idx']))
            
        all_rms = [c['rms'] for c in candidates]
        avg_rms = np.mean(all_rms) if all_rms else 0
        high_threshold = avg_rms * 1.5
        
        offbeat_candidates = [c for c in candidates if not c['is_downbeat']]
        for c in offbeat_candidates:
            if c['rms'] > high_threshold:
                if self._check_jump_safety(measures, c['m_idx'], c['r_idx']):
                    jump_locations.add((c['m_idx'], c['r_idx']))
                
        new_measures = [list(m) for m in measures]
        for m_idx, r_idx in jump_locations:
            current_row = new_measures[m_idx][r_idx]
            new_measures[m_idx][r_idx] = self._make_jump(current_row)
            
        return new_measures

    def _check_jump_safety(self, measures, m_idx, r_idx):
        # Calculate current beat
        rows_curr = len(measures[m_idx])
        beat_curr = (m_idx * 4) + (r_idx / rows_curr * 4)
        
        # Check for 8th notes at +/- 0.5
        prev_8th_beat = beat_curr - 0.5
        next_8th_beat = beat_curr + 0.5
        
        has_prev = self._has_note_at(measures, prev_8th_beat)
        has_next = self._has_note_at(measures, next_8th_beat)
        
        if not has_prev and not has_next:
            return True # Safe, no adjacent 8ths
            
        # Rule: If adjacent 8th, must have pause before OR after the cluster.
        epsilon = 0.01
        
        if has_prev:
            # Cluster: [Prev, Curr]
            # Pause Before: [beat_curr - 1.5, beat_curr - 0.5)
            pause_before = self._is_range_empty(measures, beat_curr - 1.5, beat_curr - 0.5 - epsilon)
            # Pause After: (beat_curr, beat_curr + 1.0]
            pause_after = self._is_range_empty(measures, beat_curr + epsilon, beat_curr + 1.0)
            
            if not (pause_before or pause_after):
                return False
                
        if has_next:
            # Cluster: [Curr, Next]
            # Pause Before: [beat_curr - 1.0, beat_curr)
            pause_before = self._is_range_empty(measures, beat_curr - 1.0, beat_curr - epsilon)
            # Pause After: (beat_curr + 0.5, beat_curr + 1.5]
            pause_after = self._is_range_empty(measures, beat_curr + 0.5 + epsilon, beat_curr + 1.5)
            
            if not (pause_before or pause_after):
                return False
                
        return True

    def _has_note_at(self, measures, beat):
        if beat < 0: return False
        m_idx = int(beat // 4)
        if m_idx >= len(measures): return False
        measure = measures[m_idx]
        rows = len(measure)
        if rows == 0: return False
        
        remainder = beat % 4
        # Calculate row index. Must be close to integer.
        r_idx_float = (remainder / 4) * rows
        r_idx = int(round(r_idx_float))
        
        # Tolerance check (e.g. if quantization doesn't match)
        if abs(r_idx_float - r_idx) > 0.01:
            return False # Not aligned with this measure's quantization
            
        if r_idx >= rows: return False
        
        row = measure[r_idx]
        return any(c in '124' for c in row) # 1=Tap, 2=Hold, 4=Roll

    def _is_range_empty(self, measures, start_beat, end_beat):
        start_m = max(0, int(start_beat // 4))
        end_m = int(end_beat // 4)
        if end_m >= len(measures): end_m = len(measures) - 1
        
        for m in range(start_m, end_m + 1):
            if m >= len(measures): break
            measure = measures[m]
            rows = len(measure)
            if rows == 0: continue
            
            for r in range(rows):
                beat_abs = (m * 4) + (r / rows * 4)
                if start_beat <= beat_abs <= end_beat:
                    # Check if note exists
                    row_str = measure[r]
                    if any(c in '124' for c in row_str):
                        return False
        return True

    def _make_jump(self, current_row):
        active_cols = [i for i, c in enumerate(current_row) if c != '0']
        if len(active_cols) != 1: return current_row
        available_cols = [i for i in range(4) if i not in active_cols]
        new_col = random.choice(available_cols)
        chars = list(current_row)
        chars[new_col] = '1'
        return "".join(chars)

    def _inject_chart(self, measures, header_parts):
        measure_str = ',\n'.join(['\n'.join(m) for m in measures])
        
        with open(self.sm_input, 'r', encoding='utf-8') as f:
            content = f.read()
            
        parts = re.split(r'(?=#NOTES:)', content, flags=re.IGNORECASE)
        header = parts[0]
        existing_charts = parts[1:]
        
        new_charts = []
        replaced = False
        target_diff = "medium"
        
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
             if header_parts:
                 h_str = "\n     " + ":\n     ".join([p.strip() for p in header_parts])
             else:
                 h_str = "\n     dance-single:\n     Medium Refiner Jump:\n     Medium:\n     5:\n     0.0,0.0,0.0,0.0,0.0"
             
             new_chart = f"\n//--------------- dance-single - {target_diff.capitalize()} ----------------\n#NOTES:{h_str}:\n{measure_str}\n;"
             new_charts.append(new_chart)
             
        full_content = header + "".join(new_charts)
             
        with open(self.sm_output, 'w', encoding='utf-8') as f:
            f.write(full_content)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python medium_jump.py <input_sm> <output_sm> <analysis_json>")
    else:
        refiner = MediumRefinerJump(sys.argv[1], sys.argv[2], sys.argv[3])
        refiner.run()
