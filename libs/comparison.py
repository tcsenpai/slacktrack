"""
User comparison functionality for analyzing multiple users' productivity.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from .data_utils import load_user_data, load_personal_data, load_comparison_data, extract_metrics


class UserComparator:
    """Compare productivity metrics between multiple users."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.users_data = {}
        
    def _verbose_print(self, message: str):
        """Print verbose messages if enabled."""
        if self.verbose:
            print(f"[VERBOSE] {message}")
    
    def load_user_data_for_comparison(self, username: str, data_file: Optional[str] = None) -> bool:
        """Load all available user data (raw, personal, comparison) for comprehensive comparison."""
        if data_file:
            # If specific file provided, load just that
            try:
                with open(data_file, 'r') as f:
                    data = json.load(f)
                self.users_data[username] = data
                self._verbose_print(f"Loaded data for {username} from {data_file}")
                return True
            except (FileNotFoundError, json.JSONDecodeError):
                print(f"Error: Could not load data from {data_file}")
                return False
        
        # Load all available data types for the user
        user_data = {}
        found_any = False
        
        # Try to load raw organization data
        raw_data = load_user_data(username)
        if raw_data:
            user_data['raw_data'] = raw_data
            found_any = True
            self._verbose_print(f"Loaded raw data for {username}")
        
        # Try to load personal data
        personal_data = load_personal_data(username)
        if personal_data:
            user_data['personal_data'] = personal_data
            found_any = True
            self._verbose_print(f"Loaded personal data for {username}")
        
        # Try to load comparison data
        comparison_data = load_comparison_data(username)
        if comparison_data:
            user_data['comparison_data'] = comparison_data
            found_any = True
            self._verbose_print(f"Loaded comparison data for {username}")
        
        if found_any:
            self.users_data[username] = user_data
            return True
        else:
            print(f"Error: No data found for user '{username}'")
            return False
    
    def analyze_personal_vs_org_ratio(self, username: str) -> Dict:
        """Analyze personal vs organization ratio for a user."""
        user_data = self.users_data.get(username)
        if not user_data:
            return {'error': f'No data found for user {username}'}
        
        # Handle new multi-data structure
        if isinstance(user_data, dict) and ('raw_data' in user_data or 'personal_data' in user_data or 'comparison_data' in user_data):
            # Extract individual data types
            org_data = user_data.get('raw_data')
            personal_data = user_data.get('personal_data')
            comparison_data = user_data.get('comparison_data')
            
            # If we have comparison data, use it directly
            if comparison_data and 'comparison' in comparison_data:
                analysis = {
                    'username': username,
                    'has_org_data': True,
                    'has_personal_data': True,
                    'comparison_data': comparison_data
                }
                
                # Extract ratios from comparison data
                comp = comparison_data.get('comparison', {})
                org_commits = comp.get('total_commits', {}).get('organization', 0)
                personal_commits = comp.get('total_commits', {}).get('personal', 0)
                total_commits = org_commits + personal_commits
                
                if total_commits > 0:
                    analysis['ratios'] = {
                        'org_percentage': (org_commits / total_commits) * 100,
                        'personal_percentage': (personal_commits / total_commits) * 100,
                        'org_commits': org_commits,
                        'personal_commits': personal_commits,
                        'total_commits': total_commits
                    }
                else:
                    analysis['ratios'] = {
                        'org_percentage': 0,
                        'personal_percentage': 0,
                        'org_commits': 0,
                        'personal_commits': 0,
                        'total_commits': 0
                    }
                
                # Extract metrics from nested data
                if comparison_data.get('organization', {}).get('data'):
                    analysis['org_metrics'] = extract_metrics(comparison_data['organization']['data'])
                if comparison_data.get('personal', {}).get('data'):
                    analysis['personal_metrics'] = extract_metrics(comparison_data['personal']['data'])
                
                return analysis
            
            # If we have separate org and personal data, calculate ratios
            elif org_data and personal_data:
                analysis = {
                    'username': username,
                    'has_org_data': True,
                    'has_personal_data': True,
                    'org_metrics': extract_metrics(org_data),
                    'personal_metrics': extract_metrics(personal_data)
                }
                
                # Calculate ratios
                org_commits = analysis['org_metrics']['total_commits']
                personal_commits = analysis['personal_metrics']['total_commits']
                total_commits = org_commits + personal_commits
                
                if total_commits > 0:
                    analysis['ratios'] = {
                        'org_percentage': (org_commits / total_commits) * 100,
                        'personal_percentage': (personal_commits / total_commits) * 100,
                        'org_commits': org_commits,
                        'personal_commits': personal_commits,
                        'total_commits': total_commits
                    }
                else:
                    analysis['ratios'] = {
                        'org_percentage': 0,
                        'personal_percentage': 0,
                        'org_commits': 0,
                        'personal_commits': 0,
                        'total_commits': 0
                    }
                
                return analysis
            
            # If we only have org data, show that
            elif org_data:
                analysis = {
                    'username': username,
                    'has_org_data': True,
                    'has_personal_data': False,
                    'org_metrics': extract_metrics(org_data)
                }
                return analysis
            
            # If we only have personal data, show that
            elif personal_data:
                analysis = {
                    'username': username,
                    'has_org_data': False,
                    'has_personal_data': True,
                    'personal_metrics': extract_metrics(personal_data)
                }
                return analysis
        
        # Fallback to legacy single-data handling
        org_data = user_data
        
        # Check if org_data is actually comparison data
        if org_data and 'comparison' in org_data:
            # Use the comparison data directly
            comparison_data = org_data
            analysis = {
                'username': username,
                'has_org_data': True,
                'has_personal_data': True,
                'comparison_data': comparison_data
            }
            
            # Extract ratios from comparison data
            comp = comparison_data.get('comparison', {})
            org_commits = comp.get('total_commits', {}).get('organization', 0)
            personal_commits = comp.get('total_commits', {}).get('personal', 0)
            total_commits = org_commits + personal_commits
            
            if total_commits > 0:
                analysis['ratios'] = {
                    'org_percentage': (org_commits / total_commits) * 100,
                    'personal_percentage': (personal_commits / total_commits) * 100,
                    'org_commits': org_commits,
                    'personal_commits': personal_commits,
                    'total_commits': total_commits
                }
            else:
                analysis['ratios'] = {
                    'org_percentage': 0,
                    'personal_percentage': 0,
                    'org_commits': 0,
                    'personal_commits': 0,
                    'total_commits': 0
                }
            
            # Extract metrics from nested data
            if comparison_data.get('organization', {}).get('data'):
                analysis['org_metrics'] = extract_metrics(comparison_data['organization']['data'])
            if comparison_data.get('personal', {}).get('data'):
                analysis['personal_metrics'] = extract_metrics(comparison_data['personal']['data'])
            
            return analysis
        
        # Fallback to loading separate files
        personal_data = load_personal_data(username)
        comparison_data = load_comparison_data(username)
        
        # Check if we have ratio summary data
        if comparison_data and 'ratios' in comparison_data and not 'comparison' in comparison_data:
            # This is a ratio summary file
            analysis = {
                'username': username,
                'has_org_data': True,
                'has_personal_data': True,
                'ratios': {
                    'org_percentage': comparison_data['ratios']['org_percentage'],
                    'personal_percentage': comparison_data['ratios']['personal_percentage'],
                    'org_commits': comparison_data['ratios']['organization'],
                    'personal_commits': comparison_data['ratios']['personal'],
                    'total_commits': comparison_data['ratios']['organization'] + comparison_data['ratios']['personal']
                }
            }
            return analysis
        
        if not org_data and not personal_data and not comparison_data:
            return {'error': f'No data found for user {username}'}
        
        analysis = {
            'username': username,
            'has_org_data': org_data is not None,
            'has_personal_data': personal_data is not None,
            'org_metrics': extract_metrics(org_data) if org_data else None,
            'personal_metrics': extract_metrics(personal_data) if personal_data else None
        }
        
        # Calculate ratios if both datasets exist
        if analysis['has_org_data'] and analysis['has_personal_data']:
            org_commits = analysis['org_metrics']['total_commits']
            personal_commits = analysis['personal_metrics']['total_commits']
            total_commits = org_commits + personal_commits
            
            if total_commits > 0:
                analysis['ratios'] = {
                    'org_percentage': (org_commits / total_commits) * 100,
                    'personal_percentage': (personal_commits / total_commits) * 100,
                    'org_commits': org_commits,
                    'personal_commits': personal_commits,
                    'total_commits': total_commits
                }
            else:
                analysis['ratios'] = {
                    'org_percentage': 0,
                    'personal_percentage': 0,
                    'org_commits': 0,
                    'personal_commits': 0,
                    'total_commits': 0
                }
        
        return analysis
    
    def compare_users(self, usernames: List[str]) -> Dict:
        """Compare multiple users across various metrics."""
        comparison = {
            'users': usernames,
            'timestamp': datetime.now().isoformat(),
            'individual_metrics': {},
            'personal_vs_org_analysis': {},
            'cross_user_comparison': {
                'org_productivity': {},
                'personal_productivity': {},
                'combined_productivity': {}
            },
            'insights': []
        }
        
        # Analyze each user individually
        for username in usernames:
            if username in self.users_data:
                user_data = self.users_data[username]
                
                # Handle new multi-data structure
                if isinstance(user_data, dict) and ('raw_data' in user_data or 'personal_data' in user_data or 'comparison_data' in user_data):
                    # Use raw organization data for individual metrics, fallback to comparison data
                    if user_data.get('raw_data'):
                        comparison['individual_metrics'][username] = extract_metrics(user_data['raw_data'])
                    elif user_data.get('comparison_data') and user_data['comparison_data'].get('organization', {}).get('data'):
                        comparison['individual_metrics'][username] = extract_metrics(user_data['comparison_data']['organization']['data'])
                    elif user_data.get('personal_data'):
                        # If only personal data, use that for individual metrics
                        comparison['individual_metrics'][username] = extract_metrics(user_data['personal_data'])
                else:
                    # Legacy single-data handling
                    comparison['individual_metrics'][username] = extract_metrics(user_data)
                
                comparison['personal_vs_org_analysis'][username] = self.analyze_personal_vs_org_ratio(username)
            else:
                print(f"Warning: No data loaded for user {username}")
        
        # Cross-user comparisons
        self._perform_cross_user_analysis(comparison)
        
        # Generate insights
        self._generate_insights(comparison)
        
        return comparison
    
    def _perform_cross_user_analysis(self, comparison: Dict):
        """Perform detailed cross-user analysis."""
        users = comparison['users']
        
        # Compare organization productivity
        org_metrics = {}
        for username in users:
            if username in comparison['individual_metrics']:
                org_metrics[username] = comparison['individual_metrics'][username]
        
        comparison['cross_user_comparison']['org_productivity'] = self._compare_metrics(org_metrics)
        
        # Compare personal productivity (if available)
        personal_metrics = {}
        for username in users:
            personal_analysis = comparison['personal_vs_org_analysis'].get(username)
            if personal_analysis and personal_analysis.get('personal_metrics'):
                personal_metrics[username] = personal_analysis['personal_metrics']
        
        if personal_metrics:
            comparison['cross_user_comparison']['personal_productivity'] = self._compare_metrics(personal_metrics)
        
        # Combined productivity comparison
        combined_metrics = {}
        for username in users:
            org_analysis = comparison['personal_vs_org_analysis'].get(username)
            if org_analysis and org_analysis.get('ratios'):
                combined_metrics[username] = {
                    'total_commits': org_analysis['ratios']['total_commits'],
                    'org_percentage': org_analysis['ratios']['org_percentage'],
                    'personal_percentage': org_analysis['ratios']['personal_percentage']
                }
        
        comparison['cross_user_comparison']['combined_productivity'] = combined_metrics
    
    def _compare_metrics(self, user_metrics: Dict) -> Dict:
        """Compare metrics across users."""
        if not user_metrics:
            return {}
            
        comparison = {
            'commits': {},
            'repositories': {},
            'activity_patterns': {},
            'code_volume': {}
        }
        
        for username, metrics in user_metrics.items():
            comparison['commits'][username] = {
                'total': metrics['total_commits'],
                'per_day': metrics['avg_commits_per_day'],
                'per_repo': metrics['avg_commits_per_repo']
            }
            
            comparison['repositories'][username] = {
                'total': metrics['total_repositories'],
                'most_active': max(metrics['commits_by_repo'].items(), key=lambda x: x[1])[0] if metrics['commits_by_repo'] else 'None'
            }
            
            comparison['activity_patterns'][username] = {
                'active_days': metrics['total_active_days'],
                'commit_distribution': metrics['commits_by_date']
            }
            
            comparison['code_volume'][username] = {
                'lines_added': metrics['total_lines_added'],
                'lines_deleted': metrics['total_lines_deleted'],
                'lines_changed': metrics['total_lines_changed']
            }
        
        return comparison
    
    def _generate_insights(self, comparison: Dict):
        """Generate insights from the comparison data."""
        insights = []
        users = comparison['users']
        
        # Personal vs Org ratio insights
        ratio_data = []
        for username in users:
            analysis = comparison['personal_vs_org_analysis'].get(username)
            if analysis and analysis.get('ratios'):
                ratio_data.append((username, analysis['ratios']))
        
        if ratio_data:
            insights.append("Personal vs Organization Work Balance:")
            for username, ratios in ratio_data:
                insights.append(f"  • {username}: {ratios['org_percentage']:.1f}% org, {ratios['personal_percentage']:.1f}% personal")
        
        # Productivity comparison insights
        org_comparison = comparison['cross_user_comparison']['org_productivity']
        if org_comparison and 'commits' in org_comparison:
            commits_data = [(user, data['total']) for user, data in org_comparison['commits'].items()]
            commits_data.sort(key=lambda x: x[1], reverse=True)
            
            if len(commits_data) >= 2:
                top_user, top_commits = commits_data[0]
                insights.append(f"\nOrganization Productivity Leader:")
                insights.append(f"  • {top_user} leads with {top_commits} commits")
        
        # Activity pattern insights
        for username in users:
            analysis = comparison['personal_vs_org_analysis'].get(username)
            if analysis:
                org_metrics = analysis.get('org_metrics')
                personal_metrics = analysis.get('personal_metrics')
                
                if org_metrics and personal_metrics:
                    org_repos = org_metrics['total_repositories']
                    personal_repos = personal_metrics['total_repositories']
                    insights.append(f"\n{username} Repository Engagement:")
                    insights.append(f"  • Organization: {org_repos} repos")
                    insights.append(f"  • Personal: {personal_repos} repos")
        
        comparison['insights'] = insights
    
    def create_comparison_visualizations(self, comparison: Dict, output_dir: str = "outputs/comparisons") -> List[str]:
        """Create comprehensive visualizations for user comparison."""
        # Create a specific folder for this comparison
        users_str = "_vs_".join(comparison['users'])
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        comparison_dir = os.path.join(output_dir, f"{users_str}_{timestamp}")
        os.makedirs(comparison_dir, exist_ok=True)
        created_files = []
        
        # Set up the style
        plt.style.use('default')
        sns.set_palette("husl")
        
        # 1. Commits comparison bar chart
        fig, ax = plt.subplots(figsize=(12, 6))
        users = comparison['users']
        
        org_commits = []
        personal_commits = []
        user_labels = []
        
        for username in users:
            analysis = comparison['personal_vs_org_analysis'].get(username)
            if analysis and analysis.get('ratios'):
                ratios = analysis['ratios']
                org_commits.append(ratios['org_commits'])
                personal_commits.append(ratios['personal_commits'])
                user_labels.append(username)
            elif username in comparison['individual_metrics']:
                metrics = comparison['individual_metrics'][username]
                org_commits.append(metrics['total_commits'])
                personal_commits.append(0)
                user_labels.append(username)
        
        if user_labels:
            x = np.arange(len(user_labels))
            width = 0.35
            
            bars1 = ax.bar(x - width/2, org_commits, width, label='Organization', alpha=0.8)
            bars2 = ax.bar(x + width/2, personal_commits, width, label='Personal', alpha=0.8)
            
            ax.set_xlabel('Users')
            ax.set_ylabel('Number of Commits')
            ax.set_title('Commit Distribution: Organization vs Personal')
            ax.set_xticks(x)
            ax.set_xticklabels(user_labels)
            ax.legend()
            
            # Add value labels on bars
            for bar in bars1:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{int(height)}', ha='center', va='bottom')
            
            for bar in bars2:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{int(height)}', ha='center', va='bottom')
            
            plt.tight_layout()
            commits_file = os.path.join(comparison_dir, "commits_comparison.png")
            plt.savefig(commits_file, dpi=300, bbox_inches='tight')
            created_files.append(commits_file)
            plt.close()
        
        # 2. Personal vs Organization ratio pie charts
        ratio_users = [u for u in users if comparison['personal_vs_org_analysis'].get(u, {}).get('ratios')]
        if ratio_users:
            fig, axes = plt.subplots(1, len(ratio_users), figsize=(6*len(ratio_users), 5))
            if len(ratio_users) == 1:
                axes = [axes]
            
            for i, username in enumerate(ratio_users):
                analysis = comparison['personal_vs_org_analysis'].get(username)
                ratios = analysis['ratios']
                if ratios['total_commits'] > 0:
                    sizes = [ratios['org_commits'], ratios['personal_commits']]
                    labels = ['Organization', 'Personal']
                    colors = ['#ff9999', '#66b3ff']
                    
                    axes[i].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                               startangle=90, textprops={'fontsize': 10})
                    axes[i].set_title(f'{username}\\nTotal: {ratios["total_commits"]} commits')
                else:
                    axes[i].text(0.5, 0.5, 'No commits', ha='center', va='center', transform=axes[i].transAxes)
                    axes[i].set_title(f'{username}\\nNo data')
            
            plt.tight_layout()
            ratios_file = os.path.join(comparison_dir, "ratios_comparison.png")
            plt.savefig(ratios_file, dpi=300, bbox_inches='tight')
            created_files.append(ratios_file)
            plt.close()
        
        # 3. Activity heatmap comparison
        fig, axes = plt.subplots(len(users), 1, figsize=(15, 4*len(users)))
        if len(users) == 1:
            axes = [axes]
        
        for i, username in enumerate(users):
            metrics = comparison['individual_metrics'].get(username)
            if metrics and metrics['commits_by_date']:
                # Create date range for the timeframe
                dates = list(metrics['commits_by_date'].keys())
                if dates:
                    start_date = datetime.strptime(min(dates), '%Y-%m-%d')
                    end_date = datetime.strptime(max(dates), '%Y-%m-%d')
                    
                    # Create a complete date range
                    date_range = []
                    current_date = start_date
                    while current_date <= end_date:
                        date_range.append(current_date.strftime('%Y-%m-%d'))
                        current_date += timedelta(days=1)
                    
                    # Create data for heatmap
                    commit_counts = [metrics['commits_by_date'].get(date, 0) for date in date_range]
                    
                    # Create heatmap data (reshape for weekly view)
                    weeks = len(date_range) // 7 + (1 if len(date_range) % 7 else 0)
                    heatmap_data = np.zeros((weeks, 7))
                    
                    for idx, count in enumerate(commit_counts):
                        week = idx // 7
                        day = idx % 7
                        if week < weeks:
                            heatmap_data[week, day] = count
                    
                    # Create heatmap
                    sns.heatmap(heatmap_data, annot=True, fmt='g', cmap='YlOrRd',
                               cbar_kws={'label': 'Commits'}, ax=axes[i],
                               xticklabels=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
                    axes[i].set_title(f'{username} - Activity Heatmap')
                    axes[i].set_ylabel('Week')
            else:
                axes[i].text(0.5, 0.5, 'No activity data', ha='center', va='center', transform=axes[i].transAxes)
                axes[i].set_title(f'{username} - No Activity Data')
        
        plt.tight_layout()
        heatmap_file = os.path.join(comparison_dir, "activity_heatmap.png")
        plt.savefig(heatmap_file, dpi=300, bbox_inches='tight')
        created_files.append(heatmap_file)
        plt.close()
        
        # 4. Repository contribution comparison
        fig, ax = plt.subplots(figsize=(12, 8))
        
        all_repos = set()
        user_repo_data = {}
        
        for username in users:
            metrics = comparison['individual_metrics'].get(username)
            if metrics:
                user_repo_data[username] = metrics['commits_by_repo']
                all_repos.update(metrics['commits_by_repo'].keys())
        
        if all_repos and user_repo_data:
            # Create matrix for heatmap
            repos = sorted(list(all_repos))
            matrix_data = []
            
            for username in users:
                row = [user_repo_data[username].get(repo, 0) for repo in repos]
                matrix_data.append(row)
            
            # Create heatmap
            sns.heatmap(matrix_data, annot=True, fmt='d', cmap='Blues',
                       xticklabels=repos, yticklabels=users, ax=ax)
            ax.set_title('Repository Contribution Matrix')
            ax.set_xlabel('Repositories')
            ax.set_ylabel('Users')
            plt.xticks(rotation=45, ha='right')
            
            plt.tight_layout()
            repos_file = os.path.join(comparison_dir, "repository_matrix.png")
            plt.savefig(repos_file, dpi=300, bbox_inches='tight')
            created_files.append(repos_file)
            plt.close()
        
        self._verbose_print(f"Created {len(created_files)} visualization files in {comparison_dir}")
        return created_files
    
    def generate_comparison_report(self, comparison: Dict, output_file: Optional[str] = None) -> str:
        """Generate a comprehensive comparison report."""
        report_lines = []
        
        # Header
        report_lines.append("=" * 80)
        report_lines.append("GITHUB USER PRODUCTIVITY COMPARISON REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {comparison['timestamp']}")
        report_lines.append(f"Users: {', '.join(comparison['users'])}")
        report_lines.append("")
        
        # Individual user summaries
        report_lines.append("INDIVIDUAL USER SUMMARIES")
        report_lines.append("-" * 40)
        
        for username in comparison['users']:
            analysis = comparison['personal_vs_org_analysis'].get(username)
            if analysis:
                report_lines.append(f"\n{username.upper()}:")
                
                if analysis.get('ratios'):
                    ratios = analysis['ratios']
                    report_lines.append(f"  Total Commits: {ratios['total_commits']}")
                    report_lines.append(f"  Organization: {ratios['org_commits']} ({ratios['org_percentage']:.1f}%)")
                    report_lines.append(f"  Personal: {ratios['personal_commits']} ({ratios['personal_percentage']:.1f}%)")
                
                if analysis.get('org_metrics'):
                    org = analysis['org_metrics']
                    report_lines.append(f"  Org Repositories: {org['total_repositories']}")
                    report_lines.append(f"  Org Active Days: {org['total_active_days']}")
                
                if analysis.get('personal_metrics'):
                    personal = analysis['personal_metrics']
                    report_lines.append(f"  Personal Repositories: {personal['total_repositories']}")
                    report_lines.append(f"  Personal Active Days: {personal['total_active_days']}")
        
        # Cross-user comparison
        report_lines.append("\n\nCROSS-USER COMPARISON")
        report_lines.append("-" * 40)
        
        org_comparison = comparison['cross_user_comparison']['org_productivity']
        if org_comparison and 'commits' in org_comparison:
            report_lines.append("\nOrganization Productivity:")
            for user, data in org_comparison['commits'].items():
                report_lines.append(f"  {user}: {data['total']} commits ({data['per_day']:.1f}/day)")
        
        # Insights
        if comparison['insights']:
            report_lines.append("\n\nKEY INSIGHTS")
            report_lines.append("-" * 40)
            for insight in comparison['insights']:
                report_lines.append(insight)
        
        report_lines.append("\n" + "=" * 80)
        
        report_content = "\n".join(report_lines)
        
        # Save to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            self._verbose_print(f"Report saved to {output_file}")
        
        return report_content