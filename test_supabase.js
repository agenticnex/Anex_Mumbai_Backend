// Test Supabase connection
const { createClient } = require('@supabase/supabase-js');
require('dotenv').config();

// Use environment variables for Supabase credentials
const SUPABASE_URL = process.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.VITE_SUPABASE_ANON_KEY;

console.log("Using Supabase URL:", SUPABASE_URL);
console.log("Using Supabase Key:", SUPABASE_ANON_KEY ? "Key is set (not showing for security)" : "Key is not set");

// Create Supabase client
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function testConnection() {
  try {
    // Try to create the documents table
    const { error: createError } = await supabase.rpc('create_documents_table', {});
    if (createError) {
      console.log("Error creating table via RPC:", createError);
      
      // Try to create the table using SQL
      console.log("Creating documents table using SQL...");
      const createTableSQL = `
        CREATE TABLE IF NOT EXISTS public.documents (
          id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
          file_name TEXT NOT NULL,
          suid TEXT,
          extracted_data JSONB,
          status TEXT DEFAULT 'completed',
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          pdf_data BYTEA
        );
        
        -- Allow public access for development purposes
        ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS "Allow public access for development" ON public.documents;
        CREATE POLICY "Allow public access for development"
          ON public.documents
          FOR ALL
          USING (true);
      `;
      
      // Execute SQL directly
      const { error: sqlError } = await supabase.rpc('pgrest_exec', { query: createTableSQL });
      if (sqlError) {
        console.log("Error executing SQL:", sqlError);
      } else {
        console.log("Successfully created documents table using SQL");
      }
    } else {
      console.log("Successfully created documents table via RPC");
    }
    
    // Test inserting a record
    const testData = {
      file_name: "test_file.pdf",
      extracted_data: { test: "data" },
      status: "completed"
    };
    
    const { data, error } = await supabase.from('documents').insert(testData).select();
    
    if (error) {
      console.error("Error inserting test record:", error);
    } else {
      console.log("Successfully inserted test record:", data);
      
      // Delete the test record
      const { error: deleteError } = await supabase.from('documents').delete().eq('id', data[0].id);
      if (deleteError) {
        console.error("Error deleting test record:", deleteError);
      } else {
        console.log("Successfully deleted test record");
      }
    }
  } catch (error) {
    console.error("Error testing Supabase connection:", error);
  }
}

testConnection();
