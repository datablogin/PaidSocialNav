# PaidSocialNav

A unified Python application for managing paid social media advertising campaigns across multiple platforms including Meta (Facebook, Instagram, WhatsApp), Reddit, Pinterest, TikTok, and X (Twitter).

## Project Overview

PaidSocialNav provides a single interface to create, manage, and monitor advertising campaigns across major social media platforms. Write once, deploy everywhere - simplifying multi-platform advertising management.

### Supported Platforms
- **Meta Platforms**: Facebook, Instagram, WhatsApp
- **Reddit Ads**
- **Pinterest Ads**
- **TikTok Ads**
- **X (Twitter) Ads**

## Project Roadmap

### Phase 1: Core Architecture & Meta Integration
1. **Core Framework Setup**
   - [ ] Design unified campaign data model
   - [ ] Create abstract base classes for platform adapters
   - [ ] Implement configuration management system
   - [ ] Set up authentication credential storage
   - [ ] Build core API client architecture

2. **Meta Platforms Integration**
   - [ ] Implement Meta Business API client
   - [ ] Create Facebook Ads adapter
   - [ ] Create Instagram Ads adapter
   - [ ] Create WhatsApp Business Ads adapter
   - [ ] Build unified Meta campaign management interface

### Phase 2: Additional Platform Integration
3. **Reddit Ads Integration**
   - [ ] Implement Reddit Ads API client
   - [ ] Create Reddit campaign adapter
   - [ ] Map Reddit-specific features to unified model

4. **Pinterest Ads Integration**
   - [ ] Implement Pinterest Ads API client
   - [ ] Create Pinterest campaign adapter
   - [ ] Handle Pinterest-specific creative requirements

5. **TikTok Ads Integration**
   - [ ] Implement TikTok Business API client
   - [ ] Create TikTok campaign adapter
   - [ ] Support TikTok-specific ad formats

6. **X (Twitter) Ads Integration**
   - [ ] Implement X Ads API client
   - [ ] Create X campaign adapter
   - [ ] Handle X-specific targeting options

### Phase 3: Advanced Features
7. **Campaign Management Features**
   - [ ] Bulk campaign creation across platforms
   - [ ] Campaign synchronization and updates
   - [ ] Budget allocation and optimization
   - [ ] Audience targeting translation between platforms
   - [ ] Creative asset management and adaptation

8. **Analytics & Reporting**
   - [ ] Unified reporting dashboard
   - [ ] Cross-platform performance metrics
   - [ ] ROI tracking and attribution
   - [ ] Automated report generation
   - [ ] Real-time campaign monitoring

### Phase 4: Optimization & Automation
9. **Advanced Capabilities**
   - [ ] A/B testing framework
   - [ ] Automated bid optimization
   - [ ] Cross-platform budget reallocation
   - [ ] Performance-based automation rules
   - [ ] AI-powered creative recommendations

10. **Enterprise Features**
    - [ ] Multi-account management
    - [ ] Team collaboration tools
    - [ ] Approval workflows
    - [ ] Audit logging
    - [ ] API rate limit management

## Architecture Overview

```
metagraphapi/
├── core/
│   ├── models/          # Unified data models
│   ├── adapters/        # Platform-specific adapters
│   ├── auth/            # Authentication management
│   └── utils/           # Shared utilities
├── platforms/
│   ├── meta/            # Facebook, Instagram, WhatsApp
│   ├── reddit/          # Reddit Ads
│   ├── pinterest/       # Pinterest Ads
│   ├── tiktok/          # TikTok Ads
│   └── twitter/         # X (Twitter) Ads
├── api/
│   ├── campaigns/       # Campaign management endpoints
│   ├── creatives/       # Creative asset management
│   ├── analytics/       # Reporting endpoints
│   └── auth/            # Authentication endpoints
└── cli/                 # Command-line interface
```

## Setup

1. Clone the repository:
```bash
git clone https://github.com/datablogin/PaidSocialNav.git
cd PaidSocialNav
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the package in development mode:
```bash
pip install -e ".[dev,test]"
```

## Development

### One-time developer setup (recommended)
- Install pre-commit locally so formatting and hygiene checks run before each commit:
  ```bash
  pip install pre-commit
  pre-commit install
  ```
  This enables:
  - Ruff lint with auto-fix (ruff --fix)
  - Ruff format (ruff format)
  - Basic hygiene checks (no BOM, trailing whitespace, end-of-file newline, merge conflicts)

### Running Tests
```bash
pytest
```

### Linting and Formatting
```bash
ruff check .
ruff format .
# Or run all pre-commit hooks (same checks CI expects):
pre-commit run --all-files
```

### CLI examples (Meta insights)
- Sync yesterday’s campaign-level insights to the configured tenant (e.g., Fleming):
```bash
psn meta sync-insights \
  --account-id act_1234567890 \
  --level campaign \
  --date-preset yesterday \
  --tenant fleming
```

- Backfill last 7 days at the ad set level:
```bash
psn meta sync-insights \
  --account-id act_1234567890 \
  --level adset \
  --date-preset last_7d \
  --tenant fleming
```

- Use explicit dates at the ad level (mutually exclusive with --date-preset):
```bash
psn meta sync-insights \
  --account-id act_1234567890 \
  --level ad \
  --since 2025-09-01 \
  --until 2025-09-07 \
  --tenant fleming
```

### Type Checking
```bash
mypy .
```

## Configuration

Create a `.env` file with your platform credentials:
```env
# Meta
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret
META_ACCESS_TOKEN=your_access_token

# Reddit
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret

# Pinterest
PINTEREST_APP_ID=your_app_id
PINTEREST_APP_SECRET=your_app_secret

# TikTok
TIKTOK_APP_ID=your_app_id
TIKTOK_APP_SECRET=your_app_secret

# X (Twitter)
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
```

## CI/CD

This project uses GitHub Actions for continuous integration. The CI pipeline runs on every push and pull request to the main and develop branches.

### GitHub Features Used:
- **Issues**: Bug reports and feature requests templates are available
- **Pull Requests**: Template provided for consistent PR descriptions
- **Actions**: Automated testing, linting, and type checking
- **Dependabot**: Automated dependency updates

## Contributing

1. Create a new branch for your feature or bugfix
2. Make your changes
3. Ensure all tests pass and code is properly formatted
4. Submit a pull request using the provided template

## License

[Add your license here]