#!/usr/bin/env python3
"""
Hybrid OCR Processor - Extract clean text + preserve visual elements
Best cost/quality balance for Claude API usage
"""

import os
import re
import io
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple

try:
    import fitz  # PyMuPDF
    import easyocr  # Pure Python OCR - no system dependencies!
    from PIL import Image, ImageEnhance
    import cv2
    import numpy as np
except ImportError as e:
    print(f"Missing package: {e}")
    print("Install with:")
    print("  pip install PyMuPDF easyocr pillow opencv-python")
    print("No system dependencies needed - all pure Python!")
    exit(1)

# ============================================
# SETTINGS - MODIFY THESE
# ============================================
PDF_PATH = '/Users/zachklopping/Downloads/AER_Patent_laws_product_life_cycle_lengths_and_multinational_activity-pages-deleted.pdf'
OUTPUT_DIR = '/Users/zachklopping/Desktop/papers_output'
OCR_DPI = 300  # Higher = better quality, slower
FIGURE_MIN_SIZE = 15000  # Min pixels to consider a figure (filter out small graphics)

class HybridOCRProcessor:
    def __init__(self, pdf_path: str, output_dir: str):
        self.pdf_path = Path(pdf_path)
        self.output_dir = Path(output_dir)
        self.ocr_reader = None
        self.setup_directories()
        
    def setup_directories(self):
        """Create output directory structure"""
        (self.output_dir / 'text').mkdir(parents=True, exist_ok=True)
        (self.output_dir / 'figures').mkdir(parents=True, exist_ok=True)
        (self.output_dir / 'tables').mkdir(parents=True, exist_ok=True)
        
    def init_ocr(self) -> bool:
        """Initialize EasyOCR reader"""
        try:
            print("🔄 Initializing EasyOCR (may download models on first run)...")
            self.ocr_reader = easyocr.Reader(['en'])  # English only for speed
            print("✓ EasyOCR ready!")
            return True
        except Exception as e:
            print(f"✗ EasyOCR initialization failed: {e}")
            return False
        
    def check_tesseract(self) -> bool:
        """This method is no longer needed with EasyOCR"""
        return True  # EasyOCR doesn't need system dependencies
    
    def enhance_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """Enhance image quality for better OCR"""
        # Convert to grayscale for OCR
        if image.mode != 'L':
            image = image.convert('L')
        
        # Convert to OpenCV format
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_GRAY2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Noise reduction
        denoised = cv2.medianBlur(gray, 3)
        
        # Enhance contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # Slight sharpening
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        return Image.fromarray(sharpened)
    
    def is_figure_region(self, page, rect) -> bool:
        """Determine if a region contains figures/charts vs text"""
        x0, y0, x1, y1 = rect
        
        # Get text in this region
        text_in_region = page.get_textbox(rect)
        
        # Get drawings/vectors in this region
        drawings = page.get_drawings()
        drawings_in_region = []
        for drawing in drawings:
            draw_rect = drawing.get('rect', fitz.Rect())
            if draw_rect.intersects(fitz.Rect(rect)):
                drawings_in_region.append(drawing)
        
        # Decision logic
        text_density = len(text_in_region.strip()) / ((x1-x0) * (y1-y0)) * 1000000  # chars per area
        drawing_count = len(drawings_in_region)
        
        # High drawing count OR low text density = likely figure
        if drawing_count > 10 or (drawing_count > 3 and text_density < 5):
            return True
        
        # Look for figure keywords in surrounding text
        figure_keywords = ['figure', 'fig.', 'chart', 'graph', 'plot', 'diagram']
        surrounding_text = text_in_region.lower()
        if any(keyword in surrounding_text for keyword in figure_keywords):
            return True
        
        return False
    
    def identify_content_regions(self, page) -> Dict[str, List]:
        """Identify text regions vs figure regions on a page"""
        page_rect = page.rect
        
        # Get all images on the page
        images = page.get_images()
        
        # Get text blocks
        text_blocks = page.get_text("dict")["blocks"]
        
        regions = {
            'text_regions': [],
            'figure_regions': [],
            'mixed_regions': []
        }
        
        # Process embedded images
        for img_index, img in enumerate(images):
            try:
                # Get image properties
                xref = img[0]
                pix = fitz.Pixmap(page.get_contents(), xref)
                
                if pix.width * pix.height > FIGURE_MIN_SIZE:
                    # Find the image position on page
                    image_rects = page.get_image_rects(xref)
                    for rect in image_rects:
                        regions['figure_regions'].append({
                            'rect': rect,
                            'type': 'embedded_image',
                            'index': img_index
                        })
                
                pix = None
            except:
                continue
        
        # Process text blocks and look for figure-heavy areas
        for block in text_blocks:
            if 'lines' in block:  # Text block
                block_rect = fitz.Rect(block['bbox'])
                
                if self.is_figure_region(page, block_rect):
                    regions['figure_regions'].append({
                        'rect': block_rect,
                        'type': 'vector_graphics'
                    })
                else:
                    regions['text_regions'].append({
                        'rect': block_rect,
                        'type': 'text_block'
                    })
        
        return regions
    
    def extract_text_ocr(self, page, regions: List) -> str:
        """Extract text using EasyOCR from text regions"""
        all_text = []
        
        if not regions:
            # No specific regions, OCR the whole page
            mat = fitz.Matrix(OCR_DPI/72, OCR_DPI/72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            # Enhance for OCR
            enhanced = self.enhance_image_for_ocr(image)
            
            # Convert to numpy array for EasyOCR
            img_array = np.array(enhanced)
            
            # OCR the page
            results = self.ocr_reader.readtext(img_array)
            
            # Extract text from results
            text_lines = [result[1] for result in results if result[2] > 0.5]  # Confidence > 0.5
            text = '\n'.join(text_lines)
            all_text.append(text)
        else:
            # OCR specific text regions
            for region in regions:
                try:
                    rect = region['rect']
                    
                    # Render just this region
                    mat = fitz.Matrix(OCR_DPI/72, OCR_DPI/72)
                    pix = page.get_pixmap(matrix=mat, clip=rect)
                    img_data = pix.tobytes("png")
                    image = Image.open(io.BytesIO(img_data))
                    
                    # Enhance for OCR
                    enhanced = self.enhance_image_for_ocr(image)
                    
                    # Convert to numpy array for EasyOCR
                    img_array = np.array(enhanced)
                    
                    # OCR this region
                    results = self.ocr_reader.readtext(img_array)
                    
                    # Extract text from results
                    text_lines = [result[1] for result in results if result[2] > 0.5]
                    text = '\n'.join(text_lines)
                    
                    if text.strip():
                        all_text.append(text.strip())
                        
                except Exception as e:
                    print(f"    Error OCR'ing region: {e}")
                    continue
        
        return '\n\n'.join(all_text)
    
    def extract_figures(self, page, page_num: int, regions: List) -> List[Dict]:
        """Extract figure regions as images"""
        figures = []
        
        for i, region in enumerate(regions):
            try:
                rect = region['rect']
                region_type = region.get('type', 'unknown')
                
                # Render figure region at high resolution
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for figures
                pix = page.get_pixmap(matrix=mat, clip=rect)
                
                # Skip very small rendered areas
                if pix.width < 100 or pix.height < 100:
                    continue
                
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))
                
                # Enhance image quality
                if region_type == 'vector_graphics':
                    # Enhance contrast for charts/graphs
                    enhancer = ImageEnhance.Contrast(image)
                    image = enhancer.enhance(1.3)
                
                filename = f"page_{page_num}_figure_{i+1}.png"
                
                figures.append({
                    'image': image,
                    'filename': filename,
                    'type': region_type,
                    'page': page_num,
                    'dimensions': f"{image.width}x{image.height}"
                })
                
            except Exception as e:
                print(f"    Error extracting figure {i}: {e}")
                continue
        
        return figures
    
    def process_pdf(self):
        """Main processing function"""
        print(f"Hybrid OCR Processing: {self.pdf_path.name}")
        print("="*60)
        
        if not self.init_ocr():
            return
        
        if not self.pdf_path.exists():
            print(f"ERROR: PDF not found: {self.pdf_path}")
            return
        
        try:
            doc = fitz.open(self.pdf_path)
            total_pages = len(doc)
            print(f"Processing {total_pages} pages...")
            
            all_text = []
            all_figures = []
            
            for page_num in range(total_pages):
                print(f"\nPage {page_num + 1}/{total_pages}")
                print("-" * 40)
                
                page = doc[page_num]
                
                # Identify content regions
                print("  🔍 Analyzing page layout...")
                regions = self.identify_content_regions(page)
                
                text_regions = regions['text_regions']
                figure_regions = regions['figure_regions']
                
                print(f"    Text regions: {len(text_regions)}")
                print(f"    Figure regions: {len(figure_regions)}")
                
                # Extract text with OCR
                if text_regions or not figure_regions:  # OCR if we have text regions or no figures
                    print("  📝 OCR text extraction...")
                    page_text = self.extract_text_ocr(page, text_regions)
                    
                    if page_text.strip():
                        all_text.append(f"=== PAGE {page_num + 1} ===\n{page_text}\n")
                        print(f"    ✓ Extracted {len(page_text)} characters")
                    else:
                        print("    ⚠ No text extracted")
                
                # Extract figures
                if figure_regions:
                    print("  🖼️  Extracting figures...")
                    page_figures = self.extract_figures(page, page_num + 1, figure_regions)
                    all_figures.extend(page_figures)
                    print(f"    ✓ Extracted {len(page_figures)} figures")
            
            doc.close()
            
            # Save results
            self.save_results(all_text, all_figures)
            
        except Exception as e:
            print(f"Error processing PDF: {e}")
    
    def save_results(self, all_text: List[str], all_figures: List[Dict]):
        """Save extracted text and figures"""
        print(f"\n" + "="*60)
        print("SAVING RESULTS")
        print("="*60)
        
        # Save text
        if all_text:
            text_file = self.output_dir / 'text' / f"{self.pdf_path.stem}.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(all_text))
            
            char_count = len('\n\n'.join(all_text))
            print(f"📄 Text saved: {text_file}")
            print(f"   {char_count:,} characters (~{char_count//750:,} words)")
        
        # Save figures
        figure_count = 0
        for figure in all_figures:
            filepath = self.output_dir / 'figures' / figure['filename']
            figure['image'].save(filepath, 'PNG', optimize=True)
            
            # Save metadata
            meta_file = filepath.with_suffix('.txt')
            with open(meta_file, 'w') as f:
                f.write(f"Page: {figure['page']}\n")
                f.write(f"Type: {figure['type']}\n")
                f.write(f"Dimensions: {figure['dimensions']}\n")
            
            figure_count += 1
            print(f"🖼️  Figure saved: {figure['filename']} ({figure['type']})")
        
        print(f"\n🎉 PROCESSING COMPLETE!")
        print(f"📁 Output directory: {self.output_dir}")
        print(f"📄 Text files: {1 if all_text else 0}")
        print(f"🖼️  Figures: {figure_count}")
        
        # Estimate API cost savings
        if all_text:
            # Rough token estimate (1 token ≈ 0.75 words ≈ 4 characters)
            estimated_tokens = len('\n\n'.join(all_text)) / 3
            estimated_cost = estimated_tokens / 1000000 * 3  # $3 per million tokens
            print(f"💰 Estimated API cost: ~${estimated_cost:.3f} (vs ~$0.27 for direct PDF)")


def main():
    print("Hybrid OCR Processor - Using EasyOCR (Pure Python)")
    print("Extracts clean text + preserves visual elements")
    print("="*60)
    
    # Check if PDF exists
    pdf_path = Path(PDF_PATH)
    if not pdf_path.exists():
        print(f"ERROR: PDF '{PDF_PATH}' not found!")
        print("Available PDFs:")
        for f in Path('.').glob('*.pdf'):
            print(f"  - {f.name}")
        print(f"\nUpdate PDF_PATH in the script to match your file")
        return
    
    # Create processor and run
    processor = HybridOCRProcessor(PDF_PATH, OUTPUT_DIR)
    processor.process_pdf()

if __name__ == "__main__":
    main()