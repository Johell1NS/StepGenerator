import os
import sys
import webbrowser

def main():
    file_path = "Support Me.txt"
    if not os.path.exists(file_path):
        print(f"Error: '{file_path}' not found.")
        return

    url = None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                print(line.strip())
                if "http" in line:
                    url = line.strip()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    if url:
        print("\n" + "="*50)
        print("Press ENTER to open the donation page...")
        print("="*50)
        input()
        print(f"Opening: {url}")
        webbrowser.open(url)
    else:
        print("\n(No link found in the file)")
        input("\nPress ENTER to return to menu...")

if __name__ == "__main__":
    main()
