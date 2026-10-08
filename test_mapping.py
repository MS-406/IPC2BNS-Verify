from src.mapping.lookup import ConcordanceLookup

# Initialize the lookup (will load the new concordance file)
lookup = ConcordanceLookup()

# Sample sections to test
samples = ["302", "33", "120A", "417"]
for sec in samples:
    result = lookup.map_ipc_to_bns(sec)
    print(f"IPC {sec} -> BNS {result.target_section} (status: {result.status})")
