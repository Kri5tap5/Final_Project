from http.client import responses
from fastapi import FastAPI
from pydantic import BaseModel
import os
import requests
import openai
from dotenv import load_dotenv
from gtts import gTTS
from IPython.display import Audio
import time
import json
import sqlite3

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")

# Load environment variables from .env using the absolute path
load_dotenv(dotenv_path=env_path)

openai.api_key = os.getenv("openai_API_key")
thread_id = os.getenv("thread_id")
assistant_id = os.getenv("assistant_id")

OpenWeatherAPIkey = os.getenv("OpenWeatherAPIkey")
NewsAPI_key = os.getenv("NewsAPI_key")
PolygonAPI_key = os.getenv("PolygonAPI_key")

name_day_file_id = os.getenv("name_day_file_id")

app = FastAPI()

# Model for a single message
class Message(BaseModel):
    role: str
    content: str

@app.post("/send-message/")
async def process_message_and_respond(thread_id: str, message: str):
    """
    Receive a message from the user and return a test response from the virtual assistant.

    Args:
        thread_id (str): The ID of the conversation thread.
        message (str): The message sent by the user.

    Returns:
        dict: A dictionary containing the thread ID, the assistant's test response, and the original message.
    """
    response = main(message)
    return {
        "thread_id": thread_id,
        "response": response,
        "message_received": message
    }

# Retrieve a conversation history based on the thread ID, 20 messages total
@app.get("/conversation-history/")
async def conversation_history(thread_id: str):
    """
    Retrieve the conversation history for a specific thread.

    Args:
        thread_id (str): The ID of the conversation thread.

    Returns:
        dict: A dictionary containing the thread ID and a list of conversation messages, including both user and assistant messages.
    """
    conversation_history = get_chat_history(thread_id)
    return {
         "thread_id": thread_id,
         "conversation_history": conversation_history
    }

