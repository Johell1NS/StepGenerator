#!/usr/bin/env python3
"""
🟠 Medium Refiner Hold - Hold Note Injection (Medium)

Logic:
1. Identifies hold candidates from 'hold_segments' in analysis data.
2. Checks for conflicts with existing notes.
3. "Smart Logic":
   - Low Energy (< 0.6): Favors Holds (clears conflicting taps).
   - High Energy (> 0.6): Favors Taps (cuts holds).
4. Limits total inputs (Holds + Taps) to 2.
"""

import json
import logging
from pathlib import Path
import re
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MediumRefinerHold:
    def __init__(self, sm_input, sm_output, analysis_file):
        self.sm_input = Path(sm_input)
        self.sm_output = Path(sm_output)
        self.analysis_file = Path(analysis_file)

    def run(self):
        logger.info(f"🟠 Starting Medium Hold Refiner: {self.sm_input} -> {self.sm_output}")
        
        # 1. Load Analysis Data
        try:
            with open(self.analysis_file, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            hold_segments = analysis_data.get('hold_segments', [])
            beat_stats = analysis_data.get('beat_stats', [])
            
            if not hold_segments:
                logger.info("No hold segments found. Just copying file.")
                self._copy_file()
                return
                
            hold_segments.sort(key=lambda x: x['start'])
            
        except FileNotFoundError:
            logger.error(f"Analysis file not found: {self.analysis_file}")
            return

        # 2. Parse SM File
        try:
            with open(self.sm_input, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed to read SM file: {e}")
            return

        # Parse Metadata
        offset = 0.0
        bpms = []
        for line in lines:
            if line.startswith("#OFFSET:"):
                try:
                    offset = float(line.split(":")[1].strip().replace(";", ""))
                except: pass
            elif line.startswith("#BPMS:"):
                bpm_str = line.split(":")[1].strip().replace(";", "")
                pairs = bpm_str.split(",")
                for pair in pairs:
                    if "=" in pair:
                        b, bpm = pair.split("=")
                        bpms.append((float(b), float(bpm)))

        # Locate Notes & Measures
        notes_start_line = -1
        charts_starts = []
        for i, line in enumerate(lines):
            if "#NOTES:" in line:
                charts_starts.append(i)
        
        target_start_line = -1
        
        for start_idx in charts_starts:
            try:
                 chunk = "".join(lines[start_idx:start_idx+20])
                 chunk = re.sub(r'//.*', '', chunk)
                 parts = [p.strip() for p in chunk.split(':')]
                 if len(parts) >= 4:
                     if parts[3].strip().lower() == "medium":
                         target_start_line = start_idx
                         break
            except: pass
            
        if target_start_line == -1:
            logger.info("Medium chart not found for Hold Refiner. Skipping.")
            self._copy_file()
            return
            
        notes_start_line = target_start_line

        measure_start_line = -1
        for i in range(notes_start_line, len(lines)):
            if re.match(r'^\s*[01234MKLF]+\s*$', lines[i]):
                measure_start_line = i
                break
                
        if measure_start_line == -1:
            self._copy_file()
            return
        
        # Extract Measures
        chart_content_start = measure_start_line
        chart_data_lines = []
        for i in range(measure_start_line, len(lines)):
            line = lines[i].strip()
            if line == ";" or line.startswith(";"): break
            chart_data_lines.append(line)

        # Flatten Grid
        measures = []
        temp_measure = []
        for line in chart_data_lines:
            line_clean = line.split('//')[0].strip()
            if not line_clean: continue
            if ',' in line_clean:
                parts = line_clean.split(',')
                for j, part in enumerate(parts):
                    p = part.strip()
                    if p: temp_measure.append(p)
                    if j < len(parts) - 1:
                        measures.append(temp_measure)
                        temp_measure = []
            else:
                temp_measure.append(line_clean)
        if temp_measure: measures.append(temp_measure)
        
        grid = [m for m in measures]

        # --- LOGIC START ---
        
        candidates = self._identify_candidates(grid, hold_segments, bpms, offset)
        self._resolve_conflicts(grid, candidates, beat_stats, bpms, offset)
        final_applied = self._apply_holds(grid, candidates)
        
        logger.info(f"Applied {final_applied} confirmed holds.")

        # --- RECONSTRUCT ---
        new_chart_lines = []
        for m_idx, measure in enumerate(grid):
            for row in measure:
                new_chart_lines.append(row + "\n")
            if m_idx < len(grid) - 1:
                new_chart_lines.append(",\n")
            else:
                new_chart_lines.append(";\n")
                
        final_lines = lines[:chart_content_start] + new_chart_lines + lines[chart_content_start + len(chart_data_lines) + 1:]
        
        try:
            with open(self.sm_output, 'w', encoding='utf-8') as f:
                f.writelines(final_lines)
            logger.info("Chart update complete.")
        except Exception as e:
            logger.error(f"Failed to write SM file: {e}")

    def _copy_file(self):
        try:
            with open(self.sm_input, 'r') as f:
                content = f.read()
            with open(self.sm_output, 'w') as f:
                f.write(content)
        except:
            pass

    def _get_time_at_beat(self, beat, bpms, offset):
        current_time = -offset
        current_beat = 0.0
        
        for i in range(len(bpms)):
            b_start, bpm = bpms[i]
            if i < len(bpms) - 1:
                b_next = bpms[i+1][0]
            else:
                b_next = float('inf')
                
            if beat < b_next:
                beats_in_segment = beat - max(current_beat, b_start)
                seconds = beats_in_segment * (60.0 / bpm)
                current_time += seconds
                return current_time
            else:
                beats_in_segment = b_next - max(current_beat, b_start)
                seconds = beats_in_segment * (60.0 / bpm)
                current_time += seconds
                current_beat = b_next
        return current_time

    def _get_beat_at_time(self, target_time, bpms, offset):
        current_time = -offset
        current_beat = 0.0
        
        for i in range(len(bpms)):
            b_start, bpm = bpms[i]
            if i < len(bpms) - 1:
                b_next = bpms[i+1][0]
                beats_in_segment = b_next - max(current_beat, b_start)
                segment_duration = beats_in_segment * (60.0 / bpm)
                
                if current_time + segment_duration > target_time:
                    time_diff = target_time - current_time
                    beats_diff = time_diff * (bpm / 60.0)
                    return max(current_beat, b_start) + beats_diff
                else:
                    current_time += segment_duration
                    current_beat = b_next
            else:
                time_diff = target_time - current_time
                beats_diff = time_diff * (bpm / 60.0)
                return max(current_beat, b_start) + beats_diff
        return 0.0

    def _get_energy_in_range(self, start_time, end_time, beat_stats):
        if not beat_stats: return 0.5
        relevant = [b.get('onset_env_mean', 0.5) for b in beat_stats 
                    if start_time <= b['time'] <= end_time]
        if not relevant: return 0.5
        return sum(relevant) / len(relevant)

    def _identify_candidates(self, grid, hold_segments, bpms, offset):
        candidates = []
        candidate_id_counter = 0
        
        for m_idx, measure in enumerate(grid):
            rows = len(measure)
            for r_idx, row in enumerate(measure):
                beat = m_idx * 4.0 + (r_idx / rows) * 4.0
                time = self._get_time_at_beat(beat, bpms, offset)
                
                for col in range(4):
                    if row[col] == '1':
                        matched_seg = None
                        for seg in hold_segments:
                            if (seg['end'] - seg['start']) < 1.0: continue
                            if (seg['start'] - 0.20) <= time <= (seg['start'] + 0.40):
                                matched_seg = seg
                                break
                        
                        if matched_seg:
                            end_time = matched_seg['end']
                            end_beat = self._get_beat_at_time(end_time, bpms, offset)
                            
                            end_m = int(end_beat // 4)
                            rem = end_beat % 4
                            if end_m >= len(grid):
                                end_m = len(grid) - 1
                                end_r = len(grid[end_m]) - 1
                            else:
                                end_rows = len(grid[end_m])
                                end_r = int((rem / 4.0) * end_rows)
                            
                            candidates.append({
                                'id': candidate_id_counter,
                                'col': col,
                                'start_m': m_idx, 'start_r': r_idx,
                                'end_m': end_m, 'end_r': end_r,
                                'start_beat': beat, 'end_beat': end_beat,
                                'start_time': time, 'end_time': end_time,
                                'status': 'accepted'
                            })
                            candidate_id_counter += 1
        return candidates

    def _resolve_conflicts(self, grid, candidates, beat_stats, bpms, offset):
        taps_to_delete = set()
        flat_grid = []
        for m_idx, measure in enumerate(grid):
            rows = len(measure)
            for r_idx, row in enumerate(measure):
                beat = m_idx * 4.0 + (r_idx / rows) * 4.0
                time = self._get_time_at_beat(beat, bpms, offset)
                flat_grid.append({'m': m_idx, 'r': r_idx, 'beat': beat, 'time': time, 'row': row})

        candidates.sort(key=lambda x: x['start_beat'])
        active_holds = []
        THRESHOLD = 0.6

        for step in flat_grid:
            current_beat = step['beat']
            active_holds = [c for c in active_holds if c['end_beat'] > current_beat]
            starting_here = [c for c in candidates if c['start_m'] == step['m'] and c['start_r'] == step['r']]
            active_holds.extend(starting_here)
            
            active_accepted = [c for c in active_holds if c['status'] == 'accepted']
            
            row_chars = list(step['row'])
            taps_indices = []
            for col in range(4):
                if row_chars[col] == '1':
                    is_hold_start = any(c['col'] == col and c['start_m'] == step['m'] and c['start_r'] == step['r'] for c in active_accepted)
                    if not is_hold_start:
                        taps_indices.append(col)
            
            total_inputs = len(active_accepted) + len(taps_indices)
            
            if total_inputs > 2:
                energy = self._get_energy_in_range(step['time'], step['time'] + 0.5, beat_stats)
                ongoing_holds = [h for h in active_accepted if h['start_beat'] < current_beat]
                new_holds = [h for h in active_accepted if h['start_beat'] == current_beat]
                
                if energy > THRESHOLD:
                    # High Energy: Prefer Taps
                    for h in new_holds: h['status'] = 'rejected'
                    
                    used_slots = len(taps_indices) + len(new_holds)
                    slots_for_holds = 2 - used_slots
                    ongoing_holds.sort(key=lambda x: x['end_beat'] - current_beat, reverse=True)
                    
                    for i, h in enumerate(ongoing_holds):
                        if i >= slots_for_holds:
                            h['end_beat'] = current_beat
                            h['end_m'] = step['m']
                            h['end_r'] = step['r']
                else:
                    # Low Energy: Prefer Holds
                    all_holds = ongoing_holds + new_holds
                    all_holds.sort(key=lambda x: x['end_beat'] - current_beat, reverse=True)
                    keep_holds = all_holds[:2]
                    drop_holds = all_holds[2:]
                    
                    for h in drop_holds:
                        if h in new_holds:
                            h['status'] = 'rejected'
                            taps_to_delete.add((step['m'], step['r'], h['col']))
                        else:
                            h['end_beat'] = current_beat
                            h['end_m'] = step['m']
                            h['end_r'] = step['r']
                            
                    used_slots = len(keep_holds)
                    slots_for_taps = 2 - used_slots
                    if len(taps_indices) > slots_for_taps:
                        for col in taps_indices:
                            taps_to_delete.add((step['m'], step['r'], col))

        # Apply deletions
        for (m, r, col) in taps_to_delete:
            row_list = list(grid[m][r])
            if row_list[col] == '1':
                row_list[col] = '0'
                grid[m][r] = "".join(row_list)

    def _apply_holds(self, grid, candidates):
        count = 0
        for cand in candidates:
            if cand['status'] != 'accepted': continue
            
            m, r, col = cand['start_m'], cand['start_r'], cand['col']
            row_list = list(grid[m][r])
            row_list[col] = '2'
            grid[m][r] = "".join(row_list)
            
            em, er = cand['end_m'], cand['end_r']
            if em < len(grid) and er < len(grid[em]):
                row_list = list(grid[em][er])
                row_list[col] = '3'
                grid[em][er] = "".join(row_list)
            
            cursor_m, cursor_r = m, r + 1
            while True:
                if cursor_r >= len(grid[cursor_m]):
                    cursor_m += 1
                    cursor_r = 0
                    if cursor_m >= len(grid): break
                
                if cursor_m > em: break
                if cursor_m == em and cursor_r >= er: break
                
                row_list = list(grid[cursor_m][cursor_r])
                if row_list[col] != 'M':
                    row_list[col] = '0'
                grid[cursor_m][cursor_r] = "".join(row_list)
                
                cursor_r += 1
            count += 1
        return count

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python medium_hold.py <input_sm> <output_sm> [analysis_json]")
        sys.exit(1)
        
    input_sm = sys.argv[1]
    output_sm = sys.argv[2]
    analysis_json = sys.argv[3] if len(sys.argv) > 3 else "analysis_data.json"
    
    refiner = MediumRefinerHold(input_sm, output_sm, analysis_json)
    refiner.run()
