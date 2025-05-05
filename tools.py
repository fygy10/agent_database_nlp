#LLM call and checks if it is able to process the request
#create SQL query else end the session with LLM
#execute SQL query or retry if an error
#generate human natural language response from the query

# Add at the top
from states import AgentState
from langchain_core.runnables.config import RunnableConfig
from sql_connection import SessionLocal, User
from sqlalchemy import text
from sql_connection import engine
from sqlalchemy import inspect
from states import CheckRelevance, ConvertToSQL, RewrittenQuestion
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from profile import get_current_user  # Import from profile

def get_database_schema(engine):
    inspector = inspect(engine)
    schema = ""
    for table_name in inspector.get_table_names():
        schema += f"Table: {table_name}\n"
        for column in inspector.get_columns(table_name):
            col_name = column["name"]
            col_type = str(column["type"])
            if column.get("primary_key"):
                col_type += ", Primary Key"
            if column.get("foreign_keys"):
                fk = list(column["foreign_keys"])[0]
                col_type += f", Foreign Key to {fk.column.table.name}.{fk.column.name}"
            schema += f"- {col_name}: {col_type}\n"
        schema += "\n"
    print("Retrieved database schema.")
    return schema

def check_relevance(state: AgentState, config: RunnableConfig):
    question = state["question"]
    schema = get_database_schema(engine)
    print(f"Checking relevance of the question: {question}")
    system = """You are an assistant that determines whether a given question is related to the following database schema.

Schema:
{schema}

Respond with only "relevant" or "not_relevant".
Consider questions about the database structure, users, food items, orders, or general database content as "relevant".
""".format(schema=schema)
    human = f"Question: {question}"
    check_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", human),
        ]
    )
    llm = ChatOpenAI(temperature=0)
    structured_llm = llm.with_structured_output(CheckRelevance, method='function_calling')
    relevance_checker = check_prompt | structured_llm
    relevance = relevance_checker.invoke({})
    state["relevance"] = relevance.relevance
    print(f"Relevance determined: {state['relevance']}")
    return state

def convert_nl_to_sql(state: AgentState, config: RunnableConfig):
    question = state["question"]
    current_user = state["current_user"]
    schema = get_database_schema(engine)
    print(f"Converting question to SQL for user '{current_user}': {question}")
    
    # Different system prompt based on whether we have a current user
    if current_user and current_user != "User not found" and current_user != "Error retrieving user":
        system = """You are an assistant that converts natural language questions into SQL queries based on the following schema:

{schema}

The current user is '{current_user}'. Unless the question is explicitly about all users or the entire database, ensure that all query-related data is scoped to this user.

IMPORTANT RULES:
1. For user-specific queries, ensure data is scoped to this user using WHERE user_id = (SELECT id FROM users WHERE name = '{current_user}')
2. For database-wide queries about all users/data, do NOT restrict to the current user
3. For INSERT operations that specify both a user and related data (like an order), create multiple SQL statements as needed
4. Alias columns appropriately to match expected keys (e.g., 'food.name' as 'food_name')
5. For multiple SQL statements, separate them with a semicolon

Provide only the SQL query without any explanations.
""".format(schema=schema, current_user=current_user)
    else:
        system = """You are an assistant that converts natural language questions into SQL queries based on the following schema:

{schema}

This is a database-wide query with no specific user context.

IMPORTANT RULES:
1. Process queries about the entire database appropriately
2. For INSERT operations, create multiple SQL statements as needed
3. Alias columns appropriately to match expected keys (e.g., 'food.name' as 'food_name')
4. For multiple SQL statements, separate them with a semicolon

Provide only the SQL query without any explanations.
""".format(schema=schema)
    
    convert_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", "Question: {question}"),
        ]
    )
    llm = ChatOpenAI(temperature=0)
    structured_llm = llm.with_structured_output(ConvertToSQL)
    sql_generator = convert_prompt | structured_llm
    result = sql_generator.invoke({"question": question})
    state["sql_query"] = result.sql_query
    print(f"Generated SQL query: {state['sql_query']}")
    return state

def execute_sql(state: AgentState):
    sql_query = state["sql_query"].strip()
    session = SessionLocal()
    print(f"Executing SQL query: {sql_query}")
    
    try:
        # Handle multiple SQL statements separated by semicolons
        statements = [stmt.strip() for stmt in sql_query.split(';') if stmt.strip()]
        results = []
        
        for stmt in statements:
            if not stmt:
                continue
                
            result = session.execute(text(stmt))
            
            if stmt.lower().startswith("select"):
                rows = result.fetchall()
                columns = result.keys()
                
                if rows:
                    query_result = {
                        "columns": columns,
                        "rows": [dict(zip(columns, row)) for row in rows]
                    }
                    results.append(query_result)
                    
                    # Store the last SELECT result for the response formatting
                    state["query_rows"] = [dict(zip(columns, row)) for row in rows]
                else:
                    results.append({"message": "No results found for this query."})
                    if len(statements) == 1:  # Only set if this is the only statement
                        state["query_rows"] = []
            else:
                # For non-SELECT statements, commit after each statement
                session.commit()
                results.append({"message": f"Successfully executed: {stmt}"})
        
        # Format overall result
        if len(results) == 1 and "columns" in results[0]:
            # Single SELECT statement with results
            columns = results[0]["columns"]
            rows = results[0]["rows"]
            header = ", ".join(columns)
            data = "; ".join([f"{row.get('food_name', row.get('name', list(row.values())[0]))}" 
                             for row in rows])
            state["query_result"] = f"{header}\n{data}"
        else:
            # Multiple statements or non-SELECT
            state["query_result"] = "All operations completed successfully."
            
        state["sql_error"] = False
        print("SQL query executed successfully.")
        
    except Exception as e:
        state["query_result"] = f"Error executing SQL query: {str(e)}"
        state["sql_error"] = True
        print(f"Error executing SQL query: {str(e)}")
    finally:
        session.close()
    return state

