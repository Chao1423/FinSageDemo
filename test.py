from tools import *

TOOL_PATH = 'FinSageFlask/static/tools/tools.json'

with open(TOOL_PATH, 'r') as file:
    data = json.load(file)
tools = data['tools']

A1 = AssistantManager("Charles", "asst_2hOqg1Kd2U1Mh38Rt5qLHEcD")

A1.create_assistant("FinSage12345","You are a financial advisor robot to give me investment advice",tools = tools )
print(A1.assistant_id)

A1.add_message_to_thread("user","technical anlysis for tesla")
A1.add_message_to_thread("user","use get stock price function to get highest price of Apple and Tesla in March 2024")
A1.run_assistant("give out the link '127.0.0.1/stocks' for visualisation results every time after runing the function")
A1.wait_for_completed()

