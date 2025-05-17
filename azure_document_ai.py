import os
import tempfile
from typing import Dict, List, Any, Optional
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

class AzureDocumentAI:
    def __init__(self):
        """Initialize Azure Document AI client with credentials from environment variables."""
        self.endpoint = os.getenv("AZURE_DOCUMENT_AI_ENDPOINT")
        self.key = os.getenv("AZURE_DOCUMENT_AI_KEY")

        if not self.endpoint or not self.key:
            raise ValueError("Azure Document AI credentials not found in environment variables")

        self.client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key)
        )

    def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Process a document using Azure Document Intelligence.

        Args:
            file_path: Path to the PDF file

        Returns:
            Dictionary containing extracted data
        """
        try:
            # Read the file content
            with open(file_path, "rb") as f:
                file_content = f.read()

            # Process the document using the file content directly
            poller = self.client.begin_analyze_document(
                "prebuilt-read",
                file_content
            )

            result = poller.result()

            # Extract all text content
            extracted_text = self._extract_text_content(result)

            # Extract structured data
            structured_data = self._extract_structured_data(extracted_text)

            # Try to extract SUID from the document
            suid = self._extract_suid(extracted_text)

            # Get all the required data
            name = structured_data.get("name")
            age = structured_data.get("age")
            dob = structured_data.get("dob")
            gender = structured_data.get("gender")
            address = structured_data.get("address")
            phone = structured_data.get("phone")
            id_cards = structured_data.get("id_cards", {})

            # Print debug information
            print(f"Extracted name: {name}")
            print(f"Extracted SUID: {suid}")
            print(f"Extracted ID cards: {id_cards}")

            return {
                "raw_text": extracted_text,
                "name": name,
                "age": age,
                "dob": dob,
                "gender": gender,
                "address": address,
                "phone": phone,
                "id_cards": id_cards,
                "suid": suid,
                "pages": len(result.pages)
            }

        except Exception as e:
            print(f"Error processing document: {str(e)}")
            raise

    def _extract_text_content(self, result) -> List[str]:
        """Extract text content from each page of the document."""
        pages_text = []

        for page_idx, page in enumerate(result.pages):
            page_text = ""
            for line in page.lines:
                page_text += line.content + "\n"
            pages_text.append(page_text)

        return pages_text

    def _extract_structured_data(self, pages_text: List[str]) -> Dict[str, Any]:
        """
        Extract structured data from document text.

        This function extracts various types of information like:
        - Personal information (name, age, DOB)
        - ID card information (Government of India, Income Tax Department, Election Commission)
        - Contact information (phone, address)
        - Gender

        Args:
            pages_text: List of text content from each page

        Returns:
            Dictionary containing structured data
        """
        # Combine all pages text for pattern matching
        all_text = " ".join(pages_text)

        # First try to extract personal information from each page individually
        names = []
        age = None
        dob = None
        gender = None
        address = None
        phone = None

        # Try to extract from individual pages first
        for page_idx, page_text in enumerate(pages_text):
            # For names, collect all possible names from all pages
            page_name = self._extract_name(page_text)
            if page_name and page_name not in names:
                names.append(page_name)

            if not age:
                age = self._extract_age(page_text)
            if not dob:
                dob = self._extract_dob(page_text)
            if not gender:
                gender = self._extract_gender(page_text)
            if not address:
                address = self._extract_address(page_text)
            if not phone:
                phone = self._extract_phone(page_text)

        # If not found in individual pages, try with all text combined
        all_text_name = self._extract_name(all_text)
        if all_text_name and all_text_name not in names:
            names.append(all_text_name)

        if not age:
            age = self._extract_age(all_text)
        if not dob:
            dob = self._extract_dob(all_text)
        if not gender:
            gender = self._extract_gender(all_text)
        if not address:
            address = self._extract_address(all_text)
        if not phone:
            phone = self._extract_phone(all_text)

        # Choose the best name from the collected names
        name = self._select_best_name(names) if names else None

        # Extract ID card information from all text
        aadhar_number = self._extract_government_of_india_number(all_text)
        pan_number = self._extract_income_tax_department_number(all_text)
        epic_number = self._extract_election_commission_number(all_text)

        # Try to extract ID information from each page individually if not found
        if not aadhar_number or not pan_number or not epic_number:
            for page_text in pages_text:
                if not aadhar_number:
                    aadhar_number = self._extract_government_of_india_number(page_text)
                if not pan_number:
                    pan_number = self._extract_income_tax_department_number(page_text)
                if not epic_number:
                    epic_number = self._extract_election_commission_number(page_text)

        # Extract various data points
        data = {
            "name": name,
            "all_names": names,  # Include all extracted names
            "age": age,
            "dob": dob,
            "id_cards": {
                "government_of_india_number": aadhar_number,
                "income_tax_department_number": pan_number,
                "election_commission_number": epic_number
            },
            "phone": phone,
            "address": address,
            "gender": gender
        }

        return data

    def _extract_suid(self, pages_text: List[str]) -> Optional[str]:
        """Extract SUID from document text."""
        all_text = " ".join(pages_text)

        # Pattern for SUID format like 4/9/2/127A_U/G/14_1
        suid_pattern = r'\d+/\d+/\d+/\w+_\w+/\w+/\d+_\d+'
        match = re.search(suid_pattern, all_text)

        if match:
            return match.group(0)
        return None

    # Helper methods for extracting specific data types
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract person's name from text using various patterns and heuristics"""
        try:
            # Look for common name patterns with labels
            name_patterns = [
                # Common name labels
                r'Name\s*:?\s*([A-Za-z\s.]+)',
                r'Name of (?:the|applicant|person|candidate|individual)\s*:?\s*([A-Za-z\s.]+)',
                r'(?:Full Name|Applicant[\'s]* Name)\s*:?\s*([A-Za-z\s.]+)',

                # Titles followed by names
                r'(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+([A-Za-z\s.]+)',
                r'(?:Shri|Smt|Kumari|श्री|श्रीमती|कुमारी)\.?\s+([A-Za-z\s.]+)',

                # Relationship indicators
                r'(?:S/o|D/o|W/o|C/o)\s+(?:Shri|Smt|Sh|श्री|श्रीमती)?\.?\s*([A-Za-z\s.]+)',
                r'(?:Son of|Daughter of|Wife of|Child of)\s+(?:Shri|Smt|Sh|श्री|श्रीमती)?\.?\s*([A-Za-z\s.]+)'
            ]

            # Try each pattern
            for pattern in name_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    # Remove any trailing punctuation or numbers
                    name = re.sub(r'[0-9.,;:].*$', '', name).strip()
                    # Check if name is reasonable (at least 2 characters, not just whitespace)
                    if len(name) >= 2 and not name.isspace():
                        # Check if name contains common non-name words
                        if not any(word.lower() in name.lower() for word in ['government', 'department', 'ministry', 'india', 'certificate', 'identity', 'card']):
                            return name

            # Look for lines that might contain names
            lines = text.split('\n')
            for line in lines:
                line = line.strip()

                # Skip very short or very long lines
                if len(line) < 3 or len(line) > 50:
                    continue

                # Look for lines that might be names (2-4 capitalized words)
                words = line.split()
                if 2 <= len(words) <= 4:
                    # Check if most words are capitalized
                    capitalized_words = [w for w in words if w[0:1].isupper() and len(w) > 1]
                    if len(capitalized_words) >= 2 and len(capitalized_words) == len(words):
                        potential_name = ' '.join(capitalized_words)
                        # Filter out common non-name capitalized phrases
                        if not any(phrase in potential_name.lower() for phrase in ['government', 'department', 'ministry', 'india', 'certificate', 'identity', 'card']):
                            return potential_name

            # Look for specific document sections that might contain names
            # For example, in ID cards, the name is often prominently displayed
            short_lines = [line.strip() for line in lines if 3 <= len(line.strip()) <= 30]
            for line in short_lines:
                # Skip lines with common non-name words
                if any(word in line.lower() for word in ['government', 'department', 'ministry', 'india', 'certificate', 'identity', 'card', 'date', 'birth', 'address']):
                    continue

                # Check if line has mostly alphabetic characters (typical for names)
                alpha_chars = sum(c.isalpha() or c.isspace() for c in line)
                if alpha_chars / len(line) > 0.8 and ' ' in line:
                    # This is likely a name
                    return line

            return None

        except Exception as e:
            print(f"Error extracting name: {str(e)}")
            return None

    def _extract_age(self, text: str) -> Optional[str]:
        # Look for age patterns
        age_patterns = [
            r'Age\s*:?\s*(\d{1,3})',
            r'(?:Age|Years)\s*:?\s*(\d{1,3})\s*(?:Years|Yrs|Y)',
            r'(\d{1,3})\s*(?:Years|Yrs|Y)(?:\s*old)?'
        ]

        for pattern in age_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                age = match.group(1)
                # Validate age is reasonable (0-120)
                try:
                    age_int = int(age)
                    if 0 <= age_int <= 120:
                        return age
                except ValueError:
                    pass

        # If we have a DOB, try to calculate age
        dob = self._extract_dob(text)
        if dob:
            try:
                # Try to parse the date
                from datetime import datetime

                # Extract numbers from the DOB
                numbers = re.findall(r'\d+', dob)
                if len(numbers) == 3:
                    # Assume format is DD/MM/YYYY or similar
                    day, month, year = int(numbers[0]), int(numbers[1]), int(numbers[2])

                    # Fix two-digit years
                    if year < 100:
                        if year > 30:  # Arbitrary cutoff
                            year += 1900
                        else:
                            year += 2000

                    # Calculate age
                    today = datetime.now()
                    birth_date = datetime(year, month, day)
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

                    if 0 <= age <= 120:
                        return str(age)
            except Exception as e:
                print(f"Error calculating age from DOB: {str(e)}")
                pass

        return None

    def _extract_dob(self, text: str) -> Optional[str]:
        # Various date formats
        dob_patterns = [
            r'(?:Date of Birth|DOB|D\.O\.B\.|Birth Date|Born on)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(?:Date of Birth|DOB|D\.O\.B\.|Birth Date|Born on)\s*:?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
            r'(?:Date of Birth|DOB|D\.O\.B\.|Birth Date|Born on)\s*:?\s*(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})'
        ]

        for pattern in dob_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        # Look for standalone date patterns that might be DOB
        date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',
            r'(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})'
        ]

        # Only use standalone date patterns if we see birth-related words nearby
        if re.search(r'birth|born|dob', text, re.IGNORECASE):
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)

        return None

    def _extract_government_of_india_number(self, text: str) -> Optional[str]:
        """Extract Government of India number (Aadhar - 12 digits, may have spaces)"""
        # Look for Aadhar number (12 digits, may have spaces)
        patterns = [
            # Patterns with labels
            r'(?:Government of India|Aadhar|Aadhaar|आधार)\s*(?:Number|No|Card|ID)?\s*:?\s*(\d{4}\s*\d{4}\s*\d{4})',
            r'(?:Government of India|Aadhar|Aadhaar|आधार)\s*(?:Number|No|Card|ID)?\s*:?\s*(\d{12})',

            # Patterns without labels but with proper formatting
            r'\b(\d{4}\s+\d{4}\s+\d{4})\b',
            r'\b(\d{4}-\d{4}-\d{4})\b',

            # Any 12-digit number (as a fallback)
            r'\b(\d{12})\b'
        ]

        # Check if document contains "Government of India" or Aadhar-related keywords
        aadhar_keywords = ["Government of India", "Aadhar", "Aadhaar", "आधार", "UIDAI"]
        if any(keyword in text for keyword in aadhar_keywords):
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Remove any spaces or dashes to get clean 12-digit number
                    aadhar = re.sub(r'[\s-]', '', match.group(1))
                    # Validate it's exactly 12 digits
                    if len(aadhar) == 12 and aadhar.isdigit():
                        return aadhar

        # If not found with keywords, try to find any matching pattern
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Remove any spaces or dashes to get clean 12-digit number
                aadhar = re.sub(r'[\s-]', '', match.group(1))
                # Validate it's exactly 12 digits
                if len(aadhar) == 12 and aadhar.isdigit():
                    return aadhar

        return None

    def _extract_income_tax_department_number(self, text: str) -> Optional[str]:
        """Extract Income Tax Department number (PAN - 10 characters: 5 letters, 4 digits, 1 letter)"""
        # PAN card format: 5 uppercase letters, 4 digits, 1 uppercase letter (e.g., "AYGPM6214N")
        patterns = [
            # Patterns with labels
            r'(?:Income Tax Department|PAN|Permanent Account Number)\s*(?:Number|No|Card|ID)?\s*:?\s*([A-Z]{5}\d{4}[A-Z])',

            # Pattern without labels
            r'\b([A-Z]{5}\d{4}[A-Z])\b'
        ]

        # Check if document contains "Income Tax Department" or PAN-related keywords
        pan_keywords = ["Income Tax Department", "PAN", "Permanent Account Number", "Income Tax"]
        if any(keyword in text for keyword in pan_keywords):
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    pan = match.group(1).upper()  # Ensure uppercase
                    # Validate PAN format: 5 letters, 4 digits, 1 letter
                    if (len(pan) == 10 and
                        pan[:5].isalpha() and
                        pan[5:9].isdigit() and
                        pan[9].isalpha()):
                        return pan

        # If not found with keywords, try to find any matching pattern
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                pan = match.group(1).upper()  # Ensure uppercase
                # Validate PAN format: 5 letters, 4 digits, 1 letter
                if (len(pan) == 10 and
                    pan[:5].isalpha() and
                    pan[5:9].isdigit() and
                    pan[9].isalpha()):
                    return pan

        return None

    def _extract_election_commission_number(self, text: str) -> Optional[str]:
        """Extract Election Commission of India number (EPIC/Voter ID - 10 characters: 3 letters followed by 7 digits)"""
        # EPIC/Voter ID format: 3 uppercase letters followed by 7 digits (e.g., "RCT2854453")
        patterns = [
            # Standard format with labels
            r'(?:Election Commission of India|Voter|Electoral|EPIC|IDENTITY)\s*(?:ID|Card|Number|No)?\s*:?\s*([A-Z]{3}\d{7})\b',

            # Format without labels
            r'\b([A-Z]{3}\d{7})\b',

            # Other common formats with labels
            r'(?:Election Commission of India|Voter|Electoral|EPIC|IDENTITY)\s*(?:ID|Card|Number|No)?\s*:?\s*([A-Z]{2,3}\d{6,8})\b',

            # Format with slashes (some voter IDs are displayed with slashes)
            r'(?:Election Commission of India|Voter|Electoral|EPIC|IDENTITY)\s*(?:ID|Card|Number|No)?\s*:?\s*([A-Z]{2,3}/\d{1,3}/\d{1,3}/\d{5,8})',

            # Legacy formats that might still be in use
            r'(?:ELECTION COMMISSION OF INDIA|IDENTITY CARD)\s+([A-Z]{3}\d{5,8})\b'
        ]

        # Check if document contains Election Commission related text
        election_keywords = [
            "ELECTION COMMISSION", "IDENTITY CARD", "VOTER", "EPIC",
            "भारत निर्वाचन आयोग", "मतदाता", "ELECTORAL"
        ]

        # First, try to find the standard format (3 letters + 7 digits)
        standard_pattern = r'\b([A-Z]{3}\d{7})\b'

        # If document contains election-related text, prioritize extraction
        if any(keyword.lower() in text.lower() for keyword in election_keywords):
            # First try the standard format
            match = re.search(standard_pattern, text, re.IGNORECASE)
            if match:
                epic = match.group(1).upper()
                if len(epic) == 10 and epic[:3].isalpha() and epic[3:].isdigit():
                    return epic

            # Try each pattern in order
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    epic = match.group(1).upper()
                    # For standard format, validate strictly
                    if len(epic) == 10 and epic[:3].isalpha() and epic[3:].isdigit():
                        return epic
                    # For other formats, just return if it looks reasonable
                    elif len(epic) >= 8 and len(epic) <= 12:
                        return epic

        # If no election keywords found, still try the standard format as a fallback
        match = re.search(standard_pattern, text, re.IGNORECASE)
        if match:
            epic = match.group(1).upper()
            if len(epic) == 10 and epic[:3].isalpha() and epic[3:].isdigit():
                return epic

        # Try other patterns as a last resort
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                epic = match.group(1).upper()
                if len(epic) >= 8 and len(epic) <= 12:
                    return epic

        return None

    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number (10 digits, may have country code)"""
        try:
            # First, try to find any 10-digit number in the text
            digit_match = re.search(r'(?<!\d)(\d{10})(?!\d)', text)
            if digit_match:
                return digit_match.group(1)

            # Look for phone with label
            label_match = re.search(r'(?:Phone|Mobile|Tel|Contact|Cell|फोन|मोबाइल)\s*(?:Number|No|#|नंबर)?\s*:?\s*(\+?\d{1,3}[-\s.]?\d{3,5}[-\s.]?\d{5,7})', text)
            if label_match:
                phone = label_match.group(1)
                cleaned = ''.join(c for c in phone if c.isdigit())
                if len(cleaned) >= 10:
                    return cleaned

            # Phone with country code
            country_match = re.search(r'(\+?\d{1,3}[-\s.]?\d{3,5}[-\s.]?\d{5,7})', text)
            if country_match:
                phone = country_match.group(1)
                cleaned = ''.join(c for c in phone if c.isdigit())
                if len(cleaned) >= 10:
                    return cleaned

            # Phone with separators
            separator_match = re.search(r'\b(\d{3})[-\s.](\d{3})[-\s.](\d{4})\b', text)
            if separator_match:
                return f"{separator_match.group(1)}{separator_match.group(2)}{separator_match.group(3)}"

            # Phone with parentheses - handle carefully to avoid "no such group" error
            parentheses_match = re.search(r'\((\d{3})\)[-\s.]?(\d{3})[-\s.]?(\d{4})', text)
            if parentheses_match and parentheses_match.lastindex >= 3:
                return f"{parentheses_match.group(1)}{parentheses_match.group(2)}{parentheses_match.group(3)}"

            # Look for any digits that might be a phone number
            all_digits = re.findall(r'\d+', text)
            for digits in all_digits:
                if len(digits) == 10:
                    return digits

        except Exception as e:
            print(f"Error extracting phone number: {str(e)}")

        return None

    def _extract_address(self, text: str) -> Optional[str]:
        """Extract address from text"""
        # Address patterns are complex, look for common indicators
        address_patterns = [
            # Address with label followed by multiline text
            r'(?:Address|Residence|Add|Addr|पता)\s*:?\s*([A-Za-z0-9\s,.()/\\-]+(?:Road|Street|Lane|Avenue|Colony|Nagar|Village|District|City|State|Pincode|Pin|Postal Code|Post|ZIP)[A-Za-z0-9\s,.()/\\-]+)',

            # Address with label followed by comma-separated parts
            r'(?:Address|Residence|Add|Addr|पता)\s*:?\s*([^,\n]+,[^,\n]+,[^,\n]+(?:,[^,\n]+){0,5})',

            # Address with label followed by any text until end of line or next label
            r'(?:Address|Residence|Add|Addr|पता)\s*:?\s*(.+?)(?=\n\s*[A-Za-z]+\s*:|$)',

            # Lines containing postal keywords
            r'([A-Za-z0-9\s,.()/\\-]+(?:Road|Street|Lane|Avenue|Colony|Nagar|Village)[A-Za-z0-9\s,.()/\\-]+(?:District|City|State|Pincode|Pin|Postal Code|Post|ZIP)[A-Za-z0-9\s,.()/\\-]+)',

            # Lines with PIN code or ZIP code
            r'([A-Za-z0-9\s,.()/\\-]+(?:PIN|Pincode|Postal Code|Post|ZIP)\s*:?\s*\d{5,6}[A-Za-z0-9\s,.()/\\-]*)',

            # Any line with multiple commas (typical address format)
            r'([A-Za-z0-9\s.()/\\-]+,[A-Za-z0-9\s.()/\\-]+,[A-Za-z0-9\s.()/\\-]+(?:,[A-Za-z0-9\s.()/\\-]+){1,3})'
        ]

        # Try each pattern
        for pattern in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                address = match.group(1).strip()
                # Clean up the address
                address = re.sub(r'\s+', ' ', address)  # Replace multiple spaces with single space
                address = re.sub(r'^\s*:+\s*', '', address)  # Remove leading colons

                # Check if address is reasonable (at least 10 characters)
                if len(address) >= 10:
                    return address

        # If no match found with patterns, try to find address by looking for PIN code
        pin_match = re.search(r'(?:PIN|Pincode|Postal Code|Post|ZIP)\s*:?\s*(\d{5,6})', text, re.IGNORECASE)
        if pin_match:
            # Try to extract a few lines around the PIN code
            pin_pos = text.find(pin_match.group(0))
            if pin_pos > 0:
                # Get text from 100 characters before PIN to 20 characters after
                start_pos = max(0, pin_pos - 100)
                end_pos = min(len(text), pin_pos + len(pin_match.group(0)) + 20)
                address_context = text[start_pos:end_pos]

                # Clean up the extracted context
                address_context = re.sub(r'\s+', ' ', address_context)

                if len(address_context) >= 10:
                    return address_context.strip()

        return None

    def _select_best_name(self, names: List[str]) -> Optional[str]:
        """
        Select the best name from a list of extracted names.

        Args:
            names: List of extracted names

        Returns:
            The best name from the list, or None if the list is empty
        """
        if not names:
            return None

        if len(names) == 1:
            return names[0]

        # Score each name based on various criteria
        name_scores = []

        for name in names:
            score = 0

            # Prefer names with 2-3 words (first, middle, last name)
            words = name.split()
            if 2 <= len(words) <= 3:
                score += 3
            elif len(words) > 3:
                score += 1

            # Prefer names where all words are capitalized
            if all(word[0].isupper() for word in words if word):
                score += 2

            # Prefer names with reasonable length
            if 10 <= len(name) <= 30:
                score += 2
            elif 5 <= len(name) < 10:
                score += 1

            # Prefer names without numbers or special characters
            if all(c.isalpha() or c.isspace() for c in name):
                score += 2

            name_scores.append((name, score))

        # Sort by score (descending)
        name_scores.sort(key=lambda x: x[1], reverse=True)

        # Return the highest-scoring name
        return name_scores[0][0]

    def _extract_gender(self, text: str) -> Optional[str]:
        """Extract gender information from text"""
        # Look for explicit gender/sex mentions
        gender_patterns = [
            r'(?:Gender|Sex)\s*:?\s*(Male|Female|Other|M|F|O)',
            r'\b(Male|Female|M/F)\b',
            r'(?:Gender|Sex)\s*:?\s*(M|F)'
        ]

        for pattern in gender_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                gender = match.group(1).lower()
                if gender in ['m', 'male', 'm/f']:
                    return 'Male'
                elif gender in ['f', 'female']:
                    return 'Female'
                else:
                    return 'Other'

        # Look for gender indicators in the text
        male_indicators = ['son of', 's/o', 'mr.', 'mr ', 'shri', 'kumar', 'male', 'he', 'his', 'him']
        female_indicators = ['daughter of', 'd/o', 'wife of', 'w/o', 'mrs.', 'mrs ', 'miss', 'ms.', 'ms ', 'smt', 'kumari', 'female', 'she', 'her']

        text_lower = text.lower()

        # Count occurrences of gender indicators
        male_count = sum(1 for indicator in male_indicators if indicator in text_lower)
        female_count = sum(1 for indicator in female_indicators if indicator in text_lower)

        # Determine gender based on indicator counts
        if male_count > female_count:
            return 'Male'
        elif female_count > male_count:
            return 'Female'

        return None
