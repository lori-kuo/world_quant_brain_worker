import requests
import json
import time
from datetime import datetime
import os
from pathlib import Path
import getpass
import sys
import re

# Platform specific imports
if sys.platform == 'win32':
    import msvcrt
else:
    import tty
    import termios

def input_with_asterisks(prompt):
    """Cross-platform password input showing asterisks"""
    print(prompt, end='', flush=True)
    password = []

    try:
        if sys.platform == 'win32':
            # Windows: Use msvcrt.getch()
            while True:
                char = msvcrt.getch()
                
                # Handle Enter key
                if char in [b'\r', b'\n']:
                    print()  # New line
                    break
                
                # Handle Backspace
                elif char == b'\x08':  # Backspace
                    if password:
                        password.pop()
                        # Move cursor back, print space, move cursor back again
                        print('\b \b', end='', flush=True)
                
                # Handle Ctrl+C
                elif char == b'\x03':  # Ctrl+C
                    print()
                    raise KeyboardInterrupt
                
                # Handle printable characters (ASCII)
                elif 32 <= ord(char) <= 126:  # Printable ASCII range
                    password.append(char.decode('ascii'))
                    print('*', end='', flush=True)
                
                # Handle extended characters
                else:
                    try:
                        decoded_char = char.decode('utf-8')
                        if decoded_char.isprintable():
                            password.append(decoded_char)
                            print('*', end='', flush=True)
                    except UnicodeDecodeError:
                        continue
        else:
            # Unix/macOS: Use tty and termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                while True:
                    char = sys.stdin.read(1)
                    
                    # Handle Enter key
                    if char in ['\r', '\n']:
                        print('\r\n', end='', flush=True)
                        break
                    
                    # Handle Backspace
                    elif char in ['\x7f', '\x08']:
                        if password:
                            password.pop()
                            print('\b \b', end='', flush=True)
                    
                    # Handle Ctrl+C
                    elif char == '\x03':
                        print('\r\n', end='', flush=True)
                        raise KeyboardInterrupt
                    
                    # Handle printable characters
                    elif char.isprintable():
                        password.append(char)
                        print('*', end='', flush=True)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                
    except Exception as e:
        # Fallback to getpass
        print(f"\nError reading password: {e}")
        print("Falling back to getpass...")
        return getpass.getpass()

    return ''.join(password)

def load_user_config():
    """Load user credentials from user_config.json"""
    try:
        # Look for user_config.json in parent directories
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(os.path.dirname(script_dir))  # Go up to untracked folder
        config_path = os.path.join(parent_dir, 'user_config.json')
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                credentials = config.get('credentials', {})
                email = credentials.get('email')
                password = credentials.get('password')
                if email and password:
                    print(f"✅ Loaded credentials for: {email}")
                    return email, password
                else:
                    print("⚠️ Credentials not found in config file")
                    return None, None
        else:
            print(f"⚠️ Config file not found: {config_path}")
            return None, None
    except Exception as e:
        print(f"❌ Error loading user config: {e}")
        return None, None

def login(account_choice=None, use_config=True):
    """Login to WorldQuant Brain API"""
    s = requests.Session()
    
    email = None
    password = None
    
    # Try to load from config file first
    if use_config:
        email, password = load_user_config()
    
    # If no config credentials, prompt user
    if not email or not password:
        print("\n=== WorldQuant Brain Login ===")
        email = input("Enter your email: ").strip()
        
        # Use custom password input with asterisk masking
        try:
            password = input_with_asterisks("Enter your password: ")
            if not password:
                print("❌ Password is required.")
                return None
        except Exception as e:
            print(f"❌ Error with custom password input: {e}")
            print("Trying standard getpass...")
            try:
                password = getpass.getpass("Enter your password: ")
                if not password:
                    print("❌ Password is required.")
                    return None
            except Exception as e2:
                print(f"❌ Error reading password: {e2}")
                return None
    
    if not email:
        print("❌ Email is required.")
        return None
    
    print(f"Logging in with: {email}")
    
    # Set basic auth
    s.auth = (email, password)
    
    try:
        # Send authentication request
        response = s.post('https://api.worldquantbrain.com/authentication')
        print(f"Login response status: {response.status_code}")
        print(f"Login response headers: {dict(response.headers)}")
        
        if response.text:
            try:
                response_json = response.json()
                print(f"Login response body: {json.dumps(response_json, indent=2)}")
            except json.JSONDecodeError:
                print(f"Login response body (not JSON): {response.text}")
        
        response.raise_for_status()
        print("Login successful!")
        return s
    except requests.exceptions.RequestException as e:
        print(f"Login failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Error response status: {e.response.status_code}")
            print(f"Error response body: {e.response.text}")
        return None

