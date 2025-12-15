#!/usr/bin/env python3
"""
🎧 Audio Analyzer - The "Brain" of the StepGenerator Pipeline.

This script performs a deep-dive analysis of an audio file and synchronizes 
it with a StepMania (.sm) chart's timing grid. 

It extracts:
- Low-level spectral features (Centroid, Bandwidth, Rolloff, Contrast, Flatness)
- Rhythmic features (Onset Strength, varying hop lengths)
- Energy features (RMS, Amplitude Envelope)
- Harmonic features (Chroma, Tonnetz)
- Percussive features (Zero Crossing Rate)

It saves a rich JSON file (`analysis_data.json`) containing:
1. High-resolution time-series data for all features.
2. Beat-synchronized statistics (mean/max/median) for every beat in the chart.
"""

import json
import numpy as np
import librosa
import sys
import re
from pathlib import Path
import logging
from datetime import datetime

# Setup Logging
def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / f"audio_analyzer_{timestamp}.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class AudioAnalyzer:
    def __init__(self, mp3_path, sm_path=None):
        self.mp3_path = Path(mp3_path)
        self.sm_path = Path(sm_path) if sm_path else None
        self.data = {}
        
    def run(self, pre_analyze_only=False):
        """Main execution flow"""
        logger.info(f"🚀 Starting Analysis for: {self.mp3_path.name}")
        
        # 0. Check for cached raw features
        output_file = Path("analysis_data.json")
        cached_data = None
        has_valid_cache = False
        
        if output_file.exists():
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                
                # Verify if cache belongs to this file
                # Normalize paths for comparison
                cached_source = Path(cached_data.get('info', {}).get('source_file', '')).name
                current_source = self.mp3_path.name
                
                if cached_source == current_source and 'raw_features' in cached_data:
                    has_valid_cache = True
                    logger.info("♻️  Found valid cached features. Skipping heavy audio processing.")
            except Exception as e:
                logger.warning(f"Failed to read cache: {e}")

        features = None
        y = None
        sr = 22050 # Default
        
        # 1. Load/Extract Features
        if has_valid_cache:
            features = cached_data['raw_features']
            sr = features['metadata']['sr']
        else:
            # Load and Extract
            y, sr = self._load_audio()
            features = self._extract_features(y, sr)
            
            # If pre-analyze mode, save and exit
            if pre_analyze_only:
                self._save_partial_json(features, sr)
                logger.info("⏸️  Pre-analysis complete. Data cached.")
                return

        # 2. Parse SM Timing (Beats/BPM)
        # We need duration. If y is not loaded, get it from file.
        duration = 0.0
        if y is not None:
            duration = librosa.get_duration(y=y, sr=sr)
        else:
            duration = librosa.get_duration(path=str(self.mp3_path))
            
        beats, offset, bpms = self._parse_sm_timing(duration, sr)
        
        # 3. Synchronize Features to Beats
        beat_stats = self._calculate_beat_stats(features, beats, sr)
        
        # 4. Save Data
        self._save_json(features, beat_stats, beats, offset, bpms, sr)
        
        logger.info("✅ Analysis Complete!")

    def _save_partial_json(self, raw_features, sr):
        """Saves only the raw features for caching"""
        output_data = {
            'info': {
                'generated_at': datetime.now().isoformat(),
                'source_file': str(self.mp3_path),
                'sr': sr
            },
            'raw_features': raw_features
        }
        if 'hold_segments' in raw_features:
            output_data['hold_segments'] = raw_features['hold_segments']
            
        output_file = Path("analysis_data.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=None)
        logger.info(f"Partial data saved to {output_file.absolute()}")

    def _load_audio(self):
        logger.info("loading audio...")
        try:
            # Load with standard sr=22050 for efficiency, mono
            y, sr = librosa.load(str(self.mp3_path), sr=22050, mono=True)
            logger.info(f"Audio loaded: {len(y)/sr:.2f}s @ {sr}Hz")
            return y, sr
        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            sys.exit(1)

    def _parse_sm_timing(self, duration, sr):
        logger.info("Parsing SM timing...")
        try:
            with open(self.sm_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract Offset
            offset_match = re.search(r'#OFFSET:([-\d.]+);', content)
            if not offset_match: raise ValueError("OFFSET not found in .sm")
            offset = float(offset_match.group(1))
            
            # Extract BPMs
            bpms_match = re.search(r'#BPMS:([^;]+);', content)
            if not bpms_match: raise ValueError("BPMS not found in .sm")
            
            bpm_str = bpms_match.group(1)
            bpm_changes = []
            for item in bpm_str.split(','):
                beat, value = item.strip().split('=')
                bpm_changes.append((float(beat), float(value)))
            
            # Calculate Beat Timestamps from BPMs
            # We recreate the grid that StepMania uses
            # duration is passed as argument
            
            # SAFETY MARGIN: Stop grid generation 1.5s before end of audio
            # This ensures refiners don't place notes in the fadeout/silence
            effective_duration = max(0, duration - 1.5)
            
            beats = []
            
            curr_beat = 0.0
            curr_time = -offset
            bpm_idx = 0
            
            # We simulate walking through the song beat by beat
            while curr_time < effective_duration:
                # Find current BPM
                # Check if we passed a BPM change
                if bpm_idx < len(bpm_changes) - 1:
                    next_change_beat = bpm_changes[bpm_idx+1][0]
                    if curr_beat >= next_change_beat:
                        bpm_idx += 1
                
                current_bpm = bpm_changes[bpm_idx][1]
                
                beats.append({
                    'beat_index': round(curr_beat, 3), # Float beat index (0.0, 1.0, 2.0...)
                    'time': float(curr_time),
                    'is_downbeat': int(curr_beat) % 4 == 0,
                    'measure': int(curr_beat) // 4
                })
                
                # Advance 1 beat
                sec_per_beat = 60.0 / current_bpm
                curr_time += sec_per_beat
                curr_beat += 1.0
            
            logger.info(f"Generated {len(beats)} beats grid from SM metadata.")
            return beats, offset, bpm_changes
            
        except Exception as e:
            logger.error(f"Failed to parse SM timing: {e}")
            sys.exit(1)

    def _extract_features(self, y, sr):
        logger.info("Extracting deep audio features...")
        
        # Standard hop length for feature extraction (512 samples ~= 23ms)
        hop_length = 512
        
        def to_list(numpy_arr):
            """Helper to convert numpy arrays for JSON serialization"""
            return numpy_arr.flatten().tolist()
        
        # 1. Onset Strength (The most important for rhythm)
        # We calculate it directly
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
        
        # 2. RMS Energy (Volume/Power)
        rms = librosa.feature.rms(y=y, hop_length=hop_length)
        
        # --- BASS/LOW FREQUENCY ENERGY ---
        # Low-pass filter to isolate bass (e.g., < 200 Hz)
        # We use a 4th order Butterworth filter
        from scipy.signal import butter, sosfilt
        sos = butter(4, 200, 'low', fs=sr, output='sos')
        y_low = sosfilt(sos, y)
        low_freq_rms = librosa.feature.rms(y=y_low, hop_length=hop_length)

        # 3. Spectral Features (Timbre)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop_length)
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop_length)
        contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop_length) # Multi-band
        flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop_length)
        
        # --- HOLD DETECTION LOGIC (Harmonic Analysis) ---
        logger.info("  Analyzing harmonics for Holds...")
        # 1. Separate Harmonic (Sustained) and Percussive (Transient) components
        y_harmonic, y_percussive = librosa.effects.hpss(y)
        
        # 2. Calculate RMS energy for both
        rms_harmonic = librosa.feature.rms(y=y_harmonic, frame_length=2048, hop_length=hop_length)[0]
        rms_percussive = librosa.feature.rms(y=y_percussive, frame_length=2048, hop_length=hop_length)[0]
        
        # 3. Normalize (0-1) to make them comparable
        rms_harmonic = librosa.util.normalize(rms_harmonic)
        rms_percussive = librosa.util.normalize(rms_percussive)
        
        # 4. Identify Sustained Segments
        # Criteria: Harmonic energy > Threshold AND Harmonic > Percussive * Ratio
        hold_segments = []
        
        H_THRESH = 0.25      # Minimum harmonic intensity (0.0 - 1.0)
        HP_RATIO = 1.1       # Harmonic must be stronger than Percussive
        MIN_DURATION = 0.4   # Minimum hold length in seconds (otherwise it's just a tap)
        
        frames_per_sec = sr / hop_length
        min_frames = int(MIN_DURATION * frames_per_sec)
        
        is_holding = False
        start_frame = 0
        
        for i in range(len(rms_harmonic)):
            h_val = rms_harmonic[i]
            p_val = rms_percussive[i]
            
            # Use a small epsilon for p_val to avoid div by zero, or just simple comparison
            # Is this frame dominated by sustained sound?
            is_sustained = (h_val > H_THRESH) and (h_val > (p_val * HP_RATIO))
            
            if is_sustained and not is_holding:
                is_holding = True
                start_frame = i
            elif not is_sustained and is_holding:
                # End of a hold segment
                is_holding = False
                duration_frames = i - start_frame
                
                if duration_frames >= min_frames:
                    # Convert frames to seconds
                    start_time = librosa.frames_to_time(start_frame, sr=sr, hop_length=hop_length)
                    end_time = librosa.frames_to_time(i, sr=sr, hop_length=hop_length)
                    
                    hold_segments.append({
                        "start": float(start_time),
                        "end": float(end_time),
                        "duration": float(end_time - start_time)
                    })
        
        logger.info(f"  Found {len(hold_segments)} potential hold segments.")

        # 4. Zero Crossing Rate (Noisiness/Percussion)
        zcr = librosa.feature.zero_crossing_rate(y, hop_length=hop_length)
        
        # 5. Chroma (Harmony) - Optional/Heavy but user requested "ALL"
        # We use CQT for better musical relevance
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
        
        # 6. Tonnetz (Tonal Centroids)
        tonnetz = librosa.feature.tonnetz(y=librosa.effects.harmonic(y), sr=sr, chroma=chroma)
        
        # Time array for synchronization
        times = librosa.times_like(onset_env, sr=sr, hop_length=hop_length)
        
        features = {
            'metadata': {'sr': sr, 'hop_length': hop_length},
            'times': to_list(times),
            'onset_env': to_list(onset_env),
            'rms': to_list(rms),
            'low_freq_rms': to_list(low_freq_rms),
            'spectral_centroid': to_list(centroid),
            'spectral_bandwidth': to_list(bandwidth),
            'spectral_rolloff': to_list(rolloff),
            'spectral_flatness': to_list(flatness),
            'zero_crossing_rate': to_list(zcr),
            # Multidimensional features need care - simplified to mean for basic "strength" or kept full?
            # Keeping full can be huge. Let's keep mean for "contrast" general texture
            'spectral_contrast_mean': to_list(np.mean(contrast, axis=0)),
            # Chroma max index (dominant note) is often more useful than full matrix for simple charting
            'chroma_dominant': to_list(np.argmax(chroma, axis=0)),
            'tonnetz_mean': to_list(np.mean(tonnetz, axis=0)),
            'hold_segments': hold_segments
        }
        
        logger.info(f"Features extracted. Time frames: {len(times)}")
        return features

    def _calculate_beat_stats(self, features, beats, sr):
        logger.info("Synchronizing features to beat grid...")
        
        beat_stats = []
        hop_length = features['metadata']['hop_length']
        
        # Convert feature lists back to numpy for slicing
        # We assume all time-series features are aligned with 'times'
        # EXCLUDE 'hold_segments' from this sync process as it is not a time-series aligned with 'times'
        feature_keys = [k for k in features.keys() if k not in ['metadata', 'times', 'hold_segments']]
        np_features = {k: np.array(features[k]) for k in feature_keys}
        
        for i, beat in enumerate(beats):
            beat_time = beat['time']
            
            # Define a window around the beat to capture its "essence"
            # For 4th notes, we care about the exact hit. 
            # Window: -50ms to +100ms? Or simply calculate instantaneous value?
            # Let's take a small window of ~100ms centered on the beat for robustness
            
            start_time = max(0, beat_time - 0.05)
            end_time = beat_time + 0.05
            
            start_frame = librosa.time_to_frames(start_time, sr=sr, hop_length=hop_length)
            end_frame = librosa.time_to_frames(end_time, sr=sr, hop_length=hop_length)
            
            # Ensure valid range
            start_frame = min(start_frame, len(features['times'])-1)
            end_frame = min(end_frame, len(features['times'])-1)
            if end_frame <= start_frame: end_frame = start_frame + 1
            
            stat_entry = {
                'beat_index': beat['beat_index'],
                'time': beat['time'],
                'is_downbeat': beat['is_downbeat']
            }
            
            for key, data in np_features.items():
                segment = data[start_frame:end_frame]
                if len(segment) == 0:
                    stat_entry[key] = 0.0
                else:
                    # Capture metrics useful for logic
                    stat_entry[f"{key}_max"] = float(np.max(segment))
                    stat_entry[f"{key}_mean"] = float(np.mean(segment))
            
            beat_stats.append(stat_entry)
        
        return beat_stats

    def _save_json(self, raw_features, beat_stats, beats, offset, bpms, sr):
        output_data = {
            'info': {
                'generated_at': datetime.now().isoformat(),
                'source_file': str(self.mp3_path),
                'sr': sr,
                'offset': offset,
                'bpms': bpms
            },
            'beats': beats,
            'beat_stats': beat_stats,
            # 'raw_features': raw_features # Uncomment if needed, but beat_stats is usually enough and much smaller
        }
        
        # Save raw features in a separate file if needed, or included?
        # User said "scaricarli tutti... memorizzati... capillare". 
        # Making a single file might be huge if raw chroma is included.
        # But for 3-4 mins, it's manageable (~few MBs). Let's include everything.
        output_data['raw_features'] = raw_features
        # Explicitly add hold_segments to the root of output data for easier access
        if 'hold_segments' in raw_features:
            output_data['hold_segments'] = raw_features['hold_segments']
        
        output_file = Path("analysis_data.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=None) # Compact JSON to save space
            
        logger.info(f"Data saved to {output_file.absolute()}")


import argparse

def main():
    parser = argparse.ArgumentParser(description="Audio Analyzer for StepGenerator")
    parser.add_argument("mp3_file", nargs='?', help="Path to MP3 file")
    parser.add_argument("sm_file", nargs='?', help="Path to SM file")
    parser.add_argument("--pre-analyze", action="store_true", help="Only extract and cache raw features")
    
    args = parser.parse_args()
    
    if args.mp3_file:
        # Check requirements
        if not args.pre_analyze and not args.sm_file:
             print("Error: SM file is required for full analysis (unless --pre-analyze is used).")
             sys.exit(1)

        analyzer = AudioAnalyzer(args.mp3_file, args.sm_file)
        analyzer.run(pre_analyze_only=args.pre_analyze)
    else:
        # Fallback for testing/manual run (legacy behavior)
        if len(sys.argv) < 3:
            print("Usage: python audio_analyzer.py <mp3_file> <sm_file> [--pre-analyze]")
            # Try auto-detect
            import glob
            sm_files = glob.glob("songs/*.sm")
            if sm_files:
                sm_file = sm_files[0]
                mp3_file = sm_file.replace('.sm', '.mp3')
                print(f"Auto-detecting: {mp3_file} + {sm_file}")
                analyzer = AudioAnalyzer(mp3_file, sm_file)
                analyzer.run()
            else:
                sys.exit(1)
        else:
             # This branch might be reached if using sys.argv manually without argparse if structure was different,
             # but argparse handles it. Just safety.
             pass

if __name__ == "__main__":
    main()