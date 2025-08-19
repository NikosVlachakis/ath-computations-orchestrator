import os
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


class AggregatedResultsHandler:
    """
    Handles the final aggregated values from computation results.
    Provides methods to send results to external APIs and save to filesystem.
    """
    
    def __init__(self, default_save_path: Optional[str] = None):
        """
        Initialize the handler.
        
        Args:
            default_save_path: Default filesystem path for saving results
        """
        self.logger = logging.getLogger(__name__)
        self.default_save_path = default_save_path or "/app/results"
        
    def send_to_api(self, 
                   aggregated_data: List[Dict[str, Any]], 
                   api_url: str,
                   job_id: str,
                   client_list: List[str],
                   headers: Optional[Dict[str, str]] = None,
                   timeout: int = 30) -> bool:
        """
        Send aggregated results to an external API endpoint.
        
        Args:
            aggregated_data: The decoded/aggregated feature data
            api_url: Target API endpoint URL
            job_id: Job identifier
            client_list: List of client IDs that participated
            headers: Optional HTTP headers (defaults to JSON content-type)
            timeout: Request timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not aggregated_data:
            self.logger.warning(f"[ResultsHandler] No aggregated data to send for job {job_id}")
            return False
            
        if not api_url:
            self.logger.error(f"[ResultsHandler] API URL not provided for job {job_id}")
            return False
            
        # Prepare request headers
        if headers is None:
            headers = {"Content-Type": "application/json"}
            
        # Prepare payload
        payload = {
            "jobId": job_id,
            "timestamp": datetime.now().isoformat(),
            "clientList": client_list,
            "totalClients": len(client_list),
            "aggregatedResults": aggregated_data,
            "metadata": {
                "totalFeatures": len(aggregated_data),
                "processingCompletedAt": datetime.now().isoformat()
            }
        }
        
        self.logger.info(f"[ResultsHandler] Sending aggregated results to API: {api_url}")
        self.logger.info(f"[ResultsHandler] Job: {job_id}, Features: {len(aggregated_data)}, Clients: {client_list}")
        
        try:
            response = requests.post(
                api_url, 
                headers=headers, 
                json=payload, 
                timeout=timeout
            )
            
            if response.status_code in [200, 201, 202]:
                self.logger.info(f"[ResultsHandler] Successfully sent results to API for job {job_id}")
                self.logger.info(f"[ResultsHandler] Response status: {response.status_code}")
                
                # Log response content if available
                try:
                    response_data = response.json()
                    self.logger.info(f"[ResultsHandler] API Response: {response_data}")
                except:
                    self.logger.info(f"[ResultsHandler] API Response (text): {response.text[:200]}...")
                    
                return True
            else:
                self.logger.error(f"[ResultsHandler] API call failed with status {response.status_code}")
                self.logger.error(f"[ResultsHandler] Response: {response.text}")
                return False
                
        except requests.RequestException as e:
            self.logger.error(f"[ResultsHandler] Error sending results to API for job {job_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"[ResultsHandler] Unexpected error sending results for job {job_id}: {e}")
            return False
            
    def save_to_filesystem(self, 
                          aggregated_data: List[Dict[str, Any]], 
                          job_id: str,
                          client_list: List[str],
                          file_path: Optional[str] = None,
                          file_format: str = "json") -> bool:
        """
        Save aggregated results to the filesystem.
        
        Args:
            aggregated_data: The decoded/aggregated feature data
            job_id: Job identifier  
            client_list: List of client IDs that participated
            file_path: Custom file path (defaults to default_save_path/job_id_results.json)
            file_format: File format - 'json' or 'txt' (default: 'json')
            
        Returns:
            True if successful, False otherwise
        """
        if not aggregated_data:
            self.logger.warning(f"[ResultsHandler] No aggregated data to save for job {job_id}")
            return False
            
        # Determine file path
        if file_path is None:
            # Use default path with job_id
            os.makedirs(self.default_save_path, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{job_id}_results_{timestamp}.{file_format}"
            file_path = os.path.join(self.default_save_path, filename)
        else:
            # Ensure directory exists for custom path
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
                
        # Prepare data to save
        save_data = {
            "jobId": job_id,
            "timestamp": datetime.now().isoformat(),
            "clientList": client_list,
            "totalClients": len(client_list),
            "aggregatedResults": aggregated_data,
            "metadata": {
                "totalFeatures": len(aggregated_data),
                "processingCompletedAt": datetime.now().isoformat(),
                "savedAt": file_path
            }
        }
        
        self.logger.info(f"[ResultsHandler] Saving aggregated results to: {file_path}")
        self.logger.info(f"[ResultsHandler] Job: {job_id}, Features: {len(aggregated_data)}, Clients: {client_list}")
        
        try:
            if file_format.lower() == "json":
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, indent=4, ensure_ascii=False)
            elif file_format.lower() == "txt":
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"=== AGGREGATED RESULTS FOR JOB {job_id} ===\n")
                    f.write(f"Timestamp: {save_data['timestamp']}\n")
                    f.write(f"Clients: {', '.join(client_list)}\n")
                    f.write(f"Total Features: {len(aggregated_data)}\n\n")
                    
                    for i, feature_data in enumerate(aggregated_data, 1):
                        f.write(f"--- Feature {i}: {feature_data.get('featureName', 'Unknown')} ---\n")
                        for key, value in feature_data.items():
                            f.write(f"  {key}: {value}\n")
                        f.write("\n")
            else:
                self.logger.error(f"[ResultsHandler] Unsupported file format: {file_format}")
                return False
                
            self.logger.info(f"[ResultsHandler] Successfully saved results to: {file_path}")
            return True
            
        except IOError as e:
            self.logger.error(f"[ResultsHandler] IO error saving results for job {job_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"[ResultsHandler] Unexpected error saving results for job {job_id}: {e}")
            return False
            
    def send_and_save(self,
                     aggregated_data: List[Dict[str, Any]], 
                     job_id: str,
                     client_list: List[str],
                     api_url: Optional[str] = None,
                     file_path: Optional[str] = None,
                     **kwargs) -> Dict[str, bool]:
        """
        Convenience method to both send to API and save to filesystem.
        
        Args:
            aggregated_data: The decoded/aggregated feature data
            job_id: Job identifier
            client_list: List of client IDs that participated
            api_url: Optional API endpoint (if None, skips API call)
            file_path: Optional file path (uses default if None)
            **kwargs: Additional arguments for send_to_api or save_to_filesystem
            
        Returns:
            Dict with 'api_success' and 'save_success' boolean values
        """
        results = {
            'api_success': True,  # Default to True if not attempted
            'save_success': False
        }
        
        # Send to API if URL provided
        if api_url:
            api_kwargs = {k: v for k, v in kwargs.items() 
                         if k in ['headers', 'timeout']}
            results['api_success'] = self.send_to_api(
                aggregated_data, api_url, job_id, client_list, **api_kwargs
            )
        
        # Save to filesystem
        save_kwargs = {k: v for k, v in kwargs.items() 
                      if k in ['file_format']}
        results['save_success'] = self.save_to_filesystem(
            aggregated_data, job_id, client_list, file_path, **save_kwargs
        )
        
        self.logger.info(f"[ResultsHandler] Batch processing for job {job_id} - API: {results['api_success']}, Save: {results['save_success']}")
        
        return results
