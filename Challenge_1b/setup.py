#!/usr/bin/env python3
"""
Setup script for the Document Intelligence System.
Downloads models and sets up the environment.
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def install_requirements():
    """Install required Python packages."""
    logger.info("Installing required packages...")
    
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Requirements installed successfully")
            return True
        else:
            logger.error(f"❌ Failed to install requirements: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error installing requirements: {e}")
        return False

def setup_models(models_dir="./models", use_large_models=False):
    """Setup and download all required models."""
    logger.info("Setting up models...")
    
    try:
        from model_manager import ModelManager
        
        manager = ModelManager(models_dir)
        manager.setup_all_models(use_large_models=use_large_models)
        
        logger.info("✅ Models setup completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error setting up models: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_setup():
    """Verify that the setup is working correctly."""
    logger.info("Verifying setup...")
    
    try:
        # Test imports
        from model_manager import ModelManager
        from document_processor import DocumentProcessor
        from relevance_ranker import RelevanceRanker
        from subsection_analyzer import SubsectionAnalyzer
        
        logger.info("✅ All modules imported successfully")
        
        # Test model loading
        manager = ModelManager()
        info = manager.get_system_info()
        logger.info(f"System info: {info}")
        
        # Test basic functionality
        processor = DocumentProcessor()
        ranker = RelevanceRanker(manager)
        analyzer = SubsectionAnalyzer(manager)
        
        logger.info("✅ All components initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Setup verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_system_requirements():
    """Check system requirements and dependencies."""
    logger.info("Checking system requirements...")
    
    requirements = {
        "Python": sys.version_info >= (3, 7),
        "64-bit": sys.maxsize > 2**32
    }
    
    all_good = True
    
    for requirement, satisfied in requirements.items():
        if satisfied:
            logger.info(f"✅ {requirement}: OK")
        else:
            logger.error(f"❌ {requirement}: FAILED")
            all_good = False
    
    # Check available disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage(os.getcwd())
        free_gb = free // (1024**3)
        
        if free_gb >= 2:
            logger.info(f"✅ Disk space: {free_gb}GB available")
        else:
            logger.warning(f"⚠️ Disk space: Only {free_gb}GB available (recommended: 2GB+)")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not check disk space: {e}")
    
    return all_good

def create_example_usage():
    """Create an example usage script."""
    example_script = '''#!/usr/bin/env python3
"""
Example usage of the Document Intelligence System.
"""
import os

# Example command to run the system
# Replace paths and parameters with your actual values

# For Collection 1 (South of France travel guides)
os.system("""
python run.py \\
    --input-dir "./Collection 1/PDFs" \\
    --persona "Travel Planner" \\
    --job "Plan a trip of 4 days for a group of 10 college friends" \\
    --output-file "./Collection 1/challenge1b_output.json" \\
    --top-sections 5 \\
    --top-subsections 5 \\
    --verbose
""")

# For Collection 2 (Adobe Acrobat guides)  
os.system("""
python run.py \\
    --input-dir "./Collection 2/PDFs" \\
    --persona "Software Trainer" \\
    --job "Create a training curriculum for new Adobe Acrobat users" \\
    --output-file "./Collection 2/challenge1b_output.json" \\
    --top-sections 5 \\
    --top-subsections 5 \\
    --use-large-models \\
    --verbose
""")

print("Example runs completed!")
'''

    with open("example_usage.py", "w") as f:
        f.write(example_script)
    
    logger.info("✅ Created example_usage.py")

def main():
    parser = argparse.ArgumentParser(description="Setup Document Intelligence System")
    parser.add_argument("--models-dir", type=str, default="./models",
                        help="Directory to store models")
    parser.add_argument("--large-models", action="store_true",
                        help="Download larger, more accurate models")
    parser.add_argument("--skip-requirements", action="store_true",
                        help="Skip installing requirements")
    parser.add_argument("--skip-models", action="store_true",
                        help="Skip downloading models")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only verify existing setup")
    
    args = parser.parse_args()
    
    logger.info("🚀 Starting Document Intelligence System setup...")
    
    success = True
    
    # Check system requirements
    if not check_system_requirements():
        logger.error("❌ System requirements not met")
        success = False
    
    if args.verify_only:
        if verify_setup():
            logger.info("✅ Setup verification successful!")
        else:
            logger.error("❌ Setup verification failed!")
            success = False
    else:
        # Install requirements
        if not args.skip_requirements:
            if not install_requirements():
                success = False
        
        # Setup models  
        if not args.skip_models and success:
            if not setup_models(args.models_dir, args.large_models):
                success = False
        
        # Verify setup
        if success:
            if not verify_setup():
                success = False
        
        # Create examples
        if success:
            create_example_usage()
    
    if success:
        logger.info("🎉 Setup completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Check example_usage.py for usage examples")
        logger.info("2. Run 'python enhanced_test.py' to test the system")
        logger.info("3. Run 'python run.py --help' for full command options")
        
        if args.large_models:
            logger.info("\nNote: Large models are enabled for better accuracy")
        
    else:
        logger.error("💥 Setup failed! Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
