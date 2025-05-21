from fastapi import FastAPI, Request
from pydantic import BaseModel
import logging
import os
from dotenv import load_dotenv
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_community.vectorstores.chroma import Chroma
from langchain_openai import ChatOpenAI
from neo4j import GraphDatabase
from typing import List, Dict, Any
import re
from fastapi.middleware.cors import CORSMiddleware

# Load .env variables 
load_dotenv()

# Neo4j connection details
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")  # Ensure bolt:// protocol
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Initialize Neo4j driver
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Check if API key is available and log appropriate message
api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key.startswith("your-") or len(api_key) < 20:
    print("WARNING: Valid OpenAI API key not found in .env file!")
    print("Please set OPENAI_API_KEY=sk-... in your .env file")
else:
    print("OpenAI API key found (starting with {})".format(api_key[:5]))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat_api")

# FastAPI app
app = FastAPI()

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or ["http://localhost:8080"] for more security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schema
class AskRequest(BaseModel):
    question: str

# Load vector store
PERSIST_DIR = "rag/nestle_vectordb"

def load_vectorstore():
    embeddings = VertexAIEmbeddings(model_name="text-embedding-004")
    return Chroma(persist_directory=PERSIST_DIR, embedding_function=embeddings)

vectorstore = load_vectorstore()

# Initialize OpenAI model
try:
    openai_model = ChatOpenAI(
        temperature=0,
        model_name="gpt-3.5-turbo",
        openai_api_key=api_key
    )
    print("OpenAI client initialized successfully")
except Exception as e:
    print(f"WARNING: Error initializing OpenAI client: {e}")
    openai_model = None

# Mock response function that doesn't require OpenAI
def get_mock_response(question, context):
    # Simple response that shows the retrieved context
    return f"Here's what I found about '{question}':\n\n{context}"

def query_graph_database(query: str) -> Dict[str, Any]:
    """Query Neo4j database for relevant nodes and relationships"""
    results = {
        'direct_matches': [],
        'connected_nodes': []
    }
    
    try:
        logger.info("Attempting to connect to Neo4j...")
        with neo4j_driver.session() as session:
            # Test connection first
            test_result = session.run("RETURN 1 as n")
            logger.info("Successfully connected to Neo4j")
            
            # Query 1: Direct matches
            logger.info(f"Searching for direct matches with query: {query}")
            direct_matches = session.run(
                """
                MATCH (n) 
                WHERE toLower(n.name) CONTAINS toLower($search_term) 
                RETURN n, labels(n) as type
                LIMIT 5
                """,
                search_term=query  # Changed parameter name to avoid conflict
            )
            
            for record in direct_matches:
                node = record['n']
                node_type = record['type'][0]  # Get first label
                results['direct_matches'].append({
                    'name': node['name'],
                    'type': node_type
                })
            logger.info(f"Found {len(results['direct_matches'])} direct matches")
            
            # Query 2: Connected nodes
            logger.info("Searching for connected nodes...")
            connected_nodes = session.run(
                """
                MATCH (n)-[r]-(m) 
                WHERE toLower(n.name) CONTAINS toLower($search_term) 
                RETURN n.name as source, type(r) as rel_type, m.name as target, labels(m) as target_type
                LIMIT 10
                """,
                search_term=query  # Changed parameter name to avoid conflict
            )
            
            for record in connected_nodes:
                results['connected_nodes'].append({
                    'source': record['source'],
                    'relationship': record['rel_type'],
                    'target': record['target'],
                    'target_type': record['target_type'][0]
                })
            logger.info(f"Found {len(results['connected_nodes'])} connected nodes")
                
    except Exception as e:
        logger.error(f"Error querying Neo4j: {e}")
        logger.error(f"Neo4j connection details - URI: {NEO4J_URI}, User: {NEO4J_USER}")
    
    return results

def format_graph_context(graph_results: Dict[str, Any]) -> str:
    """Format graph query results into readable, user-friendly text"""
    context_parts = []
    if graph_results['direct_matches']:
        context_parts.append("Direct matches found:")
        for match in graph_results['direct_matches']:
            context_parts.append(f"  - {match['type']}: {match['name']}")
    if graph_results['connected_nodes']:
        context_parts.append("\nRelated information:")
        for rel in graph_results['connected_nodes']:
            rel_type = rel['relationship'].replace('_', ' ').capitalize()
            context_parts.append(
                f"  - {rel['source']} {rel_type} {rel['target']} ({rel['target_type']})"
            )
    return "\n".join(context_parts) if context_parts else ""

def extract_entity_from_question(question: str) -> str:
    """
    Extracts the most likely entity (recipe, ingredient, category) from the question.
    Uses quotes, 'in', or 'of', or falls back to capitalized phrases.
    """
    # Try to extract quoted text
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', question)
    if quoted:
        # Return the first quoted group that is not empty
        for q in quoted[0]:
            if q:
                return q.strip()
    # Try to extract after 'in' or 'of'
    match = re.search(r'(?:in|of) ([A-Z][A-Za-z0-9 &\-]+)', question)
    if match:
        return match.group(1).strip()
    # Try to extract a long capitalized phrase
    match = re.search(r'([A-Z][A-Za-z0-9 &\-]{5,})', question)
    if match:
        return match.group(1).strip()
    # fallback: return the whole question
    return question.strip()

@app.post("/ask")
async def ask_question(req: AskRequest):
    try:
        logger.info(f"Received question: {req.question}")
        # Step 1: Get vector store context
        vector_docs = vectorstore.similarity_search(req.question, k=5)
        vector_context = "\n".join([doc.page_content for doc in vector_docs]) if vector_docs else ""
        logger.info(f"Vector store context found: {bool(vector_context)}")
        # Step 2: Extract entity from question
        entity = extract_entity_from_question(req.question)
        logger.info(f"Entity extracted for graph search: {entity}")
        # Step 3: Get graph database context
        graph_results = query_graph_database(entity)
        graph_context = format_graph_context(graph_results)
        logger.info(f"Graph context found: {bool(graph_context)}")
        # Step 4: Combine contexts
        combined_context = ""
        if vector_context:
            combined_context += "Text-based information:\n" + vector_context + "\n\n"
        if graph_context:
            combined_context += "Graph-based information:\n" + graph_context
        if not combined_context:
            logger.info("No relevant information found in either context.")
            return {"answer": "Sorry, I couldn't find any relevant information."}
        # If OpenAI client is available, try to use it
        if openai_model and api_key and len(api_key) > 20:
            try:
                # Step 5: Prepare prompt
                prompt = f"""
You are a helpful assistant that answers questions based on Nestlé's content.\nUse only the context provided below to answer.\nThe context comes from two sources:\n1. Text-based information from Nestlé's content\n2. Graph-based information showing relationships between recipes, ingredients, and categories\n\nContext:\n{combined_context}\n\nQuestion:\n{req.question}\n"""
                # Step 6: Get GPT answer
                response = openai_model.predict(prompt)
                logger.info("OpenAI model used for answer.")
                return {"answer": response.strip()}
            except Exception as openai_error:
                logger.warning(f"OpenAI error: {openai_error}. Using mock response.")
                mock_answer = get_mock_response(req.question, combined_context)
                return {"answer": mock_answer}
        else:
            logger.warning("OpenAI client not available. Using mock response.")
            mock_answer = get_mock_response(req.question, combined_context)
            return {"answer": mock_answer}
    except Exception as e:
        logger.error(f"Error in /ask: {e}")
        return {"error": str(e)}

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
