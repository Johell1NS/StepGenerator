import os
import time
import pygame
import librosa
import numpy as np

# Console Color Configuration
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def get_top_bpm_candidates_fft(onset_env, sr, hop_length, n_candidates=5):
    """
    Calculates the best BPM candidates using FFT.
    Returns a list of tuples (bpm, score) normalized.
    """
    try:
        # 1. Signal Preparation
        onset_centered = onset_env - np.mean(onset_env)
        window = np.hanning(len(onset_centered))
        signal = onset_centered * window

        # 2. FFT
        n_fft = 1 << 20
        spectrum = np.abs(np.fft.rfft(signal, n=n_fft))
        freqs = np.fft.rfftfreq(n_fft, d=hop_length/sr)

        # 3. Conversion
        bpms = freqs * 60.0
        mask = (bpms >= 40) & (bpms <= 250)

        if not np.any(mask):
            return [(120.0, 0.0)]

        spectrum_masked = spectrum[mask]
        bpms_masked = bpms[mask]

        # 4. Find Peaks
        peaks = []
        for i in range(1, len(spectrum_masked) - 1):
            if spectrum_masked[i] > spectrum_masked[i-1] and spectrum_masked[i] > spectrum_masked[i+1]:
                peaks.append((spectrum_masked[i], i))

        # Sort by score
        peaks.sort(key=lambda x: x[0], reverse=True)

        # Normalize score (0-1)
        max_score = peaks[0][0] if peaks else 1.0
        if max_score == 0: max_score = 1.0

        top_peaks = peaks[:n_candidates]
        candidates = []

        global_indices = np.where(mask)[0]

        for amp, local_idx in top_peaks:
            peak_global_idx = global_indices[local_idx]
            refined_bpm = bpms_masked[local_idx]

            # Interpolation
            if 0 < peak_global_idx < len(spectrum) - 1:
                y0 = spectrum[peak_global_idx - 1]
                y1 = spectrum[peak_global_idx]
                y2 = spectrum[peak_global_idx + 1]
                denom = y0 - 2 * y1 + y2
                if denom != 0:
                    p = 0.5 * (y0 - y2) / denom
                    refined_freq = freqs[peak_global_idx] + p * (freqs[1] - freqs[0])
                    refined_bpm = refined_freq * 60.0

            candidates.append((refined_bpm, amp / max_score))
            
        return candidates
        
    except Exception as e:
        print(f"FFT BPM Error: {e}")
        return [(120.0, 0.0)]

def get_candidates_autocorr(onset_env, sr, hop_length, n_candidates=5):
    """
    Finds BPM candidates using Autocorrelation.
    Returns a list of tuples (bpm, score) normalized.
    """
    try:
        max_lag = int(60.0 / 40.0 * sr / hop_length)
        min_lag = int(60.0 / 250.0 * sr / hop_length)
        
        ac = librosa.autocorrelate(onset_env, max_size=max_lag + 100)
        
        candidates = []
        for lag in range(min_lag, max_lag):
            if lag >= len(ac) - 1: break
            
            if ac[lag] > ac[lag-1] and ac[lag] > ac[lag+1]:
                y0, y1, y2 = ac[lag-1], ac[lag], ac[lag+1]
                denom = y0 - 2 * y1 + y2
                refined_lag = lag + (0.5 * (y0 - y2) / denom) if denom != 0 else lag
                
                bpm = 60.0 * sr / (hop_length * refined_lag)
                candidates.append((bpm, ac[lag]))
        
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Normalize score
        max_score = candidates[0][1] if candidates else 1.0
        if max_score == 0: max_score = 1.0
        
        return [(c[0], c[1] / max_score) for c in candidates[:n_candidates]]
        
    except Exception as e:
        print(f"Autocorr BPM Error: {e}")
        return []

def calculate_phase_coherence(bpm, beat_times):
    """
    Calculates phase coherence for a given BPM with respect to detected beats.
    Returns a value between 0 and 1 (1 = perfect coherence).
    """
    if bpm <= 0 or len(beat_times) == 0:
        return 0.0
    
    # Phase angle for each beat: phi = (time * BPM / 60) * 2pi
    # If the BPM is correct, phi mod 2pi should be constant (or vary slowly)
    # We calculate the unit vector sum
    phases = 2 * np.pi * beat_times * (bpm / 60.0)
    vector_sum = np.sum(np.exp(1j * phases))
    coherence = np.abs(vector_sum) / len(beat_times)
    return coherence

