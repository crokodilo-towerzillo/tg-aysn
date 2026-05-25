import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
FERNET_KEY: str = os.environ["FERNET_KEY"]
fernet = Fernet(FERNET_KEY.encode())
