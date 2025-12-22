import os
import sys
import webbrowser

def main():
    support_text = """This project is developed entirely in my spare time with the goal of making chart creation accessible to everyone. It is and will always remain free and open source.

If the tool has saved you time and you're enjoying the songs you've created, consider buying me a (virtual) coffee to support the development of future updates!

https://ko-fi.com/stepgenerator"""

    print(support_text)
    
    # Extract URL explicitly or just use the known one
    url = "https://ko-fi.com/stepgenerator"

    print("\n" + "="*50)
    print("Press ENTER to open the donation page...")
    print("="*50)
    input()
    print(f"Opening: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    main()
