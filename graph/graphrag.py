import json
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
import logging
from typing import List, Dict, Any
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Neo4jGraphBuilder:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Neo4j connection details
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        print("Loaded Neo4j password:", repr(self.password))
        
        # Initialize driver
        self.driver = None
        
    def connect(self):
        """Connect to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Verify connection
            with self.driver.session() as session:
                result = session.run("RETURN 1 as n")
                logger.info("Successfully connected to Neo4j")
                return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False

    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def clear_database(self):
        """Clear all nodes and relationships from the database"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Database cleared")

    def extract_entities(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Extract entities from the data"""
        entities = {
            'recipes': [],
            'ingredients': [],
            'categories': []
        }
        
        # Extract from headings
        if 'headings' in data:
            for heading in data['headings']:
                heading_text = heading.get('text', '') if isinstance(heading, dict) else str(heading)
                if any(keyword in heading_text.lower() for keyword in ['recipe', 'how to make', 'how to prepare']):
                    entities['recipes'].append(heading_text)
                elif any(keyword in heading_text.lower() for keyword in ['dessert', 'main dish', 'breakfast', 'lunch', 'dinner']):
                    entities['categories'].append(heading_text)

        # Extract from paragraphs
        if 'paragraphs' in data:
            for para in data['paragraphs']:
                para_text = para.get('text', '') if isinstance(para, dict) else str(para)
                # Look for ingredient lists
                if 'ingredients:' in para_text.lower():
                    # Split by common list markers
                    items = re.split(r'[•\-\*]', para_text)
                    for item in items:
                        item = item.strip()
                        if item and len(item) > 2:  # Basic validation
                            entities['ingredients'].append(item)

        # Extract from list_items (if present)
        if 'list_items' in data:
            for li in data['list_items']:
                li_text = li.get('text', '') if isinstance(li, dict) else str(li)
                if li_text and len(li_text) > 2:
                    entities['ingredients'].append(li_text)

        # Extract from tables (if present)
        if 'tables' in data:
            for table in data['tables']:
                # Extract ingredients from table rows
                for row in table.get('rows', []):
                    for cell in row:
                        cell_text = str(cell)
                        if cell_text and len(cell_text) > 2:
                            entities['ingredients'].append(cell_text)

        return entities

    def create_graph(self, data_file: str):
        """Create the graph from the data file"""
        try:
            # Load data
            with open(data_file, 'r') as f:
                data = json.load(f)

            # Extract entities
            entities = self.extract_entities(data)

            # Create nodes and relationships
            with self.driver.session() as session:
                # Create recipes
                for recipe in entities['recipes']:
                    session.run(
                        "MERGE (r:Recipe {name: $name})",
                        name=recipe
                    )

                # Create categories
                for category in entities['categories']:
                    session.run(
                        "MERGE (c:Category {name: $name})",
                        name=category
                    )

                # Create ingredients and relationships
                for ingredient in entities['ingredients']:
                    session.run(
                        "MERGE (i:Ingredient {name: $name})",
                        name=ingredient
                    )

                # Create relationships between recipes and ingredients
                for recipe in entities['recipes']:
                    for ingredient in entities['ingredients']:
                        session.run(
                            """
                            MATCH (r:Recipe {name: $recipe})
                            MATCH (i:Ingredient {name: $ingredient})
                            MERGE (r)-[:HAS_INGREDIENT]->(i)
                            """,
                            recipe=recipe,
                            ingredient=ingredient
                        )

                # Create relationships between recipes and categories
                for recipe in entities['recipes']:
                    for category in entities['categories']:
                        session.run(
                            """
                            MATCH (r:Recipe {name: $recipe})
                            MATCH (c:Category {name: $category})
                            MERGE (r)-[:BELONGS_TO_CATEGORY]->(c)
                            """,
                            recipe=recipe,
                            category=category
                        )

            logger.info("Graph creation completed successfully")

        except Exception as e:
            logger.error(f"Error creating graph: {e}")

def main():
    # Initialize graph builder
    graph_builder = Neo4jGraphBuilder()
    
    # Connect to Neo4j
    if not graph_builder.connect():
        logger.error("Failed to connect to Neo4j. Please check if Neo4j is running.")
        return

    try:
        # Clear existing data
        graph_builder.clear_database()
        
        # Create graph from data
        graph_builder.create_graph("/Users/palakdesai/Downloads/ChatBot/scraper/nestle_full_data.json")
        
    finally:
        # Close connection
        graph_builder.close()

if __name__ == "__main__":
    main() 