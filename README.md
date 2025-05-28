# Nestlé Recipe Chatbot

An intelligent chatbot that helps users find recipes and information from the Made with Nestlé website. The chatbot combines vector search and graph database capabilities to provide accurate and contextual responses.

## Features

- Recipe search and recommendations
- Ingredient-based recipe discovery
- Category-based recipe browsing
- Contextual responses using RAG (Retrieval Augmented Generation)
- Graph-based relationship queries
- Vector similarity search

## Technologies Used

- **Backend Framework**: FastAPI
- **Vector Database**: Chroma DB
- **Graph Database**: Neo4j
- **Embeddings**: Google Vertex AI
- **LLM**: OpenAI GPT-3.5 Turbo
- **Data Processing**: Python
- **API Testing**: Postman

## Prerequisites

- Python 3.9+
- Neo4j Desktop
- Google Cloud Account (for Vertex AI)
- OpenAI API Key
- Git
- Postman (for API testing)

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/palakdesai4501/AI-Based-Chatbot.git
   cd ChatBot
   ```

2. **Create and Activate Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**
   Create a `.env` file in the root directory with:
   ```
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_APPLICATION_CREDENTIALS=path_to_your_google_credentials.json
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_neo4j_password
   ```

5. **Set Up Neo4j**
   - Install Neo4j Desktop
   - Create a new database
   - Start the database
   - Update the credentials in `.env`

6. **Set Up Google Cloud**
   - Create a project in Google Cloud Console
   - Enable Vertex AI API
   - Create service account and download credentials
   - Set the path in GOOGLE_APPLICATION_CREDENTIALS

7. **Run the Application**
   ```bash
   uvicorn main:app --reload --port 8001
   ```

8. **Test the API**
   - Import the provided Postman collection
   - Test the chatbot endpoint: POST http://localhost:8001/ask
   - Example request body:
   ```json
   {
     "question": "What recipes use chocolate?"
   }
   ```

## Project Structure

```
ChatBot/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── .env                # Environment variables
├── .env-example        # Environment variables template
├── .gitignore         # Git ignore rules
├── scraper/            # Web scraping scripts
├── rag/               # RAG implementation
│   ├── embed_data.py  # Vector store creation
│   └── nestle_vectordb/ # Vector database
├── graph/             # Neo4j graph implementation
│   └── graphrag.py    # Graph database operations
└── frontend/          # Frontend implementation
    ├── index.html     # Main HTML file
    └── assets/        # Frontend assets
```

## API Endpoints

- `POST /ask`: Main endpoint for querying the chatbot
  ```json
  {
    "question": "What recipes use chocolate?"
  }
  ```

## Known Limitations

1. OpenAI API quota limitations
2. Requires active internet connection
3. Neo4j database must be running locally
4. Google Cloud credentials must be valid

## Additional Features

1. Vector-based semantic search
2. Graph-based relationship queries
3. Combined RAG and GraphRAG approach
4. Fallback responses when API quota is exceeded

## Testing

1. **Postman Collection**
   - Import the provided Postman collection
   - Test all endpoints
   - Example request:
   ```bash
   curl -X POST http://localhost:8001/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "What recipes use chocolate?"}'
   ```

## Deployment

The application is deployed on Azure and can be accessed at: [Your Azure Deployment URL]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

