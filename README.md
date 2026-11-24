# Weather and Citi Bike starts in 2023

CISC7204 Data Visualization, 2026/2027 Semester 1. Class D, Team 02.

This project examines observed daily starts in the supplied 2023 non-JC Citi Bike release and weather observed at NOAA Central Park. The analysis compares a calendar baseline with a weather-adjusted model and reports uncertainty using heteroskedasticity and autocorrelation consistent standard errors.

## Reproduce from the course archive

1. Extract the full course ZIP into a new directory. Keep the archive structure. The annual Citi Bike ZIP contains all 40 trip CSVs. The annual ZIP, NOAA CSV and NOAA documentation are under data/raw. The preparation notebook reads one monthly archive into temporary storage at a time. Keep several GB of available RAM and temporary disk space.
2. Use Python 3.12. In a terminal at the extracted root, create an environment and install the packages:

   ```text
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   .venv\Scripts\jupyter-lab.exe
   ```

   On macOS or Linux use .venv/bin/python and .venv/bin/jupyter-lab. Select the resulting Python environment as the kernel. Use Run > Run All Cells in 01_Prepare_Daily_Data.ipynb, then do the same in 02_Weather_Association.ipynb. Saved outputs are available for quick review. If working with the included frozen daily table, Notebook 02 can be run directly with the NOAA CSV.
3. Equivalent CLI commands from the archive root:

   ```text
   python verify_inputs.py
   python prepare_data.py
   python model_analysis.py
   python make_figures.py
   ```

4. Check results/audit.json for 35,106,986 input rows, 600 exclusions, zero duplicate valid IDs, 35,106,386 retained starts and 365 matched days. Compare results/model_summary.json and results/sensitivity.csv. Open results/demo.html in a browser for the project walkthrough. If using a different source release, record any count/hash differences and the new release date.

## Inputs and research outputs

- Citi Bike System Data, January–December 2023, supplied non-JC monthly archives. The trip source includes ride ID, ride time, origin coordinates and member category. https://citibikenyc.com/system-data
- NOAA NCEI Daily Summaries, supplied 2023 weather export. Primary station USW00094728 (Central Park), alternate USW00014732 (LaGuardia). https://www.ncei.noaa.gov/cdo-web/datasets/GHCND
- raw_manifest.json gives exact SHA-256 values for the archived input bytes. data_sources.md describes paths and public repository setup.
- results/daily_2023.csv, trip_inventory.csv, audit.json, coefficients.csv, sensitivity.csv and diagnostics.csv make the calculations auditable. The temperature curve is drawn separately for each month. temperature_support.csv gives the endpoint support audit by month and precipitation scope.
- CODEBOOK.md records analysis fields. PNG charts and figure_guide.json contain figure-level design explanations. The report and slides use the same data.

## Scope

The results describe observed daily trip starts in the supplied release and cannot establish the effect of weather on unconstrained demand. The timestamps do not contain offsets. The source date is interpreted as New York local civil date. A coordinate rectangle is a screening check, and no exact administrative boundary overlay was available. PRCP grouping avoids assuming a physical precipitation unit. The numerical PRCP amount model retains the raw CSV scale. The main temperature variable is the midpoint of the confirmed Fahrenheit high and low.
