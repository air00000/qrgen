#!/usr/bin/env python3
"""
Test suite for new API requirements:
1. Missing data should not raise errors
2. Photo input changed from base64 to Data URI
3. Overlong strings truncated with ellipsis
4. Unified method names across providers
"""

import sys
import base64
import requests
from pathlib import Path

# Test server configuration
BASE_URL = "http://localhost:8000"
API_KEY = "test_key_123"  # Replace with actual key

# Sample base64 image (1x1 pixel PNG)
SAMPLE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

# Data URI versions
DATA_URI_PNG = f"data:image/png;base64,{SAMPLE_BASE64}"
DATA_URI_JPEG = f"data:image/jpeg;base64,{SAMPLE_BASE64}"


def test_missing_fields_no_error():
    """Test that missing optional fields don't cause errors"""
    print("\n=== Test: Missing Fields Should Not Raise Errors ===")
    
    tests = [
        {
            "name": "Missing photo and URL",
            "data": {
                "country": "nl",
                "service": "marktplaats",
                "method": "qr",
                "title": "Test Item",
                "price": 10.0,
                # url and photo missing
            }
        },
        {
            "name": "Missing all optional fields for Subito",
            "data": {
                "country": "it",
                "service": "subito",
                "method": "email_request",
                "title": "Test",
                "price": 5.0,
                # photo, name, address all missing
            }
        },
        {
            "name": "Missing seller info for Wallapop",
            "data": {
                "country": "es",
                "service": "wallapop",
                "method": "email_request",
                "title": "Test",
                "price": 20.0,
                # seller_name missing, should use empty string
            }
        },
    ]
    
    for test in tests:
        print(f"\n  Testing: {test['name']}")
        response = requests.post(
            f"{BASE_URL}/generate",
            json=test["data"],
            headers={"X-API-Key": API_KEY}
        )
        
        if response.status_code == 200:
            print(f"    ✓ Success - Generated image ({len(response.content)} bytes)")
        else:
            print(f"    ✗ Failed - {response.status_code}: {response.text}")
            return False
    
    print("\n✓ All missing fields tests passed")
    return True


def test_data_uri_format():
    """Test that Data URI format is accepted for photos"""
    print("\n=== Test: Data URI Photo Format ===")
    
    tests = [
        {
            "name": "Data URI with image/png",
            "data": {
                "country": "nl",
                "service": "marktplaats",
                "method": "qr",
                "title": "Test Item",
                "price": 10.0,
                "url": "https://example.com",
                "photo": DATA_URI_PNG
            }
        },
        {
            "name": "Data URI with image/jpeg",
            "data": {
                "country": "es",
                "service": "wallapop",
                "method": "email_request",
                "title": "Test",
                "price": 15.0,
                "seller_name": "John",
                "photo": DATA_URI_JPEG,
                "seller_photo": DATA_URI_PNG
            }
        },
        {
            "name": "Malformed Data URI (should not fail)",
            "data": {
                "country": "nl",
                "service": "marktplaats",
                "method": "qr",
                "title": "Test",
                "price": 5.0,
                "url": "https://example.com",
                "photo": "data:invalid_format"
            }
        },
    ]
    
    for test in tests:
        print(f"\n  Testing: {test['name']}")
        response = requests.post(
            f"{BASE_URL}/generate",
            json=test["data"],
            headers={"X-API-Key": API_KEY}
        )
        
        if response.status_code == 200:
            print(f"    ✓ Success - Generated image ({len(response.content)} bytes)")
        else:
            print(f"    ✗ Failed - {response.status_code}: {response.text}")
            return False
    
    print("\n✓ All Data URI tests passed")
    return True


def test_text_truncation():
    """Test that overlong strings are truncated"""
    print("\n=== Test: Text Truncation ===")
    
    # Create very long strings
    long_title = "A" * 150  # Exceeds MAX_LENGTH_TITLE (100)
    long_name = "B" * 80    # Exceeds MAX_LENGTH_NAME (50)
    long_address = "C" * 150  # Exceeds MAX_LENGTH_ADDRESS (100)
    long_url = "https://example.com/" + "x" * 600  # Exceeds MAX_LENGTH_URL (500)
    
    tests = [
        {
            "name": "Long title truncation",
            "data": {
                "country": "nl",
                "service": "marktplaats",
                "method": "qr",
                "title": long_title,
                "price": 10.0,
                "url": "https://example.com"
            }
        },
        {
            "name": "Long name and address truncation",
            "data": {
                "country": "it",
                "service": "subito",
                "method": "qr",
                "title": long_title,
                "price": 5.0,
                "url": "https://example.com",
                "name": long_name,
                "address": long_address
            }
        },
        {
            "name": "Long URL truncation",
            "data": {
                "country": "nl",
                "service": "marktplaats",
                "method": "qr",
                "title": "Test",
                "price": 10.0,
                "url": long_url
            }
        },
    ]
    
    for test in tests:
        print(f"\n  Testing: {test['name']}")
        response = requests.post(
            f"{BASE_URL}/generate",
            json=test["data"],
            headers={"X-API-Key": API_KEY}
        )
        
        if response.status_code == 200:
            print(f"    ✓ Success - Generated image ({len(response.content)} bytes)")
        else:
            print(f"    ✗ Failed - {response.status_code}: {response.text}")
            return False
    
    print("\n✓ All truncation tests passed")
    return True


def test_unified_method_names():
    """Test that unified method names work across all providers"""
    print("\n=== Test: Unified Method Names ===")
    
    # Test canonical method set: qr, email_request, email_confirm, sms_request, sms_confirm
    tests = [
        {
            "name": "Subito email_confirm",
            "data": {
                "country": "it",
                "service": "subito",
                "method": "email_confirm",
                "title": "Test",
                "price": 10.0
            }
        },
        {
            "name": "Wallapop email_confirm (was email_payment)",
            "data": {
                "country": "es",
                "service": "wallapop",
                "method": "email_confirm",
                "title": "Test",
                "price": 15.0,
                "seller_name": "John"
            }
        },
        {
            "name": "Wallapop sms_confirm (was sms_payment)",
            "data": {
                "country": "es",
                "service": "wallapop",
                "method": "sms_confirm",
                "title": "Test",
                "price": 20.0,
                "seller_name": "Jane"
            }
        },
        {
            "name": "Depop email_confirm",
            "data": {
                "country": "au",
                "service": "depop",
                "method": "email_confirm",
                "title": "Test",
                "price": 25.0
            }
        },
    ]
    
    for test in tests:
        print(f"\n  Testing: {test['name']}")
        response = requests.post(
            f"{BASE_URL}/generate",
            json=test["data"],
            headers={"X-API-Key": API_KEY}
        )
        
        if response.status_code == 200:
            print(f"    ✓ Success - Method name accepted")
        else:
            print(f"    ✗ Failed - {response.status_code}: {response.text}")
            return False
    
    print("\n✓ All method name tests passed")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("API Requirements Test Suite")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/get-geo", headers={"X-API-Key": API_KEY})
        if response.status_code != 200:
            print(f"\n✗ Server not accessible or API key invalid")
            return 1
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Cannot connect to server at {BASE_URL}")
        print("  Make sure the API server is running")
        return 1
    
    print(f"\n✓ Connected to API server at {BASE_URL}")
    
    # Run all tests
    all_passed = True
    all_passed &= test_missing_fields_no_error()
    all_passed &= test_data_uri_format()
    all_passed &= test_text_truncation()
    all_passed &= test_unified_method_names()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    # Allow API key to be passed as argument
    if len(sys.argv) > 1:
        API_KEY = sys.argv[1]
    
    sys.exit(main())
