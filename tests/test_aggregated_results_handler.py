#!/usr/bin/env python
"""
Test usage of the AggregatedResultsHandler class.
This demonstrates how to use the handler for both API calls and filesystem saving.
"""

import sys
import os

# Add the app directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app'))

from services.aggregated_results_handler import AggregatedResultsHandler
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def create_sample_data():
    """Create sample aggregated data for demonstration."""
    return [
        {
            "featureName": "age",
            "dataType": "NUMERIC", 
            "aggregatedNotNull": 1000,
            "aggregatedSum": 45000,
            "aggregatedAvg": 45.0,
            "aggregatedQ1": 30.0,
            "aggregatedQ2": 45.0,
            "aggregatedQ3": 60.0
        },
        {
            "featureName": "is_employed",
            "dataType": "BOOLEAN",
            "aggregatedNotNull": 1000,
            "aggregatedTrue": 750,
            "percentageTrue": 75.0
        },
        {
            "featureName": "department",
            "dataType": "CATEGORICAL",
            "aggregatedNotNull": 950,
            "aggregatedUniqueValues": 8,
            "aggregatedTopValueCount": 200,
            "diversity": 8.42
        }
    ]


def example_api_call():
    """Example: Send results to an API endpoint."""
    print("\n=== EXAMPLE: API Call ===")
    
    # Initialize handler
    handler = AggregatedResultsHandler()
    
    # Sample data
    sample_data = create_sample_data()
    job_id = "example_job_001"
    client_list = ["client1", "client2", "client3"]
    
    # API endpoint (replace with real endpoint)
    api_url = "https://httpbin.org/post"  # Test endpoint that echoes back
    
    # Send to API
    success = handler.send_to_api(
        aggregated_data=sample_data,
        api_url=api_url,
        job_id=job_id,
        client_list=client_list,
        timeout=10
    )
    
    print(f"API call successful: {success}")


def example_filesystem_save():
    """Example: Save results to filesystem."""
    print("\n=== EXAMPLE: Filesystem Save ===")
    
    # Initialize handler with custom path
    handler = AggregatedResultsHandler(default_save_path="./test_results")
    
    # Sample data
    sample_data = create_sample_data()
    job_id = "example_job_002"
    client_list = ["client1", "client2"]
    
    # Save as JSON (default)
    success_json = handler.save_to_filesystem(
        aggregated_data=sample_data,
        job_id=job_id,
        client_list=client_list
    )
    
    # Save as TXT with custom path
    success_txt = handler.save_to_filesystem(
        aggregated_data=sample_data,
        job_id=job_id,
        client_list=client_list,
        file_path="./test_results/custom_results.txt",
        file_format="txt"
    )
    
    print(f"JSON save successful: {success_json}")
    print(f"TXT save successful: {success_txt}")


def example_combined():
    """Example: Both API call and filesystem save."""
    print("\n=== EXAMPLE: Combined API + Save ===")
    
    # Initialize handler
    handler = AggregatedResultsHandler(default_save_path="./test_results")
    
    # Sample data
    sample_data = create_sample_data()
    job_id = "example_job_003"
    client_list = ["client1", "client2", "client3", "client4"]
    
    # Combined operation
    results = handler.send_and_save(
        aggregated_data=sample_data,
        job_id=job_id,
        client_list=client_list,
        api_url="https://httpbin.org/post",
        file_format="json",
        timeout=10
    )
    
    print(f"Combined results: {results}")


def example_error_handling():
    """Example: Error handling with invalid endpoints."""
    print("\n=== EXAMPLE: Error Handling ===")
    
    handler = AggregatedResultsHandler()
    sample_data = create_sample_data()
    
    # Test with invalid API URL
    success = handler.send_to_api(
        aggregated_data=sample_data,
        api_url="http://invalid-url-that-does-not-exist:9999/api",
        job_id="error_test_job",
        client_list=["client1"],
        timeout=5
    )
    
    print(f"Expected failure - API call successful: {success}")
    
    # Test with invalid file path (permission denied)
    success = handler.save_to_filesystem(
        aggregated_data=sample_data,
        job_id="error_test_job",
        client_list=["client1"],
        file_path="/root/readonly/cannot_write_here.json"  # This should fail
    )
    
    print(f"Expected failure - File save successful: {success}")


if __name__ == "__main__":
    print("AggregatedResultsHandler Tests")
    print("=" * 50)
    
    # Run examples
    try:
        example_api_call()
        example_filesystem_save()
        example_combined() 
        example_error_handling()
        
        print("\n=== Tests completed ===")
        print("Check the './test_results/' directory for saved files!")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()
