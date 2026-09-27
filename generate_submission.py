import json
import os
from bot import generate_message

# Load all required datasets
with open('dataset/test_pairs.json') as f:
    test_pairs = json.load(f)['pairs']

categories = {}
merchants = {}
customers = {}
triggers = {}

def load_data():
    for filename in os.listdir('dataset/categories'):
        with open(f'dataset/categories/{filename}') as f:
            data = json.load(f)
            categories[data['slug']] = data
    for filename in os.listdir('dataset/merchants'):
        with open(f'dataset/merchants/{filename}') as f:
            data = json.load(f)
            merchants[data['merchant_id']] = data
    for filename in os.listdir('dataset/customers'):
        with open(f'dataset/customers/{filename}') as f:
            data = json.load(f)
            customers[data['customer_id']] = data
    for filename in os.listdir('dataset/triggers'):
        with open(f'dataset/triggers/{filename}') as f:
            data = json.load(f)
            triggers[data['id']] = data

load_data()

with open('submission.jsonl', 'w') as out_f:
    for pair in test_pairs:
        test_id = pair['test_id']
        merchant = merchants[pair['merchant_id']]
        trigger = triggers[pair['trigger_id']]
        category = categories[merchant.get('category_slug', trigger.get('payload', {}).get('category', 'unknown'))]
        
        customer = None
        if pair.get('customer_id'):
            customer = customers[pair['customer_id']]
            
        msg_data = generate_message(merchant, category, trigger, customer)
        
        out_line = {
            "test_id": test_id,
            "body": msg_data["body"],
            "cta": msg_data["cta"],
            "send_as": msg_data["send_as"],
            "suppression_key": msg_data["suppression_key"],
            "rationale": msg_data["rationale"]
        }
        out_f.write(json.dumps(out_line) + '\n')

print("Generated submission.jsonl with", len(test_pairs), "entries.")
