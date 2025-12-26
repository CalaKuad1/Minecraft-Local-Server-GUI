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

    def search_mods(self, query: str, loader: str = "fabric", version: str = None, project_type: str = "mod", sort: str = "downloads", category: str = None) -> List[Dict]:
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

            if category and category.lower() != "all":
                 facets.append([f"categories:{category}"])
            
            params = {
                "query": query,
                "limit": 20,
                "facets": json.dumps(facets)
            }
            
            # Sort mapping
            if sort:
                 params["index"] = sort
            elif not query or query.strip() == "":
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

    def install_mod(self, version_id: str, server_path: str, progress_callback=None) -> Dict:
        """
        Download and install a specific mod version or modpack.
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
            
            # Detect Modpack
            if filename.endswith(".mrpack"):
                if progress_callback: progress_callback(0, "Downloading modpack...")
                return self.install_modpack(url, filename, server_path, progress_callback)

            mods_dir = os.path.join(server_path, "mods")
            if not os.path.exists(mods_dir):
                os.makedirs(mods_dir)
                
            file_path = os.path.join(mods_dir, filename)
            
            # Download
            if progress_callback: progress_callback(10, f"Downloading {filename}...")
            logging.info(f"Downloading mod: {url} -> {file_path}")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            if progress_callback: progress_callback(100, "Installed!")
            return {"success": True, "filename": filename, "path": file_path}
            
        except Exception as e:
            logging.error(f"Error installing mod: {e}")
            return {"success": False, "error": str(e)}

    def install_modpack(self, url: str, filename: str, server_path: str, progress_callback=None) -> Dict:
        import zipfile
        import shutil
        
        try:
            # 1. Download .mrpack
            temp_dir = os.path.join(server_path, "temp_modpack")
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            
            mrpack_path = os.path.join(temp_dir, filename)
            
            logging.info(f"Downloading modpack: {url}")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(mrpack_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
            # 2. Extract
            if progress_callback: progress_callback(20, "Extracting modpack...")
            with zipfile.ZipFile(mrpack_path, 'r') as zf:
                zf.extractall(temp_dir)
                
            # 3. Read index
            index_path = os.path.join(temp_dir, "modrinth.index.json")
            if not os.path.exists(index_path):
                return {"success": False, "error": "Invalid modpack: modrinth.index.json missing"}
                
            with open(index_path, 'r') as f:
                index_data = json.load(f)
                
            files_to_download = index_data.get("files", [])
            total_files = len(files_to_download)
            logging.info(f"Found {total_files} mods in modpack.")
            
            # 4. Download dependencies
            mods_dir = os.path.join(server_path, "mods") # Default base
            # Note: files in modpack might go to other folders, but usually mods/
            
            # Ensure we start with a clean state? 
            # Ideally yes for modpacks, but maybe user wants to keep some. 
            # For now, let's just add/overwrite.
            
            for i, file_info in enumerate(files_to_download):
                rel_path = file_info.get("path")
                download_urls = file_info.get("downloads", [])
                
                if not rel_path or not download_urls: continue
                
                # Report progress
                pct = 20 + int((i / total_files) * 60) # 20% to 80%
                if progress_callback: 
                    name = rel_path.split('/')[-1]
                    progress_callback(pct, f"Installing: {name}")

                target_path = os.path.join(server_path, rel_path)
                target_dir = os.path.dirname(target_path)
                if not os.path.exists(target_dir): os.makedirs(target_dir)
                
                # Download first valid url
                dl_url = download_urls[0]
                
                try:
                    with requests.get(dl_url, stream=True) as r:
                        r.raise_for_status()
                        with open(target_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                except Exception as dl_err:
                    logging.error(f"Failed to download dependency {rel_path}: {dl_err}")
                    # Continue best effort? Or fail? Modpacks usually need all.
                    # Let's log and continue to try getting most.

            # 5. Handle Overrides
            if progress_callback: progress_callback(80, "Applying configuration...")
            overrides_dir = os.path.join(temp_dir, "overrides")
            if os.path.exists(overrides_dir):
                logging.info("Applying overrides...")
                for root, dirs, files in os.walk(overrides_dir):
                    rel_root = os.path.relpath(root, overrides_dir)
                    target_root = os.path.join(server_path, rel_root)
                    if not os.path.exists(target_root): os.makedirs(target_root)
                    
                    for f in files:
                        src_file = os.path.join(root, f)
                        dst_file = os.path.join(target_root, f)
                        try:
                            shutil.copy2(src_file, dst_file)
                        except Exception as copy_err:
                            logging.error(f"Failed to copy override {f}: {copy_err}")
                        
            # Cleanup
            shutil.rmtree(temp_dir)
            
            if progress_callback: progress_callback(100, "Modpack installed successfully!")
            return {"success": True, "message": f"Installed modpack with {total_files} mods."}
            
        except Exception as e:
            logging.error(f"Modpack installation failed: {e}")
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
