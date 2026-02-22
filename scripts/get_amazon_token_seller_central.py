#!/usr/bin/env python3
"""
Amazon SP-API Token Generator for Seller Central Self-Authorization

This script helps you get a refresh token after registering your app in Seller Central.

Prerequisites:
1. Register your app in Seller Central Developer Console
2. Get your LWA Client ID and Client Secret
3. Have your app authorized in Seller Central
"""
import requests
import sys

def get_credentials():
    """Prompt user for their credentials"""
    print("=" * 70)
    print("Amazon Seller Central - Refresh Token Generator")
    print("=" * 70)
    print()
    print("First, let's get your credentials from Seller Central.")
    print()
    print("If you haven't registered your app yet:")
    print("1. Go to: https://sellercentral.amazon.in/")
    print("2. Settings → User Permissions → Developer Central")
    print("3. Register a new app and get your LWA credentials")
    print()
    print("-" * 70)
    print()
    
    client_id = input("Enter your LWA Client ID: ").strip()
    if not client_id:
        print("Error: Client ID is required")
        sys.exit(1)
    
    client_secret = input("Enter your LWA Client Secret: ").strip()
    if not client_secret:
        print("Error: Client Secret is required")
        sys.exit(1)
    
    return client_id, client_secret

def get_refresh_token(client_id, client_secret):
    """Get refresh token using authorization code"""
    print()
    print("=" * 70)
    print("STEP 1: Authorize Your Application")
    print("=" * 70)
    print()
    
    # Build authorization URL
    auth_url = (
        f"https://sellercentral.amazon.in/apps/authorize/consent"
        f"?application_id={client_id}"
        f"&state=test123"
        f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
    )
    
    print("Open this URL in your browser:")
    print()
    print(auth_url)
    print()
    print("Instructions:")
    print("1. Log in to Seller Central if prompted")
    print("2. Review permissions and click 'Authorize'")
    print("3. Amazon will display an authorization code")
    print("4. Copy the code (it expires in 5 minutes!)")
    print()
    
    code = input("Enter the authorization code: ").strip()
    
    if not code:
        print("\nError: No authorization code provided")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("STEP 2: Exchange Code for Refresh Token")
    print("=" * 70)
    print()
    print("Requesting tokens from Amazon...")
    
    try:
        response = requests.post(
            'https://api.amazon.com/auth/o2/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'
            }
        )
        
        if response.status_code == 200:
            tokens = response.json()
            
            print()
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
            print("Add these to your .env file:")
            print("=" * 70)
            print()
            print(f"AMAZON_LWA_CLIENT_ID={client_id}")
            print(f"AMAZON_LWA_CLIENT_SECRET={client_secret}")
            print(f"AMAZON_LWA_REFRESH_TOKEN={tokens['refresh_token']}")
            print()
            print("Also add your Seller ID and AWS credentials:")
            print("AMAZON_SELLER_ID=A1XXXXXXXXXXXXX  # From Seller Central Account Info")
            print("AMAZON_AWS_ACCESS_KEY=AKIA...  # Your AWS access key")
            print("AMAZON_AWS_SECRET_KEY=...  # Your AWS secret key")
            print()
            print("=" * 70)
            print("Next Steps:")
            print("=" * 70)
            print("1. Update your .env file with the credentials above")
            print("2. Run: python scripts/create_product_channels_table.py")
            print("3. Restart your Flask application")
            print("4. Test: POST /api/products/<id>/channels/amazon/sync")
            print()
            
        else:
            print()
            print("=" * 70)
            print(f"✗ Error: {response.status_code}")
            print("=" * 70)
            print()
            print("Response:", response.text)
            print()
            print("Common issues:")
            print("- Authorization code expired (valid for 5 minutes)")
            print("- Code already used (get a new one)")
            print("- Invalid client credentials")
            print("- Redirect URI mismatch")
            print()
            print("Try running the script again.")
            
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Network error: {str(e)}")
        print("Check your internet connection and try again.")
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")

def main():
    try:
        client_id, client_secret = get_credentials()
        get_refresh_token(client_id, client_secret)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        print("\nFor help, see: docs/AMAZON_SELLER_CENTRAL_SETUP.md")

if __name__ == '__main__':
    main()
