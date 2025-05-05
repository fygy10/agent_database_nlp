import os
from dotenv import load_dotenv
from sql_connection import init_db
from set_env import setup_environment
from graph import workflow, app

# Load environment variables
load_dotenv()

# Setup OpenAI model
llm = setup_environment()

# Initialize database if needed
if not os.path.exists("example.db"):
    init_db()

# Function to run a query
def run_query(question, user_id=None):
    initial_state = {
        "question": question,
        "sql_query": "",
        "query_result": "",
        "query_rows": [],
        "current_user": "",
        "attempts": 0,
        "relevance": "",
        "sql_error": False
    }
    
    # Only set user_id if explicitly provided
    config = {"configurable": {}}
    if user_id:
        config["configurable"]["current_user_id"] = user_id
    
    result = app.invoke(initial_state, config=config)
    return result["query_result"]

# Test the agent
if __name__ == "__main__":
    print("Database Query Agent - Type 'exit' to quit")
    
    while True:
        question = input("\nEnter your database question: ")
        if question.lower() == 'exit':
            break
            
        response = run_query(question)
        print("\nResponse:", response)