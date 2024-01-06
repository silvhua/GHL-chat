from openai import OpenAI
import os
from time import time

from langchain.chat_models import ChatOpenAI

# Create memory 
from langchain.memory.chat_message_histories import DynamoDBChatMessageHistory
from langchain.memory import ConversationBufferMemory

from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.schema.messages import SystemMessage

from langchain.prompts import MessagesPlaceholder

from langchain.agents import AgentExecutor

def load_txt(filename, filepath, encoding='utf-8'):
    """
    Load a text file as a string using the specified file path copied from Windows file explorer.
    Backslashes in the file path will be converted to forward slashes.

    Arguments:
    - filepath (raw string): Use the format r'<path>'.
    - filename (string).

    Returns: string object.
    """
    filename = f'{filepath}/'.replace('\\','/') + filename
    with open(filename, 'r', encoding=encoding) as file:
        text = file.read()
    return text

def create_system_message(
        business_name, prompts_filepath='../prompts',
        examples_filepath='../data/chat_examples', doc_filepath='../data/rag_docs'
        ):
    
    instructions = load_txt(f'{business_name}.md', prompts_filepath)
    examples = load_txt(f'{business_name}.txt', examples_filepath)
    document = load_txt(f'{business_name}_doc.md', doc_filepath)

    system_message = f"""# Stage 1

{instructions}

Return your response on a JSON format with the following keys:
- "response" (string): The response to the InboundMessage.
- "alert_human" (True or False): Whether or not to alert a human to review the response.

## Examples

Below are example conversations with leads. Each lead as a unique contact ID.
An InboundMessage is from the lead. An OutboundMessage is from you.

{examples}

## Relevant documentation

{document}

# Stage 2

Review your response from stage 1. 
Revise your response if needed to make sure you followed the instructions.
Make sure that if the question cannot be answered through the documentation, 
you return "[ALERT HUMAN]".

# Stage 3

Review your response from stage 2 to ensure your response is concise.
    """

    prompt = """
    Write the next OutboundMessage based on the following InboundMessage, 
    which is delimited by triple backticks: ```{InboundMessage}```
    """
    system_message = f'{system_message}{prompt}'
    return system_message

def create_chatbot(contactId, system_message, tools, model="gpt-3.5-turbo-1106", verbose=True):

    llm = ChatOpenAI(
        temperature = 0,
        openai_organization=os.environ['openai_organization'],
        openai_api_key=os.environ['openai_api_key'],
        model=model, 
        model_kwargs={"response_format": {"type": "json_object"}} # https://platform.openai.com/docs/guides/text-generation/json-mode  # https://api.python.langchain.com/en/latest/chat_models/langchain_community.chat_models.openai.ChatOpenAI.html?highlight=chatopenai#
        )
    message_history = DynamoDBChatMessageHistory(
        table_name="SessionTable", session_id=contactId,
        key={
            "SessionId": contactId,
            "type": 'ChatHistory',
            }
        )
    system_message = SystemMessage(
        content=(system_message),
        input_variables=['InboundMessage']
    )
    
    prompt = OpenAIFunctionsAgent.create_prompt(
        system_message=system_message,
        extra_prompt_messages=[
            MessagesPlaceholder(variable_name='chat_history')
            ]
    )

    agent = OpenAIFunctionsAgent(llm=llm, tools=tools, prompt=prompt)
    agent_executor = AgentExecutor(
        agent=agent, tools=tools, 
        verbose=verbose, return_intermediate_steps=True
        )
    agent_info = {
        'agent': agent,
        'agent_executor': agent_executor,
        'chat_history': message_history.messages
    }
    return agent_info

def chat_with_chatbot(user_input, agent_info):
    start_time = time()
    print(f'Chat history length: {len(agent_info["chat_history"])}')
    chat_history = agent_info['chat_history']
    result = agent_info['agent_executor']({
        "input": user_input,
        "chat_history": chat_history
        })
    print(f'Response time: {time() - start_time} seconds')
    
    return result

def placeholder_function(str):
    return None

def openai_models(env="openai_api_key", query='gpt'):
    """
    List the availabel OpenAI models.
    Parameters:
        - env (str): Name of environmental variable storing the OpenAI API key.
        - query (str): Search term for filtering models.
    """
    client = OpenAI(
        organization=os.environ['openai_organization']
    )
    # openai.api_key = os.getenv(env)
    response = client.models.list()
    filtered_models = [model for model in response.data if model.id.find(query) != -1]

    for item in filtered_models:
        print(item.id)
    return filtered_models