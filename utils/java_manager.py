import os
import sys
import json
import shutil
import platform
import subprocess
import requests
import zipfile
import tarfile
from pathlib import Path
import logging
from typing import Optional, Dict, Tuple, Callable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JavaManager:
    """
    Gestiona la instalación, detección y configuración de Java para servidores de Minecraft.
    Descarga automáticamente las versiones necesarias y las vincula a cada servidor.
    """
    
    def __init__(self, base_dir: str = None):
        """
        Inicializa el gestor de Java.
        
        Args:
            base_dir: Directorio base donde se almacenarán las instalaciones de Java
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd() / "java_runtimes"
        self.base_dir.mkdir(exist_ok=True)
        
        # Archivo de configuración para mapear servidores con sus versiones de Java
        self.config_file = self.base_dir / "java_config.json"
        self.config = self._load_config()
        
        # Mapeo de versiones de Minecraft a versiones de Java requeridas
        self.mc_java_requirements = {
            # Minecraft 1.21+ requiere Java 21
            "1.21": 21, "1.21.1": 21, "1.21.2": 21, "1.21.3": 21, "1.21.4": 21,
            # Minecraft 1.20.5+ requiere Java 21
            "1.20.5": 21, "1.20.6": 21,
            # Minecraft 1.17-1.20.4 requiere Java 17
            "1.20": 17, "1.20.1": 17, "1.20.2": 17, "1.20.3": 17, "1.20.4": 17,
            "1.19": 17, "1.19.1": 17, "1.19.2": 17, "1.19.3": 17, "1.19.4": 17,
            "1.18": 17, "1.18.1": 17, "1.18.2": 17,
            "1.17": 17, "1.17.1": 17,
            # Minecraft 1.16.5 y anteriores usan Java 8
            "1.16": 8, "1.16.1": 8, "1.16.2": 8, "1.16.3": 8, "1.16.4": 8, "1.16.5": 8,
            "1.15": 8, "1.15.1": 8, "1.15.2": 8,
            "1.14": 8, "1.14.1": 8, "1.14.2": 8, "1.14.3": 8, "1.14.4": 8,
            "1.13": 8, "1.13.1": 8, "1.13.2": 8,
            "1.12": 8, "1.12.1": 8, "1.12.2": 8,
        }
    
    def _load_config(self) -> Dict:
        """Carga la configuración desde el archivo JSON."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Error loading Java config: {e}")
        return {"servers": {}, "java_installations": {}}
    
    def _save_config(self):
        """Guarda la configuración al archivo JSON."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Error saving Java config: {e}")
    
    def get_required_java_version(self, minecraft_version: str) -> int:
        """
        Determina la versión de Java requerida para una versión específica de Minecraft.
        
        Args:
            minecraft_version: Versión de Minecraft (ej: "1.20.1")
            
        Returns:
            Versión mayor de Java requerida (8, 17, 21)
        """
        # Normalizar la versión (quitar prefijos como "v" o espacios)
        version = minecraft_version.strip().lower().replace('v', '')
        
        # Buscar coincidencia exacta
        if version in self.mc_java_requirements:
            return self.mc_java_requirements[version]
        
        # Buscar por versión mayor (ej: 1.20.x -> 1.20)
        parts = version.split('.')
        if len(parts) >= 2:
            major_minor = f"{parts[0]}.{parts[1]}"
            if major_minor in self.mc_java_requirements:
                return self.mc_java_requirements[major_minor]
            
            # Para versiones muy nuevas, asumir Java 21
            try:
                minor_version = int(parts[1])
                if minor_version >= 21:
                    return 21
                elif minor_version >= 17:
                    return 17
            except ValueError:
                pass
        
        # Fallback para versiones desconocidas
        logger.warning(f"Unknown Minecraft version {minecraft_version}, defaulting to Java 8")
        return 8
    
    def detect_system_java(self, java_path: str = "java") -> Optional[Tuple[int, str]]:
        """
        Detecta la versión de Java instalada en el sistema.
        
        Args:
            java_path: Ruta al ejecutable de Java
            
        Returns:
            Tupla (versión_mayor, ruta_completa) o None si no se encuentra
        """
        try:
            # Intentar obtener la versión
            result = subprocess.run(
                [java_path, "-version"], 
                capture_output=True, 
                text=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            if result.returncode != 0:
                return None
            
            # Parsear la salida de versión
            version_output = result.stderr or result.stdout
            
            # Buscar patrones de versión
            import re
            # Java 8: "1.8.0_xxx" o Java 9+: "11.0.x", "17.0.x", etc.
            version_match = re.search(r'version "(\d+)(?:\.(\d+))?', version_output)
            
            if not version_match:
                return None
            
            major_version = int(version_match.group(1))
            
            # Java 8 se reporta como "1.8", convertir a 8
            if major_version == 1 and version_match.group(2):
                major_version = int(version_match.group(2))
            
            # Obtener la ruta completa del ejecutable
            full_path = shutil.which(java_path) or java_path
            
            return (major_version, full_path)
            
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
            logger.debug(f"Error detecting Java: {e}")
            return None
    
    def get_platform_info(self) -> Tuple[str, str]:
        """
        Obtiene información de la plataforma para descargas.
        
        Returns:
            Tupla (os_name, architecture)
        """
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Mapear nombres de OS
        os_map = {
            "windows": "windows",
            "darwin": "mac",
            "linux": "linux"
        }
        
        # Mapear arquitecturas
        arch_map = {
            "x86_64": "x64",
            "amd64": "x64",
            "arm64": "aarch64",
            "aarch64": "aarch64"
        }
        
        os_name = os_map.get(system, "linux")
        arch = arch_map.get(machine, "x64")
        
        return (os_name, arch)
    
    def download_java(self, java_version: int, progress_callback: Callable[[float], None] = None) -> Optional[str]:
        """
        Descarga e instala una versión específica de Java.
        
        Args:
            java_version: Versión mayor de Java (8, 17, 21)
            progress_callback: Función para reportar progreso (0-100)
            
        Returns:
            Ruta al directorio de instalación de Java o None si falla
        """
        if progress_callback is None:
            progress_callback = lambda x: None
        
        os_name, arch = self.get_platform_info()
        
        # Verificar si ya está instalado
        java_dir = self.base_dir / f"java-{java_version}"
        if java_dir.exists():
            java_exe = self._get_java_executable_path(java_dir)
            if java_exe and java_exe.exists():
                logger.info(f"Java {java_version} already installed at {java_dir}")
                return str(java_dir)
        
        logger.info(f"Downloading Java {java_version} for {os_name}-{arch}")
        
        try:
            # Obtener información de descarga desde Adoptium API
            api_url = f"https://api.adoptium.net/v3/assets/latest/{java_version}/hotspot"
            params = {
                "vendor": "eclipse",
                "os": os_name,
                "architecture": arch,
                "image_type": "jre"
            }
            
            response = requests.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            releases = response.json()
            
            if not releases:
                logger.error(f"No Java {java_version} releases found for {os_name}-{arch}")
                return None
            
            # Tomar el primer release disponible
            binary_info = releases[0]["binary"]
            download_url = binary_info["package"]["link"]
            filename = binary_info["package"]["name"]
            
            logger.info(f"Downloading from: {download_url}")
            
            # Descargar el archivo
            download_path = self.base_dir / filename
            if not self._download_file(download_url, download_path, progress_callback):
                return None
            
            # Extraer el archivo
            progress_callback(90)
            if not self._extract_java_archive(download_path, java_dir):
                return None
            
            # Limpiar archivo descargado
            download_path.unlink(missing_ok=True)
            
            # Verificar instalación
            java_exe = self._get_java_executable_path(java_dir)
            if not java_exe or not java_exe.exists():
                logger.error(f"Java executable not found after extraction")
                return None
            
            # Guardar en configuración
            self.config["java_installations"][str(java_version)] = str(java_dir)
            self._save_config()
            
            progress_callback(100)
            logger.info(f"Java {java_version} successfully installed to {java_dir}")
            return str(java_dir)
            
        except Exception as e:
            logger.error(f"Error downloading Java {java_version}: {e}")
            return None
    
    def _download_file(self, url: str, path: Path, progress_callback: Callable[[float], None]) -> bool:
        """Descarga un archivo con reporte de progreso."""
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = min((downloaded / total_size) * 90, 90)  # Reservar 10% para extracción
                            progress_callback(progress)
            
            return True
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return False
    
    def _extract_java_archive(self, archive_path: Path, extract_to: Path) -> bool:
        """Extrae un archivo de Java (zip o tar.gz)."""
        try:
            extract_to.mkdir(parents=True, exist_ok=True)
            
            if archive_path.suffix.lower() == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_to)
            elif archive_path.suffix.lower() in ['.gz', '.tar']:
                with tarfile.open(archive_path, 'r:*') as tar_ref:
                    tar_ref.extractall(extract_to)
            else:
                logger.error(f"Unsupported archive format: {archive_path.suffix}")
                return False
            
            # Mover contenido si está en un subdirectorio
            self._flatten_java_directory(extract_to)
            return True
            
        except Exception as e:
            logger.error(f"Error extracting archive: {e}")
            return False
    
    def _flatten_java_directory(self, java_dir: Path):
        """Aplana la estructura de directorios si Java está en un subdirectorio."""
        contents = list(java_dir.iterdir())
        
        # Si hay solo un directorio, mover su contenido al nivel superior
        if len(contents) == 1 and contents[0].is_dir():
            subdir = contents[0]
            temp_dir = java_dir.parent / f"{java_dir.name}_temp"
            
            # Mover subdirectorio temporalmente
            subdir.rename(temp_dir)
            
            # Mover contenido del subdirectorio al directorio principal
            for item in temp_dir.iterdir():
                item.rename(java_dir / item.name)
            
            # Eliminar directorio temporal
            temp_dir.rmdir()
    
    def _get_java_executable_path(self, java_dir: Path) -> Optional[Path]:
        """Obtiene la ruta al ejecutable de Java en un directorio de instalación."""
        possible_paths = [
            java_dir / "bin" / "java.exe",  # Windows
            java_dir / "bin" / "java",      # Unix
            java_dir / "Contents" / "Home" / "bin" / "java",  # macOS
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        return None
    
    def get_java_for_server(self, server_path: str, minecraft_version: str) -> Optional[str]:
        """
        Obtiene la ruta de Java apropiada para un servidor específico.
        Descarga automáticamente si es necesario.
        
        Args:
            server_path: Ruta del servidor
            minecraft_version: Versión de Minecraft
            
        Returns:
            Ruta al ejecutable de Java o None si falla
        """
        required_version = self.get_required_java_version(minecraft_version)
        
        # Verificar si ya tenemos Java configurado para este servidor
        server_key = str(Path(server_path).resolve())
        if server_key in self.config["servers"]:
            java_path = self.config["servers"][server_key]["java_path"]
            if Path(java_path).exists():
                return java_path
        
        # Buscar instalación local de la versión requerida
        java_dir = self.base_dir / f"java-{required_version}"
        if java_dir.exists():
            java_exe = self._get_java_executable_path(java_dir)
            if java_exe and java_exe.exists():
                self._link_java_to_server(server_path, minecraft_version, str(java_exe))
                return str(java_exe)
        
        # Verificar Java del sistema
        system_java = self.detect_system_java()
        if system_java and system_java[0] >= required_version:
            self._link_java_to_server(server_path, minecraft_version, system_java[1])
            return system_java[1]
        
        # Necesitamos descargar Java
        logger.info(f"Java {required_version} required for Minecraft {minecraft_version}, downloading...")
        java_install_dir = self.download_java(required_version)
        
        if java_install_dir:
            java_exe = self._get_java_executable_path(Path(java_install_dir))
            if java_exe:
                java_path = str(java_exe)
                self._link_java_to_server(server_path, minecraft_version, java_path)
                return java_path
        
        return None
    
    def _link_java_to_server(self, server_path: str, minecraft_version: str, java_path: str):
        """Vincula una instalación de Java a un servidor específico."""
        server_key = str(Path(server_path).resolve())
        
        if "servers" not in self.config:
            self.config["servers"] = {}
        
        self.config["servers"][server_key] = {
            "minecraft_version": minecraft_version,
            "java_path": java_path,
            "java_version": self.get_required_java_version(minecraft_version)
        }
        
        self._save_config()
        logger.info(f"Linked Java {java_path} to server {server_path}")
    
    def get_java_status(self, minecraft_version: str) -> Dict[str, any]:
        """
        Obtiene el estado de Java para una versión específica de Minecraft.
        
        Returns:
            Diccionario con información del estado
        """
        required_version = self.get_required_java_version(minecraft_version)
        system_java = self.detect_system_java()
        
        # Verificar instalación local
        local_java_dir = self.base_dir / f"java-{required_version}"
        local_java_available = False
        if local_java_dir.exists():
            java_exe = self._get_java_executable_path(local_java_dir)
            local_java_available = java_exe and java_exe.exists()
        
        status = {
            "required_version": required_version,
            "system_java": system_java,
            "local_java_available": local_java_available,
            "needs_download": False,
            "status_message": "",
            "status_color": "green"
        }
        
        if local_java_available:
            status["status_message"] = f"✅ Java {required_version} disponible (instalación local)"
            status["status_color"] = "green"
        elif system_java and system_java[0] >= required_version:
            status["status_message"] = f"✅ Java {system_java[0]} del sistema (compatible)"
            status["status_color"] = "green"
        elif system_java and system_java[0] < required_version:
            status["status_message"] = f"⚠️ Java {system_java[0]} encontrado (se requiere Java {required_version}+)"
            status["status_color"] = "orange"
            status["needs_download"] = True
        else:
            status["status_message"] = f"❌ Java no encontrado (se requiere Java {required_version}+)"
            status["status_color"] = "red"
            status["needs_download"] = True
        
        return status
    
    def cleanup_unused_java(self):
        """Limpia instalaciones de Java no utilizadas."""
        used_versions = set()
        
        # Recopilar versiones en uso
        for server_info in self.config.get("servers", {}).values():
            used_versions.add(server_info.get("java_version"))
        
        # Eliminar instalaciones no utilizadas
        for java_dir in self.base_dir.glob("java-*"):
            try:
                version = int(java_dir.name.split("-")[1])
                if version not in used_versions:
                    logger.info(f"Removing unused Java {version} installation")
                    shutil.rmtree(java_dir)
            except (ValueError, IndexError):
                continue
    
    def list_installed_java_versions(self) -> Dict[int, str]:
        """Lista todas las versiones de Java instaladas localmente."""
        versions = {}
        
        for java_dir in self.base_dir.glob("java-*"):
            try:
                version = int(java_dir.name.split("-")[1])
                java_exe = self._get_java_executable_path(java_dir)
                if java_exe and java_exe.exists():
                    versions[version] = str(java_dir)
            except (ValueError, IndexError):
                continue
        
        return versions


# Función de conveniencia para uso directo
def get_java_for_minecraft(minecraft_version: str, server_path: str = None, progress_callback: Callable[[float], None] = None) -> Optional[str]:
    """
    Función de conveniencia para obtener Java para una versión específica de Minecraft.
    
    Args:
        minecraft_version: Versión de Minecraft
        server_path: Ruta del servidor (opcional)
        progress_callback: Callback de progreso para descargas
        
    Returns:
        Ruta al ejecutable de Java
    """
    manager = JavaManager()
    
    if server_path:
        return manager.get_java_for_server(server_path, minecraft_version)
    else:
        required_version = manager.get_required_java_version(minecraft_version)
        java_dir = manager.download_java(required_version, progress_callback)
        if java_dir:
            java_exe = manager._get_java_executable_path(Path(java_dir))
            return str(java_exe) if java_exe else None
        return None


if __name__ == "__main__":
    # Pruebas del módulo
    manager = JavaManager()
    
    print("=== Java Manager Test ===")
    print(f"Platform: {manager.get_platform_info()}")
    
    # Probar detección de Java del sistema
    system_java = manager.detect_system_java()
    if system_java:
        print(f"System Java: {system_java[0]} at {system_java[1]}")
    else:
        print("No system Java detected")
    
    # Probar requerimientos de versión
    test_versions = ["1.16.5", "1.17.1", "1.20.1", "1.21"]
    for version in test_versions:
        required = manager.get_required_java_version(version)
        status = manager.get_java_status(version)
        print(f"Minecraft {version} -> Java {required} | {status['status_message']}")