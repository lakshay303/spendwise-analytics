# SpendWise Analytics

A personal finance and expense analytics dashboard. Track income and expenses, set monthly budgets, import and export CSV and Excel files, and get automatic insights from your own data.

Built with Python, Streamlit, Pandas, SQLite and Plotly.

**Live demo:** https://spendwise-analytics-lakshay.streamlit.app/

![Dashboard](docs/screenshots/dashboard.png)

## Features

- **Dashboard:** income, expenses, balance, savings rate and budget remaining, each compared with the previous month. Includes a category donut chart, an income vs expenses chart, a spending trend against last month, and automatic insights.
- **Transactions:** add, edit and delete income and expenses with validation. Search, filter by type, category and date range, and sort by any column.
- **Budgets:** monthly budget per expense category with progress bars and a status (on track, near limit, over budget). Copy last month's budgets in one click.
- **Analytics:** savings trend and savings rate, spending by category over time, top categories, and a category-by-category comparison with the previous month.
- **Insights:** plain-language findings generated from your data, such as spending changes, the category that moved most, budgets that are close to their limit, and unusually large expenses.
- **CSV and Excel import and export:** accepts `.csv` and `.xlsx` files (first sheet), validates every row, previews before importing, reports problem rows with the reason, skips duplicates, and stores descriptions safely so spreadsheet programs can't run them as formulas. Exports to CSV or a formatted Excel file.
- **Persistent storage:** all data is stored in a SQLite database.

## Screenshots

| Transactions | Budgets |
| --- | --- |
| ![Transactions](docs/screenshots/transactions.png) | ![Budgets](docs/screenshots/budgets.png) |

![Analytics](docs/screenshots/analytics.png)

![Import and export](docs/screenshots/import_export.png)

## How the calculations work

- Income and expenses live in one table, separated by a `type` column. The database rejects any other value, and a transaction's category must match its type.
- A budget's "spent" amount counts **expenses only**, in that budget's category and month. Income is never counted as spending.
- Every page gets its numbers from the same service functions, so the Dashboard, Budgets and Analytics pages always agree.
- Insights use simple, explainable rules. For example, an expense is flagged as unusual only if it is more than 3 times the median of your other expenses in that category, and only when there are at least 5 other expenses to compare against.

## Run it locally

You need Python 3.11 or newer.

Windows:

```
git clone https://github.com/lakshay303/spendwise-analytics.git
cd spendwise-analytics
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

macOS or Linux:

```
git clone https://github.com/lakshay303/spendwise-analytics.git
cd spendwise-analytics
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501. On first run it creates `data/spendwise.db`. The Dashboard offers a **Load sample data** button to try the app with example data.

To use a different database file, set the `SPENDWISE_DB` environment variable to its path before starting the app.

## CSV and Excel format

Required columns: `date`, `type`, `category`, `amount`. Optional: `description`. Excel files use the first sheet, with the column names in the first row. Both formats can be downloaded as a template from the Import tab.

```
date,type,category,amount,description
2026-10-01,income,Salary,50000,October salary
2026-10-02,expense,Food & Dining,250.00,Lunch
```

Dates can be `YYYY-MM-DD` or `DD/MM/YYYY` (real Excel dates also work). Type is `income` or `expense`. Category names must match an existing category. Uploads are limited to 5 MB and 5,000 rows.

## Tests

The calculation logic has automated checks that run against a temporary database, so your real data is never touched:

```
python tests/test_calculations.py
python tests/test_analytics.py
python tests/test_analytics_page.py
python tests/test_insights.py
python tests/test_trend.py
python tests/test_csv.py
python tests/test_excel.py
python tests/test_excel_limits.py
python tests/test_sample_data.py
```

Each script prints `PASS` or `FAIL` for every check and ends with a summary.

## Project structure

```
app.py                  Entry point and navigation
spendwise/
  database.py           SQLite connection and schema
  ui.py                 Shared styles and UI components
  charts.py             Plotly charts
  services/
    transactions.py     Add, edit, delete, list and validate transactions
    budgets.py          Monthly budgets and budget status
    analytics.py        Summaries, trends and comparisons
    insights.py         Automatic insights and unusual-expense detection
    csv_io.py           CSV and Excel import and export
    sample_data.py      Example data generator
views/                  One file per page
tests/                  Automated checks
docs/screenshots/       README images
.streamlit/config.toml  Theme
```

## Limitations

- The live demo is public and uses sample data. Everyone sees the same database, and it can reset at any time, so please don't enter personal information. For your own finances, run SpendWise locally.
- SpendWise is a single-user app with no login. If it is hosted publicly, every visitor shares the same database, and free hosting platforms may reset local files when an app restarts.
- Currency is shown in rupees (₹).

## Roadmap

- Hosted Postgres database and user accounts for a private multi-device deployment
- Recurring transaction detection
- Configurable currency

## License

MIT. See the LICENSE file.
