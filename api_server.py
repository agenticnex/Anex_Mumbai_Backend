import os
import base64
import json
import dotenv
import re
import csv
import io
import httpx
from process_bulk_upload import process_bulk_upload
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import uuid
from datetime import datetime

# Load environment variables
dotenv.load_dotenv()

# Import our modules directly - no Backend package
from azure_document_ai import AzureDocumentAI
from supabase_client import SupabaseClient
from azure_blob_storage import AzureBlobStorage

# Create FastAPI app
app = FastAPI(title="Document OCR API")
from Backend.azure_blob_storage import AzureBlobStorage

# Create FastAPI app
app = FastAPI(title="Document OCR API")

# Initialize Supabase client
supabase_client = SupabaseClient()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://anex-mum-bai-frontend.vercel.app",  # New production frontend
        "https://anex-client-1-frontend.vercel.app",  # Old production frontend
        "http://localhost:5173",  # Local development frontend
        "*"  # Allow all origins for testing
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Initialize clients
document_ai = AzureDocumentAI()
blob_storage = AzureBlobStorage()

# Models
class FileData(BaseModel):
    name: str
    content: str  # Base64 encoded content

class OCRRequest(BaseModel):
    files: List[FileData]
    extractionType: Optional[str] = "all"

class OCRResponse(BaseModel):
    results: List[Dict[str, Any]]

class BulkUploadRequest(BaseModel):
    files: List[FileData]
    extractionType: Optional[str] = "all"

class BulkUploadResponse(BaseModel):
    job_id: str
    total_files: int
    message: str

class BulkUploadStatusRequest(BaseModel):
    job_id: str

class BulkUploadStatusResponse(BaseModel):
    job_id: str
    total_files: int
    processed_files: int
    status: str
    results: Optional[List[Dict[str, Any]]] = None

