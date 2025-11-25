"""
Medical Search Application Launcher
Starts the Django server and automatically opens the browser.
Compatible with Windows, macOS and Linux.
"""

import os
import sys
import time
import webbrowser
import socket
import threading
import logging
from pathlib import Path

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MedicalSearchLauncher:
    """Launches the Medical Search application autonomously"""
    
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 8000
        self.base_dir = self._get_base_dir()
        self.server_thread = None
        
    def _get_base_dir(self):
        """Returns the base directory depending on execution mode"""
        if getattr(sys, 'frozen', False):
            # PyInstaller mode (executable)
            return Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
        else:
            # Development mode
            return Path(__file__).parent
    
    def find_free_port(self, start_port=8000, max_attempts=10):
        """Finds a free TCP port"""
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((self.host, port))
                    s.close()
                    return port
            except OSError:
                continue
        raise RuntimeError("No available port between 8000-8010")
    
    def is_server_ready(self, timeout=45):
        """Checks if the Django server is responding"""
        import urllib.request
        import urllib.error
        
        start_time = time.time()
        url = f'http://{self.host}:{self.port}/'
        
        logger.info(f"Waiting for server response on {url}...")
        
        attempt = 0
        while time.time() - start_time < timeout:
            attempt += 1
            try:
                # Try to connect
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex((self.host, self.port))
                    
                    if result == 0:
                        # Port is open, try HTTP request
                        try:
                            response = urllib.request.urlopen(url, timeout=3)
                            if response.status == 200:
                                logger.info("Server ready and operational")
                                return True
                        except urllib.error.HTTPError as e:
                            if e.code == 200:
                                logger.info("Server ready (code 200)")
                                return True
                        except Exception as e:
                            logger.debug(f"Attempt {attempt}: HTTP error - {e}")
                
                if attempt % 5 == 0:
                    logger.info(f"Still waiting... ({attempt} attempts)")
                
                time.sleep(1)
                
            except Exception as e:
                logger.debug(f"Attempt {attempt}: {e}")
                time.sleep(1)
        
        logger.error(f"Timeout after {timeout}s ({attempt} attempts)")
        return False
    
    def _run_django_server(self):
        """Executes the Django server in a secondary thread"""
        try:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
            os.environ.setdefault('DEBUG', 'true')
            # Ensure project modules are accessible
            if str(self.base_dir) not in sys.path:
                sys.path.insert(0, str(self.base_dir))
            os.chdir(self.base_dir)

            import django
            django.setup()

            from django.core.management import call_command
            call_command(
                'runserver',
                f'{self.host}:{self.port}',
                use_reloader=False,
                use_ipv6=False,
                skip_checks=False
            )
        except Exception as exc:
            logger.error(f"Django server failed: {exc}")

    def start_django_server(self):
        """Starts the Django server"""
        logger.info("Starting Django server...")

        # Find a free port
        try:
            self.port = self.find_free_port()
            logger.info(f"Port found: {self.port}")
        except RuntimeError as e:
            logger.error(str(e))
            return False

        self.server_thread = threading.Thread(target=self._run_django_server, daemon=True)
        self.server_thread.start()

        # Wait for server to be ready
        if not self.is_server_ready():
            logger.error("Server did not start in time")
            return False

        return True
    
    def open_browser(self):
        """Opens the web browser"""
        url = f'http://{self.host}:{self.port}/'
        logger.info(f"Opening browser: {url}")
        
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            logger.warning(f"Unable to open browser automatically: {e}")
            logger.info(f"Open manually: {url}")
            return False
    
    def show_welcome_message(self):
        """Displays the welcome message"""
        print("\n" + "="*60)
        print("  MEDICAL SEARCH APPLICATION v3.0")
        print("="*60)
        print(f"URL: http://{self.host}:{self.port}/")
        print(f"System: {sys.platform}")
        print("="*60)
        print("\nUsage tips:")
        print("  - Keep this window open")
        print("  - Close the browser to stop the application")
        
        if sys.platform == 'darwin':  # macOS
            print("  - Press Cmd+Q to quit")
        else:
            print("  - Press Ctrl+C to force stop")
        
        print("\n" + "="*60 + "\n")

    def stop_django_server(self):
        """Stops the Django server cleanly"""
        if self.server_thread is not None:
            self.server_thread.join(timeout=5)
            if self.server_thread.is_alive():
                logger.warning("Django server still active, forced shutdown possible")
            self.server_thread = None
    
    def run(self):
        """Launches the complete application"""
        print("\n[START] Starting Medical Search Application...\n")
        
        try:
            # Start Django server
            if not self.start_django_server():
                print("\n" + "="*60)
                print("STARTUP FAILED")
                print("="*60)
                print("\nPossible causes:")
                print("  1. Ports 8000-8010 all occupied")
                print("  2. Missing files in package")
                print("  3. Django configuration error")
                print("\nCheck the logs above for details.")
                print("="*60)
                input("\nPress Enter to close...")
                return 1
            
            # Open browser
            time.sleep(2)  # Wait a bit more for Django to be fully ready
            self.open_browser()
            
            # Welcome message
            self.show_welcome_message()
            
            # Wait for user to close
            try:
                while self.server_thread and self.server_thread.is_alive():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\n\nStop requested by user...")
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            import traceback
            traceback.print_exc()
            return 1
        
        finally:
            # Cleanup
            logger.info("Stopping Django server...")
            self.stop_django_server()
            
            print("\nApplication closed. Goodbye!\n")
            time.sleep(2)
        
        return 0


def main():
    """Main entry point"""
    launcher = MedicalSearchLauncher()
    sys.exit(launcher.run())


if __name__ == '__main__':
    main()
