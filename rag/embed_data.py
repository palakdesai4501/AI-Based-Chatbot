#!/usr/bin/env python3
"""
embed_data.py - Process and embed scraped Nestle website data for RAG applications.

This script loads the Nestle website scraped data, processes and chunks the text,
embeds it using Google Vertex AI, and stores it in a vector database for
retrieval in a chatbot pipeline.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file in project root
load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

# LangChain imports
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema.document import Document
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_google_vertexai import VertexAI
from langchain_community.vectorstores.chroma import Chroma

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('embed_data')

# Check for Google credentials
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    logger.warning("GOOGLE_APPLICATION_CREDENTIALS environment variable not set!")
    logger.warning("Follow setup instructions for Google Vertex AI authentication")

def load_nestle_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Load the Nestle scraped data from JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        List of page blocks containing the scraped data
    """
    logger.info(f"Loading data from {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Successfully loaded data: {len(data)} pages found")
        return data
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise

def extract_text_with_metadata(data: List[Dict[str, Any]]) -> List[Document]:
    """
    Extract text content from page blocks and maintain source metadata.
    
    Args:
        data: List of page blocks containing the scraped data
        
    Returns:
        List of LangChain Document objects with text and metadata
    """
    logger.info("Extracting text and metadata from scraped data")
    documents = []
    
    for page in data:
        url = page.get("url", "unknown")
        
        # Process headings
        for heading in page.get("headings", []):
            doc = Document(
                page_content=f"{heading['type']}: {heading['text']}",
                metadata={"source": url, "type": "heading"}
            )
            documents.append(doc)
        
        # Process paragraphs
        for paragraph in page.get("paragraphs", []):
            doc = Document(
                page_content=paragraph,
                metadata={"source": url, "type": "paragraph"}
            )
            documents.append(doc)
        
        # Process list items
        for item in page.get("list_items", []):
            doc = Document(
                page_content=item,
                metadata={"source": url, "type": "list_item"}
            )
            documents.append(doc)
        
        # Process tables
        for table in page.get("tables", []):
            table_text = ""
            if table.get("headers"):
                table_text += "Headers: " + " | ".join(table["headers"]) + "\n"
            for row in table.get("rows", []):
                table_text += "Row: " + " | ".join(row) + "\n"
            
            if table_text:
                doc = Document(
                    page_content=table_text,
                    metadata={"source": url, "type": "table"}
                )
                documents.append(doc)
    
    logger.info(f"Extracted {len(documents)} documents with source metadata")
    return documents

def chunk_documents(documents: List[Document], chunk_size: int = 300, chunk_overlap: int = 50) -> List[Document]:
    """
    Chunk documents into smaller pieces using RecursiveCharacterTextSplitter.
    
    Args:
        documents: List of Document objects
        chunk_size: Target size for each chunk in words (will be converted to chars)
        chunk_overlap: Overlap between chunks in words (will be converted to chars)
        
    Returns:
        List of chunked Document objects
    """
    logger.info(f"Chunking documents to ~{chunk_size} words with {chunk_overlap} words overlap")
    
    # Convert word count to approximate character count (average English word is ~5 chars)
    char_size = chunk_size * 5
    char_overlap = chunk_overlap * 5
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=char_size,
        chunk_overlap=char_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunked_docs = text_splitter.split_documents(documents)
    logger.info(f"Created {len(chunked_docs)} chunks from {len(documents)} original documents")
    return chunked_docs

def setup_embedding_model() -> VertexAIEmbeddings:
    """
    Set up the Google Vertex AI embeddings model.
    
    Returns:
        VertexAIEmbeddings model instance
    """
    logger.info("Setting up Google Vertex AI embeddings model")
    try:
        embeddings = VertexAIEmbeddings(
            model_name="text-embedding-004"  # Google's latest embedding model
        )
        return embeddings
    except Exception as e:
        logger.error(f"Error setting up embedding model: {e}")
        raise

def create_vectorstore(chunked_docs: List[Document], embeddings: VertexAIEmbeddings, persist_directory: str) -> Chroma:
    """
    Create and persist a vector store with embedded documents.
    
    Args:
        chunked_docs: List of Document chunks
        embeddings: Embedding model
        persist_directory: Directory to save the vector store
        
    Returns:
        Chroma vector store instance
    """
    logger.info(f"Creating vector store in {persist_directory}")
    try:
        # Ensure the persist directory exists
        os.makedirs(persist_directory, exist_ok=True)
        
        # Create and persist the vector store
        docs = [
            Document(page_content=chunk.page_content, metadata={"source": chunk.metadata["source"]})
            for chunk in chunked_docs
        ]
        vectorstore = Chroma.from_documents(
            docs,
            embedding=embeddings,
            persist_directory=persist_directory
        )
        
        # Explicitly persist
        vectorstore.persist()
        
        logger.info(f"Vector store created and persisted with {len(chunked_docs)} embedded chunks")
        return vectorstore
    except Exception as e:
        logger.error(f"Error creating vector store: {e}")
        raise

def main():
    """Main function to process and embed Nestle data."""
    try:
        # Define file paths
        input_file = str(Path(__file__).parent.parent / "scraper" / "nestle_full_data.json")
        persist_dir = "nestle_vectordb"  # Relative to current directory, not nested
        
        # Load data
        data = load_nestle_data(input_file)
        
        # Extract text with metadata
        documents = extract_text_with_metadata(data)
        
        # Chunk documents
        chunked_docs = chunk_documents(documents)
        
        # Setup embedding model
        embeddings = setup_embedding_model()
        
        # Create and persist vector store
        vectorstore = create_vectorstore(chunked_docs, embeddings, persist_dir)
        
        logger.info("Data processing and embedding completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        raise

if __name__ == "__main__":
    main() 