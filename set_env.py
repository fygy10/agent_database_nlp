import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


def setup_environment():
    
    #env file 
    load_dotenv()
    
    #check OAI key
    if not os.environ.get('OPENAI_API_KEY'):
        raise ValueError("OPENAI_API_KEY not found. Please add it to your .env file.")
    
    #LangChain & Tavily keys
    if os.environ.get('LANGCHAIN_API_KEY'):
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGCHAIN_PROJECT"] = "langchain-academy"
        print("LangChain tracing enabled.")
        os.environ['TAVILY_API_KEY']
    else:
        print("LangChain API key not found. Tracing will be disabled.")
    
    #llm defined
    return ChatOpenAI(model='gpt-3.5-turbo', temperature=0, max_tokens=1000)