def generate_human_readable_answer(state: AgentState):
    sql = state["sql_query"]
    result = state["query_result"]
    current_user = state["current_user"]
    query_rows = state.get("query_rows", [])
    sql_error = state.get("sql_error", False)
    question = state["question"]
    print("Generating a human-readable answer.")
    
    # Special handling for database-wide queries
    if sql.lower().startswith("select") and "from users" in sql.lower() and not "where" in sql.lower():
        # This is a query about all users
        system = """You are an assistant that converts SQL query results into clear, natural language responses.
        Respond appropriately to queries about the database as a whole.
        """
        
        if query_rows:
            # Format the names of users
            names = [row.get('name', '') for row in query_rows if row.get('name')]
            names_str = ", ".join(names)
            
            generate_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system),
                    (
                        "human",
                        f"""SQL Query:
{sql}

Result:
{names_str}

Original Question: {question}

Formulate a clear answer that lists all users in the database."""
                    ),
                ]
            )
        else:
            generate_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system),
                    (
                        "human",
                        f"""SQL Query:
{sql}

Result:
No results found.

Original Question: {question}

Formulate a clear answer stating that there are no users in the database."""
                    ),
                ]
            )
    elif sql_error:
        # Error handling
        system = """You are an assistant that converts SQL query results into clear, natural language responses.
        """
        generate_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                (
                    "human",
                    f"""SQL Query:
{sql}

Result:
{result}

Formulate a clear error message informing the user about the issue."""
                ),
            ]
        )
    elif sql.lower().startswith("select"):
        if not query_rows:
            # Handle cases with no results
            system = """You are an assistant that converts SQL query results into clear, natural language responses.
            """
            generate_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system),
                    (
                        "human",
                        f"""SQL Query:
{sql}

Result:
No results found.

Original Question: {question}

Formulate a response indicating that no results were found for this query."""
                    ),
                ]
            )
        else:
            # Handle normal query results
            system = """You are an assistant that converts SQL query results into clear, natural language responses.
            """
            generate_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system),
                    (
                        "human",
                        f"""SQL Query:
{sql}

Results:
{query_rows}

Original Question: {question}

Formulate a clear and understandable answer to the original question based on these results."""
                    ),
                ]
            )
    else:
        # Handle non-select queries (INSERT, UPDATE, etc.)
        system = """You are an assistant that converts SQL query results into clear, natural language responses.
        """
        generate_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                (
                    "human",
                    f"""SQL Query:
{sql}

Result:
{result}

Original Question: {question}

Formulate a confirmation message stating that the requested action has been completed successfully."""
                ),
            ]
        )

    llm = ChatOpenAI(temperature=0)
    human_response = generate_prompt | llm | StrOutputParser()
    answer = human_response.invoke({})
    state["query_result"] = answer
    print("Generated human-readable answer.")
    return state

def regenerate_query(state: AgentState):
    question = state["question"]
    print("Regenerating the SQL query by rewriting the question.")
    system = """You are an assistant that reformulates an original question to enable more precise SQL queries. Ensure that all necessary details, such as table joins, are preserved to retrieve complete and accurate data.
    """
    rewrite_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            (
                "human",
                f"Original Question: {question}\nReformulate the question to enable more precise SQL queries, ensuring all necessary details are preserved.",
            ),
        ]
    )
    llm = ChatOpenAI(temperature=0)
    structured_llm = llm.with_structured_output(RewrittenQuestion)
    rewriter = rewrite_prompt | structured_llm
    rewritten = rewriter.invoke({})
    state["question"] = rewritten.question
    state["attempts"] += 1
    print(f"Rewritten question: {state['question']}")
    return state

def generate_funny_response(state: AgentState):
    print("Generating a funny response for an unrelated question.")
    system = """You are a charming and funny assistant who responds in a playful manner.
    """
    human_message = "I can not help with that, but doesn't asking questions make you hungry? You can always order something delicious."
    funny_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", human_message),
        ]
    )
    llm = ChatOpenAI(temperature=0.7)
    funny_response = funny_prompt | llm | StrOutputParser()
    message = funny_response.invoke({})
    state["query_result"] = message
    print("Generated funny response.")
    return state

def end_max_iterations(state: AgentState):
    state["query_result"] = "Please try again."
    print("Maximum attempts reached. Ending the workflow.")
    return state

def relevance_router(state: AgentState):
    if state["relevance"].lower() == "relevant":
        return "convert_to_sql"
    else:
        return "generate_funny_response"

def check_attempts_router(state: AgentState):
    if state["attempts"] < 3:
        return "convert_to_sql"
    else:
        return "end_max_iterations"

def execute_sql_router(state: AgentState):
    if not state.get("sql_error", False):
        return "generate_human_readable_answer"
    else:
        return "regenerate_query"