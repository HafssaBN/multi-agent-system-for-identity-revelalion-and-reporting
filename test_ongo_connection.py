# test_mongo_connection.py
import os
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv

print("--- Starting MongoDB Connection Test ---")

# Load environment variables from .env file
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    print("❌ FAILURE: MONGO_URI not found in .env file. Please check your file.")
else:
    print("✅ MONGO_URI found in .env file.")
    print(f"Attempting to connect...")

    try:
        # Try to connect with the certificates
        client = MongoClient(
            MONGO_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000  # Increased timeout for slow networks
        )
        
        # The ping command is a lightweight way to force a connection and check authentication.
        client.admin.command('ping')
        
        print("\n" + "="*50)
        print("✅✅✅ SUCCESS: Connection to MongoDB Atlas was successful!")
        print("="*50 + "\n")

    except Exception as e:
        print("\n" + "="*50)
        print(f"❌❌❌ FAILURE: Could not connect to MongoDB Atlas.")
        print(f"ERROR DETAILS: {e}")
        print("="*50 + "\n")

print("--- Test Complete ---")