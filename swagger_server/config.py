import os
from dotenv import load_dotenv

load_dotenv()

DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() in ('true', '1', 't')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/mydatabase')

print(f"Debug mode: {DEBUG_MODE}")