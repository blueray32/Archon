#!/usr/bin/env python3
"""
Docling Convert → Chunks → Index

Processes CSV/Markdown BIM summaries through Docling, chunks them,
and creates embeddings for RAG retrieval.

Requirements:
    pip install docling langchain langchain-openai langchain-community chromadb

Usage:
    export OPENAI_API_KEY="your_key"
    export VECTOR_DB_DIR="./vectordb"  # optional
    python -m src.scripts.bim.docling_index
"""

import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    from docling.document_converter import DocumentConverter
    from docling.pipeline.standard import DefaultPipeline
except ImportError:
    logger.error("Docling not installed. Install with: pip install docling")
    sys.exit(1)

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_openai import OpenAIEmbeddings
    from langchain_community.vectorstores import Chroma
except ImportError:
    logger.error("LangChain dependencies not installed.")
    logger.error("Install with: pip install langchain langchain-openai langchain-community chromadb")
    sys.exit(1)


def main():
    """Main execution function."""
    # Configuration
    csv_path = Path(os.environ.get("BIM_CSV", "./out/elements.csv"))
    md_path = Path(os.environ.get("BIM_MD", "./out/elements.md"))
    vector_db_dir = os.environ.get("VECTOR_DB_DIR", "./vectordb")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not openai_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    if not csv_path.exists() or not md_path.exists():
        logger.error(f"CSV or Markdown files not found: {csv_path}, {md_path}")
        logger.error("Run generate_summaries.py first")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Docling + RAG Indexing Pipeline")
    logger.info("=" * 60)

    # Step 1: Convert with Docling
    logger.info("Step 1: Converting documents with Docling...")
    try:
        conv = DocumentConverter(DefaultPipeline())

        logger.info(f"  Converting CSV: {csv_path}")
        res_csv = conv.convert(str(csv_path))

        logger.info(f"  Converting Markdown: {md_path}")
        res_md = conv.convert(str(md_path))

        logger.info("  Conversion complete")
    except Exception as e:
        logger.error(f"Docling conversion failed: {e}")
        sys.exit(1)

    # Step 2: Serialize to text
    logger.info("Step 2: Serializing documents to markdown...")
    text_csv = res_csv.document.export_to_markdown()
    text_md = res_md.document.export_to_markdown()
    logger.info(f"  CSV text length: {len(text_csv)} characters")
    logger.info(f"  MD text length: {len(text_md)} characters")

    # Step 3: Chunking
    logger.info("Step 3: Chunking documents...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=120,
        separators=["\n\n", "\n", "|", " ", ""],
    )

    # Combine and chunk
    combined_text = text_csv + "\n\n" + text_md
    chunks = splitter.create_documents([combined_text], metadatas=[{"source": "aps_exchange"}])

    logger.info(f"  Created {len(chunks)} chunks")

    # Step 4: Embeddings + Vector Store
    logger.info("Step 4: Creating embeddings and vector store...")
    try:
        emb = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=openai_key)

        # Create persistent vector store
        vs = Chroma.from_documents(
            chunks,
            emb,
            collection_name="bim",
            persist_directory=vector_db_dir,
        )

        logger.info(f"  Vector store created at: {vector_db_dir}")
        logger.info(f"  Collection: bim")
        logger.info(f"  Total vectors: {len(chunks)}")
    except Exception as e:
        logger.error(f"Vector store creation failed: {e}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Indexing complete!")
    logger.info(f"  Documents processed: 2 (CSV + Markdown)")
    logger.info(f"  Chunks created: {len(chunks)}")
    logger.info(f"  Vector DB: {vector_db_dir}")
    logger.info("=" * 60)

    # Step 5: Test query (optional)
    if os.environ.get("BIM_TEST_QUERY"):
        test_query = os.environ["BIM_TEST_QUERY"]
        logger.info(f"\nTesting retrieval with query: '{test_query}'")

        retriever = vs.as_retriever(search_kwargs={"k": 3})
        results = retriever.invoke(test_query)

        logger.info(f"Retrieved {len(results)} chunks:")
        for i, doc in enumerate(results, 1):
            logger.info(f"  [{i}] {doc.page_content[:200]}...")


if __name__ == "__main__":
    main()
