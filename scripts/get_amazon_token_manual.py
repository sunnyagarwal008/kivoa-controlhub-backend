#!/usr/bin/env python3
"""
Manual Amazon refresh token generator
Use this if the automated script doesn't work due to "application failed to load" error
"""
import os
import requests

CLIENT_ID = os.environ.get("AMAZON_LWA_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("AMAZON_LWA_CLIENT_SECRET", "")

print("=" * 70)
print("Amazon SP-API Manual Token Generator")
print("=" * 70)
print()
print("This script uses manual authorization with out-of-band redirect.")
print("Amazon will display the authorization code directly on the page.")
print()

# Show authorization URL with out-of-band redirect
auth_url = (
    f"https://sellercentral.amazon.in/apps/authorize/consent"
    f"?application_id={CLIENT_ID}"
    f"&state=test123"
    f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
)

print("STEP 1: Authorize the application")
print("-" * 70)
print()
print("Open this URL in your browser:")
print()
print(auth_url)
print()
print("Instructions:")
print("1. Log in to your Amazon Seller Central account")
print("2. Review the permissions and click 'Authorize'")
print("3. Amazon will display an authorization code on the page")
print("4. Copy the entire authorization code")
print()
print("Note: The code expires in 5 minutes, so complete this quickly!")
print()

# Get authorization code from user
code = input("Enter the authorization code here: ").strip()

if not code:
    print("\n✗ Error: No code provided")
    exit(1)

print()
print("STEP 2: Exchange code for refresh token")
print("-" * 70)
print("Requesting tokens from Amazon...")
print()

try:
    response = requests.post(
        'https://api.amazon.com/auth/o2/token',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'
        }
    )
    
    if response.status_code == 200:
        tokens = response.json()
        print("=" * 70)
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
        print("=" * 70)
        print(f"✗ Error: {response.status_code}")
        print("=" * 70)
        print()
        print("Response:", response.text)
        print()
        print("Common issues:")
        print("- Authorization code expired (valid for 5 minutes only)")
        print("- Code already used (get a new one)")
        print("- Invalid client credentials")
        print("- Redirect URI mismatch")
        print()
        print("Try running the script again and authorize quickly.")
        print()
        
except requests.exceptions.RequestException as e:
    print(f"\n✗ Network error: {str(e)}")
    print("Check your internet connection and try again.")
except Exception as e:
    print(f"\n✗ Unexpected error: {str(e)}")

print()
print("If you continue to have issues, see:")
print("  docs/AMAZON_SELF_AUTHORIZATION.md")
print()
