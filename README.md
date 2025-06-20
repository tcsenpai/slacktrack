# GitHub Productivity Tracker

A comprehensive tool to track and visualize developer productivity across GitHub organization repositories. Monitors commits, pull requests, code reviews, issues, and lines of code modified with beautiful heatmap visualizations.

## ✨ Features

- **📊 Multi-Metric Tracking**: Commits, PRs, code reviews, issues, lines modified
- **🌳 All Branches Coverage**: Analyzes commits from every branch (not just main/master)
- **🎨 Rich Visualizations**: GitHub-style heatmaps, timelines, and distribution charts
- **⚡ Performance Optimized**: Parallel processing for faster analysis
- **🔍 Repository Filtering**: `.repoignore` support to exclude unwanted repositories
- **📅 Flexible Timeframes**: Presets (1 week, 1 month, 3 days) or custom date ranges
- **🔐 Private Repository Support**: Works with GitHub tokens for private org access
- **📈 Progress Tracking**: Verbose mode with detailed progress bars
- **👤 Personal Repository Analysis**: Track activity on personal repos separately (IN DEVELOPMENT)
- **📁 Organized Output**: User-specific folders with timestamped reports
- **📄 Comprehensive Summaries**: Detailed text reports with insights

## 🚀 Quick Start

### Installation

```bash
# Clone or download the script
git clone <your-repo-url>
cd github-productivity-tracker

# Install dependencies
pip install -r requirements.txt

# Make script executable
chmod +x github_productivity_tracker.py
```

### Configuration

1. **Create `.env` file**:
```bash
cp .env.example .env
```

2. **Edit `.env` with your settings**:
```env
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_USERNAME=target_username_to_track
GITHUB_ORGANIZATION=your_organization_name
```

3. **Optional: Configure repository exclusions**:
```bash
cp .repoignore.example .repoignore
# Edit .repoignore to exclude test repos, docs, etc.
```

### Basic Usage

```bash
# Track commits only (default: 1 week)
./github_productivity_tracker.py

# Track all metrics with visualization
./github_productivity_tracker.py --all --heatmap

# Custom timeframe with verbose output
./github_productivity_tracker.py --all --timeframe 1month -v --heatmap
```

## 📋 Command Line Options

### Required Arguments
- `--username` or set `GITHUB_USERNAME` in `.env`
- `--organization` or set `GITHUB_ORGANIZATION` in `.env`

### Metrics Flags
```bash
--include-prs         # Include pull request metrics
--include-reviews     # Include code review metrics  
--include-issues      # Include issue creation metrics
--include-lines       # Include lines of code modified
--all                 # Enable all metrics above
--personal            # Also analyze personal repositories (IN DEVELOPMENT)
```

### Timeframe Options
```bash
--timeframe PRESET    # 3days, 1week, 1month, custom
--start-date DATE     # Custom start (YYYY-MM-DD)
--end-date DATE       # Custom end (YYYY-MM-DD)
```

### Visualization Options
```bash
--heatmap            # Generate heatmap visualization
--timeline           # Generate timeline chart
--viz-output PATH    # Custom output path for visualizations
```

### Other Options
```bash
--token TOKEN        # GitHub token (or set GITHUB_TOKEN)
--output FILE        # Export JSON data
--repoignore FILE    # Custom .repoignore file path
-v, --verbose        # Detailed progress output
```

## 📊 Output Files

The script creates organized output in user-specific directories:

```
outputs/
└── username/
    ├── comprehensive_dashboard_username_YYYY-MM-DD.png
    ├── commit_timeline_username_YYYY-MM-DD.png
    ├── productivity_summary_username_YYYY-MM-DD.txt
    ├── raw_data_username_YYYY-MM-DD.json
    ├── personal_heatmap_username_YYYY-MM-DD.png         # --personal flag
    ├── personal_timeline_username_YYYY-MM-DD.png        # --personal flag
    ├── personal_summary_username_YYYY-MM-DD.txt         # --personal flag
    └── personal_data_username_YYYY-MM-DD.json           # --personal flag
```

### Heatmap Visualizations

**Simple Mode** (commits only):
- Commit activity heatmap (GitHub-style)
- Repository distribution pie chart

**Comprehensive Mode** (multiple metrics):
- Individual heatmaps for each metric
- Timeline charts for daily trends
- Combined activity overview
- Metrics distribution summary

### Text Summary

