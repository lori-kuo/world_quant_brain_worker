import pandas as pd
from pathlib import Path
import argparse
import sys
import re
import json
import time

def load_data(dataset_name=None):
    script_dir = Path(__file__).resolve().parent
    workspace_dir = script_dir.parent
    
    if not dataset_name:
        data_root = workspace_dir / "data"
        if not data_root.exists():
            print("Error: Data directory not found.", file=sys.stderr)
            sys.exit(1)
            
        subdirs = [d for d in data_root.iterdir() if d.is_dir()]
        
        if len(subdirs) == 1:
            dataset_name = subdirs[0].name
            print(f"Auto-detected dataset: {dataset_name}", file=sys.stderr)
        elif len(subdirs) > 1:
            print("Error: Multiple datasets found. Please specify --dataset.", file=sys.stderr)
            print("Available datasets:", file=sys.stderr)
            for d in subdirs:
                print(f"  {d.name}", file=sys.stderr)
            sys.exit(1)
        else:
            print("Error: No dataset folders found inside data directory.", file=sys.stderr)
            sys.exit(1)

    dataset_dir = workspace_dir / "data" / dataset_name
    data_path = dataset_dir / f"{dataset_name}.csv"
    
    print(f"Loading data from {data_path}...", file=sys.stderr)
    try:
        df = pd.read_csv(data_path)
        return df, dataset_dir
    except FileNotFoundError:
        print(f"Error: Data file not found at {data_path}. Please run fetch_dataset.py first.", file=sys.stderr)
        sys.exit(1)

def extract_keys_from_template(template):
    return re.findall(r'\{([A-Za-z0-9_]+)\}', template)

def match_single_horizon_auto(df, template):
    """
    Auto-detects metrics from template and finds matching fields.
    """
    metrics = extract_keys_from_template(template)
    if not metrics:
        print("Error: No variables found in template (use {variable} format).", file=sys.stderr)
        return []

    # Sort metrics by length descending to match most specific suffixes first
    metrics = sorted(metrics, key=len, reverse=True)
    primary = metrics[0]
    
    # Try different separators or exact match
    # we look for columns that end with the primary metric, optionally followed by numeric suffix (e.g. _1234)
    # Regex: .*<primary>(?:_\d+)?$
    import re
    primary_regex = re.escape(primary) + r'(?:_\d+)?$'
    candidates = df[df['id'].str.match(f'.*{primary_regex}')]['id'].unique().tolist()
    
    results = []
    seen = set()
    
    # Try different separators or exact match
    # We look for columns that contain the primary metric at any position
    import re
    primary_regex = re.escape(primary)
    candidates = df[df['id'].str.contains(primary_regex, regex=True)]['id'].unique().tolist()
    
    results = []
    seen = set()
    
    for cand in candidates:
        # Determine base prefix
        # We identify the prefix by taking everything before the first occurrence of the primary metric
        match = re.search(re.escape(primary), cand)
        if not match:
             continue
        
        # Base includes everything up to the metric (e.g., "dataset_prefix_")
        base = cand[:match.start()]

        # Verify other metrics exist with this base
        field_map = {primary: cand}
        all_found = True
        
        for m in metrics[1:]:
            # Construct target pattern for other metrics: Must start with the same base followed by the metric
            # We allow any suffix after the metric (e.g. IDs, versions)
            target_pattern = f"^{re.escape(base)}{re.escape(m)}"
            target_matches = df[df['id'].str.match(target_pattern)]['id'].tolist()
            
            if not target_matches:
                all_found = False
                break
            # Use the first match found for the secondary metric
            field_map[m] = target_matches[0]
            
        if all_found:
            try:
                expr = template.format(**field_map)
                if expr not in seen:
                    seen.add(expr)
                    # Create a readable label for the horizon/group
                    if base:
                        # Strip standard separators
                        horizon_label = base.strip("_")
                    else:
                        horizon_label = "global"
                        
                    results.append((horizon_label, expr))
            except KeyError as e:
                continue
                
    return results

def main():
    parser = argparse.ArgumentParser(description="Generate Alpha Expressions based on patterns")
    parser.add_argument("--template", required=True, help="Python format string (e.g. '{st_dev} / abs({mean})')")
    parser.add_argument("--dataset", help="Name of the dataset folder. Auto-detected if only one exists.")
    
    args = parser.parse_args()
    
    df, dataset_dir = load_data(args.dataset)
    
    results = match_single_horizon_auto(df, args.template)
        
    # Output
    expression_list = []
    if not results:
        print("No matching expressions found.")
    else:
        print(f"Generated {len(results)} expressions:\n")
        # print(f"{'Context':<30} | Expression")
        # print("-" * 120)
        
        for context, expr in results:
            # print(f"{context:<30} | {expr}")
            expression_list.append(expr)
            
    # Save results to JSON (Always save for debugging)
    timestamp = int(time.time())
    json_output = {
        "template": args.template,
        "expression_list": expression_list
    }
    
    output_file = dataset_dir / f"idea_{timestamp}.json"
    try:
        with open(output_file, 'w') as f:
            json.dump(json_output, f, indent=4)
        print(f"\nSaved idea configuration to: {output_file}")
    except Exception as e:
        print(f"Error saving JSON: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
