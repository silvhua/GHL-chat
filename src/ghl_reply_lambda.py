import json
import sys
from app.chat_functions import *
from app.ghl_requests import *
from langchain.agents import Tool
def lambda_handler(event, context):
    """
    This Lambda function is triggered by another function when the payload type is 'InboundMessage'.
    """

    response = refresh_token()
    if response['statusCode'] // 100 == 2:
        # Extract the payload from the event
        print(f"direct local invoke: {event.get('direct_local_invoke', False)}")
        if event.get('direct_local_invoke', None):
            payload = event['body']
        else:
            payload = event
        print(f'Payload: {payload}')
        contactId = payload.get('contactId')
        InboundMessage = payload.get('body')
        locationId = payload['location'].get('id', 'CoachMcloone')
        location = os.getenv(locationId, 'SamLab')
        print(f'location: {location}')

        system_message_dict = dict()
        conversation_dict = dict()
        reply_dict = dict()
        conversation_id = 1
        question_id = 1
        tools = [
            Tool(
                name=f"placeholder_function",
                func=placeholder_function,
                description=f"This function does not do anything.",
            )
        ]
        try:
            if payload.get("noReply", False) == False:

                system_message_dict[conversation_id] = create_system_message(
                    'CoachMcloone', 
                    prompts_filepath='app/private/prompts',
                    examples_filepath='app/private/data/chat_examples', doc_filepath='app/private/data/rag_docs'
                )
                conversation_dict[conversation_id] = create_chatbot(
                    contactId, system_message_dict[conversation_id], tools=tools,
                    # model='gpt-4-32k'
                    )

                reply_dict[conversation_id][question_id] = chat_with_chatbot(
                    InboundMessage, conversation_dict[conversation_id]
                )
                reply_text = reply_dict[conversation_id][question_id]["output"]
            else:
                reply_text = 'No AI reply generated for test event.'
                print(f'{reply_text}')
            ghl_api_response = ghl_request(
                contactId=contactId, 
                text=reply_text,
                endpoint='createTask', 
                payload=None, 
                location=location
            )
            print(f'GHL createTask response: {ghl_api_response}')
            if ghl_api_response['status_code'] // 100 == 2:
                message = f'Created task for contactId {contactId}: \n{ghl_api_response}\n'
            else:
                message = f'Failed to create task for contactId {contactId}: \n{ghl_api_response}\n'
                message += f'Status code: {ghl_api_response["status_code"]}. \nResponse reason: {ghl_api_response["response_reason"]}'

            # workflowId = 'ab3df14a-b4a2-495b-86ae-79ab6fad805b'
            # workflowName = 'chatbot:_1-day_follow_up'
            # ghl_workflow_response = ghl_request(
            #     contactId, 'workflow', path_param=workflowId
            # )

            # print(f'GHL workflow response: {ghl_workflow_response}')
            # if ghl_workflow_response['status_code'] // 100 == 2:
            #     message += f'\nAdded contactId {contactId} to "{workflowName}" workflow: \n{ghl_workflow_response}\n'
            # else:
            #     message += f'\nFailed to add contactId {contactId} to "{workflowName} workflow": \n{ghl_workflow_response}\n'
            #     message += f'Status code: {ghl_workflow_response["status_code"]}. \nResponse reason: {ghl_workflow_response["response_reason"]}'
            
            print(message)
            return {
                'statusCode': 200,
                'body': json.dumps(message)
            }
        except Exception as error:
            exc_type, exc_obj, tb = sys.exc_info()
            f = tb.tb_frame
            lineno = tb.tb_lineno
            filename = f.f_code.co_filename
            message = f"Error in line {lineno} of {filename}: {str(error)}"
            print(message)
            return {
                'statusCode': 500,
                'body': json.dumps(message)
            }

    else:
        print('Failed to refresh token')
        return response