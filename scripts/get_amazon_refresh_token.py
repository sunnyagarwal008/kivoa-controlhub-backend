#!/usr/bin/env python3
"""
Helper script to get Amazon SP-API refresh token
This script will guide you through the OAuth flow to get your refresh token.
"""
import os
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs

# Your Amazon app credentials (set via environment variables)
CLIENT_ID = os.environ.get("AMAZON_LWA_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("AMAZON_LWA_CLIENT_SECRET", "")

def main():
    print("=" * 70)
    print("Amazon SP-API Refresh Token Generator")
    print("=" * 70)
    print()
    
    # Step 1: Build authorization URL for self-authorization
    # Note: For self-authorization, we need to use the seller central apps page
    auth_url = (
        f"https://sellercentral.amazon.in/apps/authorize/consent"
        f"?application_id={CLIENT_ID}"
        f"&state=test123"
    )
    
    print("STEP 1: Authorize the application")
    print("-" * 70)
    print("Opening authorization URL in your browser...")
    print()
    print("If the browser doesn't open automatically, copy this URL:")
    print(auth_url)
    print()
    
    try:
        webbrowser.open(auth_url)
    except:
        print("Could not open browser automatically. Please open the URL manually.")
    
    print("Instructions:")
    print("1. Log in to your Amazon Seller Central account if prompted")
    print("2. Review the permissions and click 'Authorize'")
    print("3. You'll be redirected to a URL (might show an error page)")
    print("4. Copy the ENTIRE URL from your browser's address bar")
    print()
    
    # Step 2: Get the authorization code from user
    print("STEP 2: Get the authorization code")
    print("-" * 70)
    redirect_url = input("Paste the full redirect URL here: ").strip()
    
    if not redirect_url:
        print("\n✗ Error: No URL provided")
        return
    
    # Extract code from URL
    try:
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)
        code = params.get('code', [None])[0]
        
        if not code:
            print("\n✗ Error: Could not find 'code' parameter in URL")
            print("Make sure you copied the complete URL after authorization")
            return
        
        print(f"\n✓ Found authorization code: {code[:20]}...")
        
    except Exception as e:
        print(f"\n✗ Error parsing URL: {str(e)}")
        return
    
    # Step 3: Exchange code for refresh token
    print("\nSTEP 3: Exchange code for refresh token")
    print("-" * 70)
    print("Requesting tokens from Amazon...")
    
    try:
        response = requests.post(
            'https://api.amazon.com/auth/o2/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET
            }
        )
        
        if response.status_code == 200:
            tokens = response.json()
            
            print("\n" + "=" * 70)
            print("✓ SUCCESS! Here are your tokens:")
            print("=" * 70)
            print()
            print("Access Token (expires in 1 hour):")
            print(f"  {tokens['access_token'][:50]}...")
            print()
            print("Refresh Token (valid for 1 year):")
            print(f"  {tokens['refresh_token']}")
            print()
            print("=" * 70)
            print("Add this to your .env file:")
            print("=" * 70)
            print(f"AMAZON_LWA_REFRESH_TOKEN={tokens['refresh_token']}")
            print()
            print("Next steps:")
            print("1. Copy the refresh token to your .env file")
            print("2. Add your AWS credentials to .env")
            print("3. Run: python scripts/create_product_channels_table.py")
            print("4. Restart your Flask application")
            print("5. Test with: POST /api/products/<id>/channels/amazon/sync")
            print()
            
        else:
            print(f"\n✗ Error: {response.status_code}")
            print("Response:", response.text)
            print()
            print("Common issues:")
            print("- Authorization code expired (valid for 5 minutes only)")
            print("- Code already used (get a new one)")
            print("- Invalid client credentials")
            print()
            print("Try running the script again and authorize quickly.")
            
    except Exception as e:
        print(f"\n✗ Error requesting tokens: {str(e)}")
        return

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")
