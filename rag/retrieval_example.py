#!/usr/bin/env python3
"""
retrieval_example.py - Example script for retrieving data from the Nestle vector store.

This script demonstrates how to load the vector store and perform similarity searches.
"""

import os
import logging
from typing import List
from dotenv import load_dotenv
from pathlib import Path
from langchain.schema.document import Document
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_community.vectorstores.chroma import Chroma

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('retrieval_example')

# Load environment variables from .env file in project root
load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

def load_vectorstore(persist_directory: str) -> Chroma:
    """
    Load the existing vector store.
    
    Args:
        persist_directory: Directory where the vector store is saved
        
    Returns:
        Chroma vector store instance
    """
    logger.info(f"Loading vector store from {persist_directory}")
    
    # Initialize the same embedding model used during creation
    embeddings = VertexAIEmbeddings(
        model_name="text-embedding-004"  # Google's latest embedding model
    )
    
    # Load the existing vector store
    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )
    
    return vectorstore

def perform_similarity_search(vectorstore: Chroma, query: str, k: int = 5) -> List[Document]:
    """
    Perform a similarity search on the vector store.
    
    Args:
        vectorstore: The vector store instance
        query: Search query
        k: Number of results to return
        
    Returns:
        List of document results
    """
    logger.info(f"Performing similarity search for: '{query}'")
    documents = vectorstore.similarity_search(query, k=k)
    return documents

def display_results(documents: List[Document]):
    """
    Display the search results in a readable format.
    
    Args:
        documents: List of Document objects from the search
    """
    logger.info(f"Found {len(documents)} results")
    
    for i, doc in enumerate(documents):
        print(f"\n--- Result {i+1} ---")
        print(f"Source: {doc.metadata.get('source', 'Unknown')}")
        print(f"Type: {doc.metadata.get('type', 'Unknown')}")
        print(f"Content: {doc.page_content[:200]}...")
        print("-" * 50)

def main():
    """Main function to demonstrate vector store retrieval."""
    try:
        # Define vector store directory
        persist_dir = "nestle_vectordb"  # Simplified path relative to current directory
        
        # Example queries to try
        example_queries = [
            "What chocolate products does Nestle offer?",
            "Tell me about KitKat bars",
            "Nestle's approach to sustainability",
            "Ice cream products from Nestle"
        ]
        
        # Load the vector store
        vectorstore = load_vectorstore(persist_dir)
        
        # Try each example query
        for query in example_queries:
            print(f"\n\n===== QUERY: {query} =====")
            results = perform_similarity_search(vectorstore, query)
            display_results(results)
        
    except Exception as e:
        logger.error(f"Error in retrieval process: {e}")
        raise

if __name__ == "__main__":
    main() 