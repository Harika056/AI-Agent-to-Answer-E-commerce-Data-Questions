from fastapi import FastAPI
from pydantic import BaseModel
import os
import sqlite3
import requests
import json
import sys

# Import CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Initialize the FastAPI application
app = FastAPI(debug=True)

# --- Serve Static Files (index.html) ---
app.mount("/static", StaticFiles(directory="."), name="static")

# --- CORS Configuration ---
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "*" # Allows all origins - useful for debugging, restrict in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- End CORS Configuration ---


# Pydantic model for the incoming query
class Query(BaseModel):
    question: str

# --- YOUR ACTUAL GEMINI API KEY IS HARDCODED HERE ---
API_KEY = "AIzaSyD75IpF9MlfKtc8-aYtEvJu1JHbhQvWO60" # <--- YOUR KEY IS HERE

if not API_KEY:
    raise ValueError("API Key is empty. Please ensure your actual key is correctly placed in the API_KEY variable.")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
DATABASE_NAME = "ecommerce.db"
# Get the absolute path for the database file
DATABASE_PATH = os.path.join(os.getcwd(), DATABASE_NAME)


def setup_database():
    """
    Sets up a basic SQLite database with sample tables and data.
    It will delete the existing database file to ensure a fresh start.
    """
    print(f"DEBUG: Starting setup_database() function. Database path: {DATABASE_PATH}")
    # --- IMPORTANT: Delete existing database file to ensure a fresh setup ---
    if os.path.exists(DATABASE_PATH):
        try:
            os.remove(DATABASE_PATH)
            print(f"DEBUG: Successfully deleted existing database '{DATABASE_PATH}' for fresh setup.")
        except OSError as e:
            print(f"DEBUG: ERROR: Could not delete existing database file '{DATABASE_PATH}': {e}")
            print("DEBUG: This might indicate the file is in use by another process.")
            print("DEBUG: Please ensure no other programs (like SQLite browsers) are open.")
            sys.exit(1) # Exit if we can't delete, as fresh setup is critical
    else:
        print(f"DEBUG: No existing database '{DATABASE_PATH}' found, proceeding to create new.")
    # --- End IMPORTANT ---

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        print(f"DEBUG: Connected to database '{DATABASE_PATH}'.")

        print("DEBUG: Creating eligibility table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eligibility (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO eligibility (id, user_id, status) VALUES (1, 'user123', 'eligible')")
        cursor.execute("INSERT OR IGNORE INTO eligibility (id, user_id, status) VALUES (2, 'user456', 'not eligible')")
        print("DEBUG: Eligibility table created and data inserted.")

        print("DEBUG: Creating ad_sales table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ad_sales (
                id INTEGER PRIMARY KEY,
                product_id TEXT NOT NULL,
                ad_spend REAL NOT NULL,
                impressions INTEGER NOT NULL
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO ad_sales (id, product_id, ad_spend, impressions) VALUES (1, 'prodA', 100.50, 5000)")
        cursor.execute("INSERT OR IGNORE INTO ad_sales (id, product_id, ad_spend, impressions) VALUES (2, 'prodB', 75.20, 3000)")
        print("DEBUG: Ad_sales table created and data inserted.")

        print("DEBUG: Creating total_sales table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS total_sales (
                id INTEGER PRIMARY KEY,
                order_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                amount REAL NOT NULL,
                sale_date TEXT NOT NULL
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO total_sales (id, order_id, product_name, amount, sale_date) VALUES (1, 'ORD001', 'Laptop', 1200.00, '2025-07-20')")
        cursor.execute("INSERT OR IGNORE INTO total_sales (id, order_id, product_name, amount, sale_date) VALUES (2, 'ORD002', 'Mouse', 25.50, '2025-07-21')")
        cursor.execute("INSERT OR IGNORE INTO total_sales (id, order_id, product_name, amount, sale_date) VALUES (3, 'ORD003', 'Keyboard', 75.00, '2025-07-21')")
        cursor.execute("INSERT OR IGNORE INTO total_sales (id, order_id, product_name, amount, sale_date) VALUES (4, 'ORD004', 'Laptop', 1500.00, '2025-07-22')")
        print("DEBUG: Total_sales table created and data inserted.")

        conn.commit()
        print(f"DEBUG: Database '{DATABASE_NAME}' committed and tables are ready.")
    except sqlite3.Error as e:
        print(f"DEBUG: FATAL ERROR during database setup: {e}")
        sys.exit(1) # Exit if database setup fails
    finally:
        if conn:
            conn.close()
        print(f"DEBUG: Finished setup_database() function.")

# --- NEW: Call setup_database() on FastAPI startup event ---
@app.on_event("startup")
async def startup_event():
    print("DEBUG: FastAPI startup event triggered. Calling setup_database().")
    setup_database()
    # --- Final check for database table existence after setup_database completes ---
    conn_check = None
    try:
        conn_check = sqlite3.connect(DATABASE_PATH)
        cursor_check = conn_check.cursor()
        cursor_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='total_sales';")
        if cursor_check.fetchone():
            print("DEBUG: Confirmed 'total_sales' table exists after startup event.")
        else:
            print("DEBUG: FATAL ERROR: 'total_sales' table DOES NOT exist after startup event. Exiting.")
            sys.exit(1)
    except sqlite3.Error as e:
        print(f"DEBUG: FATAL ERROR checking table existence during startup event: {e}. Exiting.")
        sys.exit(1)
    finally:
        if conn_check:
            conn_check.close()
    print("DEBUG: Startup event finished.")
# --- End NEW ---


def generate_sql(question: str) -> str:
    """
    Generates an SQL query from a natural language question using the Gemini API,
    requesting a structured JSON response to ensure clean SQL output.
    """
    prompt = f"""
    You are an expert SQL generator. Convert the following natural language question into an SQL query for a SQLite database with tables: eligibility, ad_sales, total_sales.
    Provide ONLY the SQL query, without any additional text or explanation.
    Example:
    Question: What are the total sales?
    SQL: SELECT SUM(amount) FROM total_sales;

    Question: {question}
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 100,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "sql_query": {"type": "STRING"}
                },
                "required": ["sql_query"]
            }
        }
    }
    
    try:
        response = requests.post(GEMINI_URL, json=payload)
        response.raise_for_status()
        
        gemini_response_json = response.json()
        
        print("Gemini raw response:", gemini_response_json)

        if 'candidates' in gemini_response_json and \
           len(gemini_response_json['candidates']) > 0 and \
           'content' in gemini_response_json['candidates'][0] and \
           'parts' in gemini_response_json['candidates'][0]['content'] and \
           len(gemini_response_json['candidates'][0]['content']['parts']) > 0 and \
           'text' in gemini_response_json['candidates'][0]['content']['parts'][0]:
            
            json_text = gemini_response_json['candidates'][0]['content']['parts'][0]['text']
            parsed_response = json.loads(json_text)
            
            sql_query = parsed_response.get('sql_query', '').strip()
            
            if not sql_query:
                print("Gemini response did not contain 'sql_query' key or it was empty.")
                return "SELECT 'Error: Gemini generated empty or missing SQL query.'"
            return sql_query
        else:
            print("Gemini response structure unexpected or missing content:", gemini_response_json)
            return "SELECT 'Error: Could not generate SQL from Gemini. Unexpected response structure.'"
            
    except requests.exceptions.RequestException as req_err:
        print(f"Request to Gemini API failed: {req_err}")
        return f"SELECT 'Error: Gemini API request failed: {req_err}'"
    except json.JSONDecodeError as json_err:
        print(f"Error decoding Gemini response JSON: {json_err}. Raw text: {json_text if 'json_text' in locals() else 'N/A'}")
        return f"SELECT 'Error: Failed to parse Gemini JSON response: {json_err}'"
    except Exception as e:
        print(f"Error in generate_sql: {e}")
        return f"SELECT 'Error: An unexpected error occurred in SQL generation: {e}'"


def execute_sql(sql_query: str):
    """
    Executes an SQL query against the SQLite database and returns the results.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH) # Use DATABASE_PATH here as well
        cursor = conn.cursor()
        cursor.execute(sql_query)
        result = cursor.fetchall()
        conn.close()
        return result
    except sqlite3.Error as e:
        raise ValueError(f"SQLite error: {e}")
    finally:
        if conn:
            conn.close()

@app.post("/ask")
async def ask(query: Query):
    """
    API endpoint to receive a natural language question, convert it to SQL,
    execute it, and return the result or an error.
    """
    print(f"Received question: {query.question}")
    sql_query = generate_sql(query.question)
    print(f"Generated SQL: {sql_query}")
    
    try:
        result = execute_sql(sql_query)
        return {"answer": [list(row) for row in result]}
    except Exception as e:
        print(f"Error executing SQL: {e}")
        return {"error": str(e)}

# Add a root endpoint to serve the index.html file
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# This block allows you to run the FastAPI application directly using Uvicorn
if __name__ == "__main__":
    # Removed setup_database() from here, as it's now in @app.on_event("startup")
    # Also removed the final check from here, as it's now in @app.on_event("startup")
    print("DEBUG: Running Uvicorn from __main__ block.")
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
