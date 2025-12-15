#!/usr/bin/env python3
"""
🦘 Hard Refiner Jump - The Energy Layer (Hard)

Logic:
1. Identifies existing notes (4th/8th).
2. Converts Single Notes -> Jumps (Double) IF:
   - Downbeat: Top 60% Energy (More aggressive than Medium).
   - Off-beat: Energy > 1.3x Global Average (More accents).
3. Bass Check: Requires bass energy > 30% of avg bass.
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

class HardRefinerJump:
    def __init__(self, sm_input, sm_output, analysis_file):
        self.sm_input = Path(sm_input)
        self.sm_output = Path(sm_output)
        self.analysis_file = Path(analysis_file)
        
    def run(self):
        logger.info(f"🦘 Starting Hard Jump Refiner...")
        
        with open(self.analysis_file, 'r') as f:
            self.analysis = json.load(f)
            
        with open(self.sm_input, 'r', encoding='utf-8') as f:
            self.sm_content = f.read()
            
        existing_measures, chart_header = self._parse_chart()
        if not existing_measures:
            logger.error("Could not find Hard chart to refine!")
            return
            
        refined_measures = self._apply_jump_logic(existing_measures)
        self._inject_chart(refined_measures, chart_header)
        logger.info(f"✅ Hard Jump Layer Applied: {self.sm_output}")

    def _parse_chart(self):
        content_buffer = self.sm_content
        notes_pattern = re.compile(r'#NOTES:(.*?);', re.DOTALL)
        matches = notes_pattern.findall(content_buffer)
        
        target_chart_data = None
        target_header_parts = None
        
        for match_str in matches:
            parts = [p.strip() for p in match_str.split(':')]
            if len(parts) >= 3:
                if parts[2].strip().lower() == "hard":
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
            bass_threshold = np.mean(low_freq_rms) * 0.3 # Lower bass threshold for Hard
        
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
        
        qty_to_jump = int(len(downbeat_candidates) * 0.60) # Top 60%
        top_downbeats = downbeat_candidates[:qty_to_jump]
        
        jump_locations = set()
        for c in top_downbeats:
            jump_locations.add((c['m_idx'], c['r_idx']))
            
        all_rms = [c['rms'] for c in candidates]
        avg_rms = np.mean(all_rms) if all_rms else 0
        high_threshold = avg_rms * 1.3 # Lower threshold for offbeats
        
        offbeat_candidates = [c for c in candidates if not c['is_downbeat']]
        for c in offbeat_candidates:
            if c['rms'] > high_threshold:
                jump_locations.add((c['m_idx'], c['r_idx']))
                
        new_measures = [list(m) for m in measures]
        for m_idx, r_idx in jump_locations:
            current_row = new_measures[m_idx][r_idx]
            new_measures[m_idx][r_idx] = self._make_jump(current_row)
            
        return new_measures

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
        target_diff = "hard"
        
        for chart in existing_charts:
            # Normalize to remove comments for checking
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
             # Fallback: Append if not found
             if header_parts:
                 h_str = "\n     " + ":\n     ".join([p.strip() for p in header_parts])
             else:
                 h_str = "\n     dance-single:\n     Hard Refiner Jump:\n     Hard:\n     8:\n     0.0,0.0,0.0,0.0,0.0"
             
             new_chart = f"\n//--------------- dance-single - {target_diff.capitalize()} ----------------\n#NOTES:{h_str}:\n{measure_str}\n;"
             new_charts.append(new_chart)
             
        full_content = header + "".join(new_charts)
             
        with open(self.sm_output, 'w', encoding='utf-8') as f:
            f.write(full_content)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python hard_jump.py <input_sm> <output_sm> <analysis_json>")
    else:
        refiner = HardRefinerJump(sys.argv[1], sys.argv[2], sys.argv[3])
        refiner.run()
