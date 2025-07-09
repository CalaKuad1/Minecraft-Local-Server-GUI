import requests
from PIL import Image, ImageTk, UnidentifiedImageError
import io
import logging
import json
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_server_versions(server_type):
    """Fetches available server versions for a given type from mcutils.com API."""
    try:
        url = f"https://mcutils.com/api/server-jars/{server_type.lower()}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"API Error: Could not fetch server versions for '{server_type}'. Reason: {e}")
        return []

def fetch_player_avatar_image(player_identifier, size=(24, 24)):
    """Fetches a player's avatar from Mineskin API and returns a PIL Image object."""
    try:
        url = f"https://mineskin.eu/avatar/{player_identifier}/{size[0]}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content)).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
        return img
    except (requests.RequestException, UnidentifiedImageError) as e:
        logging.debug(f"Could not fetch avatar for '{player_identifier}'. Reason: {e}")
        return None

def fetch_player_uuid(player_name):
    """Fetches a player's UUID from Mojang API."""
    try:
        response = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{player_name}", timeout=10)
        if response.status_code == 204:
            return None
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"API Error: Could not fetch UUID for '{player_name}'. Reason: {e}")
        raise

def fetch_username_from_uuid(uuid_str):
    """Fetches a player's username from their UUID using Mojang's API."""
    if not uuid_str:
        return None
    # Ensure UUID has no dashes for the API call
    uuid_clean = uuid_str.replace('-', '')
    url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid_clean}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 204 or response.status_code == 404:
            logging.debug(f"No profile found for UUID '{uuid_clean}'.")
            return None
        response.raise_for_status()
        data = response.json()
        return data.get('name')
    except requests.RequestException as e:
        logging.error(f"API Error: Could not fetch username for UUID '{uuid_clean}'. Reason: {e}")
        return None
    except json.JSONDecodeError:
        logging.error(f"API Error: Could not parse username response for UUID '{uuid_clean}'.")
        return None

def download_server_jar(server_type, server_version, save_path, progress_callback):
    """Downloads the server.jar file for a given type and version with progress."""
    # Ensure the directory exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    try:
        download_url = f"https://mcutils.com/api/server-jars/{server_type}/{server_version}/download"
        
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            bytes_downloaded = 0
            
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    if total_size > 0:
                        progress = (bytes_downloaded / total_size) * 100
                        progress_callback(progress)
        
        progress_callback(100) # Ensure it finishes at 100%
        return True

    except requests.RequestException as e:
        logging.error(f"Failed to download server jar: {e}")
        return False

if __name__ == '__main__':
    # Example usage (optional, for testing)
    print("Fetching server versions for 'paper'...")
    versions = get_server_versions('paper')
    if versions:
        print(f"Available versions: {versions[:5]}")

    print("\nFetching UUID for player 'Notch'...")
    uuid_info = fetch_player_uuid('Notch')
    if uuid_info:
        print(f"UUID info: {uuid_info}")

    # The following function requires a Tkinter root window, so it cannot be tested from the command line.
    # print("\nFetching avatar for player 'Notch'...")
    # avatar = fetch_player_avatar_image('Notch')
    # if avatar:
    #     print("Avatar fetched successfully.")

    print("\nTesting download (will not save file)...")
    def dummy_progress(p):
        print(f"Download progress: {p:.2f}%")
    # download_server_jar('paper', '1.17.1', 'paper-1.17.1.jar', dummy_progress)
