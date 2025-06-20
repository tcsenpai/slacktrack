"""
Visualization functions for productivity data.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import seaborn as sns
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Optional
import os

from .data_utils import create_output_directory


def create_comprehensive_heatmap(data: Dict, output_path: str = None):
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
        ax_summary_pie.set_title(f"Productivity Metrics Distribution\\nTotal Activity: {sum(metric_totals)}", 
                               fontweight='bold', fontsize=14)
    
    # Format dates for better readability
    since_formatted = since_date.strftime('%B %d, %Y')
    until_formatted = until_date.strftime('%B %d, %Y')
    
    fig.suptitle(f"Comprehensive Productivity Dashboard: {data['username']}\\n{since_formatted} to {until_formatted}", 
                fontsize=16, fontweight='bold', y=0.98)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.95)
    
    # Create output directory and save files
    output_dir = create_output_directory(data['username'])
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    if output_path:
        final_path = output_path
    else:
        final_path = os.path.join(output_dir, f"comprehensive_dashboard_{data['username']}_{timestamp}.png")
    
    plt.savefig(final_path, dpi=300, bbox_inches='tight')
    print(f"Comprehensive heatmap saved to {final_path}")
    
    try:
        plt.show()
    except Exception:
        print("Plot saved to file (display not available)")


def create_simple_heatmap(data: Dict, output_path: str = None):
    """Create a simple heatmap visualization for commits only."""
    if not data or not data.get('repositories'):
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
    ax2.set_title(f"Commit Distribution by Repository\\nTotal: {data['total_commits']} commits", 
                 fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    
    # Create output directory and save files
    output_dir = create_output_directory(data['username'])
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    if output_path:
        final_path = output_path
    else:
        final_path = os.path.join(output_dir, f"productivity_heatmap_{data['username']}_{timestamp}.png")
    
    plt.savefig(final_path, dpi=300, bbox_inches='tight')
    print(f"Heatmap saved to {final_path}")
    
    try:
        plt.show()
    except Exception:
        print("Plot saved to file (display not available)")


def create_heatmap(data: Dict, output_path: str = None):
    """Create a heatmap visualization - delegates to comprehensive version if multiple metrics available."""
    # Handle comparison data structure
    if 'comparison' in data:
        print("Comparison data detected - using organization data for visualization...")
        viz_data = data['organization']['data']
    else:
        viz_data = data
    
    # Check if we have additional metrics beyond commits
    has_additional_metrics = any([
        viz_data.get('pull_requests', {}).get('total', 0) > 0,
        viz_data.get('code_reviews', {}).get('total', 0) > 0,
        viz_data.get('issues', {}).get('total', 0) > 0,
        viz_data.get('line_stats', {}).get('total_changes', 0) > 0
    ])
    
    if has_additional_metrics:
        print("Multiple metrics detected - creating comprehensive dashboard...")
        create_comprehensive_heatmap(viz_data, output_path)
    else:
        create_simple_heatmap(viz_data, output_path)


def create_timeline_chart(data: Dict, output_path: str = None):
    """Create a timeline chart showing daily commit activity."""
    # Handle both regular data and comparison data structures
    repositories_data = None
    chart_title = "Daily Commit Activity"
    
    if 'repositories' in data:
        # Regular tracking data
        repositories_data = data['repositories']
        chart_title = f"Daily Commit Activity - {data.get('username', 'User')}"
    elif 'organization' in data and 'personal' in data:
        # Comparison data - combine both org and personal commits
        daily_commits = defaultdict(int)
        
        # Add organization commits
        if data['organization'] and data['organization'].get('data', {}).get('repositories'):
            for repo_data in data['organization']['data']['repositories'].values():
                for commit in repo_data.get('commits', []):
                    commit_date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
                    date_key = commit_date.date()
                    daily_commits[date_key] += 1
        
        # Add personal commits
        if data['personal'] and data['personal'].get('data', {}).get('repositories'):
            for repo_data in data['personal']['data']['repositories'].values():
                for commit in repo_data.get('commits', []):
                    commit_date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
                    date_key = commit_date.date()
                    daily_commits[date_key] += 1
        
        # Create timeline with combined data
        if not daily_commits:
            print("No commits found for timeline chart generation.")
            return
        
        dates = sorted(daily_commits.keys())
        counts = [daily_commits[date] for date in dates]
        chart_title = f"Combined Daily Activity - {data.get('username', 'User')}"
        
        # Create the chart directly here for comparison data
        fig, ax = plt.subplots(figsize=(15, 6))
        ax.plot(dates, counts, marker='o', linewidth=2, markersize=4, label='Total Commits')
        
        # Add separate lines for org vs personal if we want to show breakdown
        org_daily = defaultdict(int)
        personal_daily = defaultdict(int)
        
        if data['organization'] and data['organization'].get('data', {}).get('repositories'):
            for repo_data in data['organization']['data']['repositories'].values():
                for commit in repo_data.get('commits', []):
                    commit_date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
                    date_key = commit_date.date()
                    org_daily[date_key] += 1
        
        if data['personal'] and data['personal'].get('data', {}).get('repositories'):
            for repo_data in data['personal']['data']['repositories'].values():
                for commit in repo_data.get('commits', []):
                    commit_date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
                    date_key = commit_date.date()
                    personal_daily[date_key] += 1
        
        # Plot separate lines for org and personal
        org_counts = [org_daily.get(date, 0) for date in dates]
        personal_counts = [personal_daily.get(date, 0) for date in dates]
        
        ax.plot(dates, org_counts, marker='s', linewidth=1, markersize=3, alpha=0.7, label='Organization')
        ax.plot(dates, personal_counts, marker='^', linewidth=1, markersize=3, alpha=0.7, label='Personal')
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Number of Commits')
        ax.set_title(chart_title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"Timeline chart saved to {output_path}")
        
        try:
            plt.show()
        except Exception:
            print("Plot saved to file (display not available)")
        
        return
    else:
        print("No valid data structure found for timeline chart generation.")
        return
    
    if not repositories_data:
        print("No repository data available for timeline chart generation.")
        return
    
    # Collect all commits with dates (for regular data)
    daily_commits = defaultdict(int)
    for repo_data in repositories_data.values():
        for commit in repo_data.get('commits', []):
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
    
    ax.set_title(chart_title + f"\\n{data.get('timeframe', {}).get('since', '')} to {data.get('timeframe', {}).get('until', '')}", 
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
    username = data.get('username', 'user')
    output_dir = create_output_directory(username)
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    if output_path:
        final_path = output_path
    else:
        final_path = os.path.join(output_dir, f"commit_timeline_{username}_{timestamp}.png")
    
    plt.savefig(final_path, dpi=300, bbox_inches='tight')
    print(f"Timeline chart saved to {final_path}")
    
    try:
        plt.show()
    except Exception:
        print("Plot saved to file (display not available)")