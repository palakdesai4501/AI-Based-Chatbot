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
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA

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

# 1) Load LLM
llm = ChatOpenAI(
    temperature=0,
    model_name="gpt-3.5-turbo",
    openai_api_key=api_key,
)

# 2) Build your retriever
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# 3) Write a system+human prompt that asks for citations
template = """
System:
You are Smartie, the MadeWithNestlé assistant. Use ONLY the facts in the Context
and include citations like [1], [2] pointing to the source URL.

Context:
{context}

User:
{question}

Assistant:"""

prompt = PromptTemplate(
    input_variables=["context", "question"],
    template=template
)

# 4) Tie it together with RetrievalQA
qa = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True,
    chain_type_kwargs={"prompt": prompt},
)

@app.post("/ask")
async def ask_question(req: AskRequest):
    try:
        logger.info(f"Received question: {req.question}")

        # 1. Get vector context (top-k docs)
        vector_docs = vectorstore.similarity_search(req.question, k=5)
        docs_context = "\n\n".join([doc.page_content for doc in vector_docs])

        # 2. Get graph context (plain-English bullet points)
        entity = extract_entity_from_question(req.question)
        graph_results = query_graph_database(entity)
        graph_context = format_graph_context(graph_results)

        # 3. Combine both contexts
        full_context = f"Graph Knowledge:\n{graph_context}\n\n{docs_context}"

        # 4. Use RetrievalQA with custom context
        result = qa({"query": req.question, "context": full_context})
        answer = result["result"]
        docs = result["source_documents"]
        sources = [d.metadata.get("source", "") for d in docs]

        return {"answer": answer, "sources": sources}
    except Exception as e:
        logger.error(f"Error in /ask: {e}")
        return {"error": str(e)}

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
