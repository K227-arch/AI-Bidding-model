# AI Model for Government Contracting Bid Applications

An intelligent system that automatically finds and applies for I.T and cybersecurity government contracts using AI-powered matching and document processing.

## Features

- **Automated Bid Discovery**: Scrapes government contracting websites (SAM.gov, FBO.gov) for relevant opportunities
- **AI-Powered Matching**: Uses OpenAI GPT models to match opportunities with company capabilities
- **Document Processing**: Extracts and analyzes company documents (PDF, DOCX, TXT, Excel)
- **Application Generation**: Automatically generates professional bid applications and proposals
- **Automated Submission**: Submits applications directly to government portals (optional)
- **Comprehensive Logging**: Detailed logging and reporting of all activities

## Installation

1. **Clone or download the project**:
   ```bash
   cd /Users/ucctestbed/Desktop/ai-model
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp config.env.example .env
   # Edit .env with your API keys and company information
   ```

4. **Add your company documents** to the `documents/` folder:
   - Company profile/capability statements
   - Past performance documents
   - Team qualifications
   - Certifications
   - Any other relevant materials

## Configuration

Edit the `.env` file with your information:

```env
# Required: OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Government API Keys
SAM_GOV_API_KEY=your_sam_gov_api_key_here
GOVWIN_API_KEY=your_govwin_api_key_here

# Company Information
COMPANY_NAME=Your Company Name
COMPANY_DUNS=your_duns_number
COMPANY_NAICS_CODES=541511,541512,541519,541690

# Application Settings
AUTO_SUBMIT=false
REVIEW_MODE=true
MAX_APPLICATIONS_PER_DAY=10
```

## Usage

### Basic Usage

```bash
# Run with default settings (review mode, no auto-submit)
python main.py

# Search for opportunities from the last 14 days
python main.py --days-back 14

# Process up to 100 opportunities
python main.py --max-opportunities 100

# Enable automatic submission (use with caution!)
python main.py --auto-submit

# Disable review mode for automated runs
python main.py --no-review
```

### Configuration Check

```bash
# Check your configuration
python main.py --config-check
```

### Advanced Usage

```bash
# Full automated run with submission
python main.py --days-back 7 --max-opportunities 50 --auto-submit --no-review
```

## How It Works

### 1. Document Processing
- Scans the `documents/` folder for company materials
- Extracts text from PDFs, Word docs, Excel files, and text files
- Identifies technical capabilities, certifications, and experience
- Creates a comprehensive company profile

### 2. Opportunity Discovery
- Searches SAM.gov and FBO.gov for I.T and cybersecurity opportunities
- Uses configurable keywords to find relevant contracts
- Filters opportunities based on due dates and relevance

### 3. AI-Powered Matching
- Uses OpenAI GPT models to analyze opportunities
- Compares requirements against company capabilities
- Calculates match scores and confidence levels
- Identifies missing requirements and provides recommendations

### 4. Application Generation
- Generates professional cover letters
- Creates technical approach sections
- Develops past performance narratives
- Builds team qualification statements
- Produces executive summaries

### 5. Automated Submission
- Fills out government portal forms automatically
- Uploads required documents
- Submits applications (when auto-submit is enabled)
- Logs all submission activities

## File Structure

```
ai-model/
├── main.py                 # Main application runner
├── requirements.txt        # Python dependencies
├── config.env.example     # Configuration template
├── README.md              # This file
├── src/                   # Source code
│   ├── config/           # Configuration management
│   ├── scrapers/         # Bid opportunity scrapers
│   ├── processors/       # Document processing
│   ├── ai/              # AI matching system
│   └── applicators/     # Application generation/submission
├── documents/            # Company documents (add your files here)
├── templates/           # Application templates
├── applications/        # Generated applications
└── logs/               # System logs
```

## Safety Features

- **Review Mode**: By default, applications are generated but not submitted
- **Manual Approval**: Review generated applications before submission
- **Rate Limiting**: Configurable limits on daily applications
- **Comprehensive Logging**: All activities are logged for audit trails
- **Error Handling**: Robust error handling and recovery

## Important Notes

### Before Using Auto-Submit

1. **Test First**: Run without `--auto-submit` to review generated applications
2. **Verify Documents**: Ensure all company documents are accurate and up-to-date
3. **Check Configuration**: Verify company information and capabilities
4. **Review Opportunities**: Manually review matched opportunities before submission

### Legal and Ethical Considerations

- Ensure compliance with government contracting regulations
- Verify that automated submissions are allowed for specific opportunities
- Review all generated content for accuracy and appropriateness
- Maintain proper documentation of all submissions

## Troubleshooting

### Common Issues

1. **No Documents Found**: Add company documents to the `documents/` folder
2. **API Key Errors**: Verify your OpenAI API key in the `.env` file
3. **No Opportunities Found**: Try increasing `--days-back` or check internet connection
4. **Submission Failures**: Government portals may have changed; check logs for details

### Logs

Check the `logs/` folder for detailed information:
- `bid_application.log`: Main system log
- `submissions.json`: Submission history

## Support

For issues or questions:
1. Check the logs in the `logs/` folder
2. Verify your configuration with `--config-check`
3. Review the generated applications in the `applications/` folder
4. Ensure all dependencies are installed correctly

## License

This project is provided as-is for educational and business purposes. Please ensure compliance with all applicable laws and regulations when using automated submission features.

# AI-Bidding-model
