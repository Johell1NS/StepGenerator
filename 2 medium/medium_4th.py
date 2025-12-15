#!/usr/bin/env python3
"""
🟠 Medium Refiner 4th - The Foundation Layer (Medium)

Logic:
1. Downbeats: ALWAYS Note.
2. Other Beats: Note if Onset Strength > MEDIUM Threshold (0.8 * local_avg).
   (Standard threshold for balanced density).
3. Max 2 consecutive pauses.
"""

import json
import random
import sys
import re
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MediumRefiner4th:
    def __init__(self, sm_input, sm_output, analysis_file):
        self.sm_input = Path(sm_input)
        self.sm_output = Path(sm_output)
        self.analysis_file = Path(analysis_file)
        
    def run(self):
        logger.info(f"🟠 Starting Medium 4th Refiner...")
        
        with open(self.analysis_file, 'r') as f:
            self.analysis = json.load(f)
        
        with open(self.sm_input, 'r', encoding='utf-8') as f:
            self.sm_content = f.read()
            
        measures = self._generate_4th_layer()
        self._inject_chart(measures)
        logger.info(f"✅ Medium 4th Layer Generated: {self.sm_output}")

    def _generate_4th_layer(self):
        beat_stats = self.analysis['beat_stats']
        onsets = [b['onset_env_max'] for b in beat_stats]
        
        current_measure_notes = []
        consecutive_pauses = 0
        
        for i, beat in enumerate(beat_stats):
            is_note = False
            
            if beat['is_downbeat']:
                is_note = True
            elif consecutive_pauses >= 2:
                is_note = True
            else:
                start = max(0, i - 4)
                end = min(len(onsets), i + 4)
                local_window = onsets[start:end]
                local_avg = np.mean(local_window) if local_window else 0
                
                threshold = local_avg * 0.8
                
                if beat['onset_env_max'] > threshold:
                    is_note = True
                else:
                    is_note = False
            
            if is_note:
                direction = random.choice(['1000', '0100', '0010', '0001'])
                current_measure_notes.append(direction)
                consecutive_pauses = 0
            else:
                current_measure_notes.append('0000')
                consecutive_pauses += 1
                
        measures = []
        for i in range(0, len(current_measure_notes), 4):
            chunk = current_measure_notes[i:i+4]
            while len(chunk) < 4:
                chunk.append('0000')
            measures.append('\n'.join(chunk))
            
        return measures

    def _inject_chart(self, measures):
        # Read existing content
        if self.sm_input.exists():
            with open(self.sm_input, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = ""

        # Identify Header and Existing Charts
        parts = re.split(r'(?=#NOTES:)', content, flags=re.IGNORECASE)
        
        if parts:
            header = parts[0].strip()
            existing_charts = parts[1:]
        else:
            header = content.strip()
            existing_charts = []

        # Filter out existing Medium chart
        final_charts = []
        for chart in existing_charts:
            if not re.search(r'^\s*Medium:\s*$', chart, re.MULTILINE | re.IGNORECASE):
                final_charts.append(chart)

        # Construct new chart
        measure_str = ',\n'.join(measures)
        new_chart_data = (
            "\n"
            "//--------------- dance-single - Medium ----------------\n"
            "#NOTES:\n"
            "     dance-single:\n"
            "     Medium Refiner:\n"
            "     Medium:\n"
            "     5:\n"
            "     0.0,0.0,0.0,0.0,0.0:\n"
            f"{measure_str};"
        )
        
        # Add new chart
        final_charts.append(new_chart_data)
        
        # Reconstruct file
        full_content = header + "\n" + "".join(final_charts)
        
        with open(self.sm_output, 'w', encoding='utf-8') as f:
            f.write(full_content)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python medium_4th.py <input_sm> <output_sm> <analysis_json>")
    else:
        refiner = MediumRefiner4th(sys.argv[1], sys.argv[2], sys.argv[3])
        refiner.run()