def main(message):
    #Gets the current absolute path for openai tools
    current_dir = os.path.dirname(os.path.abspath(__file__))
    tools_path = os.path.join(current_dir, "tools.json")
    with open(tools_path, "r") as file:
        tools = json.load(file)

    #If running the code for the first time, comment out the assistant_id line and change the ...assistants.update() to assistants.create()
    #Run the create() command only once and remember to write down the assistant.id string. Later, place the assistant id in a .env file!
    assistant = openai.beta.assistants.update(
        assistant_id=assistant_id,
        name="MorningAssistant",
        instructions="You are a very talkative morning assistant with access to custom tools that return different responses based on what the user might want to know in the morning.",
        model="gpt-4o-mini",
        tools=tools
    )
    print(f"Assistant updated with ID: {assistant.id}")

    # Run the next two lines of code only when running the code for the first time. After that, write down the thread.id string and place it in a .env file
    # thread = openai.beta.threads.create()
    # print(f"Thread created with ID: {thread.id}")

    run_status, run_id = check_for_active_run(thread_id)

    if run_id is not None:
        print("Active run found, finishing it!")
        run = openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
    else:  # Message that the Assistant will try to find an answer to
        message = openai.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )
        # Runs the assistant with message input given above
        run = openai.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

    # Wait for the run to complete
    attempt = 1
    while run.status != "completed":
        print(f"Run status: {run.status}, attempt: {attempt}")
        run = openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

        if run.status == "requires_action":
            break

        if run.status == "failed":
            # Handle the error message if it exists
            if hasattr(run, 'last_error') and run.last_error is not None:
                error_message = run.last_error.message
            else:
                error_message = "No error message found..."

            print(
                f"Run {run.id} failed! Status: {run.status}\n  thread_id: {run.thread_id}\n  assistant_id: {run.assistant_id}\n  error_message: {error_message}")
            print(str(run))

        attempt += 1
        time.sleep(3)

    # status "requires_action" means that the assistant decided it needs to call an external tool
    # assistant gives us names of tools it needs, we call the corresponding function and return the data back to the assistant
    if run.status == "requires_action":
        print("Run requires action, assistant wants to use a tool")
        if run.required_action:
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                print(tool_call)
                tool_params = json.loads(
                    tool_call.function.arguments) if tool_call.function.arguments else {}  # Loads the tool_params variable full of key info from the user input (Processed by AI)

                if tool_call.function.name == "current_weather":  # Flow for the current_weather() function
                    print("current_weather called")
                    city = tool_params.get('city')
                    output = current_weather(city, OpenWeatherAPIkey)

                elif tool_call.function.name == "random_fact":  # Flow for the random_fact() function
                    fact_type = tool_params.get('fact_type')
                    print(f"random_fact called, Fact type: {fact_type}")
                    output = random_fact(fact_type)

                elif tool_call.function.name == "coordinates_city":  # Flow for the coordinates_city() function
                    city = tool_params.get('city')
                    print("coordinates_city called")
                    longitude, latitude = coordinates_city(city, OpenWeatherAPIkey)
                    output = f'the city of {city} has the longitude of {longitude} and latitude of {latitude} '

                elif tool_call.function.name == "world_news":  # Flow for the world_news() function
                    country = tool_params.get('country')
                    category = tool_params.get('category')
                    q = tool_params.get('q')
                    print(f"world_news called, Country: {country}, Category: {category}, Query: {q}")
                    output = world_news(country, category, q, NewsAPI_key)

                elif tool_call.function.name == "stocks_yesterday":  # Flow for the stocks_yesterday() function
                    ticker = tool_params.get('ticker')
                    print(f"stocks_yesterday called for {ticker}")
                    output = stocks_yesterday(ticker, PolygonAPI_key)

                elif tool_call.function.name == "name_days_of_today":  # Flow for the name_days_of_today() function
                    print(f"name_days_of_today called")
                    output = name_days_of_today(name_day_file_id)

                elif tool_call.function.name == "compare_stock_values":  # Flow for the compare_stock_values() function
                    ticker = tool_params.get('ticker')
                    if tool_params.get('stock_purchase_value') is not None:
                        purchase_price = float(tool_params.get('stock_purchase_value'))
                    else:
                        purchase_price = None
                    print(f"compare_stock_values called, ticker: {ticker}, stock_purchase_value: {purchase_price}")
                    output = compare_stock_values(ticker, purchase_price)

                elif tool_call.function.name == "update_purchase_price":
                    ticker = tool_params.get('ticker')
                    purchase_price = tool_params.get('stock_purchase_value')
                    print(f"update_purchase_price called, ticker: {ticker}")
                    output = update_purchase_price(ticker, purchase_price)

                elif tool_call.function.name == "delete_purchase_price":
                    ticker = tool_params.get('ticker')
                    print(f"delete_purchase_price called, ticker: {ticker}")
                    output = delete_purchase_price(ticker)

                else:
                    print("Unknown function call")
                    output = None
                print(f"  Generated output: {output}")

                # submit the output back to assistant
                openai.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=[{
                        "tool_call_id": tool_call.id,
                        "output": str(output)
                    }]
                )

    if run.status == "requires_action":

        # After submitting tool outputs, we need to wait for the run to complete, again
        run = openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        attempt = 1
        while run.status not in ["completed", "failed"]:
            print(f"Run status: {run.status}, attempt: {attempt}")
            time.sleep(1)
            run = openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            attempt += 1

    if run.status == "completed":
        # Retrieve and print the assistant's response
        messages = openai.beta.threads.messages.list(thread_id=thread_id)
        final_answer = messages.data[0].content[0].text.value
        print(f"=========\n{final_answer}")
    elif run.status == "failed":
        # Handle the error message if it exists
        if hasattr(run, 'last_error') and run.last_error is not None:
            error_message = run.last_error.message
        else:
            error_message = "No error message found..."

        print(
            f"Run {run.id} failed! Status: {run.status}\n  thread_id: {run.thread_id}\n  assistant_id: {run.assistant_id}\n  error_message: {error_message}")
        print(str(run))
    else:
        print(f"Unexpected run status: {run.status}")

    # Could use openAI text to speech module
    # response_tts = openai.audio.speech.create(
    #     model="tts-1",
    #     voice="alloy",
    #     input=final_answer,
    # )

    # response_tts.stream_to_file("output.mp3")

    # Converts the final answer from the assistant into TTS which is automatically played after receiving an answer.
    #Currently, TTS is not implemented in frontend app :/
    if final_answer:
        text = final_answer
        tts = gTTS(text)
        tts.save("output.mp3")
        Audio("output.mp3", autoplay=True)
    else:
        print('Unable to speak, because final_answer was not received')

    return final_answer

