import requests
import os
import logging
import json
import time
from typing import List, Dict, Optional

from .api_client import download_file_from_url


class ModsManager:
    BASE_URL = "https://api.modrinth.com/v2"

    def __init__(self):
        self.headers = {"User-Agent": "MinecraftLocalServerGUI/1.0 (internal-dev)"}

    def search_mods(
        self,
        query: str,
        loader: str = "fabric",
        version: str = None,
        project_type: str = "mod",
        sort: str = "downloads",
        category: str = None,
    ) -> List[Dict]:
        """
        Search for mods or modpacks on Modrinth.
        """
        try:
            # Build facets safely
            facets = [[f"project_type:{project_type}"]]

            if loader and loader.lower() != "any":
                facets.append([f"categories:{loader}"])

            if version and version.strip():
                facets.append([f"versions:{version}"])

            if category and category.lower() != "all":
                facets.append([f"categories:{category}"])

            params = {"query": query, "limit": 20, "facets": json.dumps(facets)}

            # Sort mapping
            if sort:
                params["index"] = sort
            elif not query or query.strip() == "":
                params["index"] = "downloads"

            logging.info(f"Searching mods: query='{query}' params={params}")
            response = requests.get(
                f"{self.BASE_URL}/search",
                params=params,
                headers=self.headers,
                timeout=10,
            )

            if response.status_code != 200:
                logging.error(
                    f"Modrinth Search API Error: {response.status_code} - {response.text}"
                )
                return []

            data = response.json()
            hits = data.get("hits", [])
            logging.info(f"Found {len(hits)} mods for query '{query}'")
            return hits
        except Exception as e:
            logging.exception(f"Exception searching mods: {e}")
            return []

    def get_mod_versions(
        self, slug: str, loader: str = "fabric", version: str = None
    ) -> List[Dict]:
        """
        Get compatible versions for a specific mod project.
        """
        try:
            params = {
                "loaders": f'["{loader}"]',
                "game_versions": f'["{version}"]' if version else None,
            }

            # 'any'/'all' are UI-sentinel values, not real Modrinth loaders —
            # omit the filter so every published artifact (and its exact
            # filename) is returned instead of an empty list.
            if loader and loader.lower() in ("any", "all"):
                del params["loaders"]

            # Remove None values
            params = {k: v for k, v in params.items() if v}

            response = requests.get(
                f"{self.BASE_URL}/project/{slug}/version",
                params=params,
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error fetching mod versions for {slug}: {e}")
            return []

    # Small in-process cache so "is this project installed?" resolution (one
    # request per search on the client) doesn't re-hit Modrinth on every query.
    PROJECT_FILES_CACHE = {}
    PROJECT_FILES_TTL = 6 * 3600  # seconds

    def get_project_files(self, slug: str) -> List[str]:
        """
        Return every filename this project has published on Modrinth
        (unfiltered by loader/game-version), lowercased and de-duplicated.

        Used to resolve installed jars back to their Modrinth project: the
        on-disk artifact is compared against these real published filenames.
        """
        slug = (slug or "").strip().lower()
        if not slug:
            return []
        now = time.time()
        hit = self.PROJECT_FILES_CACHE.get(slug)
        if hit and hit[0] > now:
            return hit[1]
        try:
            response = requests.get(
                f"{self.BASE_URL}/project/{slug}/version",
                headers=self.headers,
                timeout=15,
            )
            response.raise_for_status()
            names = sorted(
                {
                    f["filename"].lower()
                    for v in response.json()
                    for f in v.get("files", [])
                }
            )
        except Exception as e:
            logging.error(f"Error fetching project files for {slug}: {e}")
            return []
        self.PROJECT_FILES_CACHE[slug] = (now + self.PROJECT_FILES_TTL, names)
        return names

    def install_mod(
        self, version_id: str, server_path: str, progress_callback=None
    ) -> Dict:
        """
        Download and install a specific mod version or modpack.
        """
        try:
            # Get version info to find the file URL
            response = requests.get(
                f"{self.BASE_URL}/version/{version_id}",
                headers=self.headers,
                timeout=10,
            )
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
                if progress_callback:
                    progress_callback(0, "Downloading modpack...")
                return self.install_modpack(
                    url, filename, server_path, progress_callback
                )

            mods_dir = os.path.join(server_path, "mods")
            if not os.path.exists(mods_dir):
                os.makedirs(mods_dir)

            file_path = os.path.join(mods_dir, filename)

            # Download through the shared pipeline so mod installs get the same
            # retry-on-transient-errors, size verification and partial-file
            # cleanup as server JAR downloads.
            if progress_callback:
                progress_callback(10, f"Downloading {filename}...")
            logging.info(f"Downloading mod: {url} -> {file_path}")

            def dl_progress(p):
                if progress_callback:
                    progress_callback(10 + p * 0.8, f"Downloading {filename}...")

            if not download_file_from_url(url, file_path, dl_progress):
                reason = getattr(
                    download_file_from_url, "last_error", None
                ) or "Unknown error"
                return {
                    "success": False,
                    "error": f"Failed to download {filename}: {reason}",
                }

            if progress_callback:
                progress_callback(100, "Installed!")
            return {"success": True, "filename": filename, "path": file_path}

        except Exception as e:
            logging.error(f"Error installing mod: {e}")
            return {"success": False, "error": str(e)}

    def install_modpack(
        self, url: str, filename: str, server_path: str, progress_callback=None
    ) -> Dict:
        import zipfile
        import shutil

        temp_dir = os.path.join(server_path, "temp_modpack")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)

        mrpack_path = os.path.join(temp_dir, filename)

        # Transactional install journal. Every file the modpack writes to is
        # backed up here *before* it is touched, so a failed install can restore
        # the exact previous content — including files that existed before and
        # were overwritten (e.g. the user's configs). Entries are
        # (target_path, backup_path_or_None).
        installed_files = []
        tracked_targets = set()
        backup_dir = os.path.join(temp_dir, "backup")
        backup_counter = 0

        def _backup_and_track(target_path):
            nonlocal backup_counter
            if target_path in tracked_targets:
                return
            tracked_targets.add(target_path)
            backup_path = None
            if os.path.exists(target_path):
                backup_counter += 1
                os.makedirs(backup_dir, exist_ok=True)
                backup_path = os.path.join(backup_dir, f"{backup_counter:06d}")
                try:
                    shutil.copy2(target_path, backup_path)
                except OSError as e:
                    logging.warning(f"Could not back up {target_path}: {e}")
                    backup_path = None
            installed_files.append((target_path, backup_path))

        def cleanup_partial():
            # Restore overwritten files from their backups, then remove files
            # this install created. Newly created directories are left alone.
            for path, backup_path in reversed(installed_files):
                try:
                    if backup_path and os.path.isfile(backup_path):
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        shutil.copy2(backup_path, path)
                    elif path and os.path.isfile(path) and os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
            shutil.rmtree(temp_dir, ignore_errors=True)

        try:
            # 1. Download .mrpack through the shared pipeline (retries,
            #    size verification, partial cleanup).
            logging.info(f"Downloading modpack: {url}")
            if progress_callback:
                progress_callback(10, "Downloading modpack...")
            if not download_file_from_url(url, mrpack_path, None):
                reason = getattr(
                    download_file_from_url, "last_error", None
                ) or "Unknown error"
                cleanup_partial()
                return {
                    "success": False,
                    "error": f"Failed to download modpack: {reason}",
                }

            # 2. Extract
            if progress_callback:
                progress_callback(20, "Extracting modpack...")
            with zipfile.ZipFile(mrpack_path, "r") as zf:
                zf.extractall(temp_dir)

            # 3. Read index
            index_path = os.path.join(temp_dir, "modrinth.index.json")
            if not os.path.exists(index_path):
                cleanup_partial()
                return {
                    "success": False,
                    "error": "Invalid modpack: modrinth.index.json missing",
                }

            with open(index_path, "r") as f:
                index_data = json.load(f)

            files_to_download = index_data.get("files", [])
            total_files = len(files_to_download)
            logging.info(f"Found {total_files} mods in modpack.")

            # 4. Download dependencies
            mods_dir = os.path.join(server_path, "mods")
            # Note: files in modpack might go to other folders, but usually mods/

            # Ensure we start with a clean state?
            # Ideally yes for modpacks, but maybe user wants to keep some.
            # For now, let's just add/overwrite.

            real_server = os.path.realpath(server_path)
            failed_files = []

            def _safe_target(rel_path):
                """Resolves a modpack index path inside the server folder.

                Guards against path traversal (e.g. "../../etc/...") from a
                tampered or malicious index so a download can never escape the
                server directory.
                """
                target = os.path.join(server_path, rel_path)
                real_target = os.path.realpath(target)
                if real_target != real_server and not real_target.startswith(
                    real_server + os.sep
                ):
                    return None
                return target

            for i, file_info in enumerate(files_to_download):
                rel_path = file_info.get("path")
                download_urls = file_info.get("downloads", [])

                if not rel_path or not download_urls:
                    continue

                # Report progress
                pct = 20 + int((i / total_files) * 60) if total_files else 20
                if progress_callback:
                    name = rel_path.split("/")[-1]
                    progress_callback(pct, f"Installing: {name}")

                target_path = _safe_target(rel_path)
                if target_path is None:
                    logging.error(f"Skipping unsafe modpack path: {rel_path}")
                    failed_files.append(rel_path)
                    continue

                target_dir = os.path.dirname(target_path)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)

                # Back up any existing file before the download pipeline touches
                # it: on failure the pipeline deletes the destination, so without
                # this a failed attempt would destroy the user's previous file.
                _backup_and_track(target_path)

                # Try every mirror Modrinth provides; a file only counts as
                # failed once all of its download URLs have been exhausted.
                downloaded = False
                for dl_url in download_urls:
                    if download_file_from_url(dl_url, target_path, None):
                        downloaded = True
                        break
                if not downloaded:
                    reason = getattr(
                        download_file_from_url, "last_error", None
                    ) or "Unknown error"
                    logging.error(
                        f"Failed to download dependency {rel_path}: {reason}"
                    )
                    failed_files.append(rel_path)

            # 5. Handle Overrides
            if progress_callback:
                progress_callback(80, "Applying configuration...")
            overrides_dir = os.path.join(temp_dir, "overrides")
            if os.path.exists(overrides_dir):
                logging.info("Applying overrides...")
                for root, dirs, files in os.walk(overrides_dir):
                    rel_root = os.path.relpath(root, overrides_dir)
                    target_root = os.path.join(server_path, rel_root)
                    if not os.path.exists(target_root):
                        os.makedirs(target_root)

                    for f in files:
                        src_file = os.path.join(root, f)
                        dst_file = os.path.join(target_root, f)
                        try:
                            _backup_and_track(dst_file)
                            shutil.copy2(src_file, dst_file)
                        except Exception as copy_err:
                            logging.error(f"Failed to copy override {f}: {copy_err}")
                            failed_files.append(os.path.join(rel_root, f))

            # 6. A modpack with missing files is broken — roll back instead of
            #    quietly reporting success (previously failures were swallowed).
            if failed_files:
                shown = ", ".join(failed_files[:5])
                suffix = "..." if len(failed_files) > 5 else ""
                cleanup_partial()
                return {
                    "success": False,
                    "error": (
                        f"Modpack installation failed: {len(failed_files)} file(s) "
                        f"could not be downloaded ({shown}{suffix}). "
                        f"The server was left unmodified."
                    ),
                }

            # Success — remove the temp working directory only.
            shutil.rmtree(temp_dir, ignore_errors=True)

            if progress_callback:
                progress_callback(100, "Modpack installed successfully!")
            return {
                "success": True,
                "message": f"Installed modpack with {total_files} mods.",
            }

        except Exception as e:
            logging.error(f"Modpack installation failed: {e}")
            cleanup_partial()
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
                    mods.append(
                        {"filename": f, "size": f"{size_mb} MB", "path": file_path}
                    )
        except Exception as e:
            logging.error(f"Error listing installed mods: {e}")

        return mods

    def delete_mod(self, filename: str, server_path: str) -> bool:
        try:
            # Sanitize: reject anything that isn't a plain file name so a
            # crafted request cannot escape the mods folder.
            filename = os.path.basename(filename or "")
            if not filename:
                return False
            path = os.path.join(server_path, "mods", filename)
            if os.path.exists(path) and os.path.isfile(path):
                os.remove(path)
                return True
            return False
        except Exception as e:
            logging.error(f"Error deleting mod {filename}: {e}")
            return False
