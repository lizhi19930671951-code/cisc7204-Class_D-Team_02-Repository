# Data sources and repository setup

The course archive includes the complete raw inputs. Keep the supplied raw CSVs unchanged. The file inventory records names, byte sizes and SHA-256 values.

Citi Bike data portal: https://citibikenyc.com/system-data

The official bucket lists the twelve non-JC monthly ZIP files:
https://s3.amazonaws.com/tripdata/index.html
The monthly object pattern is https://s3.amazonaws.com/tripdata/202301-citibike-tripdata.zip, with month updated through 202312. Extract each in data/raw/2023-citibike-tripdata/. Run `python verify_inputs.py` from the research root to compare against raw_manifest.json. If an official download has been revised, use the exact copy in the course ZIP to reproduce the reported counts.

NOAA Daily Summaries: https://www.ncei.noaa.gov/cdo-web/datasets/GHCND
Central Park station: https://www.ncei.noaa.gov/cdo-web/datasets/GHCND/stations/GHCND:USW00094728/detail
The archive contains nyc_weather_2023.csv, including both weather stations used in the report and their flags. Retain this exact 2023 export. GHCND_documentation.pdf defines variable and attribute formats.

## Publish the research repository

The folder is prepared for a public GitHub repo with notebooks, code, weather CSV, daily data, figures, the reproducibility guide and the input checksum manifest. The full trip dataset is in the course ZIP. Ordinary GitHub Git cannot store the 35 supplied CSVs above 100 MiB. Keep data/raw/2023-citibike-tripdata/ out of Git as configured, and confirm the course accepts the official download instructions and complete input ZIP as the large-data distribution path. If required, the team must arrange an approved large-file host. Team photos, student IDs and recordings belong in the course material the team approves for sharing.

After posting, open GitHub and the team demo video URL from a signed-out browser. Enter the repository URL in the Moodle submission and replace the demo URL field in the final PPT. Check the Moodle archive-size limit before uploading.
