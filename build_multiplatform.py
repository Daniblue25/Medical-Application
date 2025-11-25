"""
Script de build multi-plateforme pour Medical Search Application
Utilise PyInstaller pour crer des excutables standalone.
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

class Builder:
    """Constructeur d'excutables multi-plateforme"""
    
    def __init__(self):
        self.platform_info = self._get_platform_info()
        self.base_dir = Path(__file__).parent
        self.dist_dir = self.base_dir / 'distribution'
        
    def _get_platform_info(self):
        """Retourne les informations de la plateforme"""
        os_name = platform.system()
        
        platforms = {
            'Windows': {
                'name': 'windows',
                'executable_name': 'MedicalSearch.exe',
                'icon': 'static/favicon.ico',
                'separator': ';'
            },
            'Darwin': {  # macOS
                'name': 'macos',
                'executable_name': 'MedicalSearch.app',
                'icon': 'static/favicon.icns',
                'separator': ':'
            },
            'Linux': {
                'name': 'linux',
                'executable_name': 'MedicalSearch',
                'icon': 'static/favicon.png',
                'separator': ':'
            }
        }
        
        return platforms.get(os_name, platforms['Linux'])
    
    def clean(self):
        """Nettoie les anciens builds"""
        print("\n Nettoyage des anciens builds...")
        
        folders_to_clean = ['build', 'dist', '__pycache__']
        for folder in folders_to_clean:
            folder_path = self.base_dir / folder
            if folder_path.exists():
                shutil.rmtree(folder_path)
                print(f"    {folder}/ supprim")
        
        # Supprimer les fichiers .spec
        for spec_file in self.base_dir.glob('*.spec'):
            spec_file.unlink()
            print(f"    {spec_file.name} supprim")
    
    def collect_static(self):
        """Collecte les fichiers statiques Django"""
        print("\n Collecte des fichiers statiques...")
        
        try:
            subprocess.run([
                sys.executable,
                'manage.py',
                'collectstatic',
                '--noinput',
                '--clear'
            ], check=True, cwd=str(self.base_dir))
            print("    Fichiers statiques collects")
        except subprocess.CalledProcessError as e:
            print(f"     Erreur lors de la collecte: {e}")
    
    def build(self):
        """Compile l'application avec PyInstaller"""
        print(f"\n Build pour {self.platform_info['name']}...")
        
        # Fichiers  inclure
        datas = [
            ('templates', 'templates'),
            ('static', 'static'),
            ('staticfiles', 'staticfiles'),
            ('manage.py', '.'),
            ('db.sqlite3', '.'),
            ('.env.example', '.'),
            ('search', 'search'),
            ('config', 'config'),
        ]
        
        # Arguments PyInstaller
        args = [
            'launcher.py',
            f"--name=MedicalSearch",
            '--onefile',
            '--console',  # Mode console pour debug
            '--noconfirm',
            '--clean',
        ]
        
        # Ajouter l'icne si disponible
        icon_path = self.base_dir / self.platform_info['icon']
        if icon_path.exists():
            args.append(f"--icon={icon_path}")
        
        # Ajouter les donnes
        for src, dest in datas:
            src_path = self.base_dir / src
            if src_path.exists():
                args.append(f"--add-data={src}{self.platform_info['separator']}{dest}")
        
        # Hidden imports Django
        hidden_imports = [
            'django',
            'django.core.management',
            'django.core.management.commands',
            'django.core.management.commands.runserver',
            'rest_framework',
            'whitenoise',
            'whitenoise.storage',
            'whitenoise.middleware',
            'config.settings',
            'config.urls',
            'config.wsgi',
            'search',
            'search.views',
            'search.services',
            'search.models',
        ]
        
        for imp in hidden_imports:
            args.append(f"--hidden-import={imp}")
        
        # Collecter tous les modules Django
        args.extend([
            '--collect-all=django',
            '--collect-all=rest_framework',
            '--copy-metadata=django',
            '--copy-metadata=djangorestframework',
        ])
        
        # Excuter PyInstaller
        print(f"\n Commande PyInstaller:")
        print(f"   pyinstaller {' '.join(args)}\n")
        
        # Utiliser le chemin complet de PyInstaller si dans venv
        pyinstaller_cmd = 'pyinstaller'
        venv_pyinstaller = Path(sys.executable).parent / 'pyinstaller.exe'
        if venv_pyinstaller.exists():
            pyinstaller_cmd = str(venv_pyinstaller)
            print(f" Utilisation de PyInstaller du venv: {pyinstaller_cmd}\n")
        
        try:
            subprocess.run([pyinstaller_cmd] + args, check=True)
            print("\n Compilation russie!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n Erreur de compilation: {e}")
            return False
    
    def package(self):
        """Cre le package de distribution"""
        print("\n Cration du package de distribution...")
        
        # Crer le dossier distribution
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        self.dist_dir.mkdir()
        
        # Copier l'excutable
        exe_path = self.base_dir / 'dist' / self.platform_info['executable_name']
        
        if not exe_path.exists():
            print(f" Excutable introuvable: {exe_path}")
            return False
        
        if exe_path.is_file():
            shutil.copy2(exe_path, self.dist_dir)
        else:  # macOS .app bundle
            shutil.copytree(exe_path, self.dist_dir / exe_path.name)
        
        # Crer le README
        readme_content = f"""# Medical Search Application v3.0

##  Installation

1. **Extraire** tous les fichiers
2. **Double-cliquer** sur {self.platform_info['executable_name']}
3. **Attendre** quelques secondes (le serveur dmarre)
4. Le navigateur s'ouvre automatiquement !

##  Utilisation

- Entrez des mots-cls mdicaux dans la barre de recherche
- Slectionnez les filtres (type de chirurgie, priode, rgion, etc.)
- Cliquez sur "Search PubMed"
- Explorez les rsultats avec donnes gographiques
- Exportez en Excel pour analyse approfondie

##  Fonctionnalits

 Recherche dans 13 revues mdicales de premier plan
 Filtres par type de chirurgie (hpatique, gastrique, etc.)
 Dtection automatique de la rgion gographique
 Extraction du nombre de participants
 Export Excel complet (jusqu' 50 000 articles)
 Interface moderne et intuitive

##  Problmes Courants

**L'application ne dmarre pas ?**
- Windows : Vrifiez votre antivirus (peut bloquer au 1er lancement)
- macOS : Clic droit > Ouvrir (premire fois uniquement)
- Linux : Donnez les permissions d'excution (`chmod +x MedicalSearch`)

**Le navigateur ne s'ouvre pas automatiquement ?**
- Ouvrez manuellement : http://127.0.0.1:8000/
- L'application trouve automatiquement un port libre (8000-8010)

**"Port 8000 dj utilis" ?**
- Normal ! L'application trouve automatiquement un port libre
- Consultez la fentre de terminal pour voir le port utilis

**L'application est lente ?**
- Premire recherche : PubMed peut prendre 10-30 secondes
- Recherches suivantes : Mise en cache pour performances optimales

##  Support Technique

- Email: support@medical-search.com
- Version: 3.0
- Date de build: {datetime.now().strftime('%Y-%m-%d')}
- Systme: {self.platform_info['name']}

##  Journaux cibles

1. New England Journal of Medicine (NEJM)
2. The Lancet
3. Journal of the American Medical Association (JAMA)
4. JAMA Surgery
5. British Journal of Surgery
6. Annals of Surgery
7. International Journal of Surgery
8. Digestive Endoscopy
9. Liver Transplantation
10. Journal of the American College of Surgeons
11. American Journal of Transplantation
12. Endoscopy
13. Hepatobiliary Surgery and Nutrition

---
 2025 Medical Search Application. Tous droits rservs.
"""
        
        readme_path = self.dist_dir / 'README.txt'
        readme_path.write_text(readme_content, encoding='utf-8')
        
        # Taille du fichier
        if exe_path.is_file():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"    Excutable: {self.platform_info['executable_name']} ({size_mb:.1f} MB)")
        else:
            print(f"    Application: {self.platform_info['executable_name']}")
        
        print(f"    README.txt cr")
        print(f"\n Package cr dans: {self.dist_dir}/")
        
        return True
    
    def run(self, clean=False, collect_static=True):
        """Excute le build complet"""
        print("\n" + "="*60)
        print("  MEDICAL SEARCH - BUILD SYSTEM")
        print("="*60)
        print(f"Plateforme: {self.platform_info['name']}")
        print(f"Excutable: {self.platform_info['executable_name']}")
        print("="*60)
        
        try:
            if clean:
                self.clean()
            
            if collect_static:
                self.collect_static()
            
            if not self.build():
                return 1
            
            if not self.package():
                return 1
            
            print("\n" + "="*60)
            print(" BUILD TERMIN AVEC SUCCS!")
            print("="*60)
            print(f"\n Fichiers de distribution:")
            print(f"   {self.dist_dir}/")
            print(f"\n Pour tester:")
            if self.platform_info['name'] == 'windows':
                print(f"   cd distribution")
                print(f"   .\\{self.platform_info['executable_name']}")
            else:
                print(f"   cd distribution")
                print(f"   ./{self.platform_info['executable_name']}")
            print()
            
            return 0
            
        except Exception as e:
            print(f"\n Erreur fatale: {e}")
            import traceback
            traceback.print_exc()
            return 1


def main():
    """Point d'entre"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build Medical Search Application')
    parser.add_argument('--clean', action='store_true', help='Nettoyer avant le build')
    parser.add_argument('--no-collectstatic', action='store_true', help='Skip collectstatic')
    
    args = parser.parse_args()
    
    builder = Builder()
    sys.exit(builder.run(
        clean=args.clean,
        collect_static=not args.no_collectstatic
    ))


if __name__ == '__main__':
    main()
