"""
Report generation functions for productivity data.
"""

import os
from datetime import datetime
from typing import Dict, Optional


def display_productivity_report(data: Dict):
    """Display a formatted productivity report."""
    if not data:
        print("No data to display.")
        return
    
    print("\\n" + "="*80)
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
        print("\\nPER REPOSITORY BREAKDOWN:")
        print("-" * 80)
        
        # Sort repositories by commit count (descending)
        sorted_repos = sorted(data['repositories'].items(), 
                            key=lambda x: x[1]['commit_count'], reverse=True)
        
        for repo_name, repo_data in sorted_repos:
            print(f"\\n{repo_name}: {repo_data['commit_count']} commits")
            print(f"  Repository: {repo_data['repo_url']}")
            
            # Show recent commits (limit to 5)
            recent_commits = repo_data['commits'][:5]
            for commit in recent_commits:
                date = commit['commit']['author']['date']
                message = commit['commit']['message'].split('\\n')[0][:60]
                print(f"    {date[:10]} - {message}")
            
            if len(repo_data['commits']) > 5:
                print(f"    ... and {len(repo_data['commits']) - 5} more commits")
    
    print("\\n" + "="*80)


def display_personal_report(data: Dict):
    """Display a formatted personal productivity report."""
    if not data:
        print("No data to display.")
        return
    
    print("\\n" + "="*80)
    print(f"PERSONAL PRODUCTIVITY REPORT")
    print("="*80)
    # Format timeframe for human readability
    since_date = datetime.fromisoformat(data['timeframe']['since'].replace('Z', '+00:00'))
    until_date = datetime.fromisoformat(data['timeframe']['until'].replace('Z', '+00:00'))
    
    print(f"User: {data['username']}")
    print(f"Scope: Personal Repositories")
    print(f"Timeframe: {since_date.strftime('%B %d, %Y')} to {until_date.strftime('%B %d, %Y')}")
    print(f"Total Commits: {data['total_commits']}")
    print(f"Repositories with activity: {len(data['repositories'])}")
    
    # Display additional metrics if available
    if 'line_stats' in data:
        stats = data['line_stats']
        print(f"Lines Modified: +{stats['total_additions']}/-{stats['total_deletions']} ({stats['total_changes']} total)")
    
    if data['repositories']:
        print("\\nPER REPOSITORY BREAKDOWN:")
        print("-" * 80)
        
        # Sort repositories by commit count (descending)
        sorted_repos = sorted(data['repositories'].items(), 
                            key=lambda x: x[1]['commit_count'], reverse=True)
        
        for repo_name, repo_data in sorted_repos:
            fork_indicator = " (fork)" if repo_data.get('is_fork', False) else ""
            private_indicator = " (private)" if repo_data.get('is_private', False) else ""
            print(f"\\n{repo_name}: {repo_data['commit_count']} commits{fork_indicator}{private_indicator}")
            print(f"  Repository: {repo_data['repo_url']}")
            
            # Show recent commits (limit to 5)
            recent_commits = repo_data['commits'][:5]
            for commit in recent_commits:
                date = commit['commit']['author']['date']
                message = commit['commit']['message'].split('\\n')[0][:60]
                print(f"    {date[:10]} - {message}")
            
            if len(repo_data['commits']) > 5:
                print(f"    ... and {len(repo_data['commits']) - 5} more commits")
    
    print("\\n" + "="*80)


def display_comparison_report(comparison_data: Dict):
    """Display a formatted comparison report between personal and organization productivity."""
    if not comparison_data:
        print("No comparison data to display.")
        return
    
    print("\\n" + "="*80)
    print("PERSONAL VS ORGANIZATION PRODUCTIVITY COMPARISON")
    print("="*80)
    
    # Format timeframe for human readability
    timeframe = comparison_data.get('timeframe', {})
    if timeframe.get('since') and timeframe.get('until'):
        since_date = datetime.fromisoformat(timeframe['since'].replace('Z', '+00:00'))
        until_date = datetime.fromisoformat(timeframe['until'].replace('Z', '+00:00'))
        
        print(f"User: {comparison_data['username']}")
        print(f"Organization: {comparison_data['organization']['name']}")
        print(f"Timeframe: {since_date.strftime('%B %d, %Y')} to {until_date.strftime('%B %d, %Y')}")
        print()
    
    # Display comparison metrics
    comp = comparison_data['comparison']
    
    print("COMMITS COMPARISON:")
    print(f"  Organization: {comp['total_commits']['organization']}")
    print(f"  Personal:     {comp['total_commits']['personal']}")
    print(f"  Difference:   {comp['total_commits']['difference']:+d}")
    print()
    
    print("ACTIVE REPOSITORIES:")
    print(f"  Organization: {comp['active_repositories']['organization']}")
    print(f"  Personal:     {comp['active_repositories']['personal']}")
    print(f"  Difference:   {comp['active_repositories']['difference']:+d}")
    print()
    
    # Display line stats if available
    if 'line_stats' in comp:
        line_stats = comp['line_stats']
        print("LINES OF CODE COMPARISON:")
        print(f"  Lines Added:")
        print(f"    Organization: +{line_stats['organization'].get('total_additions', 0):,}")
        print(f"    Personal:     +{line_stats['personal'].get('total_additions', 0):,}")
        print(f"    Difference:   {line_stats['difference']['total_additions']:+,}")
        print(f"  Lines Deleted:")
        print(f"    Organization: -{line_stats['organization'].get('total_deletions', 0):,}")
        print(f"    Personal:     -{line_stats['personal'].get('total_deletions', 0):,}")
        print(f"    Difference:   {line_stats['difference']['total_deletions']:+,}")
        print(f"  Total Changes:")
        print(f"    Organization: {line_stats['organization'].get('total_changes', 0):,}")
        print(f"    Personal:     {line_stats['personal'].get('total_changes', 0):,}")
        print(f"    Difference:   {line_stats['difference']['total_changes']:+,}")
        print()
    
    # Display additional metrics if available
    if 'pull_requests' in comp:
        pr_comp = comp['pull_requests']
        print("PULL REQUESTS:")
        print(f"  Organization: {pr_comp['organization']}")
        print(f"  Personal:     {pr_comp['personal']}")
        print(f"  Difference:   {pr_comp['difference']:+d}")
        print()
    
    if 'code_reviews' in comp:
        review_comp = comp['code_reviews']
        print("CODE REVIEWS:")
        print(f"  Organization: {review_comp['organization']}")
        print(f"  Personal:     {review_comp['personal']}")
        print(f"  Difference:   {review_comp['difference']:+d}")
        print()
    
    if 'issues' in comp:
        issue_comp = comp['issues']
        print("ISSUES CREATED:")
        print(f"  Organization: {issue_comp['organization']}")
        print(f"  Personal:     {issue_comp['personal']}")
        print(f"  Difference:   {issue_comp['difference']:+d}")
        print()
    
    # Summary
    total_org_activity = comp['total_commits']['organization']
    total_personal_activity = comp['total_commits']['personal']
    total_activity = total_org_activity + total_personal_activity
    
    if total_activity > 0:
        org_percentage = (total_org_activity / total_activity) * 100
        personal_percentage = (total_personal_activity / total_activity) * 100
        
        print("ACTIVITY DISTRIBUTION:")
        print(f"  Organization: {org_percentage:.1f}% ({total_org_activity}/{total_activity})")
        print(f"  Personal:     {personal_percentage:.1f}% ({total_personal_activity}/{total_activity})")
    
    print("\\n" + "="*80)


