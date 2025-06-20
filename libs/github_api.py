"""
GitHub API client with rate limiting and retry logic.
"""

import requests
import time
import threading
from typing import Dict, List, Optional


class GitHubAPIClient:
    """GitHub API client with built-in rate limiting and retry logic."""
    
    def __init__(self, github_token: Optional[str] = None, verbose: bool = False):
        self.github_token = github_token
        self.base_url = "https://api.github.com"
        self.verbose = verbose
        self._lock = threading.Lock()
        
        if not self.github_token:
            print("Warning: No GitHub token provided. API rate limits will be severely restricted.")
        
        self.headers = {
            'Authorization': f'token {self.github_token}' if self.github_token else '',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Rate limiting tracking
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0
        self.search_rate_limit_remaining = 30
        self.search_rate_limit_reset = 0
    
    def _verbose_print(self, message: str):
        """Thread-safe verbose printing."""
        if self.verbose:
            with self._lock:
                print(f"[VERBOSE] {message}")
    
    def make_request(self, url: str, params: Optional[Dict] = None, is_search: bool = False, max_retries: int = 3) -> requests.Response:
        """Make API request with rate limiting and retry logic."""
        for attempt in range(max_retries):
            try:
                # Check rate limits before making request
                if is_search:
                    if self.search_rate_limit_remaining <= 1:
                        if self.search_rate_limit_reset > time.time():
                            wait_time = self.search_rate_limit_reset - time.time() + 1
                            self._verbose_print(f"Search API rate limit reached. Waiting {wait_time:.0f} seconds...")
                            time.sleep(wait_time)
                else:
                    if self.rate_limit_remaining <= 1:
                        if self.rate_limit_reset > time.time():
                            wait_time = self.rate_limit_reset - time.time() + 1
                            self._verbose_print(f"API rate limit reached. Waiting {wait_time:.0f} seconds...")
                            time.sleep(wait_time)
                
                response = requests.get(url, headers=self.headers, params=params)
                
                # Update rate limit tracking from response headers
                if 'X-RateLimit-Remaining' in response.headers:
                    if is_search:
                        self.search_rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 30))
                        self.search_rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                    else:
                        self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 5000))
                        self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
                
                # Handle rate limit exceeded (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    if attempt < max_retries - 1:
                        self._verbose_print(f"Rate limit exceeded (429). Retrying after {retry_after} seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_after)
                        continue
                    else:
                        print(f"Rate limit exceeded and max retries reached. Response: {response.status_code}")
                        return response
                
                # Handle other server errors with exponential backoff
                if response.status_code >= 500 and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    self._verbose_print(f"Server error {response.status_code}. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    self._verbose_print(f"Request exception: {e}. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Request failed after {max_retries} attempts: {e}")
                    raise
        
        return response
    
    def get_organization_repos(self, org_name: str) -> List[Dict]:
        """Fetch all repositories in the organization."""
        repos = []
        page = 1
        
        while True:
            url = f"{self.base_url}/orgs/{org_name}/repos"
            params = {
                'page': page,
                'per_page': 100,
                'type': 'all'
            }
            
            response = self.make_request(url, params)
            
            if response.status_code != 200:
                print(f"Error fetching repositories: {response.status_code}")
                if response.status_code == 401:
                    print("Authentication failed. Check your GitHub token.")
                elif response.status_code == 403:
                    print("Access forbidden. Token may lack organization access.")
                break
            
            page_repos = response.json()
            if not page_repos:
                break
            
            repos.extend(page_repos)
            page += 1
        
        return repos
    
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

            response = self.make_request(url, params)

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

        return repos
    
    def get_repo_branches(self, org_name: str, repo_name: str) -> List[str]:
        """Get all branches for a repository."""
        branches = []
        page = 1
        
        while True:
            url = f"{self.base_url}/repos/{org_name}/{repo_name}/branches"
            params = {'page': page, 'per_page': 100}
            
            response = self.make_request(url, params)
            
            if response.status_code != 200:
                self._verbose_print(f"Error fetching branches for {repo_name}: {response.status_code}")
                break
            
            page_branches = response.json()
            if not page_branches:
                break
            
            branches.extend([branch['name'] for branch in page_branches])
            page += 1
        
        return branches
    
    def get_branch_commits(self, org_name: str, repo_name: str, branch: str, username: str, since: str, until: str) -> List[Dict]:
        """Get commits for a specific branch."""
        commits = []
        page = 1
        
        self._verbose_print(f"Starting branch {branch} in {repo_name}")
        
        while True:
            url = f"{self.base_url}/repos/{org_name}/{repo_name}/commits"
            params = {
                'author': username,
                'sha': branch,
                'since': since,
                'until': until,
                'page': page,
                'per_page': 100
            }
            
            response = self.make_request(url, params)
            
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
    
    def get_commit_stats(self, org_name: str, repo_name: str, commit_sha: str) -> Dict:
        """Get statistics for a single commit."""
        url = f"{self.base_url}/repos/{org_name}/{repo_name}/commits/{commit_sha}"
        response = self.make_request(url)
        
        if response.status_code == 200:
            detailed = response.json()
            return {
                'stats': detailed.get('stats', {}),
                'files': detailed.get('files', [])
            }
        else:
            return {
                'stats': {'total': 0, 'additions': 0, 'deletions': 0},
                'files': []
            }
    
    def search_pull_requests(self, username: str, org_name: str, since: str, until: str) -> List[Dict]:
        """Get pull requests created by the user in the organization."""
        prs = []
        page = 1
        
        while True:
            url = f"{self.base_url}/search/issues"
            query = f"type:pr author:{username} org:{org_name} created:{since}..{until}"
            params = {
                'q': query,
                'page': page,
                'per_page': 100
            }
            
            response = self.make_request(url, params, is_search=True)
            
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
    
    def search_code_reviews(self, username: str, org_name: str, since: str, until: str) -> List[Dict]:
        """Get code reviews performed by the user."""
        reviews = []
        page = 1
        
        while True:
            url = f"{self.base_url}/search/issues"
            query = f"type:pr reviewed-by:{username} org:{org_name} updated:{since}..{until}"
            params = {
                'q': query,
                'page': page,
                'per_page': 100
            }
            
            response = self.make_request(url, params, is_search=True)
            
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
    
    def search_issues(self, username: str, org_name: str, since: str, until: str) -> List[Dict]:
        """Get issues created by the user."""
        issues = []
        page = 1
        
        while True:
            url = f"{self.base_url}/search/issues"
            query = f"type:issue author:{username} org:{org_name} created:{since}..{until}"
            params = {
                'q': query,
                'page': page,
                'per_page': 100
            }
            
            response = self.make_request(url, params, is_search=True)
            
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