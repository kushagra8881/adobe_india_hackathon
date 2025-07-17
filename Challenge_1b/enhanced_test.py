#!/usr/bin/env python3
"""
Enhanced test script for the Document Intelligence System.
Tests various scenarios and edge cases.
"""
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_model_manager():
    """Test the model manager functionality."""
    logger.info("Testing ModelManager...")
    
    try:
        from model_manager import ModelManager
        
        # Test with temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelManager(temp_dir)
            
            # Test system info
            info = manager.get_system_info()
            assert isinstance(info, dict)
            assert "torch_available" in info
            logger.info("✅ ModelManager system info works")
            
            # Test NLTK data download
            manager.download_nltk_data()
            logger.info("✅ NLTK data download works")
            
            # Test sentence transformer loading (may take time)
            logger.info("Testing sentence transformer loading...")
            model = manager.load_sentence_transformer()
            assert model is not None
            logger.info("✅ Sentence transformer loading works")
            
        logger.info("✅ ModelManager tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ ModelManager test failed: {e}")
        return False

def test_document_processor():
    """Test document processor with various scenarios."""
    logger.info("Testing DocumentProcessor...")
    
    try:
        from document_processor import DocumentProcessor
        
        processor = DocumentProcessor(use_ocr=False)  # Disable OCR for testing
        
        # Test with existing PDFs
        test_dirs = ["./documents", "./Collection 1/PDFs", "./Collection 2/PDFs"]
        test_pdf_found = False
        
        for test_dir in test_dirs:
            if os.path.exists(test_dir):
                pdf_files = [f for f in os.listdir(test_dir) if f.lower().endswith('.pdf')]
                if pdf_files:
                    test_pdf = os.path.join(test_dir, pdf_files[0])
                    logger.info(f"Testing with PDF: {test_pdf}")
                    
                    # Test single document processing
                    result = processor.process_document(test_pdf)
                    if result:
                        assert "filename" in result
                        assert "sections" in result
                        assert isinstance(result["sections"], list)
                        logger.info(f"✅ Processed {result['filename']} with {len(result['sections'])} sections")
                        test_pdf_found = True
                        break
        
        if not test_pdf_found:
            logger.warning("⚠️ No PDF files found for testing DocumentProcessor")
            return True  # Don't fail if no PDFs available
            
        logger.info("✅ DocumentProcessor tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ DocumentProcessor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_relevance_ranker():
    """Test relevance ranker functionality."""
    logger.info("Testing RelevanceRanker...")
    
    try:
        from model_manager import ModelManager
        from relevance_ranker import RelevanceRanker
        
        # Create test documents
        test_documents = [
            {
                "filename": "test1.pdf",
                "sections": [
                    {
                        "title": "Travel Tips for Groups",
                        "page_number": 1,
                        "content": "When traveling with a group of friends, it's important to plan activities that everyone will enjoy. Budget-friendly options include free walking tours and group discounts at museums."
                    },
                    {
                        "title": "Solo Travel Guide", 
                        "page_number": 2,
                        "content": "Individual travelers often prefer flexibility in their itinerary. Solo dining and single accommodations are common considerations."
                    }
                ]
            }
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelManager(temp_dir)
            ranker = RelevanceRanker(manager)
            
            # Test ranking
            persona = "Travel Planner"
            job = "Plan a trip for a group of college friends"
            
            ranked_sections = ranker.rank_sections(test_documents, persona, job, top_n=2)
            
            assert isinstance(ranked_sections, list)
            assert len(ranked_sections) <= 2
            
            if ranked_sections:
                first_section = ranked_sections[0]
                assert "document" in first_section
                assert "importance_rank" in first_section
                assert first_section["importance_rank"] == 1
                logger.info(f"✅ Top ranked section: {first_section['section_title']}")
        
        logger.info("✅ RelevanceRanker tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ RelevanceRanker test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_subsection_analyzer():
    """Test subsection analyzer functionality."""
    logger.info("Testing SubsectionAnalyzer...")
    
    try:
        from model_manager import ModelManager
        from subsection_analyzer import SubsectionAnalyzer
        
        # Create test data
        test_documents = [
            {
                "filename": "test1.pdf",
                "sections": [
                    {
                        "title": "Budget Travel Tips",
                        "page_number": 1,
                        "content": "Traveling on a budget requires careful planning. Consider hostels for accommodation, cook your own meals when possible, and look for free activities like hiking or visiting public museums on free days. Group travel can help split costs for accommodation and transportation."
                    }
                ]
            }
        ]
        
        ranked_sections = [
            {
                "document": "test1.pdf",
                "section_title": "Budget Travel Tips",
                "importance_rank": 1,
                "page_number": 1
            }
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelManager(temp_dir)
            analyzer = SubsectionAnalyzer(manager)
            
            # Test analysis
            persona = "Travel Planner"
            job = "Plan a budget trip for college friends"
            
            analysis = analyzer.analyze_subsections(
                test_documents, ranked_sections, persona, job, top_n=1
            )
            
            assert isinstance(analysis, list)
            if analysis:
                first_analysis = analysis[0]
                assert "document" in first_analysis
                assert "refined_text" in first_analysis
                assert len(first_analysis["refined_text"]) > 10
                logger.info(f"✅ Refined text: {first_analysis['refined_text'][:100]}...")
        
        logger.info("✅ SubsectionAnalyzer tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ SubsectionAnalyzer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_end_to_end():
    """Test the entire system end-to-end."""
    logger.info("Testing end-to-end system...")
    
    try:
        # Find a test collection
        test_collections = ["./Collection 1", "./Collection 2", "./documents"]
        test_collection = None
        
        for collection in test_collections:
            pdf_dir = os.path.join(collection, "PDFs") if collection.startswith("./Collection") else collection
            if os.path.exists(pdf_dir):
                pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
                if pdf_files:
                    test_collection = pdf_dir
                    break
        
        if not test_collection:
            logger.warning("⚠️ No test collection found for end-to-end test")
            return True
        
        # Run the main script programmatically
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_output:
            temp_output_path = temp_output.name
        
        try:
            cmd = [
                sys.executable, "run.py",
                "--input-dir", test_collection,
                "--persona", "Travel Planner",
                "--job", "Plan a 4-day trip for college friends",
                "--output-file", temp_output_path,
                "--top-sections", "3",
                "--top-subsections", "3"
            ]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                # Check output file
                if os.path.exists(temp_output_path):
                    with open(temp_output_path, 'r') as f:
                        output = json.load(f)
                    
                    assert "metadata" in output
                    assert "extracted_sections" in output
                    assert "subsection_analysis" in output
                    
                    logger.info(f"✅ End-to-end test successful")
                    logger.info(f"   Processed: {len(output['metadata']['input_documents'])} documents")
                    logger.info(f"   Sections: {len(output['extracted_sections'])}")
                    logger.info(f"   Analyses: {len(output['subsection_analysis'])}")
                    
                else:
                    logger.error("❌ Output file not created")
                    return False
            else:
                logger.error(f"❌ Command failed with return code {result.returncode}")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                return False
                
        finally:
            # Clean up
            if os.path.exists(temp_output_path):
                os.unlink(temp_output_path)
        
        logger.info("✅ End-to-end tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    logger.info("Starting enhanced test suite...")
    
    tests = [
        ("Model Manager", test_model_manager),
        ("Document Processor", test_document_processor),
        ("Relevance Ranker", test_relevance_ranker),
        ("Subsection Analyzer", test_subsection_analyzer),
        ("End-to-End", test_end_to_end)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running {test_name} test...")
        logger.info(f"{'='*50}")
        
        try:
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} test PASSED")
            else:
                failed += 1
                logger.error(f"❌ {test_name} test FAILED")
        except Exception as e:
            failed += 1
            logger.error(f"❌ {test_name} test FAILED with exception: {e}")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    logger.info(f"{'='*50}")
    
    if failed == 0:
        logger.info("🎉 All tests passed!")
        return True
    else:
        logger.error(f"💥 {failed} test(s) failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
