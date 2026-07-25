# NCLT Scraper

This project is a web scraper for the National Company Law Tribunal (NCLT) website. It fetches case details, downloads related PDFs, and stores the data in a structured format.

## Features

- Fetches case details from all NCLT benches
- Downloads related PDF documents
- Stores data in JSON and CSV formats
- Multithreaded for efficient scraping
- Command-line interface for easy date range specification

## Requirements

- Python 3.7+
- Required Python packages (install using `pip install -r requirements.txt`):
  - requests
  - beautifulsoup4
  - pandas
  - tqdm

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/tushar-anand15/nclt-scraper.git
   cd nclt-scraper
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

Run the scraper from the command line using the following syntax:

```
python main.py START_DATE END_DATE
```

- `START_DATE`: The start date for data retrieval (format: DD/MM/YYYY)
- `END_DATE`: The end date for data retrieval (format: DD/MM/YYYY)

Example:
```
python main.py 01/08/2023 15/08/2023
```

This will scrape NCLT data from August 1, 2023, to August 15, 2023.

For help and to see all available options:
```
python main.py -h
```

## Output

The scraper will create a `data` directory with the following structure:

```
data/
├── {job_id}/
│   ├── html/
│   ├── json/
│   ├── pdfs/
│   └── logs/
└── NCLT_ALL_BENCH_{job_id}.csv
```

- `html/`: Contains raw HTML files for each case
- `json/`: Contains parsed case data in JSON format
- `pdfs/`: Contains downloaded PDF documents
- `logs/`: Contains log files for the scraping process
- `NCLT_ALL_BENCH_{job_id}.csv`: A CSV file containing summary data for all scraped cases
