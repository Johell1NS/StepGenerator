import os
import sys
import shutil
import filecmp

def main():
    if len(sys.argv) < 2:
        print("Usage: python azioni_finali.py <sm_file_path>")
        sys.exit(1)

    sm_path = sys.argv[1]
    # Converti in percorso assoluto per sicurezza
    sm_path = os.path.abspath(sm_path)
    
    preserve_json = "--preserve-json" in sys.argv
    if preserve_json:
        print("🔧 --preserve-json option active: The analysis_data.json file in the folder will not be overwritten.")
    
    if not os.path.exists(sm_path):
        print(f"Error: .sm file not found: {sm_path}")
        sys.exit(1)

    directory = os.path.dirname(sm_path)
    sm_filename = os.path.basename(sm_path)
    
    print("--- Running Final Actions ---")
    print(f"Analyzing file: {sm_filename}")

    # 1. Find the MP3 filename by reading the .sm file
    mp3_filename = None
    try:
        with open(sm_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("#MUSIC:"):
                    # Example: #MUSIC:song.mp3;
                    content = line.split(":", 1)[1].strip()
                    if content.endswith(";"):
                        content = content[:-1]
                    mp3_filename = content.strip()
                    break
    except Exception as e:
        print(f"Error reading .sm file: {e}")
        sys.exit(1)

    if not mp3_filename:
        print("Warning: Unable to find #MUSIC tag in the .sm file")
        # Fallback: use same name as .sm but with .mp3 extension
        mp3_filename = os.path.splitext(sm_filename)[0] + ".mp3"
        print(f"Fallback: searching for audio based on .sm name: {mp3_filename}")

    mp3_path = os.path.join(directory, mp3_filename)
    
    # 2. Define folder name (mp3 filename without extension)
    folder_name = os.path.splitext(mp3_filename)[0]
    target_folder = os.path.join(directory, folder_name)
    
    # Safety check: if we're already inside the target folder, do nothing
    # Case 1: Identical paths (shouldn't happen with join)
    if os.path.normpath(directory) == os.path.normpath(target_folder):
        print("Files are already organized in the correct folder.")
        sys.exit(0)

    # Case 2: If the current folder already has the song name, assume it's already in place
    if os.path.basename(os.path.normpath(directory)).lower() == folder_name.lower():
         print(f"Files already appear to be in the correct folder '{folder_name}'. No move necessary.")
         # However, make sure analysis_data.json is present/updated if available in root/source
         analysis_src = os.path.join(os.getcwd(), "analysis_data.json")
         analysis_dest = os.path.join(directory, "analysis_data.json")
         
         if os.path.exists(analysis_src):
             should_copy = True
             if os.path.exists(analysis_dest):
                 if preserve_json:
                     should_copy = False
                     print("analysis_data.json preserved (--preserve-json flag active).")
                 else:
                     try:
                         # Compare content to avoid unnecessary updates (preserve timestamp)
                         if filecmp.cmp(analysis_src, analysis_dest, shallow=False):
                             should_copy = False
                     except: pass
             
             if should_copy:
                 try:
                     shutil.copy(analysis_src, analysis_dest)
                     print("Updated: analysis_data.json")
                 except: pass
             elif not preserve_json:
                 print("analysis_data.json already up to date (no changes).")
         sys.exit(0)

    # 3. Create folder if it doesn't exist
    if not os.path.exists(target_folder):
        try:
            os.makedirs(target_folder)
            print(f"Created new folder: {target_folder}")
        except Exception as e:
            print(f"Folder creation error: {e}")
            sys.exit(1)
    else:
        print(f"Destination folder already exists: {target_folder}")

    # 4. List of files to move
    files_to_move = [sm_path]
    
    if os.path.exists(mp3_path):
        files_to_move.append(mp3_path)
    else:
        print(f"Warning: MP3 file not found at '{mp3_path}'. It will not be moved.")

    # Also look for .ssc file
    ssc_filename = os.path.splitext(sm_filename)[0] + ".ssc"
    ssc_path = os.path.join(directory, ssc_filename)
    if os.path.exists(ssc_path):
        files_to_move.append(ssc_path)

    # Look for graphic files BG.png and BN.png
    bg_path = os.path.join(directory, "BG.png")
    bn_path = os.path.join(directory, "BN.png")
    if os.path.exists(bg_path):
        files_to_move.append(bg_path)
    if os.path.exists(bn_path):
        files_to_move.append(bn_path)
        
    # Look for any .lrc files or other correlated files with the same base name?
    # For now, limit to sm, ssc and mp3 as requested.

    # 5. Move files
    success_count = 0
    for file_path in files_to_move:
        try:
            fname = os.path.basename(file_path)
            dest_path = os.path.join(target_folder, fname)
            
            # If file already exists in destination, remove it first to overwrite
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except Exception as remove_err:
                    print(f"Unable to remove existing file {fname}: {remove_err}")
                    continue

            shutil.move(file_path, dest_path)
            print(f"Moved: {fname}")
            success_count += 1
        except Exception as e:
            print(f"Move error {file_path}: {e}")

    if success_count > 0:
        print(f"Operation completed. {success_count} file(s) moved into '{folder_name}'.")
    else:
        print("No files moved.")
    
    analysis_candidates = [
        os.path.join(os.getcwd(), "analysis_data.json"),
        os.path.join(directory, "analysis_data.json")
    ]
    analysis_src = None
    for cand in analysis_candidates:
        if os.path.exists(cand):
            analysis_src = cand
            break
    if analysis_src:
        dest_json_path = os.path.join(target_folder, "analysis_data.json")
        
        should_copy = True
        if os.path.exists(dest_json_path) and preserve_json:
             should_copy = False
             print("analysis_data.json preserved at destination (--preserve-json flag active).")
             
        if should_copy:
            try:
                shutil.copy(analysis_src, dest_json_path)
                print("Copied: analysis_data.json")
            except Exception as e:
                print(f"analysis_data.json copy error: {e}")
    else:
        print("Warning: analysis_data.json not found, no copy performed.")

if __name__ == "__main__":
    main()
