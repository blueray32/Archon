"""
Document Processing Utilities

This module provides utilities for extracting text from various document formats
including PDF, Word documents, and plain text files using Docling for superior extraction.
"""

import io

# Import document processing libraries with availability checks
try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from ..config.logfire_config import get_logger, logfire

logger = get_logger(__name__)

# Initialize Docling converter once for reuse (thread-safe)
_docling_converter = None

def get_docling_converter():
    """Get or create a Docling document converter instance."""
    global _docling_converter
    if _docling_converter is None and DOCLING_AVAILABLE:
        try:
            from docling.document_converter import PdfFormatOption
            import os

            # Disable OCR by default for performance - OCR is extremely slow
            # Set DOCLING_ENABLE_OCR=true in environment to enable OCR
            enable_ocr = os.getenv("DOCLING_ENABLE_OCR", "false").lower() == "true"

            # Configure PDF options with optional OCR and table extraction
            pdf_options = PdfFormatOption(pipeline_options=PdfPipelineOptions(
                do_ocr=enable_ocr,
                do_table_structure=True
            ))

            _docling_converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF, InputFormat.DOCX, InputFormat.HTML, InputFormat.PPTX],
                format_options={InputFormat.PDF: pdf_options}
            )
            logger.info(f"Docling converter initialized successfully (OCR: {enable_ocr})")
        except Exception as e:
            logger.error(f"Failed to initialize Docling converter: {e}")
            _docling_converter = None
    return _docling_converter


def extract_text_from_document(file_content: bytes, filename: str, content_type: str) -> str:
    """
    Extract text from various document formats using Docling with fallback to legacy extractors.

    Args:
        file_content: Raw file bytes
        filename: Name of the file
        content_type: MIME type of the file

    Returns:
        Extracted text content

    Raises:
        ValueError: If the file format is not supported
        Exception: If extraction fails
    """
    try:
        # Text files (markdown, txt, etc.) - handle directly without Docling
        if content_type.startswith("text/") or filename.lower().endswith((
            ".txt",
            ".md",
            ".markdown",
            ".rst",
        )):
            return file_content.decode("utf-8", errors="ignore")

        # Try Docling first for PDF and DOCX (superior extraction with OCR and table support)
        if DOCLING_AVAILABLE:
            is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")
            is_docx = content_type in [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
            ] or filename.lower().endswith((".docx", ".doc"))

            if is_pdf or is_docx:
                try:
                    return extract_text_with_docling(file_content, filename)
                except Exception as e:
                    logger.warning(f"Docling extraction failed for {filename}: {e}, falling back to legacy extractors")
                    # Fall through to legacy extractors

        # Fallback to legacy extractors
        if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            return extract_text_from_pdf(file_content)

        elif content_type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ] or filename.lower().endswith((".docx", ".doc")):
            return extract_text_from_docx(file_content)

        else:
            raise ValueError(f"Unsupported file format: {content_type} ({filename})")

    except Exception as e:
        logfire.error(
            "Document text extraction failed",
            filename=filename,
            content_type=content_type,
            error=str(e),
        )
        raise Exception(f"Failed to extract text from {filename}: {str(e)}")


def extract_text_with_docling(file_content: bytes, filename: str) -> str:
    """
    Extract text from documents using Docling with advanced features (table extraction, optional OCR).

    Args:
        file_content: Raw file bytes
        filename: Name of the file

    Returns:
        Extracted text content with preserved structure

    Raises:
        Exception: If Docling extraction fails
    """
    if not DOCLING_AVAILABLE:
        raise Exception("Docling not available")

    converter = get_docling_converter()
    if converter is None:
        raise Exception("Failed to initialize Docling converter")

    try:
        import tempfile
        import os

        # Docling requires file path, so write to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name

        try:
            logger.info(f"Starting Docling extraction for {filename} ({len(file_content)} bytes)")

            # Convert document with timeout handling
            import asyncio
            import concurrent.futures

            # Run conversion in thread pool to allow timeout
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(converter.convert, tmp_path)
                try:
                    # 60 second timeout for conversion
                    result = future.result(timeout=60)
                except concurrent.futures.TimeoutError:
                    raise Exception(f"Docling conversion timed out after 60s for {filename}")

            # Extract markdown representation (preserves structure, tables, headings)
            text_content = result.document.export_to_markdown()

            if not text_content or len(text_content.strip()) < 10:
                raise Exception("Docling extracted insufficient content")

            logger.info(f"Docling successfully extracted {len(text_content)} characters from {filename}")
            return text_content

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        raise Exception(f"Docling extraction failed: {str(e)}")


def extract_text_from_pdf(file_content: bytes) -> str:
    """
    Extract text from PDF using both PyPDF2 and pdfplumber for best results.

    Args:
        file_content: Raw PDF bytes

    Returns:
        Extracted text content
    """
    if not PDFPLUMBER_AVAILABLE and not PYPDF2_AVAILABLE:
        raise Exception(
            "No PDF processing libraries available. Please install pdfplumber and PyPDF2."
        )

    text_content = []

    # First try with pdfplumber (better for complex layouts)
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_content.append(f"--- Page {page_num + 1} ---\n{page_text}")
                    except Exception as e:
                        logfire.warning(f"pdfplumber failed on page {page_num + 1}: {e}")
                        continue

            # If pdfplumber got good results, use them
            if text_content and len("\n".join(text_content).strip()) > 100:
                return "\n\n".join(text_content)

        except Exception as e:
            logfire.warning(f"pdfplumber extraction failed: {e}, trying PyPDF2")

    # Fallback to PyPDF2
    if PYPDF2_AVAILABLE:
        try:
            text_content = []
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))

            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(f"--- Page {page_num + 1} ---\n{page_text}")
                except Exception as e:
                    logfire.warning(f"PyPDF2 failed on page {page_num + 1}: {e}")
                    continue

            if text_content:
                return "\n\n".join(text_content)
            else:
                raise Exception("No text could be extracted from PDF")

        except Exception as e:
            raise Exception(f"PyPDF2 failed to extract text: {str(e)}")

    # If we get here, no libraries worked
    raise Exception("Failed to extract text from PDF - no working PDF libraries available")


def extract_text_from_docx(file_content: bytes) -> str:
    """
    Extract text from Word documents (.docx).

    Args:
        file_content: Raw DOCX bytes

    Returns:
        Extracted text content
    """
    if not DOCX_AVAILABLE:
        raise Exception("python-docx library not available. Please install python-docx.")

    try:
        doc = DocxDocument(io.BytesIO(file_content))
        text_content = []

        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content.append(paragraph.text)

        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_text.append(cell.text.strip())
                if row_text:
                    text_content.append(" | ".join(row_text))

        if not text_content:
            raise Exception("No text content found in document")

        return "\n\n".join(text_content)

    except Exception as e:
        raise Exception(f"Failed to extract text from Word document: {str(e)}")
