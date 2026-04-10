import subprocess
import webbrowser
import wikipedia
import urllib.parse
import os
from backend.utils import get_logger

logger = get_logger("Actions")


# 🔥 Safer app launcher
def open_desktop_app(app_name: str) -> bool:
    logger.info(f"Opening desktop app: {app_name}")
    
    common_apps = {
        "calculator": "calc.exe",
        "notepad": "notepad.exe",
        "paint": "mspaint.exe",
        "command prompt": "cmd.exe",
        "terminal": "wt.exe",
        "explorer": "explorer.exe",
        "task manager": "taskmgr.exe",
        "spotify": "spotify.exe",
        "whatsapp": "whatsapp.exe",
        "discord": "discord.exe",
        "vlc": "vlc.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "firefox": "firefox.exe",
        "brave": "brave.exe"
    }

    target = app_name.lower().strip()

    # 1. Direct match
    if target in common_apps:
        try:
            subprocess.Popen([common_apps[target]])
            return True
        except Exception as e:
            logger.error(e)
            return False

    # 2. Start Menu search (improved match)
    start_menu_paths = [
        os.path.join(os.environ.get('PROGRAMDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
        os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs')
    ]

    best_match = None

    for base_path in start_menu_paths:
        if not os.path.exists(base_path):
            continue

        for root, _, files in os.walk(base_path):
            for file in files:
                if file.endswith((".lnk", ".url")):
                    file_name = file.rsplit('.', 1)[0].lower()

                    # Better matching logic
                    if target == file_name:
                        best_match = os.path.join(root, file)
                        break
                    elif target in file_name or file_name in target:
                        best_match = os.path.join(root, file)

            if best_match:
                break

        if best_match:
            break

    if best_match:
        try:
            os.startfile(best_match)
            return True
        except Exception as e:
            logger.error(e)
            return False

    logger.warning(f"No app found for: {app_name}")
    return False


# 🔍 Fallback search
def fallback_search(target: str):
    query = urllib.parse.quote(target)
    webbrowser.open(f"https://www.google.com/search?q={query}")


# 🌐 Improved website opener
def open_website(target: str):
    logger.info(f"Opening website: {target}")

    target = target.lower().strip()

    # If user already gave domain
    if target.endswith((".com", ".org", ".in", ".net")):
        webbrowser.open(f"https://www.{target}")
        return

    # If it's likely a known service → assume .com
    if " " not in target:
        webbrowser.open(f"https://www.{target}.com")
        return

    # Otherwise fallback
    fallback_search(target)


# 📚 Wikipedia (fixed multilingual issue)
def get_wikipedia_summary(topic: str, lang: str) -> dict:
    try:
        # Always fetch in English for reliability
        wikipedia.set_lang("en")
        summary = wikipedia.summary(topic, sentences=2)

        # Translate if needed
        if lang != "en":
            try:
                from deep_translator import GoogleTranslator
                summary = GoogleTranslator(source='auto', target=lang).translate(summary)
            except Exception as e:
                logger.error(f"Translation failed: {e}")

        prefix = {
            "en": "According to Wikipedia: ",
            "hi": "विकिपीडिया के अनुसार: ",
            "te": "వికీపీడియా ప్రకారం: "
        }

        return {"success": True, "text": prefix.get(lang, "Wikipedia: ") + summary}

    except wikipedia.exceptions.DisambiguationError as e:
        options = ", ".join(e.options[:3])
        return {"success": False, "text": f"Multiple results found: {options}"}

    except wikipedia.exceptions.PageError:
        return {"success": False, "text": None}

    except Exception as e:
        logger.error(f"Wiki error: {e}")
        return {"success": False, "text": None}

# ⬇️ Install app fallback
def install_app_fallback(app_name: str):
    logger.info(f"Opening install for {app_name}")
    try:
        # Try to open Microsoft Store search
        subprocess.Popen(['cmd', '/c', f'start ms-windows-store://search/?query={app_name}'])
    except Exception as e:
        logger.error(f"Store launch failed, falling back to web: {e}")
        webbrowser.open(f"https://www.google.com/search?q=download+{urllib.parse.quote(app_name)}")