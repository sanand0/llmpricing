#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "statistics",
#     "tqdm",
# ]
# ///
import httpx
import statistics
from tqdm import tqdm
import json


def fetch_models():
    """Fetch all models and extract endpoint info."""
    response = httpx.get("https://openrouter.ai/api/frontend/models")
    response.raise_for_status()

    endpoints = {}
    for item in response.json()["data"]:
        endpoint = item["endpoint"]
        if endpoint:
            endpoints[endpoint["id"]] = {
                "model_slug": endpoint["model"]["slug"],
                "pricing_completion": endpoint["pricing"]["completion"],
                "created_at": endpoint["model"]["created_at"],
            }
    return endpoints


def fetch_throughput_batch(ids):
    """Fetch throughput stats for a batch of IDs."""
    url = f"https://openrouter.ai/api/frontend/stats/throughput-comparison?ids={','.join(ids)}"
    response = httpx.get(url)
    response.raise_for_status()

    # Calculate average throughput per ID
    data_points = response.json()["data"]
    if not data_points:
        return {id_: 0 for id_ in ids}

    averages = {}
    for id_ in ids:
        values = [point["y"].get(id_, 0) for point in data_points if id_ in point["y"]]
        averages[id_] = statistics.mean(values) if values else 0

    return averages


def add_throughput_data(endpoints):
    """Add throughput data to endpoints in batches of 10."""
    ids = list(endpoints.keys())
    batches = [ids[i : i + 10] for i in range(0, len(ids), 10)]

    for batch in tqdm(batches, desc="Fetching throughput"):
        throughput_data = fetch_throughput_batch(batch)
        for id_, throughput in throughput_data.items():
            endpoints[id_]["throughput"] = throughput


def calculate_billing_rates(endpoints):
    """Calculate billing rate for each endpoint."""
    for data in endpoints.values():
        pricing = data["pricing_completion"]
        throughput = data["throughput"]
        data["billing_rate"] = float(pricing) * float(throughput) * 3600


def main():
    endpoints = fetch_models()
    add_throughput_data(endpoints)
    calculate_billing_rates(endpoints)

    with open("billing.json", "w") as f:
        json.dump(list(endpoints.values()), f)


if __name__ == "__main__":
    main()
