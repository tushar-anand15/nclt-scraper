import subprocess
import pandas as pd
import os
import re

# Define the range of workers to test
worker_counts = [1, 2, 3, 4, 6, 8, 12, 16]
worker_counts = worker_counts[::-1]
date_range = ("01/01/2021", "07/01/2021")
reports_dir = "data"

# Function to extract information from a report file
def extract_report_info(report_path):
    report_data = {}
    with open(report_path, 'r') as file:
        for line in file:
            key, value = line.strip().split(": ", 1)
            report_data[key] = value
    return report_data

# Run the scraper for each worker count
for workers in worker_counts:
    print(f"Running scraper with {workers} workers...")
    subprocess.run(["python", "main.py", date_range[0], date_range[1], "--workers", str(workers)])

# Collect results from each report
results = []
for workers in worker_counts:
    # Find the latest job_id directory
    job_dirs = [d for d in os.listdir(reports_dir) if os.path.isdir(os.path.join(reports_dir, d))]
    latest_job_id = max(job_dirs, key=lambda d: int(re.search(r'\d+', d).group()))
    report_path = os.path.join(reports_dir, latest_job_id, "logs", f"report_{latest_job_id}.txt")
    
    if os.path.exists(report_path):
        report_info = extract_report_info(report_path)
        report_info["Workers"] = workers
        results.append(report_info)
    else:
        print(f"Report not found for {workers} workers.")

# Create a DataFrame from the results
df = pd.DataFrame(results)

# Display the consolidated DataFrame
print(df)