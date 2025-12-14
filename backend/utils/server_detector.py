import os
import glob
import json
import zipfile
import re
from typing import Dict, Optional, Tuple

class ServerDetector:
    def __init__(self):
        pass

    def detect(self, server_path: str) -> Dict[str, any]:
        """
        Analyzes the server directory to detect type and version.
        Returns: {
            "type": str (vanilla, paper, forge, fabric, unknown),
            "version": str (e.g., 1.20.1 or None),
            "detected": bool
        }
        """
        result = {
            "type": "unknown",
            "version": None,
            "detected": False
        }

        if not os.path.exists(server_path):
            return result

        # 1. Search for known JAR patterns
        jars = glob.glob(os.path.join(server_path, "*.jar"))
        
        best_candidate = None
        
        # Priority scan for well-known server JAR names
        for jar in jars:
            name = os.path.basename(jar).lower()
            if "installer" in name: continue
            
            # Common names
            if name in ["server.jar", "paper.jar", "spigot.jar", "fabric-server-launch.jar"]:
                best_candidate = jar
                break
            
            # Pattern matching names
            if re.search(r"paper-\d", name) or re.search(r"server-\d", name) or re.search(r"forge-\d", name):
                best_candidate = jar
                break
        
        if not best_candidate and jars:
            # Fallback to largest non-installer JAR
            # Filter out installers
            valid_jars = [j for j in jars if "installer" not in os.path.basename(j).lower()]
            if valid_jars:
                # Sort by size, largest likely the server
                best_candidate = sorted(valid_jars, key=lambda x: os.path.getsize(x), reverse=True)[0]

        if best_candidate:
            detected_info = self._analyze_jar(best_candidate)
            if detected_info:
                result.update(detected_info)
                result["detected"] = True
                return result

        # 2. Check for File Structure signals (if JAR analysis failed)
        if os.path.exists(os.path.join(server_path, ".fabric")):
             result["type"] = "fabric"
             result["detected"] = True # Partial detection

        return result

    def _analyze_jar(self, jar_path: str) -> Optional[Dict[str, str]]:
        """Opens a JAR and attempts to find version/type info."""
        name = os.path.basename(jar_path).lower()
        info = {"type": "unknown", "version": None}
        
        # Name-based heuristic first (fastest)
        # matches: paper-1.20.1-430.jar -> 1.20.1
        version_match = re.search(r"(\d+\.\d+(\.\d+)?)", name)
        if version_match:
            info["version"] = version_match.group(1)

        if "paper" in name: info["type"] = "paper"
        elif "forge" in name: info["type"] = "forge"
        elif "fabric" in name: info["type"] = "fabric"
        elif "spigot" in name: info["type"] = "spigot"
        elif "server" in name and "vanilla" not in name: info["type"] = "vanilla" # Generic server.jar is usually vanilla 

        # Deep inspection
        try:
            with zipfile.ZipFile(jar_path, 'r') as zf:
                # Check for version.json (common in Vanilla/Paper since 1.14+)
                if "version.json" in zf.namelist():
                    try:
                        with zf.open("version.json") as f:
                            data = json.load(f)
                            if "id" in data:
                                info["version"] = data["id"]
                                # If type was unknown, infer from id or branding
                                if info["type"] == "unknown":
                                    if "paper" in data.get("name", "").lower(): info["type"] = "paper"
                                    else: info["type"] = "vanilla"
                    except: pass
                
                # Check Manifest for Implementation-Version
                if "META-INF/MANIFEST.MF" in zf.namelist():
                     with zf.open("META-INF/MANIFEST.MF") as f:
                        content = f.read().decode('utf-8', errors='ignore')
                        # Manifest analysis logic could go here
                        pass

        except Exception:
            pass
        
        if info["type"] != "unknown" or info["version"]:
            return info
        return None
