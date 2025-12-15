#!/usr/bin/env python3
"""
🟢 Easy Refiner 4th - The Foundation Layer (Easy)

Logic:
1. Downbeats: ALWAYS Note.
2. Other Beats: Note if Onset Strength > LOW Threshold (0.6 * local_avg).
   (We use a lower threshold to ensure the chart isn't too empty, as Easy relies mostly on 4th notes).
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

class EasyRefiner4th:
    def __init__(self, sm_input, sm_output, analysis_file):
        self.sm_input = Path(sm_input)
        self.sm_output = Path(sm_output)
        self.analysis_file = Path(analysis_file)
        
    def run(self):
        logger.info(f"🟢 Starting Easy 4th Refiner...")
        
        with open(self.analysis_file, 'r') as f:
            self.analysis = json.load(f)
        
        with open(self.sm_input, 'r', encoding='utf-8') as f:
            self.sm_content = f.read()
            
        measures = self._generate_4th_layer()
        self._inject_chart(measures)
        logger.info(f"✅ Easy 4th Layer Generated: {self.sm_output}")

    def _generate_4th_layer(self):
        beat_stats = self.analysis['beat_stats']
        onsets = [b['onset_env_max'] for b in beat_stats]
        
        current_measure_notes = []
        consecutive_pauses = 0
        
        for i, beat in enumerate(beat_stats):
            is_note = False
            
            # Rule 1: Downbeat -> ALWAYS Note
            if beat['is_downbeat']:
                is_note = True
            # Rule 2: Max 2 consecutive pauses
            elif consecutive_pauses >= 2:
                is_note = True
            # Rule 3: Onset Strength > LOW Threshold (0.6)
            else:
                start = max(0, i - 4)
                end = min(len(onsets), i + 4)
                local_window = onsets[start:end]
                local_avg = np.mean(local_window)
                
                threshold = local_avg * 0.6
                
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
        # We split by lookahead for #NOTES:
        parts = re.split(r'(?=#NOTES:)', content, flags=re.IGNORECASE)
        
        if parts:
            header = parts[0].strip()
            existing_charts = parts[1:]
        else:
            header = content.strip()
            existing_charts = []

        # Filter out existing Easy chart to avoid duplicates/overwrites
        final_charts = []
        for chart in existing_charts:
            # Check for "Easy:" difficulty line
            # Regex looks for "Easy:" on a standalone line (ignoring whitespace)
            if not re.search(r'^\s*Easy:\s*$', chart, re.MULTILINE | re.IGNORECASE):
                final_charts.append(chart)

        # Construct new chart
        measure_str = ',\n'.join(measures)
        new_chart_data = (
            "\n"
            "//--------------- dance-single - Easy ----------------\n"
            "#NOTES:\n"
            "     dance-single:\n"
            "     Easy Refiner:\n"
            "     Easy:\n"
            "     3:\n"
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
        print("Usage: python easy_4th.py input.sm output.sm analysis.json")
    else:
        refiner = EasyRefiner4th(sys.argv[1], sys.argv[2], sys.argv[3])
        refiner.run()