#Checks for already active and unfinished runs
def check_for_active_run(thread_id):
    runs = openai.beta.threads.runs.list(thread_id=thread_id)
    for run in runs.data:
        if run.status in ["active", "requires_action"]:
            print(f"Active run found: {run.id} with status {run.status}")
            return run.status, run.id  #If an active run is found, the code will attempt to complete it

    return None, None #If no active run is found, a new one will be created

#Returns precise coordinates of a city mentioned
def coordinates_city(city, OpenWeatherAPIkey):
    url = f'https://api.openweathermap.org/geo/1.0/direct?q={city}&limit={2}&appid={OpenWeatherAPIkey}'
    response = requests.get(url)
    if response.status_code==200:
        city = response.json()
        latitude = city[0]['lat']
        longitude = city[0]['lon']
        return latitude, longitude
    else:
        print("API connection Failed!")
        return None, None

#Returns the current weather for set coordinates
def current_weather(city, OpenWeatherAPIkey):
    latitude, longitude = coordinates_city(city, OpenWeatherAPIkey)
    cardinal_directions = ['N', 'N/NE', 'NE', 'E/NE', 'E', 'E/SE', 'SE', 'S/SE', 'S', 'S/SW', 'SW', 'W/SW', 'W', 'W/NW', 'NW', 'N/NW']
    url = f'https://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&units=metric&appid={OpenWeatherAPIkey}'
    response = requests.get(url)
    if response.status_code==200:
        data = response.json()

        current_weather_pred = data['weather'][0]['description']
        current_temperature = data['main']['temp']
        wind_speed = data ['wind']['speed']
        humidity = data ['main']['humidity']

        wind_direction_deg = data ['wind']['deg']
        ix = round(wind_direction_deg/22.5)
        wind_direction = cardinal_directions[ix]

        print(f'Current temperature is {current_temperature} °C and the weather is {str(current_weather_pred)}. Wind is blowing {wind_direction} with {str(wind_speed)} m/s. \n')
        output = f'Current temperature is {str(current_temperature)} °Celsius and the weather is {str(current_weather_pred)}. Wind is blowing {wind_direction} with {str(wind_speed)} m/s. Humidity: {humidity} \n\n'
        return output
    else:
        print("API connection Failed!")
        return None

#Returns a fact of the Day(today) OR a Random(random) fact based on user input
def random_fact(fact_type):
    print(f'Fact type func: {fact_type}')
    url = f"https://uselessfacts.jsph.pl/api/v2/facts/{fact_type}?language=en"
    response = requests.get(url)
    if response.status_code==200:
        data = response.json()
        output = data['text']
        return output
    else:
        print("API connection Failed!")
        return None

#Returns top news articles which the user might want to know about ¯\(°_o)/¯
def world_news(country, category, query, NewsAPI_key):
    base_url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": NewsAPI_key,
        "country": country,      # e.g., 'us' for the United States
        "category": category,    # e.g., 'technology', 'sports'
        "q": query               # Search query term (e.g., 'elections')
    }
    print("world_news() parameters: ", params)
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        data = response.json()
        # Check if articles are returned
        if data['articles']:
            # Extract the top news article title and description
            articles = data['articles'][:3]  # Limit to top 3
            news_output = ""
            for i, article in enumerate(articles, 1):
                title = article.get("title")
                description = article.get("description")
                news_output += f"{i}. {title}\n{description}\n\n"
            return news_output
        else:
            return "No news articles found for the specified parameters."
    else:
        print("API connection Failed!")
        return None
