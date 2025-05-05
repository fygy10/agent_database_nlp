#get the user id and information 
#verify credentials for LLM and database access
#define and update user state for what was done in the session and

from states import AgentState
from langchain_core.runnables.config import RunnableConfig
from sql_connection import SessionLocal, User


def get_current_user(state: AgentState, config: RunnableConfig):
    print("Retrieving the current user based on user ID.")
    user_id = config["configurable"].get("current_user_id", None)
    
    # If no user_id provided, leave the user blank for database-wide queries
    if not user_id:
        state["current_user"] = ""
        print("No user ID provided. This will be treated as a database-wide query.")
        return state

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == int(user_id)).first()
        if user:
            state["current_user"] = user.name
            print(f"Current user set to: {state['current_user']}")
        else:
            state["current_user"] = "User not found"
            print("User not found in the database.")
    except Exception as e:
        state["current_user"] = "Error retrieving user"
        print(f"Error retrieving user: {str(e)}")
    finally:
        session.close()
    return state