# Helper function to search page details for ID information
def search_page_details_for_ids(detailed_data: Dict[str, Any]) -> None:
    """
    Search through Page_Details section to extract ID card information that might have been missed.
    Updates the ID_Cards section with any new information found.

    Args:
        detailed_data: Dictionary containing the detailed data structure
    """
    # Define regex patterns for different ID types
    aadhar_pattern = r'\b(\d{4}\s*\d{4}\s*\d{4})\b|\b(\d{12})\b'
    pan_pattern = r'\b([A-Z]{5}\d{4}[A-Z])\b'
    epic_pattern = r'\b([A-Z]{3}\d{7})\b'

    # Initialize variables to store found IDs
    aadhar_number = None
    pan_number = None
    epic_number = None

    # Check if we already have these IDs in the ID_Cards section
    for card in detailed_data.get("ID_Cards", []):
        if card.get("ID_Type") == "Government of India" and card.get("Aadhar_Number"):
            aadhar_number = card.get("Aadhar_Number")
        elif card.get("ID_Type") == "Income Tax Department" and card.get("PAN_Number"):
            pan_number = card.get("PAN_Number")
        elif card.get("ID_Type") == "Election Commission of India" and card.get("EPIC_Number"):
            epic_number = card.get("EPIC_Number")

    # Search through each page's text for ID information
    for _, page_data in detailed_data.get("Page_Details", {}).items():
        page_text = page_data.get("Text", "")

        # Search for Aadhar number
        if not aadhar_number:
            aadhar_match = re.search(aadhar_pattern, page_text)
            if aadhar_match:
                # Group 1 is the format with spaces, Group 2 is without spaces
                matched_group = aadhar_match.group(1) if aadhar_match.group(1) else aadhar_match.group(2)
                if matched_group:
                    # Remove spaces to get clean 12-digit number
                    aadhar_number = re.sub(r'\s', '', matched_group)
                    # Validate it's exactly 12 digits
                    if len(aadhar_number) == 12 and aadhar_number.isdigit():
                        # Add to ID_Cards if not already present
                        if not any(card.get("ID_Type") == "Government of India" for card in detailed_data.get("ID_Cards", [])):
                            detailed_data["ID_Cards"].append({
                                "ID_Type": "Government of India",
                                "Card_Holder_Name": detailed_data.get("Name", "Not found"),
                                "Aadhar_Number": aadhar_number,
                                "Gender": detailed_data.get("Form_Responses", {}).get("Sections", {}).get("Personal", {}).get("Gender", "Not found"),
                                "Address": detailed_data.get("Form_Responses", {}).get("Sections", {}).get("Personal", {}).get("Address", "Not found")
                            })
                        # Otherwise update existing card
                        else:
                            for card in detailed_data.get("ID_Cards", []):
                                if card.get("ID_Type") == "Government of India":
                                    card["Aadhar_Number"] = aadhar_number

        # Search for PAN number
        if not pan_number:
            pan_match = re.search(pan_pattern, page_text, re.IGNORECASE)
            if pan_match:
                pan_number = pan_match.group(1).upper()
                # Validate PAN format: 5 letters, 4 digits, 1 letter
                if (len(pan_number) == 10 and
                    pan_number[:5].isalpha() and
                    pan_number[5:9].isdigit() and
                    pan_number[9].isalpha()):
                    # Add to ID_Cards if not already present
                    if not any(card.get("ID_Type") == "Income Tax Department" for card in detailed_data.get("ID_Cards", [])):
                        detailed_data["ID_Cards"].append({
                            "ID_Type": "Income Tax Department",
                            "Card_Holder_Name": detailed_data.get("Name", "Not found"),
                            "PAN_Number": pan_number
                        })
                    # Otherwise update existing card
                    else:
                        for card in detailed_data.get("ID_Cards", []):
                            if card.get("ID_Type") == "Income Tax Department":
                                card["PAN_Number"] = pan_number

        # Search for EPIC number
        if not epic_number:
            epic_match = re.search(epic_pattern, page_text, re.IGNORECASE)
            if epic_match:
                epic_number = epic_match.group(1).upper()
                # Validate EPIC format: 3 letters followed by 7 digits
                if len(epic_number) == 10 and epic_number[:3].isalpha() and epic_number[3:].isdigit():
                    # Add to ID_Cards if not already present
                    if not any(card.get("ID_Type") == "Election Commission of India" for card in detailed_data.get("ID_Cards", [])):
                        detailed_data["ID_Cards"].append({
                            "ID_Type": "Election Commission of India",
                            "Card_Holder_Name": detailed_data.get("Name", "Not found"),
                            "EPIC_Number": epic_number
                        })
                    # Otherwise update existing card
                    else:
                        for card in detailed_data.get("ID_Cards", []):
                            if card.get("ID_Type") == "Election Commission of India":
                                card["EPIC_Number"] = epic_number

@app.get("/")
async def root():
    return {"message": "Document OCR API is running"}

@app.post("/api/save-document")
async def save_document(request: dict):
    """
    Save document data to the database.

    Args:
        request: Dictionary containing document data

    Returns:
        Dictionary with success status and message
    """
    try:
        # Extract data from request
        file_name = request.get("fileName")
        file_content = request.get("fileContent")  # Base64 encoded
        extracted_data = request.get("extractedData")
        suid = None

        # Get SUID from extracted data
        if extracted_data and isinstance(extracted_data, dict):
            if "entities" in extracted_data and extracted_data["entities"].get("suid"):
                suid = extracted_data["entities"].get("suid")
            elif "detailedData" in extracted_data and extracted_data["detailedData"].get("SUID"):
                suid = extracted_data["detailedData"].get("SUID")
            elif "SUID" in extracted_data:
                suid = extracted_data.get("SUID")

        # Decode file content
        decoded_content = base64.b64decode(file_content) if file_content else None

        if not file_name or not decoded_content or not extracted_data:
            return {"success": False, "message": "Missing required fields"}

        # Save to database
        result = supabase_client.save_document_data(
            file_name=file_name,
            file_content=decoded_content,
            extracted_data=extracted_data,
            suid=suid
        )

        return result

    except Exception as e:
        print(f"Error saving document: {str(e)}")
        return {"success": False, "message": str(e)}