#Returns the stock value of a stock(ticker) chosen
def stocks_yesterday(ticker, PolygonAPI_key):
    #unix time that needs to be wound back to previous day in order for the API to work (FREE plan restriction)
    unix_time_1d1h = 88000000 #Unix time in ms
    unix_time_1d = unix_time_1d1h - 3600000

    #Current unix time
    current_time_unix = int(round(time.time() * 1000, 0))
    print('Current unix time: ', current_time_unix )

    #Unix time yesterday and yesterday an hour ago
    unix_from = current_time_unix - unix_time_1d1h
    unix_to = current_time_unix - unix_time_1d

    url = f'https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/hour/{unix_from}/{unix_to}?adjusted=true&sort=asc&apiKey={PolygonAPI_key}'
    response = requests.get(url)
    print(response.status_code)
    if response.status_code==200:
        data = response.json()
        if data['resultsCount'] == 0:
            output = f"No data found for the specified parameters. Maybe the ticker ({ticker}) is incorrect for the company you are trying to search"
            return output
        else:
            close_price = float(data['results'][0]['c'])
            output = f'Yesterdays closing price for {ticker} was {close_price}'
            return output, close_price
    else:
        print("API connection Failed!")
        return None

#Creates an SQL database table to keep stock purchase prices and compare them to current stock prices
def create_stocks_table():
    conn = sqlite3.connect('Assistant.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS stocks (id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL, purchase_price REAL NOT NULL)")
    # Could be able to add a date to the table and call the stock value function for that date. Date would need to be converted to unix time
    #            purchase_date DATE DEFAULT CURRENT DATE
    #            purchase_date_epoch INTEGER NOT NULL
    print('A new table "stocks" has been created')
    conn.commit()
    conn.close()

#Returns the stock(ticker) purchase value which is stored in the database
def get_purchase_price(ticker):
    boolVal = check_stocks_table()
    if boolVal is True:
        conn = sqlite3.connect('Assistant.db')
        cursor = conn.cursor()
        cursor.execute('SELECT purchase_price FROM stocks WHERE ticker = ?', (ticker,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    else:
        return None

#Adds the purchase price of a stock to the database
def add_purchase_price(ticker, price):
    print(f'Adding a new purchase price for {ticker}')
    conn = sqlite3.connect('Assistant.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO stocks (ticker, purchase_price) VALUES (?, ?)', (ticker, price))
    conn.commit()
    conn.close()

#Deletes purchase price for a stock(ticker) if the user sold this stock
def delete_purchase_price(ticker):
    boolVal = check_stocks_table()
    if boolVal is True:
        conn = sqlite3.connect('Assistant.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM stocks WHERE ticker = ?', (ticker,))
        print(f'Deleting purchase price for {ticker}...')
        conn.commit()
        conn.close()
        output = f'Stock ticker "{ticker}" has been removed from the database'
    else:
        output = f"I have no record of you adding the ticker of {ticker} to the database. Database has no entries"
    return output

#Updates purchase price of a stock(ticker) if the user sold and bought again or just bought more
def update_purchase_price(ticker, purchase_price):
    boolVal = check_stocks_table()
    if boolVal is True:
        conn = sqlite3.connect('Assistant.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE stocks SET purchase_price = ? WHERE ticker = ?', (purchase_price, ticker))
        print(f'Updating purchase price for {ticker}...')
        conn.commit()
        conn.close()
        output = f'Stock purchase price for {ticker} has been updated! Do you want to see you stock value in% now?'
    else:
        output = f"I have no records of you mentioning a previous purchase price of {purchase_price} for {ticker}, however I'll still add the value to the database!"
        add_purchase_price(ticker, purchase_price)
    return output

#Calculates the increase or decrease in stock value since purchase
def calculate_increase(current_price, purchase_price):
    print('Calculating increase...')
    result = round((((current_price - purchase_price) / purchase_price) * 100), 3)

    if result > 0:
        output = f'Your stock value has increased by {result} % of its original value!'
    elif result == 0:
        output = f'Your stock value has not increased nor decreased!'
    else:
        output = f'Your stock value has decreased by {result}% of its original % value!'
    return output

#Checks if the stocks table even exists, if not, calls function to create it
def check_stocks_table():
    print('Checking if "stocks" table has entries...')
    conn = sqlite3.connect("Assistant.db")
    cursor = conn.cursor()
    table_name = 'stocks'
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    result = cursor.fetchone()
    conn.close()
    if result is not None:
            print('Table has entries, skipping creation')
            return True
    else:
        print('No such table "stocks". Creating it...')
        create_stocks_table()
        return False

#Main function for stock value comparison which is included in assistant tools
def compare_stock_values(ticker, purchase_price):
    output, current_price = stocks_yesterday(ticker, PolygonAPI_key)
    if purchase_price is None:
        print("Assistant failed to get purchase_price from user, checking if it's stored in the database")
        purchase_price = get_purchase_price(ticker)
        if purchase_price is None:
            output = f'Please provide me the price at which you bought your stocks for {ticker}'
            #print("purchase_price was not found in the database, asking user for input")
            # purchase_price_input = float(input(f"What was your purchase price for {ticker}? Please input only float values"))
            # add_purchase_price(ticker, purchase_price_input)
            # purchase_price = purchase_price_input
            #This part crashes the app, because it's waiting for input in console. Could fix this down the line

            increase_percentage = calculate_increase(current_price, purchase_price)
            output = f'The current price for {ticker} is {current_price}. You bought this stock at a value of {purchase_price} ' + increase_percentage
        else:
            increase_percentage = calculate_increase(current_price, purchase_price)
            output = f'The current price for {ticker} is {current_price}. You bought this stock at a value of {purchase_price} ' + increase_percentage
    else:
        increase_percentage = calculate_increase(current_price, purchase_price)
        output = f'The current price for {ticker} is {current_price}. You bought this stock at a value of {purchase_price} ' + increase_percentage

    return output

#If needed, creates a local database of name days. name_day_file_id should be put in a .env file
def get_name_days(name_day_file_id):
    # Connect to the DB. If none exists, it will be created
    conn = sqlite3.connect("Assistant.db")
    cursor = conn.cursor()

    # A new table is created if none already exists
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS name_days (
            date TEXT,
            name TEXT
            )
    ''')
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM name_days")
    row_count = cursor.fetchone()[0]
    if row_count > 0:
        print('Table has entries, skipping creation')
    else:
        print('Table has no entries, creating table')
        url = f'https://drive.google.com/uc?export=download&id={name_day_file_id}'
        response = requests.get(url)
        name_days = response.json()
        if response.status_code==200:
            # Insert each name with its corresponding date
            for date, names in name_days.items():
                for name in names:
                    cursor.execute("INSERT INTO name_days (date, name) VALUES (?, ?)", (date, name))#'?, ?' prevents insertion attacks
        conn.commit()
    conn.close()

def name_days_of_today(name_day_file_id):
    conn = sqlite3.connect("Assistant.db")
    cursor = conn.cursor()
    table_name = 'name_days'
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    result = cursor.fetchone()
    if result is not None:
            print('Table exists, but may be empty')#This segment is meant for easy troubleshooting
    else:
        get_name_days(name_day_file_id)

    month = time.strftime("%m")#Need to find a way to add dynamic dates, not only today if dates are to be stored in DB
    date = time.strftime("%d")
    cursor.execute(f"SELECT * FROM name_days WHERE date LIKE '{month}-{date}'")
    rows = cursor.fetchall()
    conn.close()

    names = [row[1] for row in rows]
    output = "The people who celebrate their name day today are: " +  ', '.join(map(str, names))
    return output

def get_chat_history(thread_id):
    try:
        # Fetch all messages in the thread
        messages = openai.beta.threads.messages.list(thread_id=thread_id)
        chat_history = []

        for message in messages.data:
            # Initialize extracted_content
            extracted_content = "Invalid content format"

            # Check if content is a list
            if isinstance(message.content, list):
                # Process each item in the content array
                extracted_content = " ".join(
                    getattr(content_item.text, "value", "Invalid content format")
                    for content_item in message.content
                    if hasattr(content_item, "type") and content_item.type == "text"
                )
            elif hasattr(message.content, "text") and hasattr(message.content.text, "value"):
                # Handle single text content directly
                extracted_content = message.content.text.value

            chat_history.append({
                "role": message.role,
                "content": extracted_content
            })

        return chat_history[::-1] #Reverses the message array, so that they are displayed in the frontend client correctly
    except Exception as e:
        print(f"Error retrieving chat history: {e}")
        return []