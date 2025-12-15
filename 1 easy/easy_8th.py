#!/usr/bin/env python3
"""
🟢 Easy Refiner 8th

Logic:
- Extremely minimal 8th notes.
- Only very clear syncopation or none at all.
- Target Density: 0.05 (5%).
"""

import json
import random
import sys
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EasyRefiner8th:
    def __init__(self, sm_input, sm_output, analysis_file):
        self.sm_input = Path(sm_input)
        self.sm_output = Path(sm_output)
        self.analysis_file = Path(analysis_file)
        
    def run(self):
        logger.info(f"🟢 Starting Easy 8th Refiner...")
        
        # Easy usually avoids 8th notes unless the song is very slow.
        # For this implementation, we will perform a pass-through (Identity)
        # or just very minimal additions.
        # Let's just double the resolution to allow 8ths but NOT add them automatically
        # unless extremely prominent.
        
        # 1. Load SM
        with open(self.sm_input, 'r', encoding='utf-8') as f:
            self.sm_content = f.read()
            
        existing_measures, chart_header = self._parse_chart()
        if not existing_measures:
            logger.error("Could not find Easy chart!")
            return
            
        # 2. Expand Resolution (4 -> 8 lines) without adding notes
        refined_measures = []
        for m in existing_measures:
            new_m = []
            for line in m:
                new_m.append(line)
                new_m.append('0000') # Empty 8th
            refined_measures.append(new_m)
            
        # 3. Save
        self._inject_chart(refined_measures, chart_header)
        logger.info(f"✅ Easy 8th Layer (Resolution Expand only): {self.sm_output}")

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
                 h_str = "\n     dance-single:\n     Easy Refiner 8th:\n     Easy:\n     3:\n     0.0,0.0,0.0,0.0,0.0"
             
             new_chart = f"\n//--------------- dance-single - {target_diff.capitalize()} ----------------\n#NOTES:{h_str}:\n{measure_str}\n;"
             new_charts.append(new_chart)
             
        full_content = header + "".join(new_charts)
             
        with open(self.sm_output, 'w', encoding='utf-8') as f:
            f.write(full_content)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python easy_8th.py input.sm output.sm analysis.json")
    else:
        refiner = EasyRefiner8th(sys.argv[1], sys.argv[2], sys.argv[3])
        refiner.run()
