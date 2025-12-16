# StepMania/OutFox Semi-Auto Stepper

A Python prototype for semi-automatic step creation (Dance-Single mode) for StepMania, Project OutFox, and similar programs.


https://github.com/user-attachments/assets/2104635c-5360-45b3-b809-677a149d0cf4


---

## ⚠️ DISCLAIMER (READ BEFORE USE)

This software is a prototype. The author is not responsible for any damage resulting from use of the game.

By downloading and using this tool, you agree to the following:

1. The system automatically generates movement patterns. Some steps may be physically uncomfortable or dangerous if performed without caution.
2. The author is not responsible for physical damage or injuries (sprains, falls, etc.) that occur while playing the game.
3. The author is not responsible for hardware damage (Dance Pad, peripherals, PC) resulting from use of the software.

Always play with caution.

---

## 📖 Introduction: Why this tool?

I wanted to create this system because all the generators I've found online have never satisfied me, generating steps that, in my opinion, have nothing to do with the songs I tested.

The system is **semi-automatic** and is divided into two parts:

1. Detection of the song's BPM/Downbeat (Manual).
2. Generation of steps for the Easy, Medium, and Hard difficulty levels (Automatic).

### The problem with other algorithms

The biggest obstacle encountered during development was finding an efficient algorithm capable of detecting the exact BPM and, above all, automatically recognizing the **Downbeat** (the first quarter in 4/4 time, i.e., the loudest beat in each measure).

Currently, nothing exists that gives 100% correct results. Algorithms often fail, especially with songs that have variable BPMs, pauses, or slowdowns. If you get this first step wrong, everything that follows becomes unplayable and unfun.

### The Solution: Integration with ArrowVortex

To address this problem, the only truly efficient solution was to integrate ArrowVortex into the process.
Using ArrowVortex, we can find the exact BPM (including variations and rests) and indicate the correct tempo of the song.
Only after saving the initial `.sm` file with the correct tempo can we launch automatic arrow generation.

---

### 🎶 Example Song Included!

For your convenience, the `songs` folder includes an example simfile: **"Walk On Water - Southby, Emily J.sm"**, along with its audio and graphics.

This song is from NoCopyrightSounds (NCS), a great source for royalty-free music perfect for testing.

You can immediately see how the generated charts look and play. Feel free to use this as a reference or replace the MP3 with your own tunes to create new simfiles!

---

## ⚙️ Environment Preparation

These actions need to be performed **only the first time**.

1. Clone the project.
2. Run the `setup_venv.bat` file to install the virtual environment with all necessary dependencies.
3. Open the `path_arrowvortex.txt` file in the project folder.
4. Save the path to the ArrowVortex executable installed on your PC.
* *Example: * `C:\ArrowVortex\ArrowVortex.exe`

---

## 🚀 Main Operation

*Note: The software does not currently support English, but operation is very simple.*

### 1. File Preparation

Choose a `.mp3` song and place it in the project's `songs` folder.
**Important:** Rename the file strictly following this format:
`SongTitle - ArtistName.mp3`

Be careful not to use special characters such as apostrophes, accented letters, etc.

* *Correct example:* `The Fate of Ophelia - Taylor Swift.mp3`

### 2. Process Startup and Timing (ArrowVortex)

Open the `menu.bat` file in the project root and press the **1** key.

**ArrowVortex** will open automatically, already configured with the "Beat tick" feature enabled and the **ADJUST TEMPO** and **ADJUST SYNC** windows open.

Proceed as follows:

1. **Find the BPM:** In the "ADJUST SYNC" window, press the **Find BPM** button and then **Apply BPM**.
2. **Verify:** Play the song by pressing the **Spacebar**. Listen for the detected BPM "beep" to make sure it is synchronized with the music.
3. **Align the Downbeat:** Using the **Move first beat** function, position the correct *Downbeat* (the first strong beat of the measure). *This action is very useful for creating even more fun and rhythmically sensible graphs.*
4. **Variable BPM Management (Optional):** For complex songs (tempo changes, pauses, etc.), you can use the "ADJUST TEMPO" window (for details on how to do this, see the official ArrowVortex guide).
5. **Save:** Once you've found the correct tempo, press **Ctrl+S** (or go to *File -> Save*) to save the .sm file in the `songs` folder, exactly where you placed the MP3.

**Note:** Once you've saved the file with the correct tempo, you're done. **There's no need to create the arrows manually**; just save the blank file with the correct timing.

### 4. Generation

Return to the `menu.bat` window (which you opened in step 2) and press **ENTER**.
The system will automatically generate the steps for the difficulty levels (currently the most tested is *Medium*).
The graphics/backgrounds will also be automatically searched for.

### 5. Installation

You will find the complete song folder in `songs`.
Place this folder in the `Songs` directory of your game (StepMania or Project OutFox).
Have fun!

---

## 🛠️ Other Functions

Other options can be accessed from the `menu.bat`.

### Option 2: Regenerate Graph

This option regenerates only the steps, bypassing the ArrowVortex part.

* **When to use it:** It is useful **only** when changes have been made to the code logic (for example, following project updates).
* If there are no code updates, it makes little sense to use it because it would regenerate exactly the same arrows as before.

### Option 3: Change Difficulty

Allows you to change the density of a specific level.

1. Place the entire song folder (already generated) inside the project's `songs` folder.
2. The system will automatically detect the folder(s).
3. Choose the song you want to edit.
4. Choose the difficulty level you want to adjust.
5. Decide whether to **increase** or **decrease** the difficulty (the algorithm will add or remove **20%** of the arrows).

## ☕ Support me

This project is developed entirely in my spare time with the goal of making chart creation accessible to everyone. It is and will always remain free and open source.

If the tool has saved you time and you're enjoying the songs you've created, consider buying me a (virtual) coffee to support the development of future updates!

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/C0C21QBS11)