def check_alpha_exists(s, alpha_id):
    """Check if an alpha exists by making a GET request to /alphas/<alpha_id>"""
    try:
        response = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}")
        print(f"Alpha check response status: {response.status_code}")
        print(f"Alpha check response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            alpha_data = response.json()
            print(f"✅ Alpha {alpha_id} exists - Type: {alpha_data.get('type', 'Unknown')}")
            print(f"Alpha data: {json.dumps(alpha_data, indent=2)}")
            return True, alpha_data
        elif response.status_code == 404:
            print(f"❌ Alpha {alpha_id} does not exist (404 Not Found)")
            if response.text:
                print(f"404 response body: {response.text}")
            return False, None
        else:
            print(f"⚠️ Unexpected response for alpha {alpha_id}: {response.status_code}")
            if response.text:
                print(f"Unexpected response body: {response.text}")
            return False, None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error checking alpha {alpha_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Error response status: {e.response.status_code}")
            print(f"Error response body: {e.response.text}")
        return False, None

def get_user_alphas(s, limit=1000):
    """Get all alphas for the current user"""
    try:
        all_alphas = []
        offset = 0
        page_size = 100
        
        while True:
            url = f"https://api.worldquantbrain.com/alphas?limit={page_size}&offset={offset}"
            response = s.get(url)
            
            if response.status_code != 200:
                print(f"⚠️ Failed to fetch alphas: {response.status_code}")
                break
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                break
            
            all_alphas.extend(results)
            print(f"📋 Fetched {len(results)} alphas (total: {len(all_alphas)})...")
            
            if len(results) < page_size or len(all_alphas) >= limit:
                break
            
            offset += page_size
            time.sleep(0.5)  # Be nice to the API
        
        print(f"✅ Total alphas fetched: {len(all_alphas)}")
        return all_alphas
    except Exception as e:
        print(f"❌ Error fetching user alphas: {e}")
        return []

def check_submission_eligibility(s, alpha_id):
    """Check if an alpha is eligible for submission and return the check results"""
    try:
        response = s.post(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit")
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return None
    except Exception as e:
        print(f"Error checking {alpha_id}: {e}")
        return None

def filter_eligible_alphas(s, alphas, verbose=False):
    """Filter alphas to find those eligible for submission"""
    eligible = []
    already_submitted = []
    failed_checks = []
    
    print(f"\n🔍 Checking {len(alphas)} alphas for submission eligibility...\n")
    
    for i, alpha in enumerate(alphas, 1):
        alpha_id = alpha.get('id')
        if not alpha_id:
            continue
        
        if verbose:
            print(f"[{i}/{len(alphas)}] Checking alpha {alpha_id}...", end=" ")
        else:
            if i % 10 == 0:
                print(f"Progress: {i}/{len(alphas)}...")
        
        check_result = check_submission_eligibility(s, alpha_id)
        
        if not check_result:
            if verbose:
                print("❌ Failed to check")
            continue
        
        # Parse the check results
        is_eligible = True
        fail_reasons = []
        
        if 'is' in check_result and 'checks' in check_result['is']:
            for check in check_result['is']['checks']:
                if check['name'] == 'ALREADY_SUBMITTED':
                    is_eligible = False
                    already_submitted.append({
                        'id': alpha_id,
                        'alpha': alpha,
                        'reason': 'Already submitted'
                    })
                    if verbose:
                        print("⚪ Already submitted")
                    break
                elif check['result'] == 'FAIL':
                    is_eligible = False
                    reason = f"{check['name']}: limit={check.get('limit', 'N/A')}, value={check.get('value', 'N/A')}"
                    fail_reasons.append(reason)
        
        if is_eligible:
            eligible.append({
                'id': alpha_id,
                'alpha': alpha,
                'check_result': check_result
            })
            if verbose:
                print("✅ Eligible")
        elif fail_reasons:
            failed_checks.append({
                'id': alpha_id,
                'alpha': alpha,
                'reasons': fail_reasons
            })
            if verbose:
                print(f"❌ Failed: {', '.join(fail_reasons)}")
        
        # Be nice to the API
        time.sleep(0.3)
    
    print(f"\n📊 Summary:")
    print(f"   ✅ Eligible for submission: {len(eligible)}")
    print(f"   ⚪ Already submitted: {len(already_submitted)}")
    print(f"   ❌ Failed checks: {len(failed_checks)}")
    
    return eligible, already_submitted, failed_checks

def get_alpha_recordsets(s, alpha_id):
    """Get available record sets for an alpha"""
    try:
        response = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/recordsets")
        print(f"Recordsets response status: {response.status_code}")
        print(f"Recordsets response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            recordsets_data = response.json()
            print(f"📊 Alpha {alpha_id} has {recordsets_data.get('count', 0)} record sets available")
            print(f"Recordsets data: {json.dumps(recordsets_data, indent=2)}")
            return recordsets_data
        else:
            print(f"⚠️ Could not fetch record sets for alpha {alpha_id}: {response.status_code}")
            if response.text:
                print(f"Recordsets error response body: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching record sets for alpha {alpha_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Error response status: {e.response.status_code}")
            print(f"Error response body: {e.response.text}")
        return None

def submit(s, alpha_id):
    """Submit a single alpha with retry logic - keeps trying until success"""
    
    def submit_inner(s, alpha_id):
        """Inner submit function with rate limiting handling"""
        try:
            result = s.post(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit")
            print(f"Alpha submit, alpha_id={alpha_id}, status_code={result.status_code}")
            print(f"Response headers: {dict(result.headers)}")
            
            # Handle rate limiting
            while True:
                if "retry-after" in result.headers:
                    wait_time = float(result.headers["Retry-After"])
                    print(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    result = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit")
                    print(f"Retry GET response, status_code={result.status_code}")
                    print(f"Retry headers: {dict(result.headers)}")
                else:
                    break
            
            return result
        except Exception as e:
            print(f'Connection error: {e}, attempting to re-login...')
            new_session = login()
            if new_session is None:
                return None
            return submit_inner(new_session, alpha_id)
    
    attempt_count = 1
    result = None
    
    while True:
        print(f"Submit attempt {attempt_count} for alpha {alpha_id}")
        result = submit_inner(s, alpha_id)
        
        if result is None:
            print(f"Failed to submit {alpha_id} - connection error")
            return None
        
        if result.status_code == 200:
            print(f"✅ Alpha {alpha_id} submit successful, status_code={result.status_code}")
            return result
        elif result.status_code == 403:
            print(f"❌ Alpha {alpha_id} submit forbidden, status_code={result.status_code}")
            return result
        else:
            print(f"⚠️ Alpha submit fail, status_code={result.status_code}, alpha_id={alpha_id}, attempt {attempt_count}")
            print(f"Waiting 2 minutes before retry...")
            time.sleep(120)  # 2 minutes = 120 seconds
            attempt_count += 1
            continue

def submit_alpha(alpha_id, session=None, account_choice=None):
    """Submit a single alpha with comprehensive error handling"""
    if session is None:
        s = login(account_choice)
        if s is None:
            return False
    else:
        s = session
    
    # First check if the alpha exists
    print(f"Checking if alpha {alpha_id} exists...")
    exists, alpha_data = check_alpha_exists(s, alpha_id)
    if not exists:
        print(f"❌ Cannot submit alpha {alpha_id} - it does not exist")
        return False
    
    # Submit the alpha
    res = submit(s, alpha_id)
    
    if res is None:
        print(f"Failed to submit {alpha_id} - connection error")
        return False
    
    # Parse response
    if res.text:
        try:
            res_json = res.json()
            print(f"Submit response parsed successfully")
        except json.JSONDecodeError:
            print(f"Submit response is not JSON: {res.text[:200]}...")
            return False
    else:
        print(f"Submit response has no text content")
        return False
    
    # Check for various error conditions
    if 'detail' in res_json and res_json['detail'] == 'Not found.':
        print(f"{alpha_id} - Alpha ID not found")
        return False
    
    # Check submission status
    submitted = True
    if 'is' in res_json and 'checks' in res_json['is']:
        for item in res_json['is']['checks']:
            if item['name'] == 'ALREADY_SUBMITTED':
                submitted = False
                print(f"{alpha_id} - Already submitted")
                break
            if item['result'] == 'FAIL':
                submitted = False
                print(f"{alpha_id} - {item['name']} check failed, limit = {item['limit']}, value = {item['value']}")
                break
    
    if submitted:
        print(f'{alpha_id} - Submission successful!')
        return True
    else:
        return False

def batch_submit_alphas(session, alpha_ids):
    """Submit multiple alphas with progress reporting"""
    results = {
        'success': [],
        'failed': [],
        'total': len(alpha_ids)
    }
    
    print(f"\n🚀 Starting batch submission of {len(alpha_ids)} alphas...\n")
    
    for i, alpha_id in enumerate(alpha_ids, 1):
        print(f"\n[{i}/{len(alpha_ids)}] Submitting alpha {alpha_id}...")
        print("=" * 60)
        
        success = submit_alpha(alpha_id, session)
        
        if success:
            results['success'].append(alpha_id)
            print(f"✅ Alpha {alpha_id} submitted successfully!")
        else:
            results['failed'].append(alpha_id)
            print(f"❌ Alpha {alpha_id} submission failed.")
        
        print("=" * 60)
        
        # Progress summary
        print(f"\n📊 Progress: {i}/{len(alpha_ids)} processed | "
              f"✅ {len(results['success'])} succeeded | "
              f"❌ {len(results['failed'])} failed")
        
        # Brief pause between submissions
        if i < len(alpha_ids):
            time.sleep(1)
    
    return results

def main():
    """Main function to run the alpha submission script"""
    print("="*70)
    print("🎯 WorldQuant Brain Alpha Submitter - Auto Filter & Submit")
    print("="*70)
    print("This tool will:")
    print("  1. Login to BRAIN (auto-load from user_config.json if available)")
    print("  2. Fetch all your alphas")
    print("  3. Filter alphas that meet submission requirements")
    print("  4. Let you choose which ones to submit")
    print("="*70)
    
    # Login with user credentials (auto-load from config)
    print("\n🔑 Logging in...")
    session = login(use_config=True)
    if session is None:
        print("❌ Failed to login. Exiting.")
        return
    
    print("\n✅ Login successful!\n")
    
    while True:
        print("\n" + "="*70)
        print("📋 Main Menu")
        print("="*70)
        print("1. Auto-scan and filter eligible alphas")
        print("2. Manual submit (enter alpha ID)")
        print("3. Check alpha info")
        print("4. Re-login")
        print("5. Exit")
        print("="*70)
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == '1':
            # Auto-scan mode
            print("\n🔄 Fetching your alphas...")
            alphas = get_user_alphas(session)
            
            if not alphas:
                print("❌ No alphas found or failed to fetch.")
                continue
            
            # Filter eligible alphas
            eligible, already_submitted, failed = filter_eligible_alphas(session, alphas, verbose=False)
            
            if not eligible:
                print("\n⚠️ No eligible alphas found for submission.")
                input("\nPress Enter to continue...")
                continue
            
            # Display eligible alphas
            print("\n" + "="*70)
            print(f"✅ Found {len(eligible)} eligible alpha(s) for submission:")
            print("="*70)
            
            for i, item in enumerate(eligible, 1):
                alpha = item['alpha']
                alpha_id = item['id']
                alpha_type = alpha.get('type', 'N/A')
                print(f"{i}. Alpha ID: {alpha_id} | Type: {alpha_type}")
            
            print("="*70)
            
            # Ask user what to do
            print("\n📤 Submission Options:")
            print("  [A] Submit ALL eligible alphas")
            print("  [S] Select specific alphas to submit (e.g., 1,3,5 or 1-10)")
            print("  [C] Cancel and return to menu")
            
            submit_choice = input("\nYour choice: ").strip().upper()
            
            if submit_choice == 'C':
                continue
            elif submit_choice == 'A':
                # Submit all
                alpha_ids = [item['id'] for item in eligible]
                confirm = input(f"\n⚠️ Confirm: Submit {len(alpha_ids)} alphas? (yes/no): ").strip().lower()
                
                if confirm == 'yes':
                    results = batch_submit_alphas(session, alpha_ids)
                    print("\n" + "="*70)
                    print("🎉 Batch Submission Complete!")
                    print("="*70)
                    print(f"✅ Successfully submitted: {len(results['success'])}")
                    print(f"❌ Failed: {len(results['failed'])}")
                    if results['success']:
                        print(f"\n✅ Successful IDs: {', '.join(results['success'])}")
                    if results['failed']:
                        print(f"\n❌ Failed IDs: {', '.join(results['failed'])}")
                    print("="*70)
                else:
                    print("Cancelled.")
                
                input("\nPress Enter to continue...")
                
            elif submit_choice == 'S':
                # Select specific alphas
                selection = input("\nEnter alpha numbers (e.g., 1,3,5 or 1-10): ").strip()
                
                try:
                    selected_indices = set()
                    
                    # Parse selection
                    for part in selection.split(','):
                        part = part.strip()
                        if '-' in part:
                            # Range like 1-10
                            start, end = map(int, part.split('-'))
                            selected_indices.update(range(start, end + 1))
                        else:
                            # Single number
                            selected_indices.add(int(part))
                    
                    # Get selected alpha IDs
                    alpha_ids = [eligible[i-1]['id'] for i in selected_indices if 1 <= i <= len(eligible)]
                    
                    if not alpha_ids:
                        print("❌ No valid alphas selected.")
                        continue
                    
                    print(f"\n📋 Selected {len(alpha_ids)} alpha(s): {', '.join(alpha_ids)}")
                    confirm = input(f"\n⚠️ Confirm submission? (yes/no): ").strip().lower()
                    
                    if confirm == 'yes':
                        results = batch_submit_alphas(session, alpha_ids)
                        print("\n" + "="*70)
                        print("🎉 Batch Submission Complete!")
                        print("="*70)
                        print(f"✅ Successfully submitted: {len(results['success'])}")
                        print(f"❌ Failed: {len(results['failed'])}")
                        if results['success']:
                            print(f"\n✅ Successful IDs: {', '.join(results['success'])}")
                        if results['failed']:
                            print(f"\n❌ Failed IDs: {', '.join(results['failed'])}")
                        print("="*70)
                    else:
                        print("Cancelled.")
                    
                    input("\nPress Enter to continue...")
                    
                except (ValueError, IndexError) as e:
                    print(f"❌ Invalid selection: {e}")
                    input("\nPress Enter to continue...")
            else:
                print("❌ Invalid choice.")
                input("\nPress Enter to continue...")
        
        elif choice == '2':
            # Manual submit mode
            alpha_id = input("\nEnter alpha ID: ").strip()
            
            if not alpha_id:
                print("❌ Please enter a valid alpha ID.")
                continue
            
            print(f"\n📤 Submitting alpha: {alpha_id}")
            print("=" * 60)
            
            success = submit_alpha(alpha_id, session)
            
            if success:
                print(f"✅ Alpha {alpha_id} submitted successfully!")
            else:
                print(f"❌ Alpha {alpha_id} failed to submit.")
            
            print("=" * 60)
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            # Check alpha info
            alpha_id = input("\nEnter alpha ID to check: ").strip()
            
            if not alpha_id:
                print("❌ Please enter a valid alpha ID.")
                continue
            
            print(f"\n🔍 Checking alpha: {alpha_id}")
            print("=" * 60)
            
            exists, alpha_data = check_alpha_exists(session, alpha_id)
            if exists:
                get_alpha_recordsets(session, alpha_id)
                
                if alpha_data:
                    print(f"\n📋 Alpha Details:")
                    print(f"   ID: {alpha_data.get('id', 'N/A')}")
                    print(f"   Type: {alpha_data.get('type', 'N/A')}")
                    if 'settings' in alpha_data:
                        print(f"   Has settings: Yes")
                    if 'regular' in alpha_data:
                        print(f"   Has regular data: Yes")
            
            print("=" * 60)
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            # Re-login
            print("\n🔄 Re-logging in...")
            session = login(use_config=False)  # Force manual login
            if session is None:
                print("❌ Failed to login. Exiting.")
                return
            print("✅ Login successful!")
        
        elif choice == '5':
            # Exit
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid option. Please select 1-5.")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main() 