@app.get("/api/users/csv")
async def export_users_csv():
    """
    Export all user data as CSV.

    Returns:
        CSV file with all user data.
    """
    try:
        # Get all documents from the database
        documents = supabase_client.get_all_documents(include_data=True)

        if not documents:
            return {"message": "No data found"}

        # Create a CSV file in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header row
        writer.writerow([
            "Name", "SUID", "Age", "DOB", "Gender", "Address",
            "Aadhar_Number", "EPIC_Number", "PAN_Number", "ID_Types"
        ])

        # Process each document
        for doc in documents:
            # Extract data from the JSONB column
            extracted_data = doc.get("extracted_data", {})

            # Handle both old and new data formats
            if isinstance(extracted_data, str):
                try:
                    extracted_data = json.loads(extracted_data)
                except:
                    extracted_data = {}

            # Check if we have the new format with entities and detailedData
            has_entities = "entities" in extracted_data

            # Get basic information
            if has_entities:
                # New format
                entities = extracted_data.get("entities", {})
                detailed_data = extracted_data.get("detailedData", {})

                name = entities.get("name")
                suid = entities.get("suid")
                age = entities.get("age")
                dob = entities.get("dob")
                gender = entities.get("gender")
                address = entities.get("address")
                aadhar = entities.get("aadhar")
                epic = entities.get("epic")
                pan = entities.get("pan")

                # Get ID cards from detailed data
                id_cards = detailed_data.get("ID_Cards", [])
            else:
                # Old format
                name = extracted_data.get("Name")
                suid = extracted_data.get("SUID")

                # Get personal information
                personal = extracted_data.get("Form_Responses", {}).get("Sections", {}).get("Personal", {})
                age = personal.get("Age")
                dob = personal.get("DOB")
                gender = personal.get("Gender")
                address = personal.get("Address")

                # Get ID cards
                id_cards = extracted_data.get("ID_Cards", [])

                # Extract ID numbers
                aadhar = None
                epic = None
                pan = None

                for card in id_cards:
                    if card.get("ID_Type") == "Government of India":
                        aadhar = card.get("Aadhar_Number")
                    elif card.get("ID_Type") == "Election Commission of India":
                        epic = card.get("EPIC_Number")
                    elif card.get("ID_Type") == "Income Tax Department":
                        pan = card.get("PAN_Number")

            # Get ID types as comma-separated string
            id_types = []

            for card in id_cards:
                id_type = card.get("ID_Type")
                if id_type:
                    id_types.append(id_type)

            # Format DOB properly - if it's in a standard format, keep it as is
            formatted_dob = dob or ""
            if formatted_dob and formatted_dob.startswith("#"):
                formatted_dob = ""  # Clear masked DOBs

            # Format Aadhar number properly - ensure it's treated as text, not a number
            formatted_aadhar = ""
            if aadhar:
                # Remove any scientific notation by ensuring it's a string
                try:
                    # If it's a number in scientific notation
                    if 'e' in aadhar.lower() or 'E' in aadhar:
                        # Convert to a regular number string
                        formatted_aadhar = str(int(float(aadhar)))
                    else:
                        formatted_aadhar = aadhar
                except:
                    formatted_aadhar = aadhar

                # Ensure it's exactly 12 digits
                if formatted_aadhar.isdigit() and len(formatted_aadhar) == 12:
                    # Format with spaces for readability: XXXX XXXX XXXX
                    formatted_aadhar = f"{formatted_aadhar[:4]} {formatted_aadhar[4:8]} {formatted_aadhar[8:12]}"

            # Write data row
            writer.writerow([
                name or "",
                suid or "",
                age or "",
                formatted_dob,
                gender or "",
                address or "",
                formatted_aadhar,
                epic or "",
                pan or "",
                ", ".join(id_types) if id_types else ""
            ])

        # Get the CSV content
        csv_content = output.getvalue()
        output.close()

        # Return the CSV file
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=user_data_export.csv"
            }
        )

    except Exception as e:
        print(f"Error exporting users to CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/process-ocr", response_model=OCRResponse)
