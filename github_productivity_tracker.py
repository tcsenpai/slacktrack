#!/usr/bin/env python3
"""
GitHub Productivity Tracker

Tracks commits by a specific user across all repositories in an organization.
Supports timeframe filtering with presets and custom date ranges.
"""

import argparse
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import sys
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import defaultdict, Counter
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from tqdm import tqdm
import fnmatch
import re


class GitHubProductivityTracker:
    def __init__(self, org_name: str, github_token: Optional[str] = None, verbose: bool = False):
        self.org_name = org_name
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.base_url = "https://api.github.com"
        self.verbose = verbose
        self._lock = threading.Lock()  # For thread-safe printing
        
        if not self.github_token:
            print("Warning: No GitHub token provided. API rate limits will be severely restricted.")
            print("Please set GITHUB_TOKEN environment variable or pass token as argument.")
        
        self.headers = {
            'Authorization': f'token {self.github_token}' if self.github_token else '',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def _verbose_print(self, message: str):
        """Thread-safe verbose printing."""
        if self.verbose:
            with self._lock:
                print(f"[VERBOSE] {message}")
    
    def load_repoignore(self, repoignore_path: str = '.repoignore') -> List[str]:
        """Load repository ignore patterns from .repoignore file."""
        patterns = []
        
        if not os.path.exists(repoignore_path):
            self._verbose_print(f"No {repoignore_path} file found")
            return patterns
        
        try:
            with open(repoignore_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        patterns.append(line)
                        self._verbose_print(f"Loaded ignore pattern: {line}")
            
            if patterns:
                print(f"Loaded {len(patterns)} repository ignore patterns from {repoignore_path}")
            
        except Exception as e:
            print(f"Warning: Could not read {repoignore_path}: {e}")
        
        return patterns
    
    def should_ignore_repo(self, repo_name: str, ignore_patterns: List[str]) -> bool:
        """Check if a repository should be ignored based on patterns."""
        for pattern in ignore_patterns:
            # Support wildcards using fnmatch
            if fnmatch.fnmatch(repo_name, pattern):
                self._verbose_print(f"Ignoring repository '{repo_name}' (matches pattern: {pattern})")
                return True
            
            # Also support exact string matching (case-sensitive)
            if repo_name == pattern:
                self._verbose_print(f"Ignoring repository '{repo_name}' (exact match)")
                return True
        
        return False
    
    def get_timeframe_dates(self, timeframe: str, custom_start: str = None, custom_end: str = None) -> tuple:
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
    
    def get_organization_repos(self) -> List[Dict]:
        """Fetch all repositories in the organization (including private ones if token has access)."""
        repos = []
        page = 1
        
        while True:
            url = f"{self.base_url}/orgs/{self.org_name}/repos"
            params = {
                'page': page, 
                'per_page': 100,
                'type': 'all'  # Include both public and private repos
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching repositories: {response.status_code}")
                if response.status_code == 401:
                    print("Authentication failed. Check your GitHub token.")
                elif response.status_code == 403:
                    print("Access forbidden. Token may lack organization access.")
                print(response.text)
                break
            
            page_repos = response.json()
            if not page_repos:
                break
            
            repos.extend(page_repos)
            page += 1
        
        # Log repository visibility for debugging
        public_count = sum(1 for repo in repos if not repo.get('private', False))
        private_count = len(repos) - public_count
        print(f"Found {len(repos)} repositories ({public_count} public, {private_count} private)")
        
        return repos
    
    def filter_repositories(self, repos: List[Dict], repoignore_path: str = '.repoignore') -> List[Dict]:
        """Filter repositories based on .repoignore patterns."""
        ignore_patterns = self.load_repoignore(repoignore_path)
        
        if not ignore_patterns:
            return repos
        
        filtered_repos = []
        ignored_count = 0
        
        for repo in repos:
            repo_name = repo['name']
            if self.should_ignore_repo(repo_name, ignore_patterns):
                ignored_count += 1
            else:
                filtered_repos.append(repo)
        
        if ignored_count > 0:
            print(f"Filtered out {ignored_count} repositories based on .repoignore patterns")
            print(f"Processing {len(filtered_repos)} repositories")
        
        return filtered_repos
    
    def get_repo_branches(self, repo_name: str) -> List[str]:
        """Get all branches for a repository."""
        branches = []
        page = 1
        
        while True:
            url = f"{self.base_url}/repos/{self.org_name}/{repo_name}/branches"
            params = {'page': page, 'per_page': 100}
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching branches for {repo_name}: {response.status_code}")
                break
            
            page_branches = response.json()
            if not page_branches:
                break
            
            branches.extend([branch['name'] for branch in page_branches])
            page += 1
        
        return branches
    
    def get_branch_commits(self, repo_name: str, branch: str, username: str, since: str, until: str) -> List[Dict]:
        """Get commits for a specific branch - used for parallel processing."""
        commits = []
        page = 1
        
        self._verbose_print(f"Starting branch {branch} in {repo_name}")
        
        while True:
            url = f"{self.base_url}/repos/{self.org_name}/{repo_name}/commits"
            params = {
                'author': username,
                'sha': branch,
                'since': since,
                'until': until,
                'page': page,
                'per_page': 100
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                if response.status_code == 409:
                    self._verbose_print(f"Branch {branch} in {repo_name}: Empty or inaccessible")
                else:
                    self._verbose_print(f"Branch {branch} in {repo_name}: Error {response.status_code}")
                break
            
            page_commits = response.json()
            if not page_commits:
                break
            
            # Add branch info to each commit
            for commit in page_commits:
                commit['branch'] = branch
            
            commits.extend(page_commits)
            page += 1
        
        self._verbose_print(f"Branch {branch} in {repo_name}: Found {len(commits)} commits")
        return commits
    
    def get_commit_stats_batch(self, repo_name: str, commits: List[Dict]) -> List[Dict]:
        """Fetch commit statistics in parallel for better performance."""
        def get_single_commit_stats(commit):
            sha = commit['sha']
            stats_url = f"{self.base_url}/repos/{self.org_name}/{repo_name}/commits/{sha}"
            response = requests.get(stats_url, headers=self.headers)
            
            if response.status_code == 200:
                detailed = response.json()
                commit['stats'] = detailed.get('stats', {})
                commit['files'] = detailed.get('files', [])
            else:
                commit['stats'] = {'total': 0, 'additions': 0, 'deletions': 0}
                commit['files'] = []
            
            return commit
        
        if not commits:
            return commits
        
        self._verbose_print(f"Fetching stats for {len(commits)} commits in {repo_name}")
        
        # Use ThreadPoolExecutor for parallel stats fetching
        with ThreadPoolExecutor(max_workers=5) as executor:
            if self.verbose:
                # Show progress bar in verbose mode
                futures = {executor.submit(get_single_commit_stats, commit): commit for commit in commits}
                results = []
                for future in tqdm(as_completed(futures), total=len(commits), desc=f"Stats for {repo_name}"):
                    results.append(future.result())
            else:
                futures = [executor.submit(get_single_commit_stats, commit) for commit in commits]
                results = [future.result() for future in as_completed(futures)]
        
        return results
    
    def get_user_commits_in_repo(self, repo_name: str, username: str, since: str, until: str, include_stats: bool = False) -> List[Dict]:
        """Get commits by a specific user in a repository within the timeframe from ALL branches (optimized)."""
        # Get all branches
        branches = self.get_repo_branches(repo_name)
        if not branches:
            if self.verbose:
                print(f"  No branches found for {repo_name}")
            return []
        
        if self.verbose:
            print(f"  Checking {len(branches)} branches: {', '.join(branches[:5])}{'...' if len(branches) > 5 else ''}")
        else:
            print(f"  Checking {len(branches)} branches")
        
        # Use ThreadPoolExecutor for parallel branch processing
        all_commits = []
        seen_shas = set()
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit tasks for each branch
            future_to_branch = {
                executor.submit(self.get_branch_commits, repo_name, branch, username, since, until): branch 
                for branch in branches
            }
            
            # Collect results with progress tracking
            if self.verbose:
                for future in tqdm(as_completed(future_to_branch), total=len(branches), desc=f"Branches in {repo_name}"):
                    branch_commits = future.result()
                    # Deduplicate commits
                    for commit in branch_commits:
                        if commit['sha'] not in seen_shas:
                            seen_shas.add(commit['sha'])
                            all_commits.append(commit)
            else:
                for future in as_completed(future_to_branch):
                    branch_commits = future.result()
                    # Deduplicate commits
                    for commit in branch_commits:
                        if commit['sha'] not in seen_shas:
                            seen_shas.add(commit['sha'])
                            all_commits.append(commit)
        
        # Fetch stats in parallel if requested
        if include_stats and all_commits:
            all_commits = self.get_commit_stats_batch(repo_name, all_commits)
        
        return all_commits
    
    def get_user_pull_requests(self, username: str, since: str, until: str) -> List[Dict]:
        """Get pull requests created by the user in the organization."""
        prs = []
        page = 1
        
        while True:
            url = f"{self.base_url}/search/issues"
            query = f"type:pr author:{username} org:{self.org_name} created:{since}..{until}"
            params = {
                'q': query,
                'page': page,
                'per_page': 100
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching pull requests: {response.status_code}")
                break
            
            data = response.json()
            if not data.get('items'):
                break
            
            prs.extend(data['items'])
            page += 1
            
            if len(data['items']) < 100:
                break
        
        return prs
    
    def get_user_code_reviews(self, username: str, since: str, until: str) -> List[Dict]:
        """Get code reviews performed by the user."""
        reviews = []
        page = 1
        
        while True:
            url = f"{self.base_url}/search/issues"
            query = f"type:pr reviewed-by:{username} org:{self.org_name} updated:{since}..{until}"
            params = {
                'q': query,
                'page': page,
                'per_page': 100
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching code reviews: {response.status_code}")
                break
            
            data = response.json()
            if not data.get('items'):
                break
            
            reviews.extend(data['items'])
            page += 1
            
            if len(data['items']) < 100:
                break
        
        return reviews
    
    def get_user_issues(self, username: str, since: str, until: str) -> List[Dict]:
        """Get issues created by the user."""
        issues = []
        page = 1
        
        while True:
            url = f"{self.base_url}/search/issues"
            query = f"type:issue author:{username} org:{self.org_name} created:{since}..{until}"
            params = {
                'q': query,
                'page': page,
                'per_page': 100
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching issues: {response.status_code}")
                break
            
            data = response.json()
            if not data.get('items'):
                break
            
            issues.extend(data['items'])
            page += 1
            
            if len(data['items']) < 100:
                break
        
        return issues
    
    def track_user_productivity(self, username: str, timeframe: str, 
                              custom_start: str = None, custom_end: str = None, 
                              include_prs: bool = False, include_reviews: bool = False, 
                              include_issues: bool = False, include_lines: bool = False,
                              repoignore_path: str = '.repoignore') -> Dict:
        """Track user productivity across all organization repositories."""
        try:
            since, until = self.get_timeframe_dates(timeframe, custom_start, custom_end)
        except ValueError as e:
            print(f"Error: {e}")
            return {}
        
        print(f"Tracking productivity for {username} from {since} to {until}")
        print(f"Fetching repositories for organization: {self.org_name}")
        
        repos = self.get_organization_repos()
        if not repos:
            print("No repositories found or error fetching repositories.")
            return {}
        
        # Filter repositories based on .repoignore
        repos = self.filter_repositories(repos, repoignore_path)
        
        print(f"Found {len(repos)} repositories. Analyzing commits...")
        
        productivity_data = {}
        total_commits = 0
        
        # Process repositories with optional progress bar
        if self.verbose:
            repo_iterator = tqdm(repos, desc="Processing repositories")
        else:
            repo_iterator = repos
        
        for repo in repo_iterator:
            repo_name = repo['name']
            if not self.verbose:
                print(f"Analyzing repository: {repo_name}")
            
            commits = self.get_user_commits_in_repo(repo_name, username, since, until, include_lines)
            
            if commits:
                repo_data = {
                    'commit_count': len(commits),
                    'commits': commits,
                    'repo_url': repo['html_url']
                }
                
                # Calculate line statistics if requested
                if include_lines:
                    total_additions = sum(commit.get('stats', {}).get('additions', 0) for commit in commits)
                    total_deletions = sum(commit.get('stats', {}).get('deletions', 0) for commit in commits)
                    total_changes = sum(commit.get('stats', {}).get('total', 0) for commit in commits)
                    
                    repo_data.update({
                        'lines_added': total_additions,
                        'lines_deleted': total_deletions,
                        'lines_changed': total_changes
                    })
                    
                    print(f"  Found {len(commits)} commits (+{total_additions}/-{total_deletions} lines)")
                else:
                    print(f"  Found {len(commits)} commits")
                
                productivity_data[repo_name] = repo_data
                total_commits += len(commits)
            else:
                print(f"  No commits found")
        
        result = {
            'username': username,
            'organization': self.org_name,
            'timeframe': {
                'since': since,
                'until': until,
                'preset': timeframe
            },
            'total_commits': total_commits,
            'repositories': productivity_data
        }
        
        # Add total line statistics if requested
        if include_lines:
            total_additions = sum(repo.get('lines_added', 0) for repo in productivity_data.values())
            total_deletions = sum(repo.get('lines_deleted', 0) for repo in productivity_data.values())
            total_changes = sum(repo.get('lines_changed', 0) for repo in productivity_data.values())
            
            result['line_stats'] = {
                'total_additions': total_additions,
                'total_deletions': total_deletions,
                'total_changes': total_changes
            }
        
        # Add additional metrics if requested
        if include_prs:
            print("Fetching pull requests...")
            prs = self.get_user_pull_requests(username, since[:10], until[:10])
            result['pull_requests'] = {
                'total': len(prs),
                'data': prs
            }
            print(f"Found {len(prs)} pull requests")
        
        if include_reviews:
            print("Fetching code reviews...")
            reviews = self.get_user_code_reviews(username, since[:10], until[:10])
            result['code_reviews'] = {
                'total': len(reviews),
                'data': reviews
            }
            print(f"Found {len(reviews)} code reviews")
        
        if include_issues:
            print("Fetching issues...")
            issues = self.get_user_issues(username, since[:10], until[:10])
            result['issues'] = {
                'total': len(issues),
                'data': issues
            }
            print(f"Found {len(issues)} issues created")
        
        return result
    
    def get_user_personal_repos(self, username: str) -> List[Dict]:
        """Fetch all personal repositories of a specific user."""
        repos = []
        page = 1

        while True:
            url = f"{self.base_url}/users/{username}/repos"
            params = {
                "page": page,
                "per_page": 100,
                "type": "all",
                "sort": "updated"
            }

            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code != 200:
                print(f"Error fetching personal repositories for {username}: {response.status_code}")
                if response.status_code == 404:
                    print(f"User {username} not found or has no public repositories.")
                break

            page_repos = response.json()
            if not page_repos:
                break

            user_repos = [repo for repo in page_repos if repo["owner"]["login"].lower() == username.lower()]
            repos.extend(user_repos)
            page += 1

        public_count = sum(1 for repo in repos if not repo.get("private", False))
        private_count = len(repos) - public_count
        fork_count = sum(1 for repo in repos if repo.get("fork", False))

        print(f"Found {len(repos)} personal repositories for {username} ({public_count} public, {private_count} private, {fork_count} forks)")

        return repos
    def track_user_personal_productivity(self, username: str, timeframe: str,
                                       custom_start: str = None, custom_end: str = None,
                                       include_prs: bool = False, include_reviews: bool = False,
                                       include_issues: bool = False, include_lines: bool = False,
                                       repoignore_path: str = ".repoignore") -> Dict:
        """Track user productivity across their personal repositories."""
        try:
            since, until = self.get_timeframe_dates(timeframe, custom_start, custom_end)
        except ValueError as e:
            print(f"Error: {e}")
            return {}

        print(f"\nTracking PERSONAL productivity for {username} from {since} to {until}")
        print(f"Fetching personal repositories for user: {username}")

        original_org = self.org_name

        try:
            repos = self.get_user_personal_repos(username)
            if not repos:
                print("No personal repositories found or error fetching repositories.")
                return {}

            repos = self.filter_repositories(repos, repoignore_path)
            print(f"Analyzing {len(repos)} personal repositories...")

            productivity_data = {}
            total_commits = 0

            if self.verbose:
                repo_iterator = tqdm(repos, desc="Processing personal repositories")
            else:
                repo_iterator = repos

            for repo in repo_iterator:
                repo_name = repo["name"]
                repo_owner = repo["owner"]["login"]
                self.org_name = repo_owner

                if not self.verbose:
                    print(f"Analyzing personal repository: {repo_name}")

                commits = self.get_user_commits_in_repo(repo_name, username, since, until, include_lines)

                if commits:
                    repo_data = {
                        "commit_count": len(commits),
                        "commits": commits,
                        "repo_url": repo["html_url"],
                        "is_fork": repo.get("fork", False),
                        "is_private": repo.get("private", False)
                    }

                    if include_lines:
                        total_additions = sum(commit.get("stats", {}).get("additions", 0) for commit in commits)
                        total_deletions = sum(commit.get("stats", {}).get("deletions", 0) for commit in commits)
                        total_changes = sum(commit.get("stats", {}).get("total", 0) for commit in commits)

                        repo_data.update({
                            "lines_added": total_additions,
                            "lines_deleted": total_deletions,
                            "lines_changed": total_changes
                        })

                        fork_indicator = " (fork)" if repo.get("fork", False) else ""
                        private_indicator = " (private)" if repo.get("private", False) else ""
                        print(f"  Found {len(commits)} commits (+{total_additions}/-{total_deletions} lines){fork_indicator}{private_indicator}")
                    else:
                        fork_indicator = " (fork)" if repo.get("fork", False) else ""
                        private_indicator = " (private)" if repo.get("private", False) else ""
                        print(f"  Found {len(commits)} commits{fork_indicator}{private_indicator}")

                    productivity_data[repo_name] = repo_data
                    total_commits += len(commits)
                else:
                    print(f"  No commits found")

        finally:
            self.org_name = original_org

        result = {
            "username": username,
            "scope": "personal",
            "timeframe": {
                "since": since,
                "until": until,
                "preset": timeframe
            },
            "total_commits": total_commits,
            "repositories": productivity_data
        }

        if include_lines:
            total_additions = sum(repo.get("lines_added", 0) for repo in productivity_data.values())
            total_deletions = sum(repo.get("lines_deleted", 0) for repo in productivity_data.values())
            total_changes = sum(repo.get("lines_changed", 0) for repo in productivity_data.values())

            result["line_stats"] = {
                "total_additions": total_additions,
                "total_deletions": total_deletions,
                "total_changes": total_changes
            }

        return result


    def display_productivity_report(self, data: Dict):
        """Display a formatted productivity report."""
        if not data:
            print("No data to display.")
            return
        
        print("\n" + "="*80)
        print(f"PRODUCTIVITY REPORT")
        print("="*80)
        # Format timeframe for human readability
        since_date = datetime.fromisoformat(data['timeframe']['since'].replace('Z', '+00:00'))
        until_date = datetime.fromisoformat(data['timeframe']['until'].replace('Z', '+00:00'))
        
        print(f"User: {data['username']}")
        print(f"Organization: {data['organization']}")
        print(f"Timeframe: {since_date.strftime('%B %d, %Y')} to {until_date.strftime('%B %d, %Y')}")
        print(f"Total Commits: {data['total_commits']}")
        print(f"Repositories with activity: {len(data['repositories'])}")
        
        # Display additional metrics if available
        if 'pull_requests' in data:
            print(f"Pull Requests Created: {data['pull_requests']['total']}")
        if 'code_reviews' in data:
            print(f"Code Reviews Performed: {data['code_reviews']['total']}")
        if 'issues' in data:
            print(f"Issues Created: {data['issues']['total']}")
        if 'line_stats' in data:
            stats = data['line_stats']
            print(f"Lines Modified: +{stats['total_additions']}/-{stats['total_deletions']} ({stats['total_changes']} total)")
        
        if data['repositories']:
            print("\nPER REPOSITORY BREAKDOWN:")
            print("-" * 80)
            
            # Sort repositories by commit count (descending)
            sorted_repos = sorted(data['repositories'].items(), 
                                key=lambda x: x[1]['commit_count'], reverse=True)
            
            for repo_name, repo_data in sorted_repos:
                print(f"\n{repo_name}: {repo_data['commit_count']} commits")
                print(f"  Repository: {repo_data['repo_url']}")
                
                # Show recent commits (limit to 5)
                recent_commits = repo_data['commits'][:5]
                for commit in recent_commits:
                    date = commit['commit']['author']['date']
                    message = commit['commit']['message'].split('\n')[0][:60]
                    print(f"    {date[:10]} - {message}")
                
                if len(repo_data['commits']) > 5:
                    print(f"    ... and {len(repo_data['commits']) - 5} more commits")
        
        print("\n" + "="*80)
    
    def create_output_directory(self, username: str) -> str:
        """Create and return the output directory for a user."""
        output_dir = f"outputs/{username}"
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def generate_text_summary(self, data: Dict, output_dir: str) -> str:
        """Generate a comprehensive text summary of the productivity data."""
        if not data:
            return ""

        timestamp = datetime.now().strftime("%Y-%m-%d")
        summary_path = os.path.join(output_dir, f"productivity_summary_{data['username']}_{timestamp}.txt")

        # Format timeframe for human readability
        since_date = datetime.fromisoformat(data['timeframe']['since'].replace('Z', '+00:00'))
        until_date = datetime.fromisoformat(data['timeframe']['until'].replace('Z', '+00:00'))

        with open(summary_path, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("GITHUB PRODUCTIVITY ANALYSIS SUMMARY\n")
            f.write("=" * 80 + "\n\n")

            # Basic Information
            f.write(f"User: {data['username']}\n")
            f.write(f"Organization: {data['organization']}\n")
            f.write(f"Analysis Period: {since_date.strftime('%B %d, %Y')} to {until_date.strftime('%B %d, %Y')}\n")
            f.write(f"Report Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n\n")

            # Overall Metrics
            f.write("-" * 50 + "\n")
            f.write("OVERALL PRODUCTIVITY METRICS\n")
            f.write("-" * 50 + "\n")
            f.write(f"Total Commits: {data['total_commits']}\n")
            f.write(f"Active Repositories: {len(data['repositories'])}\n")

            if 'pull_requests' in data:
                f.write(f"Pull Requests Created: {data['pull_requests']['total']}\n")
            if 'code_reviews' in data:
                f.write(f"Code Reviews Performed: {data['code_reviews']['total']}\n")
            if 'issues' in data:
                f.write(f"Issues Created: {data['issues']['total']}\n")
            if 'line_stats' in data:
                stats = data['line_stats']
                f.write(f"Lines Added: +{stats['total_additions']:,}\n")
                f.write(f"Lines Deleted: -{stats['total_deletions']:,}\n")
                f.write(f"Total Lines Modified: {stats['total_changes']:,}\n")

            # Time-based Analysis
            f.write("\n" + "-" * 50 + "\n")
            f.write("TIME-BASED ANALYSIS\n")
            f.write("-" * 50 + "\n")

            # Calculate daily averages
            days_in_period = (until_date - since_date).days + 1
            if days_in_period > 0:
                avg_commits_per_day = data['total_commits'] / days_in_period
                f.write(f"Analysis Period: {days_in_period} days\n")
                f.write(f"Average Commits per Day: {avg_commits_per_day:.1f}\n")

                if 'line_stats' in data:
                    avg_lines_per_day = data['line_stats']['total_changes'] / days_in_period
                    f.write(f"Average Lines Modified per Day: {avg_lines_per_day:.0f}\n")

            # Summary and Insights
            f.write("\n" + "-" * 50 + "\n")
            f.write("INSIGHTS AND SUMMARY\n")
            f.write("-" * 50 + "\n")

            if data['total_commits'] == 0:
                f.write("No commit activity found in the specified timeframe.\n")
            else:
                # Productivity level assessment
                if avg_commits_per_day >= 5:
                    productivity_level = "Very High"
                elif avg_commits_per_day >= 3:
                    productivity_level = "High"
                elif avg_commits_per_day >= 1:
                    productivity_level = "Moderate"
                else:
                    productivity_level = "Low"

                f.write(f"Productivity Level: {productivity_level}\n")
                f.write(f"Repository Diversity: {len(data['repositories'])} different repositories\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("End of Report\n")
            f.write("=" * 80 + "\n")

        print(f"Text summary saved to {summary_path}")
        return summary_path

    def create_comprehensive_heatmap(self, data: Dict, output_path: str = None):
        """Create a comprehensive heatmap visualization of all productivity metrics."""
        if not data:
            print("No data available for heatmap generation.")
            return
        
        # Determine how many metrics we have
        metrics = []
        if data.get('repositories'):
            metrics.append('commits')
        if data.get('pull_requests'):
            metrics.append('pull_requests')
        if data.get('code_reviews'):
            metrics.append('code_reviews')
        if data.get('issues'):
            metrics.append('issues')
        if data.get('line_stats'):
            metrics.append('lines_modified')
        
        if not metrics:
            print("No metrics available for heatmap generation.")
            return
        
        # Calculate figure size based on number of metrics
        rows = len(metrics) + 1  # +1 for summary
        fig, axes = plt.subplots(rows, 2, figsize=(18, 4 * rows))
        if rows == 1:
            axes = [axes]
        
        # Get date range from timeframe
        since_date = datetime.fromisoformat(data['timeframe']['since'].replace('Z', '+00:00')).date()
        until_date = datetime.fromisoformat(data['timeframe']['until'].replace('Z', '+00:00')).date()
        
        # Create date range
        date_range = []
        current_date = since_date
        while current_date <= until_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        weeks = len(date_range) // 7 + 1
        colors = ['Greens', 'Blues', 'Oranges', 'Purples', 'Reds']
        all_activities = {}
        
        # Process each metric
        for idx, metric in enumerate(metrics):
            daily_counts = defaultdict(int)
            
            if metric == 'commits' and data.get('repositories'):
                for repo_data in data['repositories'].values():
                    for commit in repo_data['commits']:
                        commit_date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00')).date()
                        daily_counts[commit_date] += 1
            
            elif metric == 'pull_requests' and data.get('pull_requests'):
                for pr in data['pull_requests']['data']:
                    pr_date = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00')).date()
                    daily_counts[pr_date] += 1
            
            elif metric == 'code_reviews' and data.get('code_reviews'):
                for review in data['code_reviews']['data']:
                    review_date = datetime.fromisoformat(review['updated_at'].replace('Z', '+00:00')).date()
                    daily_counts[review_date] += 1
            
            elif metric == 'issues' and data.get('issues'):
                for issue in data['issues']['data']:
                    issue_date = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00')).date()
                    daily_counts[issue_date] += 1
            
            elif metric == 'lines_modified' and data.get('line_stats'):
                # For lines modified, we need to aggregate from commits
                for repo_data in data['repositories'].values():
                    for commit in repo_data['commits']:
                        if commit.get('stats'):
                            commit_date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00')).date()
                            lines_changed = commit['stats'].get('total', 0)
                            daily_counts[commit_date] += lines_changed
            
            all_activities[metric] = daily_counts
            
            # Create activity matrix
            activity_matrix = np.zeros((7, weeks))
            for i, date in enumerate(date_range):
                if i < 7 * weeks:
                    week = i // 7
                    day_of_week = date.weekday()
                    activity_matrix[day_of_week, week] = daily_counts.get(date, 0)
            
            # Heatmap
            ax_heatmap = axes[idx][0]
            im = ax_heatmap.imshow(activity_matrix, cmap=colors[idx % len(colors)], aspect='auto')
            ax_heatmap.set_title(f"{metric.replace('_', ' ').title()} Activity", fontweight='bold')
            ax_heatmap.set_ylabel('Day of Week')
            ax_heatmap.set_yticks(range(7))
            ax_heatmap.set_yticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
            plt.colorbar(im, ax=ax_heatmap, label=f'{metric.replace("_", " ").title()} per Day')
            
            # Timeline
            ax_timeline = axes[idx][1]
            dates = sorted(daily_counts.keys())
            counts = [daily_counts[date] for date in dates]
            if dates and counts:
                ax_timeline.plot(dates, counts, marker='o', linewidth=2, markersize=3)
                ax_timeline.fill_between(dates, counts, alpha=0.3)
            ax_timeline.set_title(f"{metric.replace('_', ' ').title()} Timeline", fontweight='bold')
            
            # Set appropriate y-axis label based on metric
            if metric == 'lines_modified':
                ax_timeline.set_ylabel('Lines Changed')
            else:
                ax_timeline.set_ylabel('Count')
            
            ax_timeline.grid(True, alpha=0.3)
            ax_timeline.tick_params(axis='x', rotation=45)
        
        # Summary row - combined activity and metrics overview
        ax_summary_heat = axes[-1][0]
        ax_summary_pie = axes[-1][1]
        
        # Combined heatmap (sum of all activities)
        combined_daily = defaultdict(int)
        for metric_counts in all_activities.values():
            for date, count in metric_counts.items():
                combined_daily[date] += count
        
        combined_matrix = np.zeros((7, weeks))
        for i, date in enumerate(date_range):
            if i < 7 * weeks:
                week = i // 7
                day_of_week = date.weekday()
                combined_matrix[day_of_week, week] = combined_daily.get(date, 0)
        
        im_combined = ax_summary_heat.imshow(combined_matrix, cmap='Reds', aspect='auto')
        ax_summary_heat.set_title('Combined Activity Heatmap', fontweight='bold', fontsize=14)
        ax_summary_heat.set_ylabel('Day of Week')
        ax_summary_heat.set_xlabel('Week')
        ax_summary_heat.set_yticks(range(7))
        ax_summary_heat.set_yticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
        plt.colorbar(im_combined, ax=ax_summary_heat, label='Total Activity per Day')
        
        # Metrics distribution pie chart
        metric_totals = []
        metric_labels = []
        for metric in metrics:
            if metric == 'commits':
                total = data['total_commits']
            elif metric == 'pull_requests':
                total = data['pull_requests']['total']
            elif metric == 'code_reviews':
                total = data['code_reviews']['total']
            elif metric == 'issues':
                total = data['issues']['total']
            elif metric == 'lines_modified':
                total = data['line_stats']['total_changes']
            
            if total > 0:
                metric_totals.append(total)
                if metric == 'lines_modified':
                    metric_labels.append(f"Lines Modified ({total})")
                else:
                    metric_labels.append(f"{metric.replace('_', ' ').title()} ({total})")
        
        if metric_totals:
            ax_summary_pie.pie(metric_totals, labels=metric_labels, autopct='%1.1f%%', startangle=90)
            ax_summary_pie.set_title(f"Productivity Metrics Distribution\nTotal Activity: {sum(metric_totals)}", 
                                   fontweight='bold', fontsize=14)
        
        # Format dates for better readability
        since_formatted = since_date.strftime('%B %d, %Y')
        until_formatted = until_date.strftime('%B %d, %Y')
        
        fig.suptitle(f"Comprehensive Productivity Dashboard: {data['username']}\n{since_formatted} to {until_formatted}", 
                    fontsize=16, fontweight='bold', y=0.98)
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.95)
        
        # Create output directory and save files
        output_dir = self.create_output_directory(data['username'])
        timestamp = datetime.now().strftime('%Y-%m-%d')
        
        if output_path:
            final_path = output_path
        else:
            final_path = os.path.join(output_dir, f"comprehensive_dashboard_{data['username']}_{timestamp}.png")
        
        plt.savefig(final_path, dpi=300, bbox_inches='tight')
        print(f"Comprehensive heatmap saved to {final_path}")
        
        # Generate text summary
        self.generate_text_summary(data, output_dir)
        
        try:
            plt.show()
        except Exception:
            print("Plot saved to file (display not available)")
    
    def create_heatmap(self, data: Dict, output_path: str = None):
        """Create a heatmap visualization - delegates to comprehensive version if multiple metrics available."""
        # Check if we have additional metrics beyond commits
        has_additional_metrics = any([
            data.get('pull_requests', {}).get('total', 0) > 0,
            data.get('code_reviews', {}).get('total', 0) > 0,
            data.get('issues', {}).get('total', 0) > 0,
            data.get('line_stats', {}).get('total_changes', 0) > 0
        ])
        
        if has_additional_metrics:
            print("Multiple metrics detected - creating comprehensive dashboard...")
            self.create_comprehensive_heatmap(data, output_path)
            return
        
        # Original simple heatmap for commits only
        if not data or not data['repositories']:
            print("No data available for heatmap generation.")
            return
        
        # Collect all commits with dates
        all_commits = []
        for repo_data in data['repositories'].values():
            for commit in repo_data['commits']:
                commit_date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
                all_commits.append(commit_date.date())
        
        if not all_commits:
            print("No commits found for heatmap generation.")
            return
        
        # Count commits per day
        commit_counts = Counter(all_commits)
        
        # Get date range
        start_date = min(all_commits)
        end_date = max(all_commits)
        
        # Create date range and commit counts array
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        # Create activity matrix (7 rows for days of week, columns for weeks)
        weeks = len(date_range) // 7 + 1
        activity_matrix = np.zeros((7, weeks))
        
        for i, date in enumerate(date_range):
            week = i // 7
            day_of_week = date.weekday()
            activity_matrix[day_of_week, week] = commit_counts.get(date, 0)
        
        # Create the heatmap
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
        
        # Daily activity heatmap (GitHub-style)
        im1 = ax1.imshow(activity_matrix, cmap='Greens', aspect='auto')
        ax1.set_title(f"Commit Activity Heatmap for {data['username']}", 
                     fontsize=14, fontweight='bold')
        ax1.set_ylabel('Day of Week')
        ax1.set_xlabel('Week')
        ax1.set_yticks(range(7))
        ax1.set_yticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
        
        # Add colorbar
        cbar1 = plt.colorbar(im1, ax=ax1)
        cbar1.set_label('Commits per Day')
        
        # Repository distribution pie chart
        repo_names = list(data['repositories'].keys())
        commit_counts_by_repo = [data['repositories'][repo]['commit_count'] for repo in repo_names]
        
        # Only show top 10 repos, group others as 'Others'
        if len(repo_names) > 10:
            sorted_repos = sorted(zip(repo_names, commit_counts_by_repo), key=lambda x: x[1], reverse=True)
            top_repos = sorted_repos[:10]
            others_count = sum([count for _, count in sorted_repos[10:]])
            
            repo_names = [name for name, _ in top_repos] + ['Others']
            commit_counts_by_repo = [count for _, count in top_repos] + [others_count]
        
        ax2.pie(commit_counts_by_repo, labels=repo_names, autopct='%1.1f%%', startangle=90)
        ax2.set_title(f"Commit Distribution by Repository\nTotal: {data['total_commits']} commits", 
                     fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        
        # Create output directory and save files
        output_dir = self.create_output_directory(data['username'])
        timestamp = datetime.now().strftime('%Y-%m-%d')
        
        if output_path:
            final_path = output_path
        else:
            final_path = os.path.join(output_dir, f"productivity_heatmap_{data['username']}_{timestamp}.png")
        
        plt.savefig(final_path, dpi=300, bbox_inches='tight')
        print(f"Heatmap saved to {final_path}")
        
        # Generate text summary
        self.generate_text_summary(data, output_dir)
        
        try:
            plt.show()
        except Exception:
            print("Plot saved to file (display not available)")
    
    def create_timeline_chart(self, data: Dict, output_path: str = None):
        """Create a timeline chart showing daily commit activity."""
        if not data or not data['repositories']:
            print("No data available for timeline chart generation.")
            return
        
        # Collect all commits with dates
        daily_commits = defaultdict(int)
        for repo_data in data['repositories'].values():
            for commit in repo_data['commits']:
                commit_date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
                date_key = commit_date.date()
                daily_commits[date_key] += 1
        
        if not daily_commits:
            print("No commits found for timeline chart generation.")
            return
        
        # Sort dates and prepare data
        dates = sorted(daily_commits.keys())
        counts = [daily_commits[date] for date in dates]
        
        # Create timeline chart
        fig, ax = plt.subplots(figsize=(15, 6))
        ax.plot(dates, counts, marker='o', linewidth=2, markersize=4)
        ax.fill_between(dates, counts, alpha=0.3)
        
        ax.set_title(f"Daily Commit Activity Timeline for {data['username']}\n{data['timeframe']['since']} to {data['timeframe']['until']}", 
                    fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Number of Commits')
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        # Create output directory and save files
        output_dir = self.create_output_directory(data['username'])
        timestamp = datetime.now().strftime('%Y-%m-%d')
        
        if output_path:
            final_path = output_path
        else:
            final_path = os.path.join(output_dir, f"commit_timeline_{data['username']}_{timestamp}.png")
        
        plt.savefig(final_path, dpi=300, bbox_inches='tight')
        print(f"Timeline chart saved to {final_path}")
        
        # Only show plot if not in headless environment
        try:
            plt.show()
        except Exception:
            print("Plot saved to file (display not available)")


def main():
    # Load environment variables from .env file
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Track GitHub user productivity across organization repositories')
    parser.add_argument('--username', help='GitHub username to track (or set GITHUB_USERNAME in .env)')
    parser.add_argument('--organization', help='GitHub organization name (or set GITHUB_ORGANIZATION in .env)')
    parser.add_argument('--timeframe', '-t', choices=['3days', '1week', '1month', 'custom'], 
                       default='1week', help='Timeframe preset (default: 1week)')
    parser.add_argument('--start-date', help='Custom start date (YYYY-MM-DD) - required for custom timeframe')
    parser.add_argument('--end-date', help='Custom end date (YYYY-MM-DD) - required for custom timeframe')
    parser.add_argument('--token', help='GitHub personal access token (or set GITHUB_TOKEN in .env)')
    parser.add_argument('--output', '-o', help='Output JSON file path (optional)')
    parser.add_argument('--heatmap', action='store_true', help='Generate heatmap visualization')
    parser.add_argument('--timeline', action='store_true', help='Generate timeline chart')
    parser.add_argument('--viz-output', help='Output path for visualization files (optional)')
    parser.add_argument('--include-prs', action='store_true', help='Include pull request metrics')
    parser.add_argument('--include-reviews', action='store_true', help='Include code review metrics')
    parser.add_argument('--include-issues', action='store_true', help='Include issue creation metrics')
    parser.add_argument('--include-lines', action='store_true', help='Include lines of code modified metrics')
    parser.add_argument('--all', action='store_true', help='Include all available productivity indicators')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed progress and branch-by-branch information')
    parser.add_argument('--repoignore', default='.repoignore', help='Path to repository ignore file (default: .repoignore)')
    
    args = parser.parse_args()
    
    # Get values from .env file or command line arguments
    username = args.username or os.getenv('GITHUB_USERNAME')
    organization = args.organization or os.getenv('GITHUB_ORGANIZATION')
    token = args.token or os.getenv('GITHUB_TOKEN')
    
    # Handle --all flag
    if args.all:
        args.include_prs = True
        args.include_reviews = True
        args.include_issues = True
        args.include_lines = True
    
    # Validate required parameters
    if not username:
        print("Error: GitHub username is required. Set GITHUB_USERNAME in .env or use --username")
        sys.exit(1)
    
    if not organization:
        print("Error: GitHub organization is required. Set GITHUB_ORGANIZATION in .env or use --organization")
        sys.exit(1)
    
    # Validate custom timeframe arguments
    if args.timeframe == 'custom':
        if not args.start_date or not args.end_date:
            print("Error: Custom timeframe requires both --start-date and --end-date")
            sys.exit(1)
    
    # Initialize tracker
    tracker = GitHubProductivityTracker(organization, token, args.verbose)
    
    # Track productivity
    data = tracker.track_user_productivity(
        username, 
        args.timeframe,
        args.start_date,
        args.end_date,
        args.include_prs,
        args.include_reviews,
        args.include_issues,
        args.include_lines,
        args.repoignore
    )
    
    # Display report
    tracker.display_productivity_report(data)
    
    # Save to file if requested
    if args.output:
        output_path = args.output
    else:
        # Create user directory and save with timestamp
        output_dir = f"outputs/{data['username']}"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y-%m-%d')
        output_path = os.path.join(output_dir, f"raw_data_{data['username']}_{timestamp}.json")
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\nData saved to {output_path}")
    
    # Generate visualizations if requested
    if args.heatmap:
        print("\nGenerating heatmap visualization...")
        viz_path = args.viz_output if args.viz_output else None
        tracker.create_heatmap(data, viz_path)
    
    if args.timeline:
        print("\nGenerating timeline chart...")
        viz_path = args.viz_output if args.viz_output else None
        tracker.create_timeline_chart(data, viz_path)


if __name__ == "__main__":
    main()