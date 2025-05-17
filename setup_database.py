import os
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_database():
    """Set up the necessary tables in Supabase."""

    # Get Supabase credentials
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")  # Use anon key for regular operations

    if not url or not key:
        print("Error: Supabase credentials not found in environment variables")
        return False

    # Set up headers for Supabase API
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    try:
        # First, check if the documents table exists
        with httpx.Client() as client:
            # Try to get a single record from the documents table
            response = client.get(
                f"{url}/rest/v1/documents",
                headers=headers,
                params={"select": "count", "limit": 1}
            )

            # If we get a 200 response, the table exists
            if response.status_code == 200:
                print("Documents table already exists!")
                return True

            # If we get a 404, the table doesn't exist and we need to create it
            elif response.status_code == 404:
                print("Documents table doesn't exist. Creating it...")

                # Create the documents table directly using the REST API
                create_table_response = client.post(
                    f"{url}/rest/v1/documents",
                    headers=headers,
                    json={
                        "id": "00000000-0000-0000-0000-000000000000",
                        "file_name": "test.pdf",
                        "file_content": "test",
                        "extracted_data": {},
                        "suid": "test"
                    }
                )

                # Check if the table was created
                if create_table_response.status_code in (201, 409):
                    print("Documents table created successfully!")

                    # Delete the test record if it was created
                    if create_table_response.status_code == 201:
                        client.delete(
                            f"{url}/rest/v1/documents",
                            headers=headers,
                            params={"id": "eq.00000000-0000-0000-0000-000000000000"}
                        )

                    return True
                else:
                    print(f"Error creating documents table: {create_table_response.text}")
                    return False
            else:
                print(f"Unexpected response when checking for documents table: {response.status_code} - {response.text}")
                return False

    except Exception as e:
        print(f"Error setting up database: {str(e)}")
        return False

if __name__ == "__main__":
    setup_database()
