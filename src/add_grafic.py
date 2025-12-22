import os
import sys
import json
import urllib.request
import urllib.parse
import re

def read_sm_tags(sm_path):
    title = ""
    artist = ""
    music = ""
    try:
        with open(sm_path, 'r', encoding='utf-8') as f:
            content = f.read()
        m_music = re.search(r"#MUSIC:([^;]+);", content, re.IGNORECASE)
        if m_music:
            music = m_music.group(1).strip()
        # Try to read title/artist tags first
        m_title = re.search(r"#TITLE:([^;]+);", content, re.IGNORECASE)
        if m_title:
            title = m_title.group(1).strip()
        m_artist = re.search(r"#ARTIST:([^;]+);", content, re.IGNORECASE)
        if m_artist:
            artist = m_artist.group(1).strip()
        # Fallback from filename pattern "Title - Artist"
        # Always check filename if tags are missing OR "Unknown"
        base = os.path.splitext(os.path.basename(music or sm_path))[0]
        if (" - " in base):
            parts = [p.strip() for p in base.split(" - ", 1)]
            # If title is empty or default base, override
            if not title or title == base:
                title = parts[0]
            # If artist is empty or "Unknown", override
            if not artist or artist.lower() == "unknown":
                artist = parts[1]
        return title or base, artist or "Unknown", music
    except Exception:
        base = os.path.splitext(os.path.basename(sm_path))[0]
        parts = [p.strip() for p in base.split(" - ", 1)]
        if len(parts) == 2:
            return parts[0], parts[1], base + ".mp3"
        return base, "Unknown", base + ".mp3"

