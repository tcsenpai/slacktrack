#!/usr/bin/env python3
"""
GitHub Productivity Tracker

Tracks commits by a specific user across all repositories in an organization.
Supports timeframe filtering with presets and custom date ranges.
"""

import argparse
import os
import sys
from dotenv import load_dotenv
from datetime import datetime

from libs.productivity_tracker import ProductivityTracker
from libs.data_utils import save_data, save_ratio_summary
from libs.reports import display_productivity_report, display_personal_report, display_comparison_report, generate_text_summary
from libs.visualizations import create_heatmap, create_timeline_chart


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
    parser.add_argument('--personal', action='store_true', help='Track personal repositories instead of organization repositories')
    parser.add_argument('--compare', action='store_true', help='Compare personal and organization productivity')
    
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
    
    # Organization is only required for non-personal tracking
    if not args.personal and not organization:
        print("Error: GitHub organization is required. Set GITHUB_ORGANIZATION in .env or use --organization")
        sys.exit(1)
    
    # For comparison mode, both organization and personal flags are needed
    if args.compare and not organization:
        print("Error: --compare requires organization to be specified")
        sys.exit(1)
    
    # Validate custom timeframe arguments
    if args.timeframe == 'custom':
        if not args.start_date or not args.end_date:
            print("Error: Custom timeframe requires both --start-date and --end-date")
            sys.exit(1)
    
    # Initialize tracker
    tracker = ProductivityTracker(organization or username, token, args.verbose)
    
    # Handle different tracking modes
    if args.compare:
        # Compare personal vs organization productivity
        data = tracker.compare_personal_vs_organization(
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
        
        # Save individual org and personal data files for future comparisons
        if data and 'organization' in data and 'personal' in data:
            org_data = data['organization']['data']
            personal_data = data['personal']['data']
            
            # Save organization data as raw_data file
            org_output_path = save_data(org_data, None, False)
            print(f"Organization data saved to {org_output_path}")
            
            # Save personal data as personal_data file
            from libs.data_utils import create_output_directory
            output_dir = create_output_directory(username)
            timestamp = datetime.now().strftime("%Y-%m-%d")
            personal_path = os.path.join(output_dir, f"personal_data_{username}_{timestamp}.json")
            
            import json
            with open(personal_path, 'w') as f:
                json.dump(personal_data, f, indent=2)
            print(f"Personal data saved to {personal_path}")
        
        # Display comparison report
        display_comparison_report(data)
        
    elif args.personal:
        # Track personal productivity only
        data = tracker.track_user_personal_productivity(
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
        
        # Display personal report
        if data:
            display_personal_report(data)
    
    else:
        # Track organization productivity (default behavior)
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
        display_productivity_report(data)
    
    # Save data
    if not data:
        print("No data to save.")
        return
    
    # Save main data file
    output_path = save_data(data, args.output, args.compare)
    print(f"\\nData saved to {output_path}")
    
    # Save ratio summary for comparison data
    if args.compare and 'comparison' in data:
        ratio_path = save_ratio_summary(data)
        if ratio_path:
            print(f"Ratio summary saved to {ratio_path}")
    
    # Generate visualizations if requested
    if args.heatmap:
        print("\\nGenerating heatmap visualization...")
        viz_path = args.viz_output if args.viz_output else None
        create_heatmap(data, viz_path)
        
        # Generate text summary
        if not args.compare:  # Only for non-comparison data
            from libs.data_utils import create_output_directory
            output_dir = create_output_directory(data['username'])
            generate_text_summary(data, output_dir)
    
    if args.timeline:
        print("\\nGenerating timeline chart...")
        viz_path = args.viz_output if args.viz_output else None
        create_timeline_chart(data, viz_path)


if __name__ == "__main__":
    main()