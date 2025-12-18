import requests
import os
import logging
import json
from typing import List, Dict, Optional

class ModsManager:
    BASE_URL = "https://api.modrinth.com/v2"
    
    def __init__(self):
        self.headers = {
            "User-Agent": "MinecraftLocalServerGUI/1.0 (internal-dev)"
        }

    def search_mods(self, query: str, loader: str = "fabric", version: str = None, project_type: str = "mod") -> List[Dict]:
        """
        Search for mods or modpacks on Modrinth.
        """
        try:
            # Build facets safely
            facets = [
                [f"project_type:{project_type}"]
            ]
            
            if loader and loader.lower() != "any":
                facets.append([f"categories:{loader}"])
                
            if version and version.strip():
                facets.append([f"versions:{version}"])
            
            params = {
                "query": query,
                "limit": 20,
                "facets": json.dumps(facets)
            }
            
            # If query is empty, sort by downloads (popular)
            if not query or query.strip() == "":
                params["index"] = "downloads"

            logging.info(f"Searching mods: query='{query}' params={params}")
            response = requests.get(f"{self.BASE_URL}/search", params=params, headers=self.headers)
            
            if response.status_code != 200:
                logging.error(f"Modrinth Search API Error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            hits = data.get("hits", [])
            logging.info(f"Found {len(hits)} mods for query '{query}'")
            return hits
        except Exception as e:
            logging.exception(f"Exception searching mods: {e}")
            return []

    def get_mod_versions(self, slug: str, loader: str = "fabric", version: str = None) -> List[Dict]:
        """
        Get compatible versions for a specific mod project.
        """
        try:
            params = {
                "loaders": f'["{loader}"]',
                "game_versions": f'["{version}"]' if version else None
            }
            
            # Remove None values
            params = {k: v for k, v in params.items() if v}

            response = requests.get(f"{self.BASE_URL}/project/{slug}/version", params=params, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error fetching mod versions for {slug}: {e}")
            return []

    def install_mod(self, version_id: str, server_path: str) -> Dict:
        """
        Download and install a specific mod version.
        """
        try:
            # Get version info to find the file URL
            response = requests.get(f"{self.BASE_URL}/version/{version_id}", headers=self.headers)
            response.raise_for_status()
            version_data = response.json()
            
            files = version_data.get("files", [])
            if not files:
                return {"success": False, "error": "No files found for this version"}
            
            # Use the primary file
            primary_file = next((f for f in files if f.get("primary")), files[0])
            url = primary_file["url"]
            filename = primary_file["filename"]
            
            mods_dir = os.path.join(server_path, "mods")
            if not os.path.exists(mods_dir):
                os.makedirs(mods_dir)
                
            file_path = os.path.join(mods_dir, filename)
            
            # Download
            logging.info(f"Downloading mod: {url} -> {file_path}")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
            return {"success": True, "filename": filename, "path": file_path}
            
        except Exception as e:
            logging.error(f"Error installing mod: {e}")
            return {"success": False, "error": str(e)}

    def get_installed_mods(self, server_path: str) -> List[Dict]:
        """
        List all .jar files in the mods folder.
        """
        mods = []
        mods_dir = os.path.join(server_path, "mods")
        if not os.path.exists(mods_dir):
            return []
            
        try:
            for f in os.listdir(mods_dir):
                if f.endswith(".jar"):
                    file_path = os.path.join(mods_dir, f)
                    size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
                    mods.append({
                        "filename": f,
                        "size": f"{size_mb} MB",
                        "path": file_path
                    })
        except Exception as e:
            logging.error(f"Error listing installed mods: {e}")
            
        return mods

    def delete_mod(self, filename: str, server_path: str) -> bool:
        try:
            path = os.path.join(server_path, "mods", filename)
            if os.path.exists(path):
                os.remove(path)
                return True
            return False
        except Exception as e:
            logging.error(f"Error deleting mod {filename}: {e}")
            return False
