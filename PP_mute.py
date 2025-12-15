#!/usr/bin/env python3
"""
🔇 Chart Refiner Mute - The Silence Cleaner

This script removes ALL notes (taps, holds, rolls, jumps) from sections 
where the audio volume is significantly low (silence or near-silence).

Logic:
1. Load Audio Analysis (RMS energy).
2. Calculate a "Silence Threshold" based on global average RMS.
3. Scan every row of every chart in the SM file.
4. If the audio energy at the row's time is below threshold -> Clear the row (0000).
"""

import json
import logging
import re
import sys
from pathlib import Path
import numpy as np

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChartRefinerMute:
    def __init__(self, sm_input, sm_output, analysis_file):
        self.sm_input = Path(sm_input)
        self.sm_output = Path(sm_output)
        self.analysis_file = Path(analysis_file)
        
    def run(self):
        logger.info(f"🔇 Starting Mute Refiner...")
        
        # 1. Load Analysis
        try:
            with open(self.analysis_file, 'r') as f:
                self.analysis = json.load(f)
        except FileNotFoundError:
            logger.error(f"Analysis file not found: {self.analysis_file}")
            return

        # 2. Load Input SM
        try:
            with open(self.sm_input, 'r', encoding='utf-8') as f:
                self.sm_content = f.read()
        except FileNotFoundError:
            logger.error(f"SM file not found: {self.sm_input}")
            return
            
        # 3. Analyze Audio Levels
        rms_threshold = self._calculate_silence_threshold()
        logger.info(f"   Silence Threshold (RMS): {rms_threshold:.4f}")
        
        # 4. Process Charts
        new_content = self._process_charts(rms_threshold)
        
        # 5. Save
        with open(self.sm_output, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info(f"✅ Mute Refiner Applied: {self.sm_output}")

    def _calculate_silence_threshold(self):
        """
        Determines what counts as 'silence'.
        Uses a percentage of the global average RMS.
        """
        beat_stats = self.analysis['beat_stats']
        # Collect all RMS values from beats
        all_rms = [b['rms_mean'] for b in beat_stats]
        
        if not all_rms:
            return 0.0
            
        avg_rms = np.mean(all_rms)
        
        # Threshold: 15% of average volume? 
        # User said "volume molto basso rispetto alla media".
        # 10-15% is usually a safe bet for "silence" vs "quiet part".
        # Let's try 15% to be aggressive enough but safe.
        threshold = avg_rms * 0.15
        
        return threshold

    def _process_charts(self, threshold):
        """
        Parses the SM file, finds all charts, and cleans them.
        """
        content = self.sm_content
        total_removed = 0
        
        # Split by #NOTES: to handle multiple charts
        parts = re.split(r'(#NOTES:)', content)
        
        new_parts = [parts[0]] # Header/Metadata
        
        beat_stats = self.analysis['beat_stats']
        if not beat_stats:
            return content # No audio data, can't process
            
        # Helper to get time from beat index
        def get_time_for_beat(beat_idx):
            int_beat = int(beat_idx)
            frac = beat_idx - int_beat
            
            if int_beat < len(beat_stats):
                t1 = beat_stats[int_beat]['time']
                if int_beat + 1 < len(beat_stats):
                    t2 = beat_stats[int_beat+1]['time']
                    return t1 + (t2 - t1) * frac
                else:
                    return t1 + frac * 0.5 # Estimate
            return 0.0

        # Helper to get RMS at time
        # We use the beat_stats approximation for speed and alignment
        def get_rms_at_beat(beat_idx):
            int_beat = int(beat_idx)
            if int_beat < len(beat_stats):
                return beat_stats[int_beat]['rms_mean']
            return 0.0

        i = 1
        while i < len(parts):
            tag = parts[i] # #NOTES:
            body = parts[i+1] # content... ;
            
            # Extract chart body (up to ;)
            end_idx = body.find(';')
            if end_idx == -1:
                # Should not happen in valid SM
                new_parts.append(tag)
                new_parts.append(body)
                i += 2
                continue
                
            chart_def = body[:end_idx]
            remainder = body[end_idx:] # ; and anything after
            
            # Parse chart def
            chart_parts = chart_def.split(':')
            if len(chart_parts) >= 6:
                # It's a chart!
                # Last part is data
                data_str = chart_parts[-1]
                # Keep prefix
                prefix = ":".join(chart_parts[:-1]) + ":"
                
                # Remove comments from data
                clean_data_str = re.sub(r'//.*', '', data_str)
                
                measures_raw = clean_data_str.split(',')
                cleaned_measures = []
                
                total_measures = len(measures_raw)
                
                for m_idx, m_str in enumerate(measures_raw):
                    rows = [r.strip() for r in m_str.strip().split('\n') if r.strip()]
                    num_rows = len(rows)
                    if num_rows == 0:
                        cleaned_measures.append(m_str) # Keep empty
                        continue
                        
                    new_rows = []
                    for r_idx, row in enumerate(rows):
                        # Calculate Beat
                        beat = (m_idx * 4) + (r_idx / num_rows * 4)
                        
                        # Get RMS
                        # We look up the closest beat stat
                        rms = get_rms_at_beat(beat)
                        
                        # Check Silence
                        if rms < threshold:
                            # MUTE!
                            # Replace with 0000 (assuming 4 lanes)
                            # Or strictly '0' * len(row) if not 4? SM is usually 4.
                            
                            # Count if we are actually removing notes (not just replacing 0000 with 0000)
                            if any(c in '1234' for c in row):
                                total_removed += 1
                                
                            new_rows.append('0000')
                        else:
                            new_rows.append(row)
                            
                    cleaned_measures.append("\n".join(new_rows))
                
                # Reconstruct
                new_data_str = ",\n".join(cleaned_measures)
                new_chart_def = prefix + "\n" + new_data_str
                
                new_parts.append(tag)
                new_parts.append(new_chart_def + remainder)
                
            else:
                # Not a chart?
                new_parts.append(tag)
                new_parts.append(body)
                
            i += 2
            
        logger.info(f"   Removed {total_removed} rows containing notes due to silence.")
        return "".join(new_parts)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        import glob
        sm_files = glob.glob("songs/*.sm")
        if sm_files:
            print(f"Auto-running Mute Refiner on {sm_files[0]}")
            refiner = ChartRefinerMute(sm_files[0], sm_files[0], "analysis_data.json")
            refiner.run()
        else:
            print("Usage: python chart_refiner_mute.py input.sm output.sm analysis.json")
    else:
        refiner = ChartRefinerMute(sys.argv[1], sys.argv[2], sys.argv[3])
        refiner.run()
