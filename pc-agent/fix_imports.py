import logging
import sys
from pathlib import Path
from typing import Generator

# Configure structured logging instead of print
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def get_python_files(root_dir: Path) -> Generator[Path, None, None]:
    """
    Recursively find all Python files in the given directory.
    
    Args:
        root_dir: The root directory to search in.
        
    Yields:
        Path objects for each .py file found.
    """
    # rglob('*') recursively finds files matching the pattern
    for path in root_dir.rglob("*.py"):
        if path.is_file():
            yield path

def fix_file_imports(file_path: Path) -> bool:
    """
    Remove 'src.' prefix from imports in the specified file.
    
    Args:
        file_path: Path to the file to process.
        
    Returns:
        True if changes were made, False otherwise.
    """
    try:
        # Read content using pathlib (handles opening/closing automatically)
        original_content = file_path.read_text(encoding="utf-8")
        
        # Apply transformations
        new_content = original_content.replace("from src.", "from ")
        new_content = new_content.replace("import src.", "import ")
        
        # Write back only if changed to preserve file modification times if possible
        if original_content != new_content:
            file_path.write_text(new_content, encoding="utf-8")
            logger.info(f"Fixed imports in: {file_path.name}")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error processing {file_path.name}: {e}")
        return False

def main() -> None:
    """Execute the import fix process relative to the script location."""
    # Determine the script's directory to allow relative path resolution
    # This works regardless of where the project is located on the disk
    current_dir = Path(__file__).parent.resolve()
    
    # Target the 'src' directory specifically
    target_dir = current_dir / "src"
    
    if not target_dir.exists():
        logger.warning(f"'src' directory not found at {target_dir}. Scanning current directory instead.")
        target_dir = current_dir

    logger.info(f"Scanning for Python files in: {target_dir}")
    
    modified_count = 0
    for file_path in get_python_files(target_dir):
        # Skip this script itself if it happens to be in the scan path
        if file_path.name == Path(__file__).name:
            continue
            
        if fix_file_imports(file_path):
            modified_count += 1
            
    logger.info(f"Process complete. Modified {modified_count} files.")

if __name__ == "__main__":
    main()