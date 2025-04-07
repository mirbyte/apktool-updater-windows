import os
import re
import sys
import shutil
import requests
import subprocess
import hashlib
import logging
import platform
from pathlib import Path
from colorama import init, Fore, Back, Style


# Initialize colorama
init()
RED = Fore.RED
GREEN = Fore.GREEN
RESET = Style.RESET_ALL

title = "APKTool Updater v1.0 (mirbyte)"
os.system(f"title {title}")

def banner():
    print("APKTool Updater v1.0")
    print("====================")

# Configure logging
logging.basicConfig(
    # INFO, DEBUG, or ERROR
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.getcwd(), 'apktool_updater.log')),
        logging.StreamHandler(stream=sys.stdout)
    ]
)

logger = logging.getLogger()
logger.handlers[1].setFormatter(logging.Formatter('%(levelname)s - %(message)s'))


def get_latest_apktool_version():
    logger.debug("Fetching latest APKTool version from GitHub")
    url = "https://api.github.com/repos/iBotPeaches/Apktool/releases/latest"
    try:
        logger.debug(f"Making request to: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        latest_version = response.json()["tag_name"]
        logger.info(f"Latest version found: {latest_version}")
        return latest_version
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching latest version: {e}")
        logger.debug(f"Request details: URL={url}, Timeout=10")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while fetching latest version: {e}")
        logger.debug(f"Error type: {type(e).__name__}")
        return None

def get_installed_apktool_version():
    logger.debug("Checking installed APKTool version")
    try:
        # try to find apktool.jar directly
        install_dir = find_apktool_install_path()
        if install_dir:
            jar_path = Path(install_dir) / "apktool.jar"
            if jar_path.exists():
                try:
                    result = subprocess.run(
                        ["java", "-jar", str(jar_path), "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return result.stdout.strip()
                except Exception:
                    pass

        commands = [
            ["apktool", "--version"],
            ["apktool.bat", "--version"]
        ]
        
        for cmd in commands:
            try:
                logger.debug(f"Executing: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if output:
                        return output
            except Exception as e:
                logger.debug(f"Version check attempt failed: {str(e)}")
                continue
                
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error checking version: {e}")
        return None

def find_apktool_install_path():
    """Finds the installation directory of apktool files."""
    logger.debug("Searching for APKTool installation directory")
    
    windows_dir = Path("C:\\Windows")
    apktool_jar = windows_dir / "apktool.jar"
    apktool_bat = windows_dir / "apktool.bat"
    if apktool_jar.exists() and apktool_bat.exists():
        return str(windows_dir)
    
    # PATH
    apktool_bat_path = shutil.which("apktool.bat")
    if apktool_bat_path:
        apktool_dir = Path(apktool_bat_path).parent
        apktool_jar = apktool_dir / "apktool.jar"
        if apktool_jar.exists():
            return str(apktool_dir)
    
    common_paths = [
        Path("C:\\apktool"),
        Path(os.environ.get("ProgramFiles", "")) / "apktool",
        Path.home() / "apktool",
    ]
    
    for path in common_paths:
        apktool_jar = path / "apktool.jar"
        if apktool_jar.exists():
            logger.info(f"Found apktool.jar at {path} but no wrapper script")
            return str(path)
    
    logger.warning("Could not find APKTool installation directory")
    return None

def download_apktool(version, install_dir):
    logger.debug(f"Starting download process for version {version} to {install_dir}")
    clean_version = version.lstrip('v') if version.startswith('v') else version
    jar_url = f"https://github.com/iBotPeaches/Apktool/releases/download/{version}/apktool_{clean_version}.jar"
    bat_url = "https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/windows/apktool.bat"
    
    if not all(validate_url(url) for url in [jar_url, bat_url]):
        logger.error("Invalid download URL detected")
        return False

    try:
        install_path = Path(install_dir)
        try:
            install_path.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            logger.error(f"Permission denied creating directory {install_path}: {e}")
            return False
        except OSError as e:
            logger.error(f"Filesystem error creating directory {install_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating directory {install_path}: {e}")
            return False
            
        jar_path = install_path / "apktool.jar"
        try:
            logger.info(f"Downloading APKTool JAR from {jar_url}")
            response = requests.get(jar_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Use atomic write with temp file
            temp_path = jar_path.with_suffix('.tmp')
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify before replacing existing file
            if not verify_file_integrity(temp_path):
                temp_path.unlink(missing_ok=True)
                raise Exception("Downloaded JAR file verification failed")
                
            # Atomic replace
            temp_path.replace(jar_path)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during JAR download: {e}")
            return False
        except IOError as e:
            logger.error(f"File I/O error during JAR download: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during JAR download: {e}")
            return False

        # Download wrapper script
        wrapper_path = install_path / "apktool.bat"
        try:
            logger.info(f"Downloading wrapper script from {bat_url}")
            response = requests.get(bat_url, timeout=10)
            response.raise_for_status()
            
            # Atomic write
            temp_path = wrapper_path.with_suffix('.tmp')
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(response.text)
                
            temp_path.replace(wrapper_path)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during wrapper download: {e}")
            return False
        except IOError as e:
            logger.error(f"File I/O error during wrapper download: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during wrapper download: {e}")
            return False

        logger.info(f"Successfully updated APKTool to {version} in {install_dir}")
        return True
        
    except Exception as e:
        logger.error(f"Critical error during update process: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return False

def verify_file_integrity(file_path, expected_size=None, expected_hash=None):
    logger.debug(f"Verifying file integrity for: {file_path}")
    if not file_path.exists():
        logger.debug("File does not exist")
        return False
    
    if expected_size and file_path.stat().st_size != expected_size:
        logger.debug(f"Size mismatch: expected={expected_size}, actual={file_path.stat().st_size}")
        return False
    
    # Calculate SHA-256
    with open(file_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    
    logger.debug(f"File {file_path} checksum: {file_hash}")
    
    if expected_hash:
        if file_hash.lower() != expected_hash.lower():
            logger.error(f"Checksum mismatch! Expected: {expected_hash}, Got: {file_hash}")
            return False
        logger.info("File checksum verified successfully")
    
    return True

def check_java_version():
    """Verifies Java 8 or higher is installed."""
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            check=True
        )
        version_output = result.stderr or result.stdout
        if "version" in version_output:
            version_str = version_output.split('"')[1]
            major_version = int(version_str.split('.')[0])
            if major_version < 1 and len(version_str.split('.')) > 1:
                major_version = int(version_str.split('.')[1])
            return major_version >= 8
        return False
    except Exception:
        return False

def validate_url(url):
    try:
        result = requests.utils.urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False
        return result.scheme == 'https'
    except Exception:
        return False

def compare_versions(v1, v2):
    """Compares two version strings, handling different formats"""
    def normalize_version(v):
        # Remove 'v' prefix and split into components
        v = v.lstrip('v').split('.')
        # Convert each component to integer, default to 0 if not numeric
        return [int(x) if x.isdigit() else 0 for x in v]
    
    # Changed from >= to < to correctly identify when an update is needed
    return normalize_version(v1) < normalize_version(v2)

def main():
    banner()
    logger.debug("Script started")
    
    # Check Java requirements
    if not check_java_version():
        logger.error("Java 8 or higher is required to run APKTool")
        print("")
        print("")
        input(RED + "Press Enter to exit..." + RESET)
        sys.exit(1)
    
    logger.debug("Starting APKTool version check")
    latest_version = get_latest_apktool_version()
    if not latest_version:
        logger.error("Failed to determine latest version")
        print("")
        print("")
        input("Press Enter to exit...")
        sys.exit(1)
    
    default_dir = "C:\\Windows"
    
    install_dir = find_apktool_install_path()
    if install_dir:
        bat_path = Path(install_dir) / "apktool.bat"
        if not bat_path.exists():
            logger.warning("Found apktool.jar but missing wrapper script")
            if input("Download missing wrapper script? [Y/n]: ").strip().lower() != 'n':
                if not download_apktool(latest_version, install_dir):
                    sys.exit(1)
    
    installed_version = get_installed_apktool_version()
    if installed_version:
        logger.info(f"Installed version: {installed_version}")
    else:
        logger.warning("APKTool is not installed or not in PATH")

    logger.debug(f"Latest version available: {latest_version}")
    
    if installed_version and not compare_versions(installed_version, latest_version.replace("v", "")):
        print(GREEN + "APKTool is already up to date" + RESET)
        print("")
        print("")
        input("Press Enter to exit...")
        sys.exit(0)
    
    # If we get here, we need to update or install APKTool
    if not install_dir:
        try:
            test_dir = Path(default_dir)
            try:
                test_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to access directory {test_dir}: {e}")
                raise

            test_path = test_dir / "apktool_test.tmp"
            try:
                with open(test_path, 'w') as f:
                    f.write("test")
                test_path.unlink()
            except Exception as e:
                logger.error(f"Failed to create test file: {e}")
                raise

            install_dir = default_dir
            logger.info(f"Using recommended directory: {install_dir}")
        except (PermissionError, OSError) as e:
            logger.error(f"Permission denied: {e}")
            logger.error("Please run this script as Administrator to install to C:\\Windows")
            print("")
            print("")
            input("Press Enter to exit...")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error during UAC test: {e}")
            print("")
            print("")
            input("Press Enter to exit...")
            sys.exit(1)
    
    logger.info(f"Updating APKTool in: {install_dir}")
    if not download_apktool(latest_version, install_dir):
        print("")
        print("")
        input("Press Enter to exit...")
        sys.exit(1)
    
    print("")
    print(GREEN + "APKTool has been successfully updated!" + RESET)
    print("")
    print("")
    input("Press Enter to exit...")



if __name__ == "__main__":
    main()