Each analysis includes a detailed text summary with:
- Overall productivity statistics
- Top active repositories
- Daily/weekly patterns
- Metric breakdowns
- Time period analysis

## 🔧 Advanced Usage

### Personal Repository Analysis
```bash
# Note: Personal repository analysis is currently IN DEVELOPMENT
# The --personal flag will be available in a future release

# Analyze both organization and personal repositories (COMING SOON)
./github_productivity_tracker.py --all --personal --heatmap

# Focus on personal repos only with custom timeframe (COMING SOON)
./github_productivity_tracker.py --personal --include-lines \
  --timeframe custom --start-date 2024-01-01 --end-date 2024-01-31
```

### Custom Timeframes
```bash
# Last 3 days
./github_productivity_tracker.py --timeframe 3days --all

# Custom date range
./github_productivity_tracker.py --timeframe custom \
  --start-date 2024-01-01 --end-date 2024-01-31 --all

# Last month with full analysis
./github_productivity_tracker.py --timeframe 1month \
  --all --heatmap --timeline -v
```

### Repository Filtering

Create `.repoignore` to exclude repositories:
```bash
# Exclude test repositories
*-test
test-*

# Exclude documentation
docs
*-docs

# Exclude infrastructure
terraform-*
k8s-*
```

### Performance Optimization

For large organizations:
```bash
# Use verbose mode to monitor progress
./github_productivity_tracker.py --all -v

# Focus on specific metrics to reduce API calls
./github_productivity_tracker.py --include-prs --include-reviews
```

## 📈 Understanding the Metrics

### Commits
- **What**: Direct commits by the user across all branches
- **Includes**: Merge commits, direct pushes, squashed commits
- **Branch Coverage**: All branches (not just main/master)

### Pull Requests
- **What**: PRs created by the user
- **Timeframe**: Based on PR creation date
- **Scope**: Organization-wide

### Code Reviews
- **What**: PRs where user performed code reviews
- **Timeframe**: Based on review activity date
- **Impact**: Measures collaboration and code quality involvement

### Issues
- **What**: Issues created by the user
- **Timeframe**: Based on issue creation date
- **Types**: Bugs, features, tasks, etc.

### Lines Modified
- **What**: Total lines added + deleted in commits
- **Granularity**: Per-commit statistics
- **Performance**: Requires additional API calls (slower)

## 🔐 Authentication & Permissions

### GitHub Token Requirements

Create a Personal Access Token with these scopes:
- `repo` (for private repositories)
- `read:org` (for organization access)
- `read:user` (for user information)

### Setting Up Token

1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token with required scopes
3. Add to `.env` file or use `--token` flag

## 🚨 Rate Limits & Performance

### GitHub API Limits
- **Authenticated**: 5,000 requests/hour
- **Unauthenticated**: 60 requests/hour
- **Search API**: 30 requests/minute

### Optimization Features
- Parallel processing (3 workers for branches, 5 for stats)
- Request deduplication
- Efficient pagination
- Smart caching

### Performance Tips
- Use `.repoignore` to exclude unnecessary repositories
- Avoid `--include-lines` for quick analysis
- Use shorter timeframes for faster results

## 🐛 Troubleshooting

### Common Issues

**No commits found**:
- Verify GitHub username spelling
- Check if user has commits in the timeframe
- Ensure token has repository access

**Rate limit exceeded**:
- Verify GitHub token is set correctly
- Reduce scope with `.repoignore`
- Use shorter timeframes

**Missing private repositories**:
- Ensure token has `repo` scope
- Verify organization membership
- Check repository access permissions

### Debug Mode
```bash
# Enable verbose output for debugging
./github_productivity_tracker.py --all -v
```

## 📝 Examples

### Daily Standup Report
```bash
./github_productivity_tracker.py --timeframe 3days --all --heatmap
```

### Weekly Team Review
```bash
./github_productivity_tracker.py --timeframe 1week \
  --include-prs --include-reviews --heatmap --timeline
```

### Monthly Performance Analysis
```bash
./github_productivity_tracker.py --timeframe 1month \
  --all --heatmap --timeline --output monthly_report.json -v
```

### Custom Sprint Analysis
```bash
./github_productivity_tracker.py --timeframe custom \
  --start-date 2024-01-15 --end-date 2024-01-29 \
  --all --heatmap
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- GitHub API for comprehensive data access
- matplotlib for beautiful visualizations
- tqdm for progress tracking
- All contributors and users of this tool

---

**Need help?** Open an issue or check the troubleshooting section above.