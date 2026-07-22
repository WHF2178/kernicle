"""
ZIP archive creation for Kernicle sessions.
Sprint 4: Creates ZIP bundles of session directories.
"""

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ZipResult:
    """Result of ZIP creation operation."""
    success: bool
    zip_path: Optional[Path] = None
    zip_size_bytes: int = 0
    zip_created_utc: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for manifest inclusion."""
        if not self.success:
            return {
                "success": False,
                "error": self.error,
            }
        return {
            "success": True,
            "zip_filename": self.zip_path.name if self.zip_path else None,
            "zip_path": str(self.zip_path) if self.zip_path else None,
            "zip_size_bytes": self.zip_size_bytes,
            "zip_created_utc": self.zip_created_utc,
        }


def create_session_zip(session_dir: Path) -> ZipResult:
    """
    Create a ZIP archive of a session directory.
    
    The ZIP is created in the same parent directory as the session,
    with the same name plus .zip extension.
    
    Args:
        session_dir: Path to the session directory to archive
        
    Returns:
        ZipResult with success status and details
    """
    if not session_dir.exists():
        return ZipResult(
            success=False,
            error=f"Session directory does not exist: {session_dir}"
        )
    
    zip_path = session_dir.parent / f"{session_dir.name}.zip"
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Walk through session directory and add all files
            for file_path in session_dir.rglob('*'):
                if file_path.is_file():
                    # Create relative path within ZIP (include session folder name)
                    arcname = file_path.relative_to(session_dir.parent)
                    zf.write(file_path, arcname)
        
        # Get ZIP stats
        zip_size = zip_path.stat().st_size
        created_utc = datetime.now(timezone.utc).isoformat()
        
        return ZipResult(
            success=True,
            zip_path=zip_path,
            zip_size_bytes=zip_size,
            zip_created_utc=created_utc,
        )
        
    except Exception as e:
        # Clean up partial ZIP if it exists
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass
        
        return ZipResult(
            success=False,
            error=f"ZIP creation failed: {str(e)}"
        )


def verify_zip_contents(zip_path: Path, expected_files: list[str]) -> tuple[bool, list[str]]:
    """
    Verify that a ZIP contains expected files.
    
    Args:
        zip_path: Path to the ZIP file
        expected_files: List of expected file paths (relative to session root)
        
    Returns:
        Tuple of (all_found, list of missing files)
    """
    if not zip_path.exists():
        return False, ["ZIP file does not exist"]
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zip_contents = set(zf.namelist())
            
            # Extract session name from first entry
            if not zip_contents:
                return False, ["ZIP is empty"]
            
            # Get session folder name from ZIP
            first_entry = next(iter(zip_contents))
            session_name = first_entry.split('/')[0]
            
            missing = []
            for expected in expected_files:
                full_path = f"{session_name}/{expected}"
                # Handle directory entries (may or may not have trailing /)
                if full_path not in zip_contents and f"{full_path}/" not in zip_contents:
                    # Check if it's a prefix for any entry (directory)
                    if not any(entry.startswith(full_path) for entry in zip_contents):
                        missing.append(expected)
            
            return len(missing) == 0, missing
            
    except zipfile.BadZipFile:
        return False, ["Invalid ZIP file"]
    except Exception as e:
        return False, [f"ZIP verification error: {str(e)}"]


def extract_zip(zip_path: Path, output_dir: Path) -> tuple[bool, Optional[str]]:
    """
    Extract a ZIP archive to a directory.
    
    Args:
        zip_path: Path to the ZIP file
        output_dir: Directory to extract to
        
    Returns:
        Tuple of (success, error message if failed)
    """
    if not zip_path.exists():
        return False, f"ZIP file does not exist: {zip_path}"
    
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(output_dir)
        
        return True, None
        
    except zipfile.BadZipFile:
        return False, "Invalid ZIP file"
    except Exception as e:
        return False, f"Extraction failed: {str(e)}"
