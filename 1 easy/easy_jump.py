#!/usr/bin/env python3
"""
🟢 Easy Refiner Jump

Logic:
- Minimal Jumps.
- Only on Downbeats with VERY High Energy (Top 10%).
- NO Off-beat Jumps.
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

class EasyRefinerJump:
    def __init__(self, sm_input, sm_output, analysis_file):
        self.sm_input = Path(sm_input)
        self.sm_output = Path(sm_output)
        self.analysis_file = Path(analysis_file)
        
    def run(self):
        logger.info(f"🟢 Starting Easy Jump Refiner...")
        
        with open(self.analysis_file, 'r') as f:
            self.analysis = json.load(f)
            
        with open(self.sm_input, 'r', encoding='utf-8') as f:
            self.sm_content = f.read()
            
        existing_measures, chart_header = self._parse_chart()
        if not existing_measures:
            logger.error("Could not find Easy chart to refine!")
            return
            
        refined_measures = self._apply_jump_logic(existing_measures)
        self._inject_chart(refined_measures, chart_header)
        logger.info(f"✅ Easy Jump Layer Applied: {self.sm_output}")

    def _parse_chart(self):
        content_buffer = self.sm_content
        notes_pattern = re.compile(r'#NOTES:(.*?);', re.DOTALL)
        matches = notes_pattern.findall(content_buffer)
        
        target_chart_data = None
        target_header_parts = None
        
        for match_str in matches:
            parts = [p.strip() for p in match_str.split(':')]
            if len(parts) >= 3:
                if parts[2].strip().lower() == "easy":
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
        
        # Calculate thresholds strictly for Easy
        # Use _mean suffix as audio_analyzer saves aggregated stats
        downbeat_energies = [b.get('low_freq_rms_mean', 0.0) for b in beat_stats if b['is_downbeat']]
        if not downbeat_energies:
            return measures
            
        # VERY HIGH Threshold: Top 10% only
        db_threshold = np.percentile(downbeat_energies, 90)
        
        beat_idx = 0
        for m_idx, measure in enumerate(measures):
            steps_per_beat = len(measure) / 4
            for i, line in enumerate(measure):
                current_beat_global = beat_idx + (i / steps_per_beat)
                
                # We only care about main beats (integers)
                if abs(current_beat_global - round(current_beat_global)) < 0.01:
                    global_idx = int(round(current_beat_global))
                    if global_idx < len(beat_stats):
                        stat = beat_stats[global_idx]
                        
                        # Only check if it's already a note (don't create new notes)
                        if '1' in line or '2' in line or 'M' in line:
                            # Rule 1: Downbeat & Very High Energy
                            # Use .get('low_freq_rms_mean', 0.0) to be safe
                            stat_energy = stat.get('low_freq_rms_mean', 0.0)
                            if stat['is_downbeat'] and stat_energy > db_threshold:
                                measure[i] = self._make_jump(line)
                                
            beat_idx += 4
        return measures

    def _make_jump(self, line):
        # Convert single note to jump (e.g., 1000 -> 1001)
        # Avoid hands (3 notes). Max 2.
        if line.count('1') + line.count('2') + line.count('M') >= 2:
            return line
            
        # Simple Logic: Add opposite arrow
        chars = list(line)
        if chars[0] in '12M': chars[3] = '1'
        elif chars[1] in '12M': chars[2] = '1'
        elif chars[2] in '12M': chars[1] = '1'
        elif chars[3] in '12M': chars[0] = '1'
        else:
            # Fallback
            chars[0] = '1'
            chars[3] = '1'
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
        target_diff = "easy"
        
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
                 h_str = "\n     dance-single:\n     Easy Refiner Jump:\n     Easy:\n     3:\n     0.0,0.0,0.0,0.0,0.0"
             
             new_chart = f"\n//--------------- dance-single - {target_diff.capitalize()} ----------------\n#NOTES:{h_str}:\n{measure_str}\n;"
             new_charts.append(new_chart)
             
        full_content = header + "".join(new_charts)
             
        with open(self.sm_output, 'w', encoding='utf-8') as f:
            f.write(full_content)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python easy_jump.py input.sm output.sm analysis.json")
    else:
        refiner = EasyRefinerJump(sys.argv[1], sys.argv[2], sys.argv[3])
        refiner.run()
