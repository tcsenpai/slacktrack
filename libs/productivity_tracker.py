"""
Core productivity tracking functionality.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from tqdm import tqdm
from typing import Dict, List, Optional
from datetime import datetime

from .github_api import GitHubAPIClient
from .data_utils import get_timeframe_dates, filter_repositories


class ProductivityTracker:
    """Core productivity tracking logic."""
    
    def __init__(self, org_name: str, github_token: Optional[str] = None, verbose: bool = False):
        self.org_name = org_name
        self.verbose = verbose
        self.api_client = GitHubAPIClient(github_token, verbose)
    
    def get_commit_stats_batch(self, repo_name: str, commits: List[Dict]) -> List[Dict]:
        """Fetch commit statistics in parallel for better performance."""
        def get_single_commit_stats(commit):
            sha = commit['sha']
            stats_data = self.api_client.get_commit_stats(self.org_name, repo_name, sha)
            commit['stats'] = stats_data['stats']
            commit['files'] = stats_data['files']
            return commit
        
        if not commits:
            return commits
        
        self.api_client._verbose_print(f"Fetching stats for {len(commits)} commits in {repo_name}")
        
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
        """Get commits by a specific user in a repository within the timeframe from ALL branches."""
        # Get all branches
        branches = self.api_client.get_repo_branches(self.org_name, repo_name)
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
                executor.submit(self.api_client.get_branch_commits, self.org_name, repo_name, branch, username, since, until): branch 
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
    
    def track_user_productivity(self, username: str, timeframe: str, 
                              custom_start: str = None, custom_end: str = None, 
                              include_prs: bool = False, include_reviews: bool = False, 
                              include_issues: bool = False, include_lines: bool = False,
                              repoignore_path: str = '.repoignore') -> Dict:
        """Track user productivity across all organization repositories."""
        try:
            since, until = get_timeframe_dates(timeframe, custom_start, custom_end)
        except ValueError as e:
            print(f"Error: {e}")
            return {}
        
        print(f"Tracking productivity for {username} from {since} to {until}")
        print(f"Fetching repositories for organization: {self.org_name}")
        
        repos = self.api_client.get_organization_repos(self.org_name)
        if not repos:
            print("No repositories found or error fetching repositories.")
            return {}
        
        # Filter repositories based on .repoignore
        repos = filter_repositories(repos, repoignore_path, self.verbose)
        
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
            prs = self.api_client.search_pull_requests(username, self.org_name, since[:10], until[:10])
            result['pull_requests'] = {
                'total': len(prs),
                'data': prs
            }
            print(f"Found {len(prs)} pull requests")
        
        if include_reviews:
            print("Fetching code reviews...")
            reviews = self.api_client.search_code_reviews(username, self.org_name, since[:10], until[:10])
            result['code_reviews'] = {
                'total': len(reviews),
                'data': reviews
            }
            print(f"Found {len(reviews)} code reviews")
        
        if include_issues:
            print("Fetching issues...")
            issues = self.api_client.search_issues(username, self.org_name, since[:10], until[:10])
            result['issues'] = {
                'total': len(issues),
                'data': issues
            }
            print(f"Found {len(issues)} issues created")
        
        return result
    
    def track_user_personal_productivity(self, username: str, timeframe: str,
                                       custom_start: str = None, custom_end: str = None,
                                       include_prs: bool = False, include_reviews: bool = False,
                                       include_issues: bool = False, include_lines: bool = False,
                                       repoignore_path: str = ".repoignore") -> Dict:
        """Track user productivity across their personal repositories."""
        try:
            since, until = get_timeframe_dates(timeframe, custom_start, custom_end)
        except ValueError as e:
            print(f"Error: {e}")
            return {}

        print(f"\nTracking PERSONAL productivity for {username} from {since} to {until}")
        print(f"Fetching personal repositories for user: {username}")

        original_org = self.org_name

        try:
            repos = self.api_client.get_user_personal_repos(username)
            if not repos:
                print("No personal repositories found or error fetching repositories.")
                return {}

            repos = filter_repositories(repos, repoignore_path, self.verbose)
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

    def compare_personal_vs_organization(self, username: str, timeframe: str,
                                       custom_start: str = None, custom_end: str = None,
                                       include_prs: bool = False, include_reviews: bool = False,
                                       include_issues: bool = False, include_lines: bool = False,
                                       repoignore_path: str = ".repoignore") -> Dict:
        """Compare productivity between personal and organization repositories."""
        print(f"Comparing personal vs organization productivity for {username}...")
        
        # Track organization productivity
        org_data = self.track_user_productivity(
            username, timeframe, custom_start, custom_end,
            include_prs, include_reviews, include_issues, include_lines, repoignore_path
        )
        
        # Track personal productivity
        personal_data = self.track_user_personal_productivity(
            username, timeframe, custom_start, custom_end,
            include_prs, include_reviews, include_issues, include_lines, repoignore_path
        )
        
        # Create comparison data structure
        comparison = {
            'username': username,
            'timeframe': org_data.get('timeframe', {}),
            'organization': {
                'name': self.org_name,
                'data': org_data
            },
            'personal': {
                'data': personal_data
            },
            'comparison': {
                'total_commits': {
                    'organization': org_data.get('total_commits', 0),
                    'personal': personal_data.get('total_commits', 0),
                    'difference': personal_data.get('total_commits', 0) - org_data.get('total_commits', 0)
                },
                'active_repositories': {
                    'organization': len(org_data.get('repositories', {})),
                    'personal': len(personal_data.get('repositories', {})),
                    'difference': len(personal_data.get('repositories', {})) - len(org_data.get('repositories', {}))
                }
            }
        }
        
        # Add line stats comparison if available
        if include_lines:
            org_lines = org_data.get('line_stats', {})
            personal_lines = personal_data.get('line_stats', {})
            
            comparison['comparison']['line_stats'] = {
                'organization': org_lines,
                'personal': personal_lines,
                'difference': {
                    'total_additions': personal_lines.get('total_additions', 0) - org_lines.get('total_additions', 0),
                    'total_deletions': personal_lines.get('total_deletions', 0) - org_lines.get('total_deletions', 0),
                    'total_changes': personal_lines.get('total_changes', 0) - org_lines.get('total_changes', 0)
                }
            }
        
        # Add PR/review/issue comparisons if available
        if include_prs:
            org_prs = org_data.get('pull_requests', {}).get('total', 0)
            personal_prs = personal_data.get('pull_requests', {}).get('total', 0)
            comparison['comparison']['pull_requests'] = {
                'organization': org_prs,
                'personal': personal_prs,
                'difference': personal_prs - org_prs
            }
        
        if include_reviews:
            org_reviews = org_data.get('code_reviews', {}).get('total', 0)
            personal_reviews = personal_data.get('code_reviews', {}).get('total', 0)
            comparison['comparison']['code_reviews'] = {
                'organization': org_reviews,
                'personal': personal_reviews,
                'difference': personal_reviews - org_reviews
            }
        
        if include_issues:
            org_issues = org_data.get('issues', {}).get('total', 0)
            personal_issues = personal_data.get('issues', {}).get('total', 0)
            comparison['comparison']['issues'] = {
                'organization': org_issues,
                'personal': personal_issues,
                'difference': personal_issues - org_issues
            }
        
        return comparison