import requests
import pandas as pd

url = "https://opendata.elia.be/api/explore/v2.1/catalog/datasets/ods134/records"

params = {
    "limit": 100,
    "order_by": "datetime",
    "where": "datetime >= date'2026-10-24' AND datetime < date'2026-10-25'"
}

response = requests.get(url, params= params, timeout=15)

if response.status_code == 200:
    data = response.json()

    total_count = data["total_count"]

    df_list = data["results"]

    # TODO (cleaning): convert datetime with pd.to_datetime(..., utc=True)
    # TODO (cleaning): decide if None and 0 mean the same thing in alpha_prime
    
    df = pd.DataFrame(df_list)

    # Check the result for one day
    print("Rows:", len(df))
    print("First datetime:", df["datetime"].iloc[0])
    print("Last datetime:", df["datetime"].iloc[-1])
    print("Quality status:", df["qualitystatus"].unique())

else: 
    print(response.status_code)
    print(response.text)