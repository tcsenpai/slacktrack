#!/usr/bin/env python3
"""
GitHub User Comparison Tool

Compares productivity metrics between multiple users using their existing JSON data.
Supports personal vs organization ratio analysis and cross-user comparisons.
"""

import argparse
import json
import sys

from libs.comparison import UserComparator


def main():
    parser = argparse.ArgumentParser(description='Compare GitHub user productivity metrics')
    parser.add_argument('users', nargs='+', help='Usernames to compare')
    parser.add_argument('--output', '-o', help='Output file for JSON results')
    parser.add_argument('--report', '-r', help='Output file for text report')
    parser.add_argument('--visualize', action='store_true', help='Generate comparison visualizations')
    parser.add_argument('--viz-output', help='Output directory for visualizations (default: outputs/comparisons)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Initialize comparator
    comparator = UserComparator(verbose=args.verbose)
    
    # Load user data
    loaded_users = []
    for username in args.users:
        if comparator.load_user_data_for_comparison(username):
            loaded_users.append(username)
        else:
            print(f"Failed to load data for {username}")
    
    if len(loaded_users) < 2:
        print("Error: Need at least 2 users with valid data to compare")
        sys.exit(1)
    
    # Perform comparison
    print(f"Comparing {len(loaded_users)} users: {', '.join(loaded_users)}")
    comparison_results = comparator.compare_users(loaded_users)
    
    # Save JSON results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(comparison_results, f, indent=2)
        print(f"Results saved to {args.output}")
    
    # Generate visualizations if requested
    if args.visualize:
        viz_output = args.viz_output or "outputs/comparisons"
        created_files = comparator.create_comparison_visualizations(comparison_results, viz_output)
        print(f"\nCreated {len(created_files)} visualization files:")
        for file_path in created_files:
            print(f"  • {file_path}")
    
    # Generate and display report
    report = comparator.generate_comparison_report(comparison_results, args.report)
    print("\n" + report)


if __name__ == "__main__":
    main()