import os
import sys
import shutil
import subprocess
import yt_dlp
import re

# Add the parent directory to sys.path to allow importing modules if needed
# (Though we might not need to import anything from root if we run standalone)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
SONGS_DIR = os.path.join(ROOT_DIR, "songs")

def clean_youtube_url(url):
    """
    Cleans the YouTube URL to keep only the video ID part.
    Removes playlist parameters and other junk.
    """
    if "&" in url:
        url = url.split("&")[0]
    return url

def get_user_input(prompt):
    return input(prompt).strip()

def download_audio(url, output_path):
    """
    Downloads audio from YouTube using yt-dlp and converts to MP3.
    Returns the filename of the downloaded file.
    """
    print(f"Downloading from: {url}")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # The file is converted to mp3, so the extension changes
        final_filename = os.path.splitext(filename)[0] + ".mp3"
        return final_filename

def main():
    if len(sys.argv) < 2:
        print("Usage: python audioYouTube.py <youtube_url>")
        return

    raw_url = sys.argv[1]
    url = clean_youtube_url(raw_url)
    
    print(f"\n--- YouTube Audio Downloader ---")
    print(f"Target URL: {url}")
    
    # 1. Ask for details
    print("\nInserisci i dettagli per rinominare il file:")
    song_name = get_user_input("Nome Canzone: ")
    artist_name = get_user_input("Nome Artista: ")
    
    if not song_name or not artist_name:
        print("Errore: Nome Canzone e Nome Artista sono obbligatori.")
        return

    full_name = f"{song_name} - {artist_name}"
    safe_name = re.sub(r'[<>:"/\\|?*]', '', full_name) # Remove invalid chars
    
    # Create temp dir or just download to songs root first?
    # User said: "lo salva dentro la cartella song"
    # Let's create a specific folder for the song to keep it clean, as per ArrowVortex structure preference
    song_folder = os.path.join(SONGS_DIR, safe_name)
    if not os.path.exists(song_folder):
        os.makedirs(song_folder)
    
    try:
        # Download
        print("\nAvvio download e conversione...")
        downloaded_file = download_audio(url, song_folder)
        
        # Rename
        final_mp3_path = os.path.join(song_folder, f"{safe_name}.mp3")
        
        # Check if downloaded file name is different (yt-dlp uses video title)
        if os.path.exists(downloaded_file):
            # Verify we aren't overwriting same name (unlikely if title matches but good to check)
            if downloaded_file != final_mp3_path:
                if os.path.exists(final_mp3_path):
                    os.remove(final_mp3_path)
                os.rename(downloaded_file, final_mp3_path)
            print(f"\n✅ File salvato: {final_mp3_path}")
        else:
            print(f"\n❌ Errore: File scaricato non trovato: {downloaded_file}")
            return

        # 2. Start "usual process" (Open in ArrowVortex)
        # We assume open_in_arrowvortex.py is in the src directory (same as this script)
        script_path = os.path.join(SCRIPT_DIR, "open_in_arrowvortex.py")
        
        if os.path.exists(script_path):
            print("\nAvvio processo ArrowVortex...")
            # Call with the new file path
            subprocess.run([sys.executable, script_path, final_mp3_path])
        else:
            print(f"Errore: {script_path} non trovato.")

    except Exception as e:
        print(f"\n❌ Errore durante il processo: {e}")
        # Clean up if empty folder
        if os.path.exists(song_folder) and not os.listdir(song_folder):
            os.rmdir(song_folder)

if __name__ == "__main__":
    main()
