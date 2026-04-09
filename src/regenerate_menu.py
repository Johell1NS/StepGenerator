import os
import sys
import glob
import shutil
import subprocess

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
SONGS_DIR = os.path.join(ROOT_DIR, "songs")

def find_regeneratable_songs():
    """
    Finds songs in subdirectories that have both an .sm file and analysis_data.json.
    Returns a list of dicts: {'folder': path, 'sm': filename, 'json': filename}
    """
    songs = []
    if not os.path.exists(SONGS_DIR):
        print(f"Directory '{SONGS_DIR}' not found.")
        return []

    # Iterate over subdirectories in songs/
    for entry in os.scandir(SONGS_DIR):
        if entry.is_dir():
            folder_path = entry.path
            
            # Look for .sm files
            sm_files = glob.glob(os.path.join(folder_path, "*.sm"))
            json_file = os.path.join(folder_path, "analysis_data.json")
            
            if sm_files and os.path.exists(json_file):
                # Use the first sm file found (usually there's only one relevant one)
                songs.append({
                    'folder': folder_path,
                    'sm_path': sm_files[0],
                    'json_path': json_file,
                    'name': entry.name
                })
    return songs

def main():
    print("\n🔄 REGENERATE CHART (Reprocess existing SM)")
    print("   (Searches folders with .sm and analysis_data.json)\n")
    
    songs = find_regeneratable_songs()
    
    if not songs:
        print("❌ No regeneratable song found (missing analysis_data.json or .sm).")
        input("\nPress Enter to go back to the menu...")
        return

    print("-" * 60)
    for idx, song in enumerate(songs, 1):
        print(f"   {idx}. {song['name']}")
    print("-" * 60)
    
    while True:
        choice = input("👉 Select the song to regenerate (0 to exit): ")
        try:
            choice_num = int(choice)
            if choice_num == 0:
                return
            if 1 <= choice_num <= len(songs):
                selected = songs[choice_num - 1]
                break
            else:
                print("❌ Invalid number.")
        except ValueError:
            print("❌ Please enter a valid number.")

    print(f"\n🚀 Starting regeneration for: {selected['name']}")
    
    # 1. Copy analysis_data.json to root (backup existing if any?)
    # We overwrite root analysis_data.json because it's transient
    root_json = "analysis_data.json"
    shutil.copy2(selected['json_path'], root_json)
    print(f"✅ Analysis data loaded from: {selected['json_path']}")
    
    # 2. Run StepMania Generator
    # Command: python stepmania_generator.py --from-sm "path/to/sm" --pipeline --skip-analysis
    stepmania_script = os.path.join(SRC_DIR, "stepmania_generator.py")
    cmd = [sys.executable, stepmania_script, "--from-sm", selected['sm_path'], "--pipeline", "--skip-analysis"]
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ Regeneration completed!")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error during regeneration: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        # Cleanup root json?
        # Maybe keep it for debugging or subsequent runs, usually safe to leave or delete.
        # Let's delete to keep root clean.
        if os.path.exists(root_json):
            os.remove(root_json)

    input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
