# Prompts

## billing.py

> Created by [Claude 3.7 Sonnet](https://claude.ai/share/3196a0a7-15f9-4064-ab00-af080edc8741) and [commited](https://github.com/sanand0/llmpricing/blob/9b66480458b712de52ea14502a64bf4c3b6a98ed/billing.py).

Write a concise, minimal Python script that fetches https://openrouter.ai/api/frontend/models

Extract the following information into a endpoints dict:
- id: .data[].endpoint.id
  - model_slug: .data[].endpoint.model.slug
  - pricing_completion: .data[].endpoint.pricing.completion

Then, in groups of 10, fetch the througput stats
https://openrouter.ai/api/frontend/stats/throughput-comparison?ids={",".join(ids)}

The response is like:

```json
{
  "data": [
    {
      "x": "2025-04-24 00:00:00",
      "y": {
        "id1": 57.197,
        "id2": 96.098,
        "id3": 37.0765,
        ...
      }
    }
  ]
}

Add the average "y" value by id to endpoints[id]["throughput"].
Calculate the endpoint's "billing_rate" as pricing_completion ($/token) * throughput (tokens/second) * 3600 (seconds per hour).
For all fetch requests, show progress via tqdm.

Style:
- Use httpx (same API as requests)
- Write SHORT, CONCISE, READABLE code
- Write modular code (iteration, functions). No duplication
- Use functions, not classes
- Validate early. Use the if-return pattern. Avoid unnecessary else statements
- Avoid try blocks unless the operation is error-prone
