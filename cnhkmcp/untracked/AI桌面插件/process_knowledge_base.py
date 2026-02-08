import os
import sys
import pandas as pd
import json
import re
from pathlib import Path
from typing import List

# Add get_knowledgeBase_tool to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.join(SCRIPT_DIR, "get_knowledgeBase_tool")
if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

# Import from tool directory
sys.path.insert(0, TOOL_DIR)
import ace_lib
from fetch_all_operators import fetch_operators, prompt_credentials
from fetch_all_documentation import (
    fetch_tutorials,
    fetch_tutorial_pages,
    fetch_page,
    _extract_page_id,
)
# Dataset fetching currently disabled per request
# from fetch_all_datasets import (
#     fetch_all_combinations,
#     fetch_datasets_for_combo,
#     merge_and_deduplicate,
# )


def ensure_knowledge_dir():
    """Ensure knowledge directory exists"""
    knowledge_dir = os.path.join(SCRIPT_DIR, "knowledge")
    os.makedirs(knowledge_dir, exist_ok=True)
    return knowledge_dir


def to_jsonable(value):
    """Convert values to JSON-serializable, handling NaN and nested structures."""
    try:
        if isinstance(value, float) and pd.isna(value):
            return None
    except TypeError:
        pass

    if isinstance(value, list):
        return [to_jsonable(v) for v in value if not (isinstance(v, float) and pd.isna(v))]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def safe_filename(name: str, suffix: str = "") -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name)).strip("_") or "doc"
    base = base[:80]
    return f"{base}{suffix}"


def process_operators(session: ace_lib.SingleSession, knowledge_dir: str):
    """
    Process operators and save as JSON files
    
    Args:
        session: Authenticated BRAIN session
        knowledge_dir: Directory to save JSON files
    """
    print("\n=== Processing Operators ===")
    
    # Fetch operators data
    print("Fetching operators...")
    operators_df = fetch_operators(session)
    
    if operators_df.empty:
        print("No operators found!")
        return
    
    print(f"Found {len(operators_df)} operator entries")
    
    # Get unique categories
    categories = sorted(operators_df['category'].dropna().unique())
    
    for category in categories:
        category_data = operators_df[operators_df['category'] == category].copy()
        
        # Create JSON file for this category
        filename = f"{category.replace(' ', '_').lower()}_operators.json"
        filepath = os.path.join(knowledge_dir, filename)
        
        print(f"Processing category: {category}")
        
        # Convert to list of dicts
        category_list = []
        for idx, row in category_data.iterrows():
            operator_dict = {}
            for col in row.index:
                value = row[col]
                operator_dict[col] = to_jsonable(value)
            category_list.append(operator_dict)
        
        # Save category JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(category_list, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Created {filename} with {len(category_list)} operators")


    # Dataset fetching intentionally disabled; keep for potential re-enable.
    # def process_datasets(session: ace_lib.SingleSession, dataset_dir: str):
    #     """Fetch datasets and save one JSON per region."""
    #     print("=== Processing Datasets ===")
    #
    #     print("Fetching valid instrument/region/delay/universe combinations...")
    #     options_df = fetch_all_combinations(session)
    #     if options_df is None or options_df.empty:
    #         print("No simulation options fetched; aborting dataset fetch.")
    #         return
    #
    #     all_datasets: list[pd.DataFrame] = []
    #     combo_idx = 0
    #
    #     for _, row in options_df.iterrows():
    #         instrument_type = row.get("InstrumentType")
    #         region = row.get("Region")
    #         delay = row.get("Delay")
    #         universes = row.get("Universe") or []
    #
    #         for universe in universes:
    #             combo_idx += 1
    #             print(f"[{combo_idx}] {instrument_type} / {region} / D{delay} / {universe}")
    #             try:
    #                 df = fetch_datasets_for_combo(session, instrument_type, region, delay, universe)
    #                 print(f"    -> {len(df)} rows")
    #                 all_datasets.append(df)
    #             except Exception as exc:
    #                 print(f"    -> Failed: {exc}")
    #
    #     if not all_datasets:
    #         print("No datasets fetched; nothing to save.")
    #         return
    #
    #     combined_df = pd.concat([df for df in all_datasets if not df.empty], ignore_index=True)
    #     if combined_df.empty:
    #         print("No datasets fetched; nothing to save.")
    #         return
    #
    #     regions = sorted(combined_df["param_region"].dropna().unique())
    #     print(f"Found regions: {', '.join(regions)}")
    #
    #     for region in regions:
    #         region_df = combined_df[combined_df["param_region"] == region]
    #         region_unique = merge_and_deduplicate([region_df])
    #
    #         region_list = []
    #         for _, row in region_unique.iterrows():
    #             record = {col: to_jsonable(row[col]) for col in row.index}
    #             region_list.append(record)
    #
    #         filename = f"{region.replace(' ', '_').lower()}_datasets.json"
    #         filepath = os.path.join(dataset_dir, filename)
    #         with open(filepath, "w", encoding="utf-8") as f:
    #             json.dump(region_list, f, ensure_ascii=False, indent=2)
    #
    #         print(f"✓ Created {filename} with {len(region_list)} datasets")


