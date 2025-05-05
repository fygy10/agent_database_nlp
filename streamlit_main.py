import os
import streamlit as st
from dotenv import load_dotenv
from sql_connection import init_db
from set_env import setup_environment
from graph import workflow, app

# Page configuration
st.set_page_config(
    page_title="Database Query Agent",
    page_icon="🤖",
    layout="wide"
)

# Load environment variables
load_dotenv()

# Initialize database if needed
if not os.path.exists("example.db"):
    init_db()
    st.success("Database initialized successfully!")

# Setup OpenAI model
try:
    llm = setup_environment()
except ValueError as e:
    st.error(f"Error: {str(e)}")
    st.stop()

# Function to run a query (from main.py)
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
    
    with st.spinner("Processing your query..."):
        result = app.invoke(initial_state, config=config)
    return result

# Streamlit UI
st.title("🤖 Database Query Agent")
st.subheader("Ask questions about your database in natural language")

# Sidebar for user selection
with st.sidebar:
    st.header("User Settings")
    user_option = st.radio(
        "Query as:",
        ["Database-wide query (no specific user)", "Specific user"]
    )
    
    user_id = None
    if user_option == "Specific user":
        user_id = st.selectbox(
            "Select user:",
            options=[1, 2, 3],
            format_func=lambda x: f"User ID: {x}"
        )
    
    st.markdown("---")
    st.markdown("### Database Information")
    
    # Show database schema or structure
    if st.button("Show Database Schema"):
        from tools import get_database_schema
        from sql_connection import engine
        
        schema = get_database_schema(engine)
        st.code(schema)
    
    st.markdown("---")
    st.markdown("### Example Questions")
    st.markdown("""
    - What food items are available?
    - Show me all users
    - What has Alice ordered?
    - How much does Pizza Margherita cost?
    """)

# Main area for query input and results
query = st.text_area("Enter your database question:", height=100)

col1, col2 = st.columns([1, 5])
with col1:
    run_button = st.button("Ask Question", type="primary")

# Debug options in an expander
with st.expander("Debug Information", expanded=False):
    show_sql = st.checkbox("Show SQL Query")
    show_full_state = st.checkbox("Show Full State")

# Process the query when the button is clicked
if run_button and query:
    full_result = run_query(query, user_id)
    
    # Display the answer
    st.markdown("### Answer")
    st.markdown(full_result["query_result"])
    
    # Show SQL query if debug option is enabled
    if show_sql:
        st.markdown("### SQL Query")
        st.code(full_result["sql_query"], language="sql")
    
    # Show full state for debugging
    if show_full_state:
        st.markdown("### Full State")
        st.json(full_result)
elif run_button and not query:
    st.warning("Please enter a question first.")