def wikipedia_thumb(query, lang="en"):
    try:
        q = urllib.parse.quote(query)
        url_search = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json"
        with urllib.request.urlopen(url_search, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        hits = data.get("query", {}).get("search", [])
        if not hits and lang != "en":
            return wikipedia_thumb(query, "en")
        if not hits:
            return None
        # Try each hit until one has a thumbnail
        pageids = [h.get("pageid") for h in hits if h.get("pageid")]
        for pageid in pageids:
            url_img = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=pageimages&pageids={pageid}&pithumbsize=800&format=json"
            with urllib.request.urlopen(url_img, timeout=10) as resp2:
                data2 = json.loads(resp2.read().decode("utf-8"))
            pages = data2.get("query", {}).get("pages", {})
            page = pages.get(str(pageid), {})
            thumb = page.get("thumbnail", {}).get("source")
            if thumb:
                return thumb
        return None
    except Exception:
        return None

def _fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.getheader("Content-Type") or "", resp.read()

def download_image(url, out_path):
    try:
        content_type, data = _fetch(url, timeout=20)
    except Exception:
        return False
    # Try to convert to PNG if Pillow is available
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        img.save(out_path, format="PNG")
        return True
    except Exception:
        # Without Pillow: only write if content is PNG already
        if "image/png" in content_type.lower():
            try:
                with open(out_path, "wb") as f:
                    f.write(data)
                return True
            except Exception:
                return False
        # Otherwise fail to trigger placeholder generation
        return False

def ensure_graphics(sm_path):
    title, artist, music = read_sm_tags(sm_path)
    base_dir = os.path.dirname(sm_path)
    # After azioni_finali, files are moved to <base_name> folder
    base_name = os.path.splitext(os.path.basename(music or sm_path))[0]
    target_dir = os.path.join(base_dir, base_name)
    if not os.path.isdir(target_dir):
        target_dir = base_dir
    bg_path = os.path.join(target_dir, "BG.png")
    bn_path = os.path.join(target_dir, "BN.png")

    # Check if files already exist to avoid re-downloading
    if os.path.exists(bg_path) and os.path.getsize(bg_path) > 0 and \
       os.path.exists(bn_path) and os.path.getsize(bn_path) > 0:
        print(f"Grafica già presente in {target_dir}, salto generazione.")
        return

    # Fetch images
    # BG: use combined query and fallbacks
    
    # Clean artist if it is "Unknown"
    search_artist = artist if artist and artist.lower() != "unknown" else ""
    
    if search_artist:
        bg_query = f"{title} {search_artist}".strip()
    else:
        bg_query = title.strip()
        
    # Reduced resolution requirements as requested (320x240)
    title_img = find_bg_url(title, search_artist, 320, 240)
    
    # For artist image (BN), only search if we have a real artist name
    artist_img = None
    if search_artist:
        # Pass reduced requirements to valid_thumb as well if needed, though wikipedia usually has high res
        artist_img = wikipedia_valid_thumb(search_artist, 320, 240) or bing_image_url(search_artist)
    
    # Se BG non trovato da sorgenti validate, prova Google/Bing con validazione
    if not title_img:
        # Try query with artist first (if exists)
        cand = None
        if search_artist:
             cand = bing_image_url(bg_query)
        
        # If failed or no artist, try just title
        if not cand:
             cand = bing_image_url(title) or google_image_url(bg_query) or google_image_url(title)
             
        if cand and validate_image_url(cand, 320, 240):
            title_img = cand
            
    if not artist_img and search_artist:
        artist_img = bing_image_url(search_artist) or google_image_url(search_artist)
    
    # Fallback: if BN is still missing but we found a BG (cover), use BG for BN too
    if not artist_img and title_img:
        print("Using BG image as fallback for BN (since artist is unknown or not found)")
        artist_img = title_img
    # Download
    ok_bg = False
    ok_bn = False
    if title_img:
        print(f"BG source: {title_img}")
    if title_img:
        ok_bg = download_image(title_img, bg_path)
        if ok_bg:
            print(f"BG saved: {bg_path}")
            try:
                from PIL import Image
                img = Image.open(bg_path)
                # Verifica dimensioni minime
                sw, sh = img.size
                print(f"BG size downloaded: {sw}x{sh}")
                if sw < 320 or sh < 240:
                    ok_bg = False
                    print("BG too small, triggering fallback...")
                    raise Exception("too small")
                target_size = (1600, 900)
                # Resize/crop to fill target (cover)
                src_w, src_h = img.size
                
                # If image is smaller than target, scale UP to fill
                # If image is larger than target, scale DOWN to fill (maintaining aspect ratio)
                # In both cases, we want to FILL the 1600x900 frame
                scale = max(target_size[0]/src_w, target_size[1]/src_h)
                new_w = int(src_w * scale)
                new_h = int(src_h * scale)
                
                # Apply high-quality resampling
                img = img.resize((new_w, new_h), Image.LANCZOS)
                
                # Center Crop to 1600x900
                left = (new_w - target_size[0]) // 2
                top = (new_h - target_size[1]) // 2
                img = img.crop((left, top, left + target_size[0], top + target_size[1]))
                
                img.save(bg_path, format="PNG")
                print(f"BG processed to {target_size[0]}x{target_size[1]}")
            except Exception as e:
                print(f"BG resize error: {e}")
    if artist_img:
        print(f"BN source: {artist_img}")
        ok_bn = download_image(artist_img, bn_path)
        if ok_bn:
            print(f"BN saved: {bn_path}")
    # If any failed, create tiny placeholder PNG
    if not ok_bg:
        try:
            from PIL import Image, ImageDraw, ImageFont
            W, H = 1280, 720
            img = Image.new("RGB", (W, H), (18, 22, 29))
            draw = ImageDraw.Draw(img)
            title_text = title or base_name
            artist_text = artist
            # Simple centered text
            try:
                font_title = ImageFont.truetype("arial.ttf", 64)
                font_artist = ImageFont.truetype("arial.ttf", 36)
            except:
                from PIL import ImageFont
                font_title = ImageFont.load_default()
                font_artist = ImageFont.load_default()
            # Compute positions using textbbox (Pillow 10+)
            # textbbox returns (left, top, right, bottom)
            bbox_t = draw.textbbox((0, 0), title_text, font=font_title)
            tw = bbox_t[2] - bbox_t[0]
            th = bbox_t[3] - bbox_t[1]
            
            bbox_a = draw.textbbox((0, 0), artist_text, font=font_artist)
            aw = bbox_a[2] - bbox_a[0]
            ah = bbox_a[3] - bbox_a[1]
            
            draw.text(((W - tw)//2, (H - th)//2 - 40), title_text, fill=(235, 235, 235), font=font_title)
            draw.text(((W - aw)//2, (H - ah)//2 + 40), artist_text, fill=(200, 200, 200), font=font_artist)
            img.save(bg_path, format="PNG")
            print(f"BG placeholder generated with text: {bg_path}")
        except Exception as e:
            print(f"Fallback graphic error: {e}")
            # Minimal 1x1 transparent PNG
            try:
                with open(bg_path, "wb") as f:
                    f.write(bytes.fromhex("89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000A49444154789C6360000002000100A5F9A64D0000000049454E44AE426082"))
            except Exception:
                pass
    if not ok_bn:
        try:
            with open(bn_path, "wb") as f:
                f.write(bytes.fromhex("89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000A49444154789C6360000002000100A5F9A64D0000000049454E44AE426082"))
            print(f"BN placeholder (1x1 transparent) generated: {bn_path}")
        except Exception:
            pass
    print(f"Grafica generata in: {target_dir} (BG.png, BN.png)")

def itunes_cover_url(query):
    """Cerca cover su iTunes API e ottiene versione ad alta risoluzione"""
    try:
        q = urllib.parse.quote(query)
        # Cerca album/canzoni
        url = f"https://itunes.apple.com/search?term={q}&media=music&entity=song&limit=5"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        results = data.get("results", [])
        if not results:
            return None
            
        for res in results:
            # Artwork 100x100 è lo standard, ma possiamo modificarlo per avere alta risoluzione
            artwork = res.get("artworkUrl100")
            if artwork:
                # Sostituisci 100x100 con 1000x1000 per avere l'alta qualità
                hi_res = artwork.replace("100x100bb", "1000x1000bb")
                print(f"DEBUG: Found iTunes cover: {hi_res}")
                return hi_res
        return None
    except Exception as e:
        print(f"DEBUG: iTunes search error: {e}")
        return None

def bing_image_url(query, min_w=256, min_h=256):
    try:
        print(f"DEBUG: Searching Bing for '{query}'...")
        q = urllib.parse.quote(query)
        url = f"https://www.bing.com/images/search?q={q}&form=HDRSC2&qft=+filterui:imagesize-large"
        content_type, html = _fetch(url, timeout=15)
        # Regex più permissive per trovare URL
        m = re.findall(rb'"murl":"(.*?)"', html) + re.findall(rb'&quot;murl&quot;:&quot;(.*?)&quot;', html)
        if not m:
             m = re.findall(rb'src="(http[^"]+)"', html)

        print(f"DEBUG: Bing found {len(m)} potential URLs")
        
        # Check up to 5 candidates and pick the largest one that passes validation
        best_url = None
        best_area = 0
        
        candidates = m[:5]
        for raw in candidates:
            try:
                u = raw.decode('utf-8')
            except:
                continue
            if any(ext in u.lower() for ext in [".jpg", ".jpeg", ".png"]):
                valid, w, h = validate_image_url(u, min_w, min_h)
                if valid:
                    area = w * h
                    if area > best_area:
                        best_area = area
                        best_url = u
        
        if best_url:
            print(f"DEBUG: Bing selected best image: {best_url} (Area: {best_area})")
            return best_url
        else:
            print("DEBUG: Bing found no valid images in top candidates")
            return None
    except Exception as e:
        print(f"DEBUG: Bing search error: {e}")
        return None

def google_image_url(query, min_w=256, min_h=256):
    try:
        print(f"DEBUG: Searching Google for '{query}'...")
        q = urllib.parse.quote(query)
        url = f"https://www.google.com/search?tbm=isch&q={q}&tbs=isz:l"
        content_type, html = _fetch(url, timeout=15)
        
        urls = []
        urls.extend(re.findall(rb'\"ou\":\"(.*?)\"', html))
        urls.extend(re.findall(rb'\"720\":\[\"(http.*?)\"', html))
        urls.extend(re.findall(rb'\"1080\":\[\"(http.*?)\"', html))
        urls.extend(re.findall(rb'imgurl=(http[^&]+)&', html))
        
        print(f"DEBUG: Google found {len(urls)} potential URLs")
        
        best_url = None
        best_area = 0
        
        candidates = urls[:5]
        for raw in candidates:
            try:
                u = urllib.parse.unquote(raw.decode('utf-8'))
                u = u.encode().decode('unicode-escape')
            except:
                continue
            
            if any(ext in u.lower() for ext in [".jpg", ".jpeg", ".png"]):
                valid, w, h = validate_image_url(u, min_w, min_h)
                if valid:
                    area = w * h
                    if area > best_area:
                        best_area = area
                        best_url = u
                        
        if best_url:
            print(f"DEBUG: Google selected best image: {best_url} (Area: {best_area})")
            return best_url
        else:
            print("DEBUG: Google found no valid images in top candidates")
            return None
    except Exception as e:
        print(f"DEBUG: Google search error: {e}")
        return None
def validate_image_url(url, min_w=256, min_h=256):
    try:
        # Request with updated user agent and accept headers
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
             data = resp.read()

        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        
        # Tolleranza del 10% sulle dimensioni
        tolerated_w = int(min_w * 0.9)
        tolerated_h = int(min_h * 0.9)
        
        if w < tolerated_w or h < tolerated_h:
            # print(f"DEBUG: Image too small ({w}x{h} < {min_w}x{min_h})")
            return False, w, h
        try:
            if "A" in img.getbands():
                alpha = img.getchannel("A")
                hist = alpha.histogram()
                total = sum(hist)
                weighted = sum(i * c for i, c in enumerate(hist))
                mean_alpha = weighted / (255.0 * total) if total else 0.0
                if mean_alpha < 0.2:
                    print("DEBUG: Image too transparent")
                    return False, w, h
        except Exception:
            pass
        return True, w, h
    except Exception as e:
        # print(f"DEBUG: Validation error for {url}: {e}")
        return False, 0, 0

def wikipedia_valid_thumb(query, min_w=256, min_h=256):
    for lang in ["it", "en"]:
        t = wikipedia_thumb(query, lang)
        if t:
            valid, w, h = validate_image_url(t, min_w, min_h)
            if valid:
                return t
    return None

def find_bg_url(title, artist, min_w=854, min_h=480):
    # 1. Try iTunes High-Res Cover first (best quality/safety)
    itunes = itunes_cover_url(f"{title} {artist}")
    if itunes:
        valid, w, h = validate_image_url(itunes, min_w, min_h)
        if valid:
            return itunes
        
    queries = [
        f"{title} {artist}".strip(),
        f"{title} cover",
        f"{title} song",
        f"{title} soundtrack",
        f"{title} {artist} cover",
        f"{title} {artist} artwork",
    ]
    for q in queries:
        # Wikipedia
        t = wikipedia_valid_thumb(q, min_w, min_h)
        if t:
            return t
        # Bing
        b = bing_image_url(q, min_w, min_h)
        if b:
            return b
        # Google
        g = google_image_url(q, min_w, min_h)
        if g:
            return g
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python add_grafic.py <sm_file_path>")
        sys.exit(1)
    sm_path = os.path.abspath(sys.argv[1])
    ensure_graphics(sm_path)

if __name__ == "__main__":
    main()