def process_documentation(session: ace_lib.SingleSession, knowledge_dir: str):
    """Fetch tutorials and pages, save one JSON per page."""
    print("=== Processing Documentation ===")

    tutorials = fetch_tutorials(session)
    if not tutorials:
        print("No tutorials fetched; skipping documentation.")
        return

    print(f"Fetched {len(tutorials)} tutorials")

    page_count = 0
    seen_pages = set()
    
    for idx, tutorial in enumerate(tutorials, start=1):
        tutorial_id = _extract_page_id(tutorial) or f"tutorial_{idx}"
        tutorial_title = tutorial.get("title") or tutorial_id

        page_candidates = []
        if isinstance(tutorial.get("pages"), list):
            page_candidates.extend(tutorial["pages"])
        if tutorial_id:
            try:
                page_candidates.extend(fetch_tutorial_pages(session, tutorial_id))
            except Exception as exc:
                print(f"[{idx:03d}] failed to fetch pages for {tutorial_id}: {exc}")

        if not page_candidates and tutorial_id:
            page_candidates.append({"id": tutorial_id, "title": tutorial_title})

        for page_entry in page_candidates:
            page_id = _extract_page_id(page_entry)
            if not page_id or page_id in seen_pages:
                continue
            seen_pages.add(page_id)
            
            try:
                page = fetch_page(session, page_id)
            except Exception as exc:
                print(f"[{idx:03d}] page {page_id} failed: {exc}")
                continue
            
            page_count += 1
            page_title = page.get("title") or page_entry.get("title") or page_id
            
            # Save each page as individual JSON
            filename = safe_filename(f"{idx:03d}_{page_title}", "_documentation.json")
            filepath = os.path.join(knowledge_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(to_jsonable(page), f, ensure_ascii=False, indent=2)
            
            print(f"[{idx:03d}] ✓ Created {filename}")
    
    print(f"✓ Total: {page_count} documentation pages saved")


def main():
    print("=== BRAIN Knowledge Base Processor ===")
    print("Starting operator processing...\n")
    
    # Get credentials
    email, password = prompt_credentials()
    ace_lib.get_credentials = lambda: (email, password)
    
    print("Logging in to BRAIN platform...")
    try:
        session = ace_lib.start_session()
        print("✓ Login successful\n")
    except Exception as exc:
        print(f"✗ Login failed: {exc}")
        return
    
    # Ensure knowledge directory exists
    knowledge_dir = ensure_knowledge_dir()
    # dataset_dir = knowledge_dir  # Save datasets directly under knowledge (disabled)
    print(f"Knowledge directory: {knowledge_dir}\n")

    # Process documentation (tutorials/pages)
    print("\nStarting documentation processing...\n")
    try:
        process_documentation(session, knowledge_dir)
    except Exception as exc:
        print(f"✗ Failed to process documentation: {exc}")
        import traceback
        traceback.print_exc()
        return

    # Process operators
    try:
        process_operators(session, knowledge_dir)
    except Exception as exc:
        print(f"✗ Failed to process operators: {exc}")
        import traceback
        traceback.print_exc()
        return

    # Dataset processing disabled; re-enable by uncommenting the block below.
    # print("\nStarting dataset processing...\n")
    # try:
    #     process_datasets(session, dataset_dir)
    # except Exception as exc:
    #     print(f"✗ Failed to process datasets: {exc}")
    #     import traceback
    #     traceback.print_exc()
    #     return

    print("\n=== Processing Complete ===")


if __name__ == "__main__":
    main()
