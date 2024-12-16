import requests
from bs4 import BeautifulSoup
import pandas as pd
import concurrent.futures
import urllib3
import random
import base64
import os
import json
import time
from requests.exceptions import RequestException
import logging
from urllib.parse import urljoin
from tqdm import tqdm
import argparse
from datetime import datetime

# Suppress only the InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NCLTScraper:
    def __init__(self, from_date, to_date):
        self.from_date = from_date
        self.to_date = to_date
        self.job_id = self.job_id_str()
        self.create_directories()
        self.setup_logging()
        self.bench_values = [
            "delhi_1", "delhi_2", "delhi_3", "delhi_4", "delhi_5", "delhi_6",
            "ahmedabad", "allahabad", "amravati", "bengaluru", "chandigarh", "chennai",
            "cuttak", "guwahati", "hyderabad", "indore", "jaipur", "kochi", "kolkata", "mumbai"
        ]
        self.max_workers = 25
        self.max_retries = 3
        self.retry_delay = 5

    def create_directories(self):
        directories = [
            f'data/{self.job_id}/html',
            f'data/{self.job_id}/json',
            f'data/{self.job_id}/pdfs',
            f'data/{self.job_id}/logs'
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def job_id_str(self):
        return f"{random.randint(100000, 999999)}"

    def setup_logging(self):
        log_file = os.path.join(f'data/{self.job_id}/logs', f'scraper_{self.job_id}.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)

        self.logger = logging.getLogger(f'NCLTScraper_{self.job_id}')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.propagate = False

    @staticmethod
    def to_base64(input_string):
        return base64.b64encode(input_string.encode('utf-8')).decode('utf-8')

    def process_page_data(self, bench, start_date, end_date, total_pages, page=1):
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://nclt.gov.in/order-date-wise-search",
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36"
        }

        params = {
            "bench": self.to_base64(bench),
            "start_date": self.to_base64(start_date),
            "end_date": self.to_base64(end_date),
            "page": page
        }

        try:
            response = requests.get(
                "https://nclt.gov.in/order-date-wise-search",
                params=params,
                headers=headers,
                verify=False,
                timeout=250
            )
            if response.status_code == 200:
                self.logger.info(f"Successfully fetched page {page} for bench {bench}")
                return BeautifulSoup(response.text, "html.parser")
            else:
                self.logger.warning(f"Failed to fetch page {page} for bench {bench} - Status code: {response.status_code}")
                return None
        except RequestException as e:
            self.logger.error(f"Network error while fetching page {page} for bench {bench}. Error: {str(e)}")
            return None

    @staticmethod
    def process_pagination(pagination_data):
        page_numbers = [int(li.text.strip()) for li in pagination_data.find_all("li") if li.text.strip().isdigit()]
        return max(page_numbers) if page_numbers else 1

    @staticmethod
    def process_table_data(html_content, bench):
        table = html_content.find("table", class_="table-borderd")
        table_data = []

        rows = table.find("tbody").find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
            
            row_data = {
                "S. No.": cells[0].text.strip(),
                "Filing No.": cells[1].text.strip(),
                "Case No": cells[2].text.strip(),
                "Petitioner Vs. Respondent": cells[3].text.strip(),
                "Listing Date / Court No.": cells[4].text.strip(),
                "Status": cells[5].text.strip(),
                "Case_Link": cells[5].find("a").get("href") if cells[5].find("a") else None,
                "Bench": bench
            }

            table_data.append(row_data)

        return table_data

    def fetch_all_pages(self, bench):
        all_data = []

        first_page_soup = self.process_page_data(bench, self.from_date, self.to_date, '1')
        if first_page_soup:
            total_pages = self.process_pagination(first_page_soup)
            all_data.extend(self.process_table_data(first_page_soup, bench))

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_page = {
                    executor.submit(self.process_page_data, bench, self.from_date, self.to_date, total_pages, page): page
                    for page in range(2, total_pages+1)
                }

                for future in tqdm(concurrent.futures.as_completed(future_to_page), 
                                   total=len(future_to_page), 
                                   desc=f"Fetching {bench} data",
                                   position=0, 
                                   leave=True):
                    page_data = future.result()
                    if page_data:
                        table_data = self.process_table_data(page_data, bench)
                        all_data.extend(table_data)

        return all_data

    def get_case_data(self, case_obj):
        url = 'https://www.nclt.gov.in/case-details'
        
        if case_obj['Bench'] in ['delhi_1', 'delhi_2', 'delhi_3', 'delhi_4', 'delhi_5', 'delhi_6']:
            bench = 'delhi'
        else:
            bench = case_obj['Bench']
        
        params = {
            'bench': self.to_base64(bench),
            'filing_no': self.to_base64(case_obj['Filing No.'])
        }
        
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Host': 'nclt.gov.in',
            'Sec-Ch-Ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
        }

        try:
            req = requests.get(url, params=params, verify=False, headers=headers, timeout=250)
            if req.status_code == 200:
                self.logger.info(f'Successfully fetched data for Filing No: {case_obj["Filing No."]}')
                
                # Save HTML file
                html_filename = f"{case_obj['Filing No.']}.html"
                html_file_path = os.path.join(f'data/{self.job_id}/html', html_filename)
                with open(html_file_path, 'w', encoding='utf-8') as html_file:
                    html_file.write(req.text)
                
                # Parse HTML and save JSON
                case_data = self.parse_html_data(html_file_path)
                json_filename = f"{case_obj['Filing No.']}.json"
                json_file_path = os.path.join(f'data/{self.job_id}/json', json_filename)
                with open(json_file_path, 'w', encoding='utf-8') as json_file:
                    json.dump(case_data, json_file, indent=2, ensure_ascii=False)

                self.logger.info(f'Saved HTML file for Filing No: {case_obj["Filing No."]} at {html_file_path}')
                self.logger.info(f'Saved JSON file for Filing No: {case_obj["Filing No."]} at {json_file_path}')
                return {
                    'status': 'success', 
                    'html_file_path': html_file_path, 
                    'json_file_path': json_file_path, 
                    'filing_no': case_obj['Filing No.'], 
                    'case_data': case_data
                }
            else:
                self.logger.warning(f'Failed to fetch data for Filing No: {case_obj["Filing No."]} - Status code: {req.status_code}')
                return {'status': 'failed', 'filing_no': case_obj['Filing No.'], 'error': f"Status code: {req.status_code}"}

        except RequestException as e:
            self.logger.error(f"Network error for Filing No: {case_obj['Filing No.']}. Error: {str(e)}")
            return {'status': 'error', 'filing_no': case_obj['Filing No.'], 'error': f"Network error: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Error processing Filing No: {case_obj['Filing No.']}. Error: {str(e)}")
            return {'status': 'error', 'filing_no': case_obj['Filing No.'], 'error': str(e)}

    def fetch_all_case_data(self, cases):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_case = {executor.submit(self.get_case_data, case): case for case in cases}
            
            results = []
            for future in tqdm(concurrent.futures.as_completed(future_to_case), 
                               total=len(cases), 
                               desc="Processing cases",
                               position=0, 
                               leave=True):
                case = future_to_case[future]
                try:
                    result = future.result()
                    if result['status'] == 'success':
                        results.append(result)
                    self.logger.info(f"Processed {result['filing_no']} with status: {result['status']}")
                except Exception as exc:
                    self.logger.error(f'{case["Filing No."]} generated an exception: {exc}')
        
        failed_cases = [case for case in cases if case['Filing No.'] not in [r['filing_no'] for r in results if r['status'] == 'success']]
        
        for retry in range(self.max_retries):
            if not failed_cases:
                break
            
            self.logger.info(f"Retry attempt {retry + 1} for {len(failed_cases)} cases")
            time.sleep(self.retry_delay)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_case = {executor.submit(self.get_case_data, case): case for case in failed_cases}
                
                new_results = []
                for future in tqdm(concurrent.futures.as_completed(future_to_case), 
                                   total=len(failed_cases), 
                                   desc=f"Retry {retry + 1}",
                                   position=0, 
                                   leave=True):
                    case = future_to_case[future]
                    try:
                        result = future.result()
                        if result['status'] == 'success':
                            new_results.append(result)
                        self.logger.info(f"Retried {result['filing_no']} with status: {result['status']}")
                    except Exception as exc:
                        self.logger.error(f'{case["Filing No."]} generated an exception on retry: {exc}')
                
                results.extend(new_results)
                failed_cases = [case for case in failed_cases if case['Filing No.'] not in [r['filing_no'] for r in new_results if r['status'] == 'success']]
        
        self.logger.info(f"Total cases processed successfully: {len([r for r in results if r['status'] == 'success'])}")
        self.logger.info(f"Total cases failed: {len(failed_cases)}")
        
        return results
    def download_pdf(self, pdf_info):
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Host': 'nclt.gov.in',
            'Sec-Ch-Ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
        }
        
        try:
            response = requests.get(pdf_info['url'], headers=headers, verify=False, timeout=250)
            if response.status_code == 200:
                with open(pdf_info['file_path'], 'wb') as pdf_file:
                    pdf_file.write(response.content)
                self.logger.info(f"Successfully downloaded PDF for date {pdf_info['date']}")
                return {'date': pdf_info['date'], 'status': 'success', 'file_path': pdf_info['file_path']}
            else:
                self.logger.warning(f"Failed to download PDF for date {pdf_info['date']}. Status code: {response.status_code}")
                return {'date': pdf_info['date'], 'status': 'failed', 'file_path': None}
        except RequestException as e:
            self.logger.error(f"Error downloading PDF for date {pdf_info['date']}. Error: {str(e)}")
            return {'date': pdf_info['date'], 'status': 'error', 'file_path': None}

    def download_pdfs(self, results):
        base_url = 'https://www.nclt.gov.in/'
        pdf_list = []

        for result in results:
            if result['status'] == 'success':
                json_file = os.path.join(f'data/{self.job_id}/json', f"{result['filing_no']}.json")
                if os.path.exists(json_file):
                    with open(json_file, 'r') as f:
                        case_data = json.load(f)
                    
                    pdf_dir = os.path.join(f'data/{self.job_id}/pdfs', case_data['Filing No.'])
                    os.makedirs(pdf_dir, exist_ok=True)
                    
                    for item in case_data.get('Listing History', []):
                        date_of_listing = item['Date of Listing']
                        pdf_url = urljoin(base_url, item['Order/Judgement Link'])
                        filename = f"{date_of_listing}.pdf"
                        file_path = os.path.join(pdf_dir, filename)
                        
                        pdf_list.append({
                            'url': pdf_url,
                            'file_path': file_path,
                            'date': date_of_listing,
                            'filing_no': case_data['Filing No.']
                        })

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_pdf = {executor.submit(self.download_pdf, pdf_info): pdf_info for pdf_info in pdf_list}
            
            download_results = []
            for future in tqdm(concurrent.futures.as_completed(future_to_pdf), 
                            total=len(pdf_list), 
                            desc="Downloading PDFs",
                            position=0, 
                            leave=True):
                pdf_info = future_to_pdf[future]
                try:
                    result = future.result()
                    download_results.append(result)
                    self.logger.info(f"Completed PDF download for Filing No: {pdf_info['filing_no']}, Date: {pdf_info['date']}")
                except Exception as exc:
                    self.logger.error(f"PDF download failed for Filing No: {pdf_info['filing_no']}, Date: {pdf_info['date']}. Error: {str(exc)}")
                    download_results.append({'date': pdf_info['date'], 'status': 'error', 'file_path': None})

        return download_results
    
    def run(self):
        all_bench_data = []
        for bench in tqdm(self.bench_values, desc="Fetching data from all benches", position=0, leave=True):
            bench_data = self.fetch_all_pages(bench)
            all_bench_data.extend(bench_data)

        all_bench_df = pd.DataFrame(all_bench_data)
        all_bench_df['S. No.'] = range(1, len(all_bench_df) + 1)
        csv_name = f"NCLT_ALL_BENCH_{self.job_id}.csv"
        all_bench_df.to_csv(csv_name, index=False)
        
        cases = all_bench_df.to_dict(orient='records')
        results = self.fetch_all_case_data(cases)
        
        download_results = self.download_pdfs(results)
        
        self.logger.info(f"Total PDFs downloaded successfully: {len([r for r in download_results if r['status'] == 'success'])}")
        self.logger.info(f"Total PDFs failed to download: {len([r for r in download_results if r['status'] != 'success'])}")
        self.logger.info("PDF download process completed.")

def validate_date(date_string):
    try:
        return datetime.strptime(date_string, "%d/%m/%Y").strftime("%d/%m/%Y")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_string}. Use DD/MM/YYYY")

def main():
    parser = argparse.ArgumentParser(description="NCLT Scraper")
    parser.add_argument("start_date", type=validate_date, help="Start date in DD/MM/YYYY format")
    parser.add_argument("end_date", type=validate_date, help="End date in DD/MM/YYYY format")
    args = parser.parse_args()

    scraper = NCLTScraper(args.start_date, args.end_date)
    scraper.run()

if __name__ == "__main__":
    main()