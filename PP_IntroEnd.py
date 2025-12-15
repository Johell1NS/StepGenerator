import json
import logging
from pathlib import Path
import re
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Thresholds for RMS (Volume)
SILENCE_THRESHOLD = 0.02      # Below this, remove ALL notes
LOW_VOLUME_THRESHOLD = 0.15   # Below this, remove non-4th notes (Blue/Yellow/etc), keep Red

def refine_chart_intro_end(sm_file_path, analysis_data_path="analysis_data.json"):
    logger.info(f"Refining chart Intro/End (Cleanup): {sm_file_path}")
    
    # 1. Load Analysis Data
    try:
        with open(analysis_data_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
        
        beat_stats = analysis_data.get('beat_stats', [])
        
        if not beat_stats:
            logger.warning("No beat_stats found in analysis data. Skipping.")
            return

    except FileNotFoundError:
        logger.error(f"Analysis file not found: {analysis_data_path}")
        return

    # 2. Analyze Volume Profile
    first_active_beat = 0.0
    last_active_beat = float('inf')
    fade_out_start_beat = float('inf')
    
    window_size = 4
    for i in range(len(beat_stats) - window_size):
        window = beat_stats[i:i+window_size]
        avg_rms = sum(b.get('rms_mean', 0) for b in window) / window_size
        if avg_rms > SILENCE_THRESHOLD:
            first_active_beat = beat_stats[i]['beat_index']
            break
            
    for i in range(len(beat_stats) - 1, -1, -1):
        rms = beat_stats[i].get('rms_mean', 0)
        if rms > SILENCE_THRESHOLD:
            last_active_beat = beat_stats[i]['beat_index']
            break
            
    for i in range(len(beat_stats) - 1, -1, -1):
        beat_idx = beat_stats[i]['beat_index']
        if beat_idx > last_active_beat: continue
        
        rms = beat_stats[i].get('rms_mean', 0)
        if rms > LOW_VOLUME_THRESHOLD:
            fade_out_start_beat = beat_idx
            break
            
    logger.info(f"Intro/End Analysis:")
    logger.info(f"  First Active Beat: {first_active_beat}")
    logger.info(f"  Fade Out Start:    {fade_out_start_beat}")
    logger.info(f"  Last Active Beat:  {last_active_beat}")

    # 3. Read SM File
    try:
        with open(sm_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read SM file: {e}")
        return

    # 4. Split Charts
    parts = re.split(r'(#NOTES:)', content, flags=re.IGNORECASE)
    
    new_parts = [parts[0]] # Header/Metadata
    
    total_notes_removed_all = 0
    
    i = 1
    while i < len(parts):
        tag = parts[i]
        body = parts[i+1]
        
        # Parse body: Header parts ... Data ... ;
        end_idx = body.find(';')
        if end_idx == -1:
            # Malformed? Just append
            new_parts.append(tag)
            new_parts.append(body)
            i += 2
            continue
            
        chart_def = body[:end_idx]
        rest = body[end_idx:] # ; and whatever follows
        
        # Split def by colon
        def_parts = chart_def.split(':')
        if len(def_parts) >= 6:
            # Last part is data
            data_str = def_parts[-1]
            # Headers
            headers = def_parts[:-1]
            
            # Process Data
            clean_data = re.sub(r'//.*', '', data_str) # Remove comments
            measures_raw = clean_data.split(',')
            
            modified_measures = []
            
            for m_idx, m_str in enumerate(measures_raw):
                rows = [r.strip() for r in m_str.strip().split('\n') if r.strip()]
                new_rows = []
                num_rows = len(rows)
                if num_rows == 0: 
                    modified_measures.append(rows)
                    continue
                    
                for r_idx, row in enumerate(rows):
                    beat = m_idx * 4.0 + (r_idx / num_rows) * 4.0
                    
                    should_remove = False
                    should_filter_blue = False
                    
                    if beat < first_active_beat:
                        should_remove = True
                    elif beat > last_active_beat:
                        should_remove = True
                    elif beat > fade_out_start_beat:
                        should_filter_blue = True
                        
                    if should_remove:
                        if row != "0000":
                            new_rows.append("0000")
                            total_notes_removed_all += 1
                        else:
                            new_rows.append(row)
                    elif should_filter_blue:
                        is_red = abs(beat - round(beat)) < 0.001
                        if not is_red:
                            if row != "0000":
                                new_rows.append("0000")
                                total_notes_removed_all += 1
                            else:
                                new_rows.append(row)
                        else:
                            new_rows.append(row)
                    else:
                        new_rows.append(row)
                
                modified_measures.append(new_rows)
            
            # Reconstruct Data String
            new_data_str = "\n" + ",\n".join(["\n".join(m) for m in modified_measures])
            
            # Reconstruct Chart Block
            new_chart_def = ":".join(headers) + ":" + new_data_str
            
            new_parts.append(tag)
            new_parts.append(new_chart_def + rest)
            
        else:
            new_parts.append(tag)
            new_parts.append(body)
            
        i += 2
        
    logger.info(f"Total notes removed across all charts: {total_notes_removed_all}")
    
    with open(sm_file_path, 'w', encoding='utf-8') as f:
        f.write("".join(new_parts))
        
    logger.info("Charts updated successfully.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        refine_chart_intro_end(sys.argv[1])
    else:
        # Test mode
        import glob
        sm_files = glob.glob("songs/*.sm")
        if sm_files:
            refine_chart_intro_end(sm_files[0])
