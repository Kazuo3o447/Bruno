"""
Smart Backup Manager für Bruno Trading Bot

Hochkomprimierte PostgreSQL-Backups mit async Unterstützung.
"""

import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

from fastapi import BackgroundTasks


class BackupManager:
    """Verwaltet PostgreSQL Backups mit maximaler Kompression."""
    
    def __init__(self, backups_dir: str = "/app/backups"):
        self.backups_dir = Path(backups_dir)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        
        # DB Konfiguration aus Umgebungsvariablen
        self.db_host = os.getenv("DB_HOST", "postgres")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_user = os.getenv("DB_USER", "bruno")
        self.db_pass = os.getenv("DB_PASS", "bruno_secret")
        self.db_name = os.getenv("DB_NAME", "bruno_trading")
    
    def _generate_filename(self) -> str:
        """Generiert ein Backup-Filename mit Zeitstempel."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"manual_backup_{timestamp}.dump"
    
    def _run_backup_command(self, filename: str) -> None:
        """Führt pg_dump aus (synchron, für Background-Task)."""
        filepath = self.backups_dir / filename
        
        # PGPASSWORD Umgebungsvariable für automatische Authentifizierung
        env = os.environ.copy()
        env["PGPASSWORD"] = self.db_pass
        
        cmd = [
            "pg_dump",
            "-h", self.db_host,
            "-p", self.db_port,
            "-U", self.db_user,
            "-d", self.db_name,
            "-Fc",  # Custom-Format
            "-Z", "9",  # Maximale Kompression (0-9)
            "-f", str(filepath)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"Backup erfolgreich: {filepath} ({self._get_file_size_mb(filepath):.2f} MB)")
        except subprocess.CalledProcessError as e:
            error_msg = f"Backup fehlgeschlagen: {e.stderr}"
            print(error_msg)
            # Lösche unvollständige Datei falls vorhanden
            if filepath.exists():
                filepath.unlink()
            raise RuntimeError(error_msg)
    
    def _get_file_size_mb(self, filepath: Path) -> float:
        """Berechnet Dateigröße in MB."""
        return filepath.stat().st_size / (1024 * 1024)
    
    def create_backup(self, background_tasks: BackgroundTasks) -> str:
        """
        Startet ein Backup als Background-Task.
        
        Returns:
            Filename des zu erstellenden Backups
        """
        filename = self._generate_filename()
        
        # Füge Backup-Task zum Background-Tasks hinzu
        background_tasks.add_task(self._run_backup_command, filename)
        
        return filename
    
    def list_backups(self) -> List[Dict]:
        """
        Listet alle verfügbaren Backups auf.
        
        Returns:
            Liste von Dictionaries mit Backup-Informationen
        """
        backups = []
        
        if not self.backups_dir.exists():
            return backups
        
        for file_path in sorted(self.backups_dir.glob("*.dump"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = file_path.stat()
            created = datetime.fromtimestamp(stat.st_mtime)
            size_mb = stat.st_size / (1024 * 1024)
            
            backups.append({
                "filename": file_path.name,
                "size_mb": round(size_mb, 2),
                "created_at": created.isoformat(),
                "created_formatted": created.strftime("%d.%m.%Y %H:%M:%S")
            })
        
        return backups
    
    def delete_backup(self, filename: str) -> bool:
        """
        Löscht ein spezifisches Backup.
        
        Args:
            filename: Name der Backup-Datei
            
        Returns:
            True wenn gelöscht, False wenn nicht gefunden
            
        Raises:
            ValueError: Wenn Dateiname ungültig (Path Traversal Versuch)
        """
        # Sicherheitscheck: Nur Basename erlaubt, kein Path Traversal
        safe_filename = Path(filename).name
        if safe_filename != filename:
            raise ValueError("Ungültiger Dateiname - Path Traversal nicht erlaubt")
        
        filepath = self.backups_dir / safe_filename
        
        # Sicherstellen, dass die Datei im backups_dir liegt
        try:
            filepath.relative_to(self.backups_dir.resolve())
        except ValueError:
            raise ValueError("Datei liegt außerhalb des Backup-Verzeichnisses")
        
        if not filepath.exists():
            return False
        
        filepath.unlink()
        return True
    
    def get_backup_path(self, filename: str) -> Path:
        """
        Gibt den vollen Pfad zu einem Backup zurück (mit Validierung).
        
        Args:
            filename: Name der Backup-Datei
            
        Returns:
            Path Objekt zum Backup
            
        Raises:
            ValueError: Wenn Dateiname ungültig
            FileNotFoundError: Wenn Datei nicht existiert
        """
        # Sicherheitscheck
        safe_filename = Path(filename).name
        if safe_filename != filename:
            raise ValueError("Ungültiger Dateiname")
        
        filepath = self.backups_dir / safe_filename
        
        # Validierung
        try:
            resolved_path = filepath.resolve()
            resolved_backups_dir = self.backups_dir.resolve()
            resolved_path.relative_to(resolved_backups_dir)
        except (ValueError, RuntimeError):
            raise ValueError("Datei liegt außerhalb des Backup-Verzeichnisses")
        
        if not filepath.exists():
            raise FileNotFoundError(f"Backup nicht gefunden: {filename}")
        
        return filepath
    
    def cleanup_old_backups(self, max_age_days: int = 14) -> int:
        """
        Löscht manuelle Backups, die älter als max_age_days sind.
        
        Args:
            max_age_days: Maximales Alter in Tagen (default: 14)
            
        Returns:
            Anzahl gelöschter Backups
        """
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        deleted_count = 0
        
        for file_path in self.backups_dir.glob("manual_backup_*.dump"):
            if file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                deleted_count += 1
                print(f"Altes Backup gelöscht: {file_path.name}")
        
        return deleted_count


# Singleton-Instanz für einfachen Zugriff
backup_manager = BackupManager()
