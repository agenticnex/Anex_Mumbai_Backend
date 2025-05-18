# Google OAuth 2.0 Integration Guide

This guide explains how to set up Google OAuth 2.0 authentication for the OCR application.

## Prerequisites

- A Google Cloud account
- Access to the Supabase dashboard
- The application codebase

## Google Cloud Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Credentials"
4. Click "Create Credentials" and select "OAuth client ID"
5. Select "Web application" as the application type
6. Add a name for your OAuth client
7. Add authorized JavaScript origins:
   - Production: `https://anex-mum-bai-frontend.vercel.app`
   - Development: `http://localhost:5173`
8. Add authorized redirect URIs:
   - Production: `https://anex-mum-bai-frontend.vercel.app/auth/callback`
   - Development: `http://localhost:5173/auth/callback`
9. Click "Create"
10. Download the credentials JSON file (this has already been done and is in the project as `client_secret.json`)

## Supabase Setup

1. Go to the [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project
3. Navigate to "Authentication" > "Providers"
4. Find "Google" in the list and click on it
5. Enable the Google provider by toggling the switch
6. Enter the Client ID and Client Secret from your Google OAuth credentials
7. Set the Authorized redirect URI to match what you configured in Google Cloud
   - Production: `https://commvqgpjibmtwwpissd.supabase.co/auth/v1/callback`
8. Save the changes

## Environment Variables

The necessary environment variables have already been added to the project:

### Backend (.env)

```
GOOGLE_CLIENT_ID="your-google-client-id"
GOOGLE_CLIENT_SECRET="your-google-client-secret"
GOOGLE_REDIRECT_URI="https://your-frontend-domain.com/auth/callback"
```

### Frontend (.env)

```
VITE_GOOGLE_CLIENT_ID=your-google-client-id
VITE_GOOGLE_REDIRECT_URI=https://your-frontend-domain.com/auth/callback
```

## Testing the Integration

1. Start the backend server:
   ```
   cd Backend
   python api_server.py
   ```

2. Start the frontend development server:
   ```
   cd Frontend
   npm run dev
   ```

3. Navigate to `http://localhost:5173/auth`
4. Click the "Sign in with Google" button
5. Complete the Google authentication flow
6. You should be redirected back to the application and logged in

## Troubleshooting

If you encounter issues with the Google OAuth integration:

1. Check the browser console for errors
2. Verify that the redirect URIs are correctly configured in both Google Cloud and Supabase
3. Ensure that the environment variables are correctly set
4. Check the Supabase authentication logs for any errors

## User Profile Data

After successful Google authentication, the following user data is saved to the database:

- User ID (from Supabase)
- Email address
- Full name (from Google profile)
- Avatar URL (from Google profile)

This data is stored in the `profiles` table in the Supabase database.
