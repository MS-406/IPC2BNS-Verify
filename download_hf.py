import pandas as pd
from datasets import load_dataset
import os

print("Downloading dataset...")
# Load the open source dataset
ds = load_dataset("nandhakumarg/IPC_and_BNS_transformation", split="train")

df = ds.to_pandas()
print("Columns in dataset:", df.columns.tolist())

# Map columns to match what lookup.py expects
out_df = pd.DataFrame()
if 'IPC_Section' in df.columns:
    out_df['ipc_section'] = df['IPC_Section'].astype(str).str.replace('Section ', '')
elif 'ipc_section' in df.columns:
    out_df['ipc_section'] = df['ipc_section']
else:
    out_df['ipc_section'] = df.iloc[:, 0]

if 'BNS_Section' in df.columns:
    out_df['bns_section'] = df['BNS_Section'].astype(str).str.replace('Section ', '')
elif 'bns_section' in df.columns:
    out_df['bns_section'] = df['bns_section']
else:
    out_df['bns_section'] = df.iloc[:, 1]

out_df['status'] = 'exact' # default

output_path = r"c:\Users\DELL\IPC2BNS-Verify\data\eval_ground_truth\concordance_v1.csv"
os.makedirs(os.path.dirname(output_path), exist_ok=True)
out_df.to_csv(output_path, index=False)
print(f"Successfully wrote {len(out_df)} mapping rows to {output_path}")
