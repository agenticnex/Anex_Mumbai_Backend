// Script to run SQL directly against Supabase
const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');

// Get Supabase credentials
const SUPABASE_URL = "https://commvqgpjibmtwwpissd.supabase.co";
const SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNvbW12cWdwamlibXR3d3Bpc3NkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NjMzNzYzMywiZXhwIjoyMDYxOTEzNjMzfQ.y7e3OYj4cGzRbkZGKKfG7dB8a5LMFeMEeVOK4ifG-IM";

// Create Supabase client
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

// Read SQL file
const sql = fs.readFileSync('./create_documents_table.sql', 'utf8');

// Execute SQL
async function runSQL() {
  try {
    console.log("Running SQL script...");
    
    // Try using the pgrest_exec RPC function
    const { data, error } = await supabase.rpc('pgrest_exec', { query: sql });
    
    if (error) {
      console.error("Error executing SQL with pgrest_exec:", error);
      
      // Try using direct fetch as a fallback
      try {
        console.log("Trying direct fetch...");
        
        const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/pgrest_exec`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            'apikey': SUPABASE_SERVICE_ROLE_KEY
          },
          body: JSON.stringify({ query: sql })
        });
        
        if (!response.ok) {
          console.error("Error with direct fetch:", await response.text());
        } else {
          console.log("SQL executed successfully with direct fetch");
        }
      } catch (fetchError) {
        console.error("Error with direct fetch:", fetchError);
      }
    } else {
      console.log("SQL executed successfully with pgrest_exec");
      console.log("Result:", data);
    }
    
    // Verify the table exists
    const { data: tableData, error: tableError } = await supabase
      .from('documents')
      .select('*')
      .limit(10);
    
    if (tableError) {
      console.error("Error verifying table:", tableError);
    } else {
      console.log("Table exists with", tableData.length, "records");
      console.log("Sample data:", tableData);
    }
  } catch (error) {
    console.error("Error running SQL:", error);
  }
}

// Run the SQL
runSQL();
