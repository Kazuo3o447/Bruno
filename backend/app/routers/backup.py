"""
Backup API Router - Steuerung des Smart Backup Systems

Endpunkte für Backup-Verwaltung über das Frontend.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.utils.backup_manager import backup_manager

router = APIRouter()


@router.get("/backups")
async def list_backups():
    """
    Liste aller verfügbaren Backups abrufen.
    
    Returns:
        Liste von Backup-Metadaten (Filename, Größe, Erstellungsdatum)
    """
    try:
        backups = backup_manager.list_backups()
        return {
            "status": "success",
            "count": len(backups),
            "backups": backups
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Auflisten: {str(e)}")


@router.post("/backups/create")
async def create_backup(background_tasks: BackgroundTasks):
    """
    Neues Backup asynchron starten.
    
    Nutzt BackgroundTasks um Timeout zu verhindern.
    Das Backup läuft im Hintergrund während sofort eine Response zurückgegeben wird.
    
    Returns:
        Bestätigung mit Backup-Filename
    """
    try:
        filename = backup_manager.create_backup(background_tasks)
        return {
            "status": "Backup started",
            "filename": filename,
            "message": f"Backup '{filename}' wird im Hintergrund erstellt"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Starten: {str(e)}")


@router.delete("/backups/{filename}")
async def delete_backup(filename: str):
    """
    Ein spezifisches Backup löschen.
    
    Args:
        filename: Name der Backup-Datei
        
    Returns:
        Bestätigung der Löschung
    """
    try:
        success = backup_manager.delete_backup(filename)
        if not success:
            raise HTTPException(status_code=404, detail=f"Backup nicht gefunden: {filename}")
        
        return {
            "status": "success",
            "message": f"Backup '{filename}' gelöscht"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Löschen: {str(e)}")


@router.get("/backups/download/{filename}")
async def download_backup(filename: str):
    """
    Backup-Datei als Download streamen.
    
    Args:
        filename: Name der Backup-Datei
        
    Returns:
        FileResponse mit der Backup-Datei
    """
    try:
        filepath = backup_manager.get_backup_path(filename)
        
        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Download: {str(e)}")


@router.post("/backups/cleanup")
async def cleanup_old_backups(max_age_days: int = 14):
    """
    Alte Backups aufräumen (älter als X Tage).
    
    Args:
        max_age_days: Maximales Alter in Tagen (Default: 14)
        
    Returns:
        Anzahl gelöschter Backups
    """
    try:
        deleted = backup_manager.cleanup_old_backups(max_age_days)
        return {
            "status": "success",
            "deleted_count": deleted,
            "message": f"{deleted} alte Backup(s) gelöscht (> {max_age_days} Tage)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Aufräumen: {str(e)}")
