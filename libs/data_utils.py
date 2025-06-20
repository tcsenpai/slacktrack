"""
Data utilities for processing and extracting metrics from GitHub data.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from pathlib import Path
from collections import defaultdict
import fnmatch


def get_timeframe_dates(timeframe: str, custom_start: str = None, custom_end: str = None) -> tuple:
    """Get start and end dates based on timeframe preset or custom dates."""
    end_date = datetime.now()
    
    if timeframe == 'custom':
        if not custom_start or not custom_end:
            raise ValueError("Custom timeframe requires both start and end dates")
        start_date = datetime.fromisoformat(custom_start)
        end_date = datetime.fromisoformat(custom_end)
    elif timeframe == '3days':
        start_date = end_date - timedelta(days=3)
    elif timeframe == '1week':
        start_date = end_date - timedelta(weeks=1)
    elif timeframe == '1month':
        start_date = end_date - timedelta(days=30)
    else:
        raise ValueError(f"Unknown timeframe: {timeframe}")
    
    return start_date.isoformat(), end_date.isoformat()


def load_repoignore(repoignore_path: str = '.repoignore', verbose: bool = False) -> List[str]:
    """Load repository ignore patterns from .repoignore file."""
    patterns = []
    
    if not os.path.exists(repoignore_path):
        if verbose:
            print(f"No {repoignore_path} file found")
        return patterns
    
    try:
        with open(repoignore_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    patterns.append(line)
                    if verbose:
                        print(f"Loaded ignore pattern: {line}")
        
        if patterns:
            print(f"Loaded {len(patterns)} repository ignore patterns from {repoignore_path}")
        
    except Exception as e:
        print(f"Warning: Could not read {repoignore_path}: {e}")
    
    return patterns


def should_ignore_repo(repo_name: str, ignore_patterns: List[str], verbose: bool = False) -> bool:
    """Check if a repository should be ignored based on patterns."""
    for pattern in ignore_patterns:
        # Support wildcards using fnmatch
        if fnmatch.fnmatch(repo_name, pattern):
            if verbose:
                print(f"Ignoring repository '{repo_name}' (matches pattern: {pattern})")
            return True
        
        # Also support exact string matching (case-sensitive)
        if repo_name == pattern:
            if verbose:
                print(f"Ignoring repository '{repo_name}' (exact match)")
            return True
    
    return False


def filter_repositories(repos: List[Dict], repoignore_path: str = '.repoignore', verbose: bool = False) -> List[Dict]:
    """Filter repositories based on .repoignore patterns."""
    ignore_patterns = load_repoignore(repoignore_path, verbose)
    
    if not ignore_patterns:
        return repos
    
    filtered_repos = []
    ignored_count = 0
    
    for repo in repos:
        repo_name = repo['name']
        if should_ignore_repo(repo_name, ignore_patterns, verbose):
            ignored_count += 1
        else:
            filtered_repos.append(repo)
    
    if ignored_count > 0:
        print(f"Filtered out {ignored_count} repositories based on .repoignore patterns")
        print(f"Processing {len(filtered_repos)} repositories")
    
    return filtered_repos


def extract_metrics(user_data: Dict) -> Dict:
    """Extract key metrics from user data."""
    # Handle comparison data structure
    if 'comparison' in user_data and 'organization' in user_data:
        # This is comparison data, extract organization data
        org_data = user_data['organization']['data']
        return extract_metrics(org_data)
    
    metrics = {
        'username': user_data.get('username', 'unknown'),
        'total_commits': user_data.get('total_commits', 0),
        'total_repositories': len(user_data.get('repositories', {})),
        'timeframe': user_data.get('timeframe', {}),
        'repositories': user_data.get('repositories', {}),
        'commits_by_date': {},
        'commits_by_repo': {},
        'active_days': set(),
        'total_lines_added': 0,
        'total_lines_deleted': 0,
        'total_lines_changed': 0
    }
    
    # Process repository data
    for repo_name, repo_data in metrics['repositories'].items():
        commit_count = repo_data.get('commit_count', 0)
        metrics['commits_by_repo'][repo_name] = commit_count
        
        # Add lines metrics if available
        if 'lines_added' in repo_data:
            metrics['total_lines_added'] += repo_data.get('lines_added', 0)
        if 'lines_deleted' in repo_data:
            metrics['total_lines_deleted'] += repo_data.get('lines_deleted', 0)
        if 'lines_changed' in repo_data:
            metrics['total_lines_changed'] += repo_data.get('lines_changed', 0)
        
        # Process commit dates
        for commit in repo_data.get('commits', []):
            commit_date = commit['commit']['author']['date'][:10]  # YYYY-MM-DD
            metrics['commits_by_date'][commit_date] = metrics['commits_by_date'].get(commit_date, 0) + 1
            metrics['active_days'].add(commit_date)
    
    metrics['total_active_days'] = len(metrics['active_days'])
    metrics['active_days'] = list(metrics['active_days'])  # Convert set to list for JSON serialization
    
    # Calculate per-day average based on timeframe period, not just active days
    timeframe = metrics.get('timeframe', {})
    if timeframe.get('since') and timeframe.get('until'):
        try:
            since_date = datetime.fromisoformat(timeframe['since'].replace('Z', '+00:00'))
            until_date = datetime.fromisoformat(timeframe['until'].replace('Z', '+00:00'))
            total_days = (until_date - since_date).days + 1
            metrics['avg_commits_per_day'] = metrics['total_commits'] / max(total_days, 1)
        except (ValueError, TypeError):
            metrics['avg_commits_per_day'] = metrics['total_commits'] / max(metrics['total_active_days'], 1)
    else:
        metrics['avg_commits_per_day'] = metrics['total_commits'] / max(metrics['total_active_days'], 1)
    
    metrics['avg_commits_per_repo'] = metrics['total_commits'] / max(metrics['total_repositories'], 1)
    
    return metrics


def create_output_directory(username: str) -> str:
    """Create and return the output directory for a user."""
    output_dir = f"outputs/{username}"
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def save_data(data: Dict, output_path: Optional[str] = None, is_comparison: bool = False) -> str:
    """Save data to JSON file with appropriate naming."""
    username = data.get('username', 'unknown')
    
    if output_path:
        final_path = output_path
    else:
        # Create user directory and save with timestamp
        output_dir = create_output_directory(username)
        timestamp = datetime.now().strftime('%Y-%m-%d')
        
        # Different naming for comparison vs regular data
        if is_comparison:
            final_path = os.path.join(output_dir, f"comparison_data_{username}_{timestamp}.json")
        else:
            final_path = os.path.join(output_dir, f"raw_data_{username}_{timestamp}.json")
    
    with open(final_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return final_path


def save_ratio_summary(data: Dict) -> Optional[str]:
    """Save simplified ratio summary for comparison data."""
    if not data.get('comparison'):
        return None
    
    username = data.get('username', 'unknown')
    output_dir = create_output_directory(username)
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    ratio_data = {
        'username': username,
        'timestamp': datetime.now().isoformat(),
        'timeframe': data.get('timeframe', {}),
        'ratios': {
            'organization': data['comparison']['total_commits']['organization'],
            'personal': data['comparison']['total_commits']['personal'],
            'org_percentage': (data['comparison']['total_commits']['organization'] / 
                             max(data['comparison']['total_commits']['organization'] + 
                                 data['comparison']['total_commits']['personal'], 1)) * 100,
            'personal_percentage': (data['comparison']['total_commits']['personal'] / 
                                  max(data['comparison']['total_commits']['organization'] + 
                                      data['comparison']['total_commits']['personal'], 1)) * 100
        }
    }
    
    ratio_path = os.path.join(output_dir, f"ratio_summary_{username}_{timestamp}.json")
    with open(ratio_path, 'w') as f:
        json.dump(ratio_data, f, indent=2)
    
    return ratio_path


def load_user_data(username: str, data_file: Optional[str] = None) -> Optional[Dict]:
    """Load user data from JSON file."""
    if data_file:
        file_path = data_file
    else:
        # Look for the most recent JSON file in user's output directory
        user_dir = Path(f"outputs/{username}")
        if not user_dir.exists():
            return None
        
        # First try to find raw_data files
        json_files = list(user_dir.glob("raw_data_*.json"))
        
        # If no raw data, try comparison data files
        if not json_files:
            json_files = list(user_dir.glob("comparison_data_*.json"))
        
        if not json_files:
            return None
        
        # Get the most recent file
        file_path = max(json_files, key=lambda f: f.stat().st_mtime)
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_personal_data(username: str) -> Optional[Dict]:
    """Load personal data for a user if available."""
    user_dir = Path(f"outputs/{username}")
    if not user_dir.exists():
        return None
    
    personal_files = list(user_dir.glob("personal_data_*.json"))
    if not personal_files:
        return None
    
    # Get the most recent personal file
    file_path = max(personal_files, key=lambda f: f.stat().st_mtime)
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_comparison_data(username: str) -> Optional[Dict]:
    """Load comparison data for a user if available."""
    user_dir = Path(f"outputs/{username}")
    if not user_dir.exists():
        return None
    
    # First try to load full comparison data
    comparison_files = list(user_dir.glob("comparison_data_*.json"))
    if comparison_files:
        file_path = max(comparison_files, key=lambda f: f.stat().st_mtime)
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    # Fallback to ratio summary files
    ratio_files = list(user_dir.glob("ratio_summary_*.json"))
    if ratio_files:
        file_path = max(ratio_files, key=lambda f: f.stat().st_mtime)
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    return None