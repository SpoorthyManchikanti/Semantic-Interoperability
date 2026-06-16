"""
Download FHIR data from OneDrive or use local path.

Usage:
    python scripts/download_data.py

This script will:
1. Check for FHIR_DATA_PATH in .env
2. If it's a URL, download and extract the data
3. If it's a local path, verify it exists
4. Create ./data folder structure
"""

import os
import sys
import zipfile
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATA_PATH = os.getenv("FHIR_DATA_PATH", "./data/import_test")
PROJECT_ROOT = Path(__file__).parent.parent


def is_url(path):
    """Check if path is a URL."""
    return path.startswith(("http://", "https://"))


def download_data(url):
    """Download data from OneDrive or direct URL."""
    print(f"\n📥 Downloading data from: {url}\n")
    
    try:
        import requests
    except ImportError:
        print("❌ ERROR: requests library not found.")
        print("   Install it with: pip install requests")
        sys.exit(1)
    
    # Create data directory
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    
    zip_path = data_dir / "fhir_data.zip"
    
    # Handle OneDrive/SharePoint URLs
    # Convert sharepoint link to direct download if needed
    if "sharepoint.com" in url:
        print("📌 SharePoint link detected. Converting to download URL...")
        # For SharePoint, we need to get a direct download link
        # This requires either:
        # 1. Public sharing enabled on the folder
        # 2. Or the user to provide a direct download link to a ZIP
        print("⚠️  NOTE: SharePoint links require additional steps.")
        print("\n   To proceed, please:")
        print("   1. Right-click the folder in OneDrive")
        print("   2. Select 'Share' → 'Copy link' → 'Anyone with link can edit'")
        print("   3. Open the shared link, download as ZIP")
        print("   4. Get the direct download link (append ?download=1)")
        print("   5. Update FHIR_DATA_PATH in .env with the direct download link")
        print("\n   Or: Place FHIR JSON files directly in: ./data/import_test")
        return False
    
    # Download file
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(zip_path, "wb") as f:
            f.write(response.content)
        
        print(f"✓ Downloaded: {zip_path}")
        
        # Extract ZIP
        extract_dir = data_dir / "import_test"
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        
        print(f"✓ Extracted to: {extract_dir}")
        
        # Cleanup ZIP
        zip_path.unlink()
        print(f"✓ Cleaned up ZIP file")
        
        return True
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False


def use_local_data(path):
    """Use local path for FHIR data."""
    path_obj = Path(path)
    
    # If it's relative, make it absolute from project root
    if not path_obj.is_absolute():
        path_obj = PROJECT_ROOT / path_obj
    
    if path_obj.exists():
        json_count = len(list(path_obj.glob("*.json")))
        print(f"✓ Found local data at: {path_obj}")
        print(f"  JSON files found: {json_count}")
        
        # Create symlink or copy to ./data/import_test for consistency
        target = PROJECT_ROOT / "data" / "import_test"
        target.parent.mkdir(exist_ok=True)
        
        if target.exists():
            shutil.rmtree(target)
        
        shutil.copytree(path_obj, target)
        print(f"✓ Copied to: {target}")
        return True
    else:
        print(f"❌ Local path not found: {path_obj}")
        return False


def main():
    """Main download logic."""
    print("\n" + "=" * 70)
    print("FHIR Data Setup")
    print("=" * 70)
    
    if not DATA_PATH:
        print("❌ ERROR: FHIR_DATA_PATH not set in .env")
        sys.exit(1)
    
    print(f"\nFHIR_DATA_PATH = {DATA_PATH}")
    
    if is_url(DATA_PATH):
        success = download_data(DATA_PATH)
    else:
        success = use_local_data(DATA_PATH)
    
    if success:
        print("\n" + "=" * 70)
        print("✓ Data setup complete!")
        print("=" * 70)
        print("\nNext step: Run ETL pipeline")
        print("  python scripts/run_etl.py")
        print("=" * 70 + "\n")
        return 0
    else:
        print("\n" + "=" * 70)
        print("❌ Data setup failed. Please check the error above.")
        print("=" * 70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