async def process_ocr(request: OCRRequest):
    try:
        results = []

        for file in request.files:
            try:
                # Decode base64 content
                file_content = base64.b64decode(file.content)

                # Save to temporary file
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(file_content)
                    tmp_file_path = tmp_file.name

                # Process with Azure Document AI
                result = document_ai.process_document(tmp_file_path)

                # Extract structured data
                name = result.get("name")
                suid = result.get("suid")

                # Get ID card information
                id_cards = result.get("id_cards", {})
                government_of_india_number = id_cards.get("government_of_india_number")
                income_tax_department_number = id_cards.get("income_tax_department_number")
                election_commission_number = id_cards.get("election_commission_number")

                # Format data for frontend
                detailed_data = {
                    "Name": name or "Not found",
                    "SUID": suid,
                    "Form_Responses": {
                        "Sections": {
                            "Personal": {
                                "Age": result.get("age", "Not found"),
                                "DOB": result.get("dob", "Not found"),
                                "Gender": result.get("gender", "Not found"),
                                "Address": result.get("address", "Not found"),
                                "Phone": result.get("phone", "Not found")
                            }
                        }
                    },
                    "ID_Cards": []
                }

                # Add ID cards if available
                if government_of_india_number:
                    detailed_data["ID_Cards"].append({
                        "ID_Type": "Government of India",
                        "Card_Holder_Name": name or "Not found",
                        "Aadhar_Number": government_of_india_number,
                        "Gender": result.get("gender", "Not found"),
                        "Address": result.get("address", "Not found")
                    })

                if income_tax_department_number:
                    detailed_data["ID_Cards"].append({
                        "ID_Type": "Income Tax Department",
                        "Card_Holder_Name": name or "Not found",
                        "PAN_Number": income_tax_department_number
                    })

                if election_commission_number:
                    detailed_data["ID_Cards"].append({
                        "ID_Type": "Election Commission of India",
                        "Card_Holder_Name": name or "Not found",
                        "EPIC_Number": election_commission_number
                    })

                # Print debug information
                print(f"Formatted detailed data: {detailed_data}")
                print(f"Extracted name: {name}")
                print(f"Extracted SUID: {suid}")
                print(f"Extracted ID cards: {detailed_data['ID_Cards']}")

                # Add page details
                detailed_data["Page_Details"] = {}
                for i, page_text in enumerate(result.get("raw_text", [])):
                    detailed_data["Page_Details"][f"Page_{i+1}"] = {
                        "Text": page_text[:500] + ("..." if len(page_text) > 500 else ""),
                        "Extracted_Name": name or "Not found",
                        "Extracted_SUID": suid or "Not found"
                    }

                # Search through Page_Details for ID information that might have been missed
                search_page_details_for_ids(detailed_data)

                # Update ID information from detailed_data
                updated_aadhar = None
                updated_pan = None
                updated_epic = None

                # Get updated ID information from ID_Cards
                for card in detailed_data.get("ID_Cards", []):
                    if card.get("ID_Type") == "Government of India" and card.get("Aadhar_Number"):
                        updated_aadhar = card.get("Aadhar_Number")
                    elif card.get("ID_Type") == "Income Tax Department" and card.get("PAN_Number"):
                        updated_pan = card.get("PAN_Number")
                    elif card.get("ID_Type") == "Election Commission of India" and card.get("EPIC_Number"):
                        updated_epic = card.get("EPIC_Number")

                # Create result object with all extracted data
                results.append({
                    "id": str(uuid.uuid4()),
                    "fileName": file.name,
                    "timestamp": datetime.now().isoformat(),
                    "text": "\n\n".join(result.get("raw_text", [""])) if result.get("raw_text") else "",
                    "entities": {
                        "name": name,
                        "suid": suid,
                        "pan": updated_pan or income_tax_department_number,
                        "epic": updated_epic or election_commission_number,
                        "aadhar": updated_aadhar or government_of_india_number,
                        "age": result.get("age"),
                        "dob": result.get("dob"),
                        "gender": result.get("gender"),
                        "address": result.get("address"),
                        "phone": result.get("phone")
                    },
                    "detailedData": detailed_data
                })

                # Print debug information about the result
                print(f"Created result object with ID: {results[-1]['id']}")
                print(f"Result entities: {results[-1]['entities']}")

                # Clean up temporary file
                os.unlink(tmp_file_path)

            except Exception as e:
                print(f"Error processing file {file.name}: {str(e)}")
                results.append({
                    "id": str(uuid.uuid4()),
                    "fileName": file.name,
                    "timestamp": datetime.now().isoformat(),
                    "text": "Error processing file",
                    "entities": {
                        "name": None,
                        "suid": None,
                        "pan": None,
                        "epic": None,
                        "aadhar": None
                    },
                    "error": str(e)
                })

        return {"results": results}

    except Exception as e:
        print(f"Error in OCR processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# In-memory storage for bulk upload jobs
bulk_upload_jobs = {}

@app.post("/api/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload(request: BulkUploadRequest):
    """
    Start a bulk upload job for processing multiple files.

    This endpoint accepts a list of files, uploads them to Azure Blob Storage,
    and starts a background task to process them with Azure Document AI.

    Returns:
        A job ID that can be used to check the status of the bulk upload.
    """
    try:
        # Generate a unique job ID
        job_id = str(uuid.uuid4())

        # Use the default "documents" container instead of creating a new one
        container_name = "documents"
        container_result = blob_storage.ensure_container_exists(container_name)

        if not container_result:
            raise HTTPException(status_code=500, detail="Failed to access documents container")

        # Initialize job status
        bulk_upload_jobs[job_id] = {
            "total_files": len(request.files),
            "processed_files": 0,
            "status": "uploading",
            "results": [],
            "errors": []
        }

        # Start a background task to process the files
        import asyncio
        asyncio.create_task(process_bulk_upload_wrapper(job_id, request.files, request.extractionType))

        return {
            "job_id": job_id,
            "total_files": len(request.files),
            "message": f"Bulk upload job started with {len(request.files)} files"
        }

    except Exception as e:
        print(f"Error starting bulk upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bulk-upload/{job_id}/status", response_model=BulkUploadStatusResponse)
async def bulk_upload_status(job_id: str):
    """
    Check the status of a bulk upload job.

    Args:
        job_id: The ID of the bulk upload job

    Returns:
        The current status of the job, including progress and results if complete
    """
    try:
        # Check if job exists
        if job_id not in bulk_upload_jobs:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")

        # Get job status
        job = bulk_upload_jobs[job_id]

        # Return status
        return {
            "job_id": job_id,
            "total_files": job["total_files"],
            "processed_files": job["processed_files"],
            "status": job["status"],
            "results": job["results"] if job["status"] == "completed" else None
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error checking bulk upload status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_bulk_upload_wrapper(job_id: str, files: List[FileData], extraction_type: str):
    """
    Wrapper function for the process_bulk_upload function.

    This function calls the imported process_bulk_upload function with all the necessary dependencies.

    Args:
        job_id: The ID of the bulk upload job
        files: List of files to process
        extraction_type: Type of extraction to perform
    """
    # Call the imported process_bulk_upload function with all dependencies
    await process_bulk_upload(
        job_id=job_id,
        files=files,
        extraction_type=extraction_type,
        bulk_upload_jobs=bulk_upload_jobs,
        blob_storage=blob_storage,
        document_ai=document_ai,
        supabase_client=supabase_client,
        search_page_details_for_ids=search_page_details_for_ids
    )

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8080, reload=True)
