import requests
from PIL import Image, ImageTk, UnidentifiedImageError
import io
import logging

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
    """Fetches a player's avatar from Mineskin API and returns a PhotoImage object."""
    try:
        url = f"https://mineskin.eu/avatar/{player_identifier}/{size[0]}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content)).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
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

def download_server_jar(server_type, server_version, save_path, progress_callback):
    """Downloads the server jar from mcutils.com API."""
    try:
        download_url = f"https://mcutils.com/api/server-jars/{server_type}/{server_version}/download"
        response = requests.get(download_url, stream=True, timeout=30)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        bytes_downloaded = 0
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bytes_downloaded += len(chunk)
                if total_size > 0:
                    progress = (bytes_downloaded / total_size) * 100
                    progress_callback(progress)
    except requests.RequestException as e:
        logging.error(f"API Error: Could not download server jar. Reason: {e}")
        raise

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