def generate_text_summary(data: Dict, output_dir: str) -> str:
    """Generate a comprehensive text summary of the productivity data."""
    if not data:
        return ""

    timestamp = datetime.now().strftime("%Y-%m-%d")
    summary_path = os.path.join(output_dir, f"productivity_summary_{data['username']}_{timestamp}.txt")

    # Format timeframe for human readability
    since_date = datetime.fromisoformat(data['timeframe']['since'].replace('Z', '+00:00'))
    until_date = datetime.fromisoformat(data['timeframe']['until'].replace('Z', '+00:00'))

    with open(summary_path, "w") as f:
        f.write("=" * 80 + "\\n")
        f.write("GITHUB PRODUCTIVITY ANALYSIS SUMMARY\\n")
        f.write("=" * 80 + "\\n\\n")

        # Basic Information
        f.write(f"User: {data['username']}\\n")
        f.write(f"Organization: {data['organization']}\\n")
        f.write(f"Analysis Period: {since_date.strftime('%B %d, %Y')} to {until_date.strftime('%B %d, %Y')}\\n")
        f.write(f"Report Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\\n\\n")

        # Overall Metrics
        f.write("-" * 50 + "\\n")
        f.write("OVERALL PRODUCTIVITY METRICS\\n")
        f.write("-" * 50 + "\\n")
        f.write(f"Total Commits: {data['total_commits']}\\n")
        f.write(f"Active Repositories: {len(data['repositories'])}\\n")

        if 'pull_requests' in data:
            f.write(f"Pull Requests Created: {data['pull_requests']['total']}\\n")
        if 'code_reviews' in data:
            f.write(f"Code Reviews Performed: {data['code_reviews']['total']}\\n")
        if 'issues' in data:
            f.write(f"Issues Created: {data['issues']['total']}\\n")
        if 'line_stats' in data:
            stats = data['line_stats']
            f.write(f"Lines Added: +{stats['total_additions']:,}\\n")
            f.write(f"Lines Deleted: -{stats['total_deletions']:,}\\n")
            f.write(f"Total Lines Modified: {stats['total_changes']:,}\\n")

        # Time-based Analysis
        f.write("\\n" + "-" * 50 + "\\n")
        f.write("TIME-BASED ANALYSIS\\n")
        f.write("-" * 50 + "\\n")

        # Calculate daily averages
        days_in_period = (until_date - since_date).days + 1
        if days_in_period > 0:
            avg_commits_per_day = data['total_commits'] / days_in_period
            f.write(f"Analysis Period: {days_in_period} days\\n")
            f.write(f"Average Commits per Day: {avg_commits_per_day:.1f}\\n")

            if 'line_stats' in data:
                avg_lines_per_day = data['line_stats']['total_changes'] / days_in_period
                f.write(f"Average Lines Modified per Day: {avg_lines_per_day:.0f}\\n")

        # Summary and Insights
        f.write("\\n" + "-" * 50 + "\\n")
        f.write("INSIGHTS AND SUMMARY\\n")
        f.write("-" * 50 + "\\n")

        if data['total_commits'] == 0:
            f.write("No commit activity found in the specified timeframe.\\n")
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

            f.write(f"Productivity Level: {productivity_level}\\n")
            f.write(f"Repository Diversity: {len(data['repositories'])} different repositories\\n")

        f.write("\\n" + "=" * 80 + "\\n")
        f.write("End of Report\\n")
        f.write("=" * 80 + "\\n")

    print(f"Text summary saved to {summary_path}")
    return summary_path