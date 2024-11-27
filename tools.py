import json
import pandas as pd
import time 
from datetime import datetime, timedelta
import requests
import os
import openai 
import pandas_ta as ta
from tradingview_ta import TA_Handler, Interval, Exchange
from dotenv import load_dotenv, find_dotenv
import yfinance as yf
import ssl
import openai
from hashlib import sha256
import flask_login
import plotly.express as px
from functools import reduce


today_date = datetime.now().date()
ssl._create_default_https_context = ssl._create_unverified_context
_ = load_dotenv(find_dotenv(),override=True)
news_api_key = os.environ.get('NEWS_API_KEY')

class User(flask_login.UserMixin):
    def __init__(self, username, email, password, nickname = 'Default User'):
        self.username = username
        self.email = email
        self.password = password
        self.nickname = nickname
        self.id = sha256(username.encode('utf-8')).hexdigest()

class StockTools:
    def __init__(self,tickers = None, start_date='2024-01-01', end_date=str(today_date), col = "Close"):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.col = col.capitalize() 
        
    def fetch_stock_data(self):
        data = {}
        for ticker in self.tickers:
            try:
                stock_data = yf.download(ticker, start=self.start_date, end=self.end_date)
                if not stock_data.empty:
                    data[ticker] = stock_data[self.col]
            except Exception as e:
                print(f"Error fetching data for {ticker}: {e}")
        return data

    def data_for_plotting(self):
        data = self.fetch_stock_data()
        if len(data) > 0:
            df_list = [data[ticker].reset_index().rename(columns={self.col: ticker}) for ticker in data]
            df = reduce(lambda left, right: pd.merge(left, right, on='Date'), df_list)
        else:
            df = pd.DataFrame(data)
        return df
    
    def technical_analysis(self,ticker):
        try:
            output = TA_Handler(
            symbol= ticker,
            screener="AMERICA",  
            exchange="NASDAQ",  
            interval=Interval.INTERVAL_1_DAY 
        )
            result = {
            "time": str(output.get_analysis().time),
            "recommendation": (output.get_analysis().summary)['RECOMMENDATION'],
            "buy_num": (output.get_analysis().summary)['BUY'],
            "sell_num": (output.get_analysis().summary)['SELL'],
            "neutral_num": (output.get_analysis().summary)['NEUTRAL'],
            "oscillators": (output.get_analysis().oscillators)['COMPUTE'],
            "moving averages": (output.get_analysis().moving_averages)['COMPUTE']
        }
            return result
        
        except Exception as e:
            return f"Something wrong when analysing stock {ticker}: {e}"
        
    def get_news(self,topic):
        url = f'https://newsapi.org/v2/everything?q={topic}&from=2024-03-24&sortBy=popularity&apiKey={news_api_key}&pageSize=5'
        try:
            response = requests.get(url)
            if response.status_code == 200:
                news = json.dumps(response.json(),indent = 4)
                news_json = json.loads(news)
                data = news_json
                #status = data["status"]
                #total_results = data["totalResults"]
                articles = data["articles"]
                final_news = []
                for article in articles:
                    source_name = article["source"]["name"]
                    author = article["author"]
                    title = article["title"]
                    description = article["description"]
                    url = article["url"]
                    content = article["content"]
                    title_description = f"""
                        Title: {title},
                        Author:{author},
                        Source: {source_name},
                        Description:{description},
                        URL:{url}
                    """
                    final_news.append(title_description)
                return final_news
            else:
                return []
        except requests.exceptions.RequestException as e:
            print("Error Occured during API Request", e)

class Recordpattern:
    def __init__(self, owner):
        base_dir = os.path.join(os.getcwd(), "static", "users")
        folder_path = os.path.join(base_dir, owner) 
        os.makedirs(folder_path, exist_ok=True)
        self.filename = os.path.join(folder_path, f"{owner}'s_assistants.json")
        self.chathistory = os.path.join(folder_path, f"{owner}'s_history.json")
        self.output_file = os.path.join(folder_path, f"{owner}'s_asst_outputs.json")
        self.assistants = self.load_assistants()
        self.history = self.load_history()
    def add_assistant(self, assistant_id, thread_id, name, description, tools):
        self.assistants[assistant_id] = {"thread_id":thread_id,"name":name,"description":description,"tools":tools}
        self.save_assistants()
    def add_history(self, assistant_id, msg):
        self.history[assistant_id] = msg
        self.save_history()
    def retrieve_assistant_thread(self, assistant_id):
        if assistant_id in self.assistants:
            thread_id = self.assistants[assistant_id]["thread_id"]
            return thread_id
        else:
            return None
    def retrieve_assistant_name(self, assistant_id):
        if assistant_id in self.assistants:
            name = self.assistants[assistant_id]["name"]
            return name
        else:
            return None 
    def retrieve_history(self,assistant_id):
        if assistant_id in self.history:
            history_msg = self.history[assistant_id]
            return history_msg
        else:
            return []
    def delete_assistant(self, assistant_id):
        if assistant_id in self.assistants:
            del self.assistants[assistant_id]
            self.save_assistants() 
    def delete_history(self,assistant_id):
        if assistant_id in self.history:
            del self.history[assistant_id]
            self.save_history()     
    def load_assistants(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as file:
                return json.load(file)
        else:
            return {}      
    def load_history(self):
        if os.path.exists(self.chathistory):
            with open(self.chathistory, 'r') as file:
                return json.load(file)
        else:
            return {}   
    def save_assistants(self):
        with open(self.filename, 'w') as file:
            json.dump(self.assistants, file, indent=4)
    def save_history(self):
        with open(self.chathistory, 'w') as file:
            json.dump(self.history, file, indent=4)
    def get_assistants(self):
        return self.assistants

class AssistantManager:
    graph = None
    def __init__(self, owner, assistant_id = None):
        self.client = openai.OpenAI()
        self.record = Recordpattern(owner) 
        self.assistant_id = assistant_id
        self.assistant = None
        self.thread = None
        self.run = None
        self.summary = None
        self.outputs = []
        if self.assistant_id:
            self.assistant = self.client.beta.assistants.retrieve(
                assistant_id = self.assistant_id
            )
            self.thread = self.client.beta.threads.retrieve(
                thread_id = self.record.retrieve_assistant_thread(self.assistant_id)
            )
    def check_assistant_list(self):
        assistant_list = self.client.beta.assistants.list(order="desc").data
        return assistant_list    
    def check_file_list(self):
        file_list = self.client.files.list(order="desc")
        return file_list
    def create_assistant(self, name, instructions, tools, model = "gpt-3.5-turbo-16k"):
        if not self.assistant:      
            try:
                assistant_obj = self.client.beta.assistants.create(
                    name = name,
                    instructions = instructions,
                    tools = tools,
                    model = model,
                )
                thread_obj = self.client.beta.threads.create()             
                self.assistant = assistant_obj
                self.thread = thread_obj   
                self.assistant_id = assistant_obj.id
                tool_names = []
                if tools:
                    for tool in tools:
                        tool_name = tool['function']['name']
                        tool_names.append(tool_name)
                self.record.add_assistant(assistant_obj.id,thread_obj.id,name,instructions,tool_names)        
                #print(f"AssisID:::{self.assistant.id}") 
                #print(f"ThreadID:::{self.thread.id}")
            except AttributeError as e:
                print(f"Failed to create thread: {e}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
    def add_message_to_thread(self, role, content):
        if self.thread:
            self.client.beta.threads.messages.create(
                thread_id = self.thread.id,
                role = role,
                content = content
            )
    def upload_file(self,file_path):
        self.client.files.create(
            file=open(file_path, "rb"),
            purpose="assistants"
            )
    def run_assistant(self,instructions):
        if self.thread and self.assistant:
            self.run = self.client.beta.threads.runs.create(
                thread_id = self.thread.id,
                assistant_id = self.assistant.id,
                instructions = instructions
            )
    def process_message(self):
        if self.thread: 
            messages = self.client.beta.threads.messages.list( thread_id = self.thread.id)
            summary = []
            last_message = messages.data[0]
            role = last_message.role
            response = last_message.content[0].text.value
            summary.append(response)
            self.summary = "\n".join(summary)
            print(f"Summary -----> {role.capitalize()}: => {response} ")
            return response
    def call_required_functions(self, required_actions):
        if not self.run:
            return
        tool_outputs = []

        # This part can be adjusted to your own functions
        for action in required_actions["tool_calls"]:
            ## print(f"Function parameters:: {action['function']}")
            func_name = action["function"]["name"]
            arguments = json.loads(action["function"]["arguments"])
            print(arguments)
            if func_name == "get_stock_data":
                if arguments.get("end_date"):
                    end_date = arguments["end_date"]
                else: 
                    start_date_time = datetime.strptime(arguments["start_date"], "%Y-%m-%d")
                    end_date_time = start_date_time + timedelta(days=1)
                    end_date = end_date_time.strftime("%Y-%m-%d")
                if arguments.get("column"):
                    column = arguments["column"]
                else: column = "Adj Close"
                print("these are the tickers ------------------------------------------",arguments["ticker"])
                stock_data = StockTools(tickers = arguments["ticker"], start_date = arguments["start_date"], end_date = end_date, col = column)
                output_df = stock_data.data_for_plotting()
                output = output_df.to_json()
                if len(output_df) <=3:
                    print(f"output::: {output_df}")
                    tool_outputs.append({"tool_call_id":action["id"], "output":output})
                else:
                    stock_tools = StockTools(arguments['ticker'])
                    output_df = stock_tools.data_for_plotting()
                    fig = px.line(output_df, x='Date', y=[col for col in output_df.columns if col != 'Date'], title='Stock Data Over Time', labels={'value': str(arguments['column']), 'variable': 'Stock Ticker'})
                    AssistantManager.graph = fig.to_json()
                    tool_outputs.append({"tool_call_id":action["id"], "output":f"{output}\nFor data more than 3 days, you can check out the graph here (127.0.0.1/stocks) for visualization."})
            
            elif func_name == "technical_analysis":

                stock_ta = StockTools()
                output = stock_ta.technical_analysis(ticker = arguments["ticker"])
                print(f"output::: {output}")
                final_str = json.dumps(output)
                tool_outputs.append({"tool_call_id":action["id"], "output":final_str})
            
            elif func_name == "get_news":

                stock_news = StockTools()
                output = stock_news.get_news(arguments["topic"])
                final_str = ""
                for item in output:
                    final_str += "".join(item)
                tool_outputs.append({"tool_call_id":action["id"], "output":final_str})
                self.outputs.append({func_name:output})
                
            else:
                raise ValueError(f"Unknown function: {func_name}") 
        print("Submitting the output back to the assistant...")
        
        self.client.beta.threads.runs.submit_tool_outputs(
            thread_id = self.thread.id,
            run_id = self.run.id,
            tool_outputs = tool_outputs
        )
    def get_summary(self):
        return self.summary     
    def wait_for_completed(self):
        erro = "Something went wrong when running."
        if self.thread and self.run:
            while True:
                time.sleep(1)
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id = self.thread.id,
                    run_id = self.run.id
                )
                print(f"Run status:: {run_status.status}")

                if run_status.status == "completed":
                    return self.process_message()
                elif run_status.status == "failed":
                    print("Run failed")
                    return erro
                elif run_status.status == "expired":
                    print("Run expired")
                    return erro
                elif run_status.status == "requires_action":
                    print("Analysing by function calling...")
                    self.call_required_functions(
                        required_actions = run_status.required_action.submit_tool_outputs.model_dump()
                    )
    def run_steps(self):
        run_steps = self.client.beta.threads.runs.steps.list(
            thread_id = self.thread.id,
            run_id = self.run.id
        )
        print(f"Steps ---> {run_steps}")
    def delete(self):
        try:
            self.client.beta.assistants.delete(assistant_id = self.assistant_id)
            self.client.beta.threads.delete(thread_id = self.record.retrieve_assistant_thread(self.assistant_id))
            self.record.delete_assistant(self.assistant_id)
            self.record.delete_history(self.assistant_id)
            msg = "Assistant Deleted Successfully"
            print(msg)
            return msg
        except Exception as e:
            print(f"An unexpected error occurred: {e}")









