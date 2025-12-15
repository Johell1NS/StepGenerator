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
        print("🔧 Opzione --preserve-json attiva: Il file analysis_data.json nella cartella non verrà sovrascritto.")
    
    if not os.path.exists(sm_path):
        print(f"Errore: File .sm non trovato: {sm_path}")
        sys.exit(1)

    directory = os.path.dirname(sm_path)
    sm_filename = os.path.basename(sm_path)
    
    print(f"--- Esecuzione Azioni Finali ---")
    print(f"Analisi file: {sm_filename}")

    # 1. Trova il nome del file MP3 leggendo il file .sm
    mp3_filename = None
    try:
        with open(sm_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("#MUSIC:"):
                    # Esempio: #MUSIC:song.mp3;
                    content = line.split(":", 1)[1].strip()
                    if content.endswith(";"):
                        content = content[:-1]
                    mp3_filename = content.strip()
                    break
    except Exception as e:
        print(f"Errore nella lettura del file .sm: {e}")
        sys.exit(1)

    if not mp3_filename:
        print("Avviso: Impossibile trovare il tag #MUSIC nel file .sm")
        # Fallback: usa lo stesso nome del file .sm ma con estensione .mp3
        mp3_filename = os.path.splitext(sm_filename)[0] + ".mp3"
        print(f"Fallback: cerco il file audio basandomi sul nome .sm: {mp3_filename}")

    mp3_path = os.path.join(directory, mp3_filename)
    
    # 2. Definisci il nome della cartella (nome del file mp3 senza estensione)
    folder_name = os.path.splitext(mp3_filename)[0]
    target_folder = os.path.join(directory, folder_name)
    
    # Controllo di sicurezza: se siamo già dentro la cartella target, non fare nulla
    # Caso 1: Path identici (non dovrebbe accadere con join)
    if os.path.normpath(directory) == os.path.normpath(target_folder):
        print("I file sono già organizzati nella cartella corretta.")
        sys.exit(0)
        
    # Caso 2: Se la cartella corrente ha già il nome della canzone, assumiamo sia già a posto
    if os.path.basename(os.path.normpath(directory)).lower() == folder_name.lower():
         print(f"I file sembrano già essere nella cartella corretta '{folder_name}'. Nessuno spostamento necessario.")
         # Tuttavia, assicuriamoci che analysis_data.json sia presente/aggiornato se disponibile nella root/source
         analysis_src = os.path.join(os.getcwd(), "analysis_data.json")
         analysis_dest = os.path.join(directory, "analysis_data.json")
         
         if os.path.exists(analysis_src):
             should_copy = True
             if os.path.exists(analysis_dest):
                 if preserve_json:
                     should_copy = False
                     print("analysis_data.json preservato (flag --preserve-json attivo).")
                 else:
                     try:
                         # Confronta contenuto per evitare aggiornamenti inutili (preserva timestamp)
                         if filecmp.cmp(analysis_src, analysis_dest, shallow=False):
                             should_copy = False
                     except: pass
             
             if should_copy:
                 try:
                     shutil.copy(analysis_src, analysis_dest)
                     print("Aggiornato: analysis_data.json")
                 except: pass
             elif not preserve_json:
                 print("analysis_data.json già allineato (nessuna modifica).")
         sys.exit(0)

    # 3. Crea la cartella se non esiste
    if not os.path.exists(target_folder):
        try:
            os.makedirs(target_folder)
            print(f"Creata nuova cartella: {target_folder}")
        except Exception as e:
            print(f"Errore creazione cartella: {e}")
            sys.exit(1)
    else:
        print(f"Cartella destinazione esistente: {target_folder}")

    # 4. Lista file da spostare
    files_to_move = [sm_path]
    
    if os.path.exists(mp3_path):
        files_to_move.append(mp3_path)
    else:
        print(f"Attenzione: File MP3 non trovato in '{mp3_path}'. Non verrà spostato.")

    # Cerca anche il file .ssc
    ssc_filename = os.path.splitext(sm_filename)[0] + ".ssc"
    ssc_path = os.path.join(directory, ssc_filename)
    if os.path.exists(ssc_path):
        files_to_move.append(ssc_path)

    # Cerca file grafici BG.png e BN.png
    bg_path = os.path.join(directory, "BG.png")
    bn_path = os.path.join(directory, "BN.png")
    if os.path.exists(bg_path):
        files_to_move.append(bg_path)
    if os.path.exists(bn_path):
        files_to_move.append(bn_path)
        
    # Cerca eventuali file .lrc o altri file correlati con lo stesso nome base? 
    # Per ora limitiamoci a sm, ssc e mp3 come richiesto.

    # 5. Sposta i file
    success_count = 0
    for file_path in files_to_move:
        try:
            fname = os.path.basename(file_path)
            dest_path = os.path.join(target_folder, fname)
            
            # Se il file esiste già nella destinazione, lo rimuoviamo prima per sovrascriverlo
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except Exception as remove_err:
                    print(f"Impossibile rimuovere file esistente {fname}: {remove_err}")
                    continue
                
            shutil.move(file_path, dest_path)
            print(f"Spostato: {fname}")
            success_count += 1
        except Exception as e:
            print(f"Errore spostamento {file_path}: {e}")

    if success_count > 0:
        print(f"Operazione completata. {success_count} file spostati in '{folder_name}'.")
    else:
        print("Nessun file spostato.")
    
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
             print("analysis_data.json preservato nella destinazione (flag --preserve-json attivo).")
             
        if should_copy:
            try:
                shutil.copy(analysis_src, dest_json_path)
                print("Copiato: analysis_data.json")
            except Exception as e:
                print(f"Errore copia analysis_data.json: {e}")
    else:
        print("Attenzione: analysis_data.json non trovato, nessuna copia eseguita.")

if __name__ == "__main__":
    main()
