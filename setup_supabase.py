import os
import dotenv
from supabase import create_client, Client

# Load environment variables
dotenv.load_dotenv()

# Get Supabase credentials
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Use service role key for admin operations

if not supabase_url or not supabase_key:
    raise ValueError("Supabase credentials not found in environment variables")

# Initialize Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

# Read SQL file
with open("Backend/setup_supabase_tables.sql", "r") as f:
    sql = f.read()

# Execute SQL commands
print("Setting up Supabase database...")
result = supabase.rpc("pgrest_exec", {"query": sql}).execute()

print("Database setup complete!")
print(result)