def load_audio_analysis(file_path):
    print(f"{Colors.BLUE}⏳ Advanced BPM Analysis (Full Song + Phase Check) in progress...{Colors.ENDC}")
    try:
        # 1. Audio Loading
        print("   Full audio loaded (22050Hz)...")
        y, sr = librosa.load(file_path, sr=22050)
        total_duration = librosa.get_duration(y=y, sr=sr)

        # 2. Onset Envelope
        hop_len = 128
        print("   Computing Onset Envelope...")
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_len)

        # 3. Generate Candidates
        print("   Generating BPM Candidates (FFT + Autocorr)...")
        # We reduce base n_candidates to be more selective
        fft_candidates = get_top_bpm_candidates_fft(onset_env, sr, hop_len, n_candidates=4)
        ac_candidates = get_candidates_autocorr(onset_env, sr, hop_len, n_candidates=4)
        
        # Candidate pool with score (BPM, Score)
        # Combined score: we give Autocorrelation slightly more weight for rhythmic stability
        weighted_candidates = []

        for bpm, score in fft_candidates:
            weighted_candidates.append((bpm, score * 1.0))

        for bpm, score in ac_candidates:
            weighted_candidates.append((bpm, score * 1.2))  # Autocorr Boost
            
        # Generate Variants (with score penalty)
        final_pool = []

        def add_candidate(bpm, score):
            if not (40 <= bpm <= 250): return

            # Check nearby duplicates
            for i, (existing_bpm, existing_score) in enumerate(final_pool):
                if abs(existing_bpm - bpm) < 0.05:
                    # If the new one is "better" (higher score), replace or ignore
                    if score > existing_score:
                        final_pool[i] = (bpm, score)
                    return  # Already present

            final_pool.append((bpm, score))

        for bpm, score in weighted_candidates:
            add_candidate(bpm, score)  # Original

            # Integer Variants (Very likely in modern songs)
            add_candidate(round(bpm), score * 0.95)

            # Semi-Integer Variants (e.g. 128.5)
            add_candidate(round(bpm * 2) / 2, score * 0.90)

            # Octave Variants (Double/Half time) - Higher penalty
            add_candidate(bpm * 2, score * 0.7)
            add_candidate(bpm * 0.5, score * 0.7)

        # Sort by Descending Score
        final_pool.sort(key=lambda x: x[1], reverse=True)

        # TAKE ONLY TOP N (e.g. 12) to avoid freeze
        top_candidates = final_pool[:12]

        print(f"   Evaluating Top {len(top_candidates)} candidates (out of {len(final_pool)} total)...")

        print(f"\n   {Colors.BLUE}Evaluating Candidates (Beat Track Seeded):{Colors.ENDC}")
        best_bpm = 120.0
        best_score = -1.0
        
        results = []
        
        for i, (start_bpm, prior_score) in enumerate(top_candidates):
            # Visual feedback for user
            print(f"   [{i+1}/{len(top_candidates)}] Testing BPM: {start_bpm:.2f}...", end="\r")
            
            try:
                tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=hop_len, start_bpm=start_bpm, tightness=100)
            except:
                continue
                
            if isinstance(tempo, np.ndarray):
                tempo = float(tempo[0]) if tempo.size > 0 else start_bpm
            else:
                tempo = float(tempo)
                
            beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=hop_len)
            
            phase_score = calculate_phase_coherence(tempo, beat_times)

            # Combine phase_score with prior_score? No, let's trust the phase.
            # Phase is the real alignment test.

            # Avoid duplicates
            exists = False
            for r in results:
                if abs(r[0] - tempo) < 0.05:
                    if phase_score > r[1]: 
                        r[1] = phase_score
                    exists = True
                    break
            
            if not exists:
                results.append([tempo, phase_score])

        print(" " * 50, end="\r")  # Clean line

        # Sort results
        results.sort(key=lambda x: x[1], reverse=True)
        
        if results:
            best_bpm = results[0][0]
            best_score = results[0][1]
            
            # Print Top 3
            for bpm, score in results[:3]:
                marker = "⭐️" if bpm == best_bpm else ""
                print(f"   BPM: {bpm:.6f} -> Coherence: {score:.4f} {marker}")
        
        print(f"\n{Colors.GREEN}✅ Winning BPM: {best_bpm:.6f} (Coherence: {best_score:.4f}){Colors.ENDC}")
        
        return best_bpm, total_duration

    except Exception as e:
        print(f"{Colors.FAIL}❌ Error during audio analysis: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        return 120.0, 0  # Fallback


def create_sm_content(title, artist, music_file, offset, bpm):
    # Base template identical to ArrowVortex's
    content = f"""#TITLE:{title};
#SUBTITLE:;
#ARTIST:{artist};
#TITLETRANSLIT:;
#SUBTITLETRANSLIT:;
#ARTISTTRANSLIT:;
#GENRE:;
#CREDIT:StepGenerator Calibrator;
#MUSIC:{music_file};
#BANNER:;
#BACKGROUND:;
#CDTITLE:;
#SAMPLESTART:0.000000;
#SAMPLELENGTH:0.000000;
#SELECTABLE:YES;
#OFFSET:{offset:.6f};
#BPMS:0.000000={bpm:.6f};
#STOPS:;
#BGCHANGES:;
#FGCHANGES:;
// NOTE DATA to be added later
"""
    return content

def main():
    # Setup Audio Buffer to reduce latency
    # 512 is standard, 256 is very aggressive (~6ms) for minimal latency
    # If you hear crackling, increase to 512 or 1024
    try:
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=256)
    except Exception:
        pass # Fallback to default if fails
        
    pygame.init()
    pygame.mixer.init()
    
    # Setup Pygame window (required for keyboard events)
    screen_width = 600
    screen_height = 400
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("StepGenerator - Manual Calibration")
    font = pygame.font.SysFont("Arial", 24)
    small_font = pygame.font.SysFont("Arial", 18)

    # Enable key repeat (Delay 400ms, Interval 100ms)
    # This allows holding arrows to scroll quickly
    pygame.key.set_repeat(400, 100)

    # 1. File Selection
    src_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(src_dir)
    songs_folder = os.path.join(root_dir, "songs")
    if not os.path.exists(songs_folder):
         # Fallback if structure is different
         songs_folder = os.path.join(os.getcwd(), "songs")
         
    if os.path.exists(songs_folder):
        mp3_files = [f for f in os.listdir(songs_folder) if f.lower().endswith('.mp3')]
    else:
        mp3_files = []
    
    if not mp3_files:
        print(f"{Colors.FAIL}No MP3 files found in the 'songs' folder.{Colors.ENDC}")
        return

    print(f"\n{Colors.HEADER}--- SELECT TRACK TO CALIBRATE ---{Colors.ENDC}")
    for i, f in enumerate(mp3_files):
        print(f"{i+1}. {f}")
        
    try:
        choice = int(input(f"\n{Colors.BLUE}Enter track number: {Colors.ENDC}")) - 1
        if choice < 0 or choice >= len(mp3_files):
            raise ValueError
        selected_mp3 = mp3_files[choice]
        mp3_path = os.path.join(songs_folder, selected_mp3)
    except:
        print("Invalid choice.")
        return

    # 2. Initial Analysis
    bpm, duration = load_audio_analysis(mp3_path)
    
    # Generate EXTRA dry metronome 'Tick' sound (Digital Click Style)
    sample_rate = 44100
    duration_beep = 0.03  # Slightly increased to give "body" to the click, but the envelope will cut it

    def generate_tick_sound(freq, duration_sec, sr):
        n_samples = int(sr * duration_sec)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False)

        # Square Wave instead of Sine
        # Square wave has many more harmonics, so it "cuts through" the mix better (more audible)
        # and is less "sweet/tonal" than sine, resulting more "mechanical/dry".
        waveform = np.sign(np.sin(2 * np.pi * freq * t))

        # Fast Percussive Envelope
        # exp(-t * 200) is a fast decay.
        # This transforms the "BEEP" (continuous square wave) into a "TIK" (short impulse).
        envelope = np.exp(-t * 150)

        # Apply envelope
        signal = waveform * envelope

        # MAX normalization (Controlled saturation)
        max_amp = 2**15 - 1
        # Use 0.95 to avoid unpleasant digital clipping, but maximize volume
        signal_int = (signal * max_amp * 0.95).astype(np.int16)
        
        return pygame.sndarray.make_sound(np.column_stack((signal_int, signal_int)))

    # Frequencies for Digital 'Click' (StepMania/ArrowVortex Style)
    # Downbeat (1): Very sharp, almost a closed 'hat'
    down_beep_sound = generate_tick_sound(2000, duration_beep, sample_rate)

    # Beat (2,3,4): Sharp but distinct
    beep_sound = generate_tick_sound(1200, duration_beep, sample_rate)
    
    # 3. Interactive Loop
    pygame.mixer.music.load(mp3_path)
    pygame.mixer.music.play()
    
    offset = 0.0
    is_calibrated = False
    last_beat_time = 0
    running = True
    clock = pygame.time.Clock()
    
    # Playback Time Management
    playback_offset = 0.0  # Temporal offset due to seeks (forward/backward)
    
    # Volume Control
    beep_volume = 0.5
    beep_sound.set_volume(beep_volume)
    down_beep_sound.set_volume(beep_volume)
    
    instruction_text = [
        "CONTROLS:",
        "DOWN ARROW: Set the FIRST DOWNBEAT (Sync)",
        "NUMPAD 4/6: Shift Offset +/- 10ms (Fine Tuning)",
        "NUMPAD 8/2: Double/Halve BPM",
        "1-9, 0: Adjust Beep Volume (10%-100%)",
        "LEFT/RIGHT ARROW (Hold): Skip +/- 5s",
        "ENTER: Save and Exit",
        "ESC: Exit without saving"
    ]

    while running:
        if pygame.mixer.music.get_busy():
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms < 0: pos_ms = 0
            current_time = playback_offset + (pos_ms / 1000.0)
        else:
            current_time = playback_offset
        
        # Gestione Eventi (Click singoli e Ripetizione)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RETURN:
                    if is_calibrated:
                        running = False
                        # Save
                        sm_filename = os.path.splitext(selected_mp3)[0] + ".sm"
                        sm_path = os.path.join(songs_folder, sm_filename)
                        
                        # Ask for basic info if not available
                        title = os.path.splitext(selected_mp3)[0]
                        artist = "Unknown"
                        
                        content = create_sm_content(title, artist, selected_mp3, offset, bpm)
                        with open(sm_path, "w") as f:
                            f.write(content)
                        print(f"\n{Colors.GREEN}✅ File saved: {sm_filename}{Colors.ENDC}")
                        print(f"   Offset: {offset:.6f}")
                        print(f"   BPM: {bpm:.6f}")
                    else:
                        print(f"{Colors.WARNING}⚠️  Set the downbeat first with DOWN ARROW!{Colors.ENDC}")

                elif event.key == pygame.K_DOWN:
                    # CALIBRATION
                    seconds_per_beat = 60.0 / bpm

                    # 1. Find nearest beat (snapping)
                    n_beats = round(current_time / seconds_per_beat)

                    # 2. Calculate measure phase (0, 1, 2, 3)
                    # We want the current beat to be a Downbeat (0)
                    # If n_beats % 4 != 0, we need to shift offset to align
                    rem = n_beats % 4

                    # 3. Calculate theoretical "Downbeat Index"
                    # This is the beat number (multiple of 4) that "should" be here
                    downbeat_index = n_beats - rem

                    # 4. Calculate offset based on this downbeat index
                    # Formula SM: Time = Offset + Beat * SPB  =>  Offset = Time - Beat * SPB
                    offset = current_time - (downbeat_index * seconds_per_beat)

                    # 5. Normalize Offset to keep it near 0 (between -2*SPB and +2*SPB)
                    # This avoids huge offsets if syncing mid-song
                    half_measure = seconds_per_beat * 2
                    measure = seconds_per_beat * 4

                    while offset > half_measure:
                        offset -= measure
                    while offset < -half_measure:
                        offset += measure

                    is_calibrated = True
                    screen.fill((50, 50, 50))  # Visual flash
                
                # FINE TUNING OFFSET (Numpad 4/6)
                elif event.key == pygame.K_KP4:
                    # Shift grid left (anticipate beat) -> Decrease Offset
                    offset -= 0.01  # -10ms
                    is_calibrated = True

                elif event.key == pygame.K_KP6:
                    # Shift grid right (delay beat) -> Increase Offset
                    offset += 0.01  # +10ms
                    is_calibrated = True
                    
                # BPM DOUBLING/HALVING (Numpad 8/2)
                elif event.key == pygame.K_KP8:
                    # Double BPM (Double Time)
                    # Note: Offset remains temporally valid, but beat index changes
                    bpm *= 2.0
                    print(f"BPM Doubled: {bpm:.2f}")

                elif event.key == pygame.K_KP2:
                    # Halve BPM (Half Time)
                    bpm /= 2.0
                    print(f"BPM Halved: {bpm:.2f}")

                # Volume Controls
                elif pygame.K_0 <= event.key <= pygame.K_9:
                    if event.key == pygame.K_0:
                        beep_volume = 1.0
                    else:
                        beep_volume = (event.key - pygame.K_0) / 10.0
                    
                    beep_sound.set_volume(beep_volume)
                    down_beep_sound.set_volume(beep_volume)
                    
                elif event.key == pygame.K_LEFT:
                    # REWIND 5s
                    new_pos = max(0, current_time - 5.0)
                    pygame.mixer.music.play(start=new_pos)
                    playback_offset = new_pos
                    
                elif event.key == pygame.K_RIGHT:
                    # FORWARD 5s
                    new_pos = min(duration, current_time + 5.0)
                    pygame.mixer.music.play(start=new_pos)
                    playback_offset = new_pos

        # Draw Interface
        screen.fill((0, 0, 0))

        # Info Text
        y_pos = 20
        text_surf = font.render(f"File: {selected_mp3}", True, (255, 255, 255))
        screen.blit(text_surf, (20, y_pos))
        y_pos += 40
        
        text_surf = font.render(f"BPM: {bpm:.2f}", True, (0, 255, 0))
        screen.blit(text_surf, (20, y_pos))
        y_pos += 40
        
        status_color = (0, 255, 0) if is_calibrated else (255, 0, 0)
        status_txt = f"Offset: {offset:.6f} s" if is_calibrated else "Offset: NOT CALIBRATED"
        text_surf = font.render(status_txt, True, status_color)
        screen.blit(text_surf, (20, y_pos))
        y_pos += 40
        
        vol_txt = f"Volume Beep: {int(beep_volume * 100)}%"
        text_surf = font.render(vol_txt, True, (200, 200, 0))
        screen.blit(text_surf, (20, y_pos))
        y_pos += 40

        # Time Display
        def format_time(seconds):
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m:02d}:{s:02d}"
            
        current_str = format_time(current_time)
        total_str = format_time(duration)
        time_txt = f"Time: {current_str} / {total_str}"
        
        text_surf = font.render(time_txt, True, (0, 200, 255))  # Cyan/Blue
        screen.blit(text_surf, (20, y_pos))
        y_pos += 60
        
        for line in instruction_text:
            t = small_font.render(line, True, (200, 200, 200))
            screen.blit(t, (20, y_pos))
            y_pos += 25
            
        # Metronome Logic
        if bpm > 0:
            spb = 60.0 / bpm

            effective_time = current_time

            # Formula SM: Time = Offset + Beat * SPB
            # Beat = (Time - Offset) / SPB
            beat_exact = (effective_time - offset) / spb
            beat_int = int(beat_exact)

            # If a new beat triggered
            if beat_int > last_beat_time:
                # Determine if it's a downbeat (start of 4/4 measure)
                is_downbeat = (beat_int % 4) == 0

                if is_calibrated:
                    # ONLY if calibrated we differentiate the sound
                    if is_downbeat:
                        down_beep_sound.play()
                        pygame.draw.circle(screen, (0, 255, 255), (500, 50), 20)  # Visual Flash Cyan
                    else:
                        beep_sound.play()
                        pygame.draw.circle(screen, (100, 100, 100), (500, 50), 15)  # Grey
                else:
                    # If NOT calibrated, always sounds the same (standard beep)
                    beep_sound.play()
                    pygame.draw.circle(screen, (100, 100, 100), (500, 50), 15)  # Grey
                
                last_beat_time = beat_int

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()