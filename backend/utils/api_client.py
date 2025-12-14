import requests
from PIL import Image, UnidentifiedImageError
import io
import logging
import json
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
import re
import zipfile

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

def get_forge_versions():
    """Fetches and parses Forge versions from the official Maven repository."""
    url = "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        versions_node = root.find('versioning/versions')
        if versions_node is None:
            return {}

        structured_versions = defaultdict(list)
        version_pattern = re.compile(r'^(\d+\.\d+(\.\d+)?)-(.+)$') # Corrected line

        for version_tag in versions_node.findall('version'):
            version_str = version_tag.text
            if not version_str: continue
            match = version_pattern.match(version_str)
            if match:
                mc_version = match.group(1)
                forge_version = match.group(3)
                structured_versions[mc_version].append(forge_version)
        
        def version_key(v_str):
            """Robustly splits a version string for sorting."""
            parts = re.split(r'[.-]', v_str)
            key = []
            for part in parts:
                try:
                    key.append(int(part))
                except ValueError:
                    key.append(part.lower())
            return key

        sorted_mc_versions = sorted(structured_versions.keys(), key=version_key, reverse=True)
        
        sorted_structured_versions = {}
        for mc in sorted_mc_versions:
            sorted_forge_versions = sorted(structured_versions[mc], key=version_key, reverse=True)
            sorted_structured_versions[mc] = sorted_forge_versions

        return sorted_structured_versions

    except (requests.RequestException, ET.ParseError) as e:
        logging.error(f"Failed to fetch or parse Forge versions: {e}")
        return {}

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
    uuid_clean = uuid_str.replace('-', '')
    url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid_clean}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code in [204, 404]:
            logging.debug(f"No profile found for UUID '{uuid_clean}'.")
            return None
        response.raise_for_status()
        return response.json().get('name')
    except (requests.RequestException, json.JSONDecodeError) as e:
        logging.error(f"API Error for UUID '{uuid_clean}': {e}")
        return None

def download_server_jar(server_type, server_version, save_path, progress_callback):
    """Downloads the server.jar file for a given type and version with progress."""
    download_url = f"https://mcutils.com/api/server-jars/{server_type}/{server_version}/download"
    return download_file_from_url(download_url, save_path, progress_callback)

def download_file_from_url(download_url, save_path, progress_callback):
    """Downloads a file from a specific URL with progress."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    try:
        with requests.get(download_url, stream=True, timeout=30) as r:
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
        progress_callback(100)
        return True
    except requests.RequestException as e:
        logging.error(f"Failed to download file: {e}")
        return False

def download_and_extract_zip(url, extract_to_dir, progress_callback, contains_single_folder=True):
    """
    Downloads a zip file and extracts its contents.
    If contains_single_folder is True, it moves the contents of the single top-level folder up one level.
    """
    os.makedirs(extract_to_dir, exist_ok=True)
    zip_path = os.path.join(extract_to_dir, 'temp.zip')
    
    logging.info(f"Downloading zip from {url} to {zip_path}")
    if not download_file_from_url(url, zip_path, progress_callback):
        logging.error("Failed to download the zip file.")
        return False
    
    logging.info(f"Extracting {zip_path} to {extract_to_dir}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            if contains_single_folder:
                # Extract to a temporary subdirectory to handle the nested folder structure
                temp_extract_dir = os.path.join(extract_to_dir, "temp_extract")
                os.makedirs(temp_extract_dir, exist_ok=True)
                zip_ref.extractall(temp_extract_dir)
                
                # Identify the single folder inside the temp directory
                extracted_items = os.listdir(temp_extract_dir)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_dir, extracted_items[0])):
                    single_folder_path = os.path.join(temp_extract_dir, extracted_items[0])
                    # Move each item from the single folder to the final destination
                    for item_name in os.listdir(single_folder_path):
                        source_item = os.path.join(single_folder_path, item_name)
                        dest_item = os.path.join(extract_to_dir, item_name)
                        os.rename(source_item, dest_item)
                    # Clean up the temporary extraction directory
                    os.rmdir(single_folder_path)
                    os.rmdir(temp_extract_dir)
                else:
                    # If it's not a single folder, move items directly
                    for item_name in extracted_items:
                        source_item = os.path.join(temp_extract_dir, item_name)
                        dest_item = os.path.join(extract_to_dir, item_name)
                        os.rename(source_item, dest_item)
                    os.rmdir(temp_extract_dir)

            else: # Original behavior
                zip_ref.extractall(extract_to_dir)

        logging.info("Extraction complete.")
    except (zipfile.BadZipFile, IOError) as e:
        logging.error(f"Failed to extract: {e}")
        return False
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
    return True

def download_jre(java_version, os_type="windows", arch="x64", progress_callback=None):
    """
    Downloads a portable JRE from Adoptium API.
    Returns the path to the extracted JRE folder or None on failure.
    """
    if progress_callback is None:
        progress_callback = lambda p: None

    try:
        api_url = f"https://api.adoptium.net/v3/assets/latest/{java_version}/hotspot?vendor=eclipse"
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        releases = response.json()

        binary_info = None
        for release in releases:
            if release['binary']['os'] == os_type and release['binary']['architecture'] == arch and release['binary']['image_type'] == 'jre':
                binary_info = release['binary']
                break
        
        if not binary_info:
            logging.error(f"Could not find a matching JRE for Java {java_version}, OS: {os_type}, Arch: {arch}")
            return None

        download_url = binary_info['package']['link']
        jre_name = f"jre-{java_version}"
        extract_path = os.path.join(os.getcwd(), "jre_temp") # Temp extraction folder
        final_path = os.path.join(os.getcwd(), jre_name) # Final destination

        if os.path.exists(final_path):
            logging.info(f"JRE for Java {java_version} already exists. Skipping download.")
            return final_path

        logging.info(f"Downloading JRE from: {download_url}")
        
        # The JRE zip from Adoptium contains a single top-level folder, so we need to handle that.
        if download_and_extract_zip(download_url, extract_path, progress_callback, contains_single_folder=True):
            os.rename(extract_path, final_path)
            logging.info(f"JRE successfully downloaded and extracted to {final_path}")
            return final_path
        else:
            logging.error("Failed to download and extract JRE.")
            # Clean up failed extraction
            if os.path.exists(extract_path):
                import shutil
                shutil.rmtree(extract_path)
            return None

    except requests.RequestException as e:
        logging.error(f"API Error fetching JRE data: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during JRE download: {e}")
        return None

if __name__ == '__main__':
    print("Fetching Forge versions...")
    forge_versions = get_forge_versions()
    if forge_versions:
        print("Available Minecraft versions for Forge:")
        for mc_version in list(forge_versions.keys())[:5]:
            print(f"- {mc_version}: {forge_versions[mc_version][:3]}")
    else:
        print("Could not fetch Forge